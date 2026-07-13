"""Queue compiling, context wall shape, ledger cap (items 3, 4)."""

import json

import pytest

from src.engine.state import Question
from src.session.manager import InterviewerContext, SessionManager, USER_DOC_KEYS
from src.session.queue import compile_queue
from src.session.setup import QuestionSourceConfig, SessionConfig
from src.persona.extract import PersonaTags
from src.persona.resolve import resolve


def make_cfg(**kw) -> SessionConfig:
    defaults = dict(profile_id="pm")
    defaults.update(kw)
    return SessionConfig(**defaults)


class TestQueue:
    def test_scripted_first_order_kept(self):
        cfg = make_cfg(source=QuestionSourceConfig(
            scripted=["Q one?", "Q two?"], bank_count=2))
        queue = compile_queue(cfg, seed=7)
        assert queue[0].text == "Q one?" and queue[1].text == "Q two?"
        assert len(queue) == 4
        assert all(q.source == "bank" for q in queue[2:])

    def test_dedupe_on_text(self):
        cfg = make_cfg(source=QuestionSourceConfig(
            scripted=["Same question?", "same question?"], bank_count=0))
        assert len(compile_queue(cfg)) == 1

    def test_topic_emphasis_biases_sampling(self):
        cfg = make_cfg(source=QuestionSourceConfig(bank_count=5))
        hits_with, hits_without = 0, 0
        for seed in range(30):
            with_topics = compile_queue(cfg, topic_emphasis=["data"], seed=seed)
            without = compile_queue(cfg, seed=seed)
            hits_with += sum("data" in q.topics for q in with_topics)
            hits_without += sum("data" in q.topics for q in without)
        assert hits_with > hits_without

    def test_pack_and_intel_passed_in(self):
        cfg = make_cfg(source=QuestionSourceConfig(bank_count=0, use_pack=True))
        pack = [Question(id="pk_1", text="Pack question?", source="pack")]
        intel = [Question(id="in_1", text="Intel question?", source="intel")]
        queue = compile_queue(cfg, pack_questions=pack, intel_questions=intel)
        assert [q.source for q in queue] == ["pack", "intel"]


class TestContextWall:
    def make_manager(self):
        cfg = make_cfg(materials={
            "resume": "Resume: shipped Orange France telecom migration.",
            "jd": "JD: senior PM for voice.",
            "stories": "Story: the Berlin outage save.",
            "bio": "Partner at McKinsey.",
        })
        persona = resolve(PersonaTags(), selected_round="pm")
        return SessionManager(cfg, persona)

    def test_interviewer_context_has_no_doc_fields(self):
        assert not (set(InterviewerContext.model_fields) &
                    {"docs", "resume", "jd", "stories", "bio", "materials"})

    def test_interviewer_context_content_is_clean(self):
        manager = self.make_manager()
        q = Question(id="q1", text="Tell me about a conflict.")
        ictx = manager.interviewer_context(q)
        blob = ictx.model_dump_json()
        for leak in ("Orange France", "Berlin outage", "McKinsey", "senior PM for voice"):
            assert leak not in blob

    def test_interviewer_prompt_is_clean(self):
        manager = self.make_manager()
        q = Question(id="q1", text="Tell me about a conflict.")
        prompt = manager.interviewer_system_prompt(manager.interviewer_context(q))
        for leak in ("Orange France", "Berlin outage", "McKinsey", "voice"):
            assert leak not in prompt

    def test_grader_sees_docs_but_not_bio(self):
        manager = self.make_manager()
        docs = {d.name for d in manager.user_docs()}
        assert docs == {"resume", "jd", "stories"}

    def test_grader_context_carries_docs(self):
        manager = self.make_manager()
        q = Question(id="q1", text="Tell me about a conflict.")
        state = manager.new_answer_state(q)
        gctx = manager.grader_context(q, "transcript text", state, 120.0)
        assert any("Orange France" in d.text for d in gctx.docs)


class TestDocsIngestion:
    def test_any_subset_of_docs_works(self):
        # Spec 5.3: no fixed doc requirement; any subset the user supplied.
        for materials in ({}, {"resume": "R text"}, {"jd": "J text"},
                          {"resume": "R", "stories": "S"}):
            cfg = make_cfg(materials=materials)
            persona = resolve(PersonaTags(), selected_round="pm")
            manager = SessionManager(cfg, persona)
            names = {d.name for d in manager.user_docs()}
            assert names == {k for k, v in materials.items() if k != "bio"}

    def test_coach_context_matches_grader_docs(self):
        cfg = make_cfg(materials={"resume": "R", "jd": "J"})
        persona = resolve(PersonaTags(), selected_round="pm")
        manager = SessionManager(cfg, persona)
        assert ({d.name for d in manager.coach_context().docs}
                == {d.name for d in manager.user_docs()})

    def test_wizard_config_roundtrips_through_json(self, tmp_path):
        cfg = make_cfg(materials={"resume": "line one\nline two"},
                       source=QuestionSourceConfig(scripted=["Q?"], bank_count=1))
        path = tmp_path / "next_session.json"
        path.write_text(cfg.model_dump_json())
        loaded = SessionConfig(**json.loads(path.read_text()))
        assert loaded == cfg

    def test_manager_is_only_context_assembler(self):
        """The wall lives in manager.py: no other src module builds an
        interviewer context or touches cfg.materials."""
        import pathlib
        src = pathlib.Path(__file__).resolve().parents[1] / "src"
        offenders = []
        for py in src.rglob("*.py"):
            if py.name == "manager.py":
                continue
            text = py.read_text()
            if "InterviewerContext(" in text or ".materials[" in text:
                offenders.append(py.name)
        # agent.py may read materials only for the persona bio input path.
        assert offenders in ([], ["agent.py"])


class TestLedger:
    def test_daily_cap_blocks_gemini_and_reports_without_groq(
            self, tmp_path, monkeypatch):
        from src.llm import client
        monkeypatch.setattr(client, "LEDGER_PATH", tmp_path / "ledger.json")
        monkeypatch.setattr(client, "_settings", None)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        def gemini_429(prompt, schema, model=None):
            raise Exception("429 RESOURCE_EXHAUSTED")

        monkeypatch.setattr(client, "_call_gemini", gemini_429)
        client.settings().daily_call_cap = 3
        for _ in range(3):
            client._ledger_bump()
        # Cap reached, lite also exhausted, no failover: stop loudly with
        # the cap as the headline error.
        with pytest.raises(client.DailyCapReached):
            client.complete("probe_rewrite", {
                "seed": "x", "probe_type": "SPECIFICITY",
                "offending_phrase": "", "recent_context": "", "intensity": "3"})
        assert client.calls_today() == 3  # capped call did not bump the ledger

    def test_at_cap_skips_flash_but_still_tries_lite(self, tmp_path, monkeypatch):
        from src.llm import client
        monkeypatch.setattr(client, "LEDGER_PATH", tmp_path / "ledger.json")
        monkeypatch.setattr(client, "_settings", None)
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
        monkeypatch.setattr(client, "_call_groq", lambda p, s: "groq says hi")
        models_tried = []

        def gemini_429(prompt, schema, model=None):
            models_tried.append(model or client.settings().primary_model)
            raise Exception("429 RESOURCE_EXHAUSTED")

        monkeypatch.setattr(client, "_call_gemini", gemini_429)
        client.settings().daily_call_cap = 1
        client._ledger_bump()
        result = client.complete("probe_rewrite", {
            "seed": "x", "probe_type": "SPECIFICITY",
            "offending_phrase": "", "recent_context": "", "intensity": "3"})
        assert result.provider == "groq"
        # Capped: flash never attempted, but lite (its own quota pool) was.
        assert models_tried == [client.settings().lite_model]

    def test_at_cap_lite_serves_without_groq_needed(self, tmp_path, monkeypatch):
        from src.llm import client
        monkeypatch.setattr(client, "LEDGER_PATH", tmp_path / "ledger.json")
        monkeypatch.setattr(client, "_settings", None)

        def gemini_lite_only(prompt, schema, model=None):
            assert model == client.settings().lite_model, \
                "flash attempted past the ledger cap"
            return "lite says hi"

        monkeypatch.setattr(client, "_call_gemini", gemini_lite_only)
        client.settings().daily_call_cap = 1
        client._ledger_bump()
        result = client.complete("probe_rewrite", {
            "seed": "x", "probe_type": "SPECIFICITY",
            "offending_phrase": "", "recent_context": "", "intensity": "3"})
        assert result.provider == "gemini-lite" and result.failovers == 1

    def test_rate_limit_detection(self):
        from src.llm.client import _is_rate_limit
        assert _is_rate_limit(Exception("429 RESOURCE_EXHAUSTED"))
        assert _is_rate_limit(Exception("Rate limit reached for model"))
        assert not _is_rate_limit(Exception("invalid api key"))
