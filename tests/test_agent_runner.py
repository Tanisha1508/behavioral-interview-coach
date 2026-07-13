"""DrillRunner turn-end behavior: no pause of any length finishes an
answer, and post-grading replies are verdicts, not answer content.
Regression tests for the 2026-07-10 live-rep bugs (one-word answer graded
at the first pause; time-based wrap check cutting the candidate off; "end"
triggering a second grading pass). User rule: only an explicit done
phrase, a spec-complete answer, or a double deflection ends an answer."""

import asyncio
import time

import src.agent as agent_mod
from src.agent import DrillRunner
from src.engine.state import Question
from src.persona.extract import PersonaTags
from src.persona.resolve import resolve
from src.session.manager import SessionManager
from src.session.setup import SessionConfig


class FakeSession:
    def __init__(self):
        self.spoken: list[str] = []

    async def say(self, text, allow_interruptions=True):
        self.spoken.append(text)

    def interrupt(self):
        pass


def make_runner(n_questions=1, on_end=None, followup_mode="listen"):
    cfg = SessionConfig(profile_id="pm", followup_mode=followup_mode)
    persona = resolve(PersonaTags(), overrides=cfg.persona_overrides,
                      selected_round=cfg.profile_id)
    manager = SessionManager(cfg, persona)
    session = FakeSession()
    queue = [Question(id=f"q{i}", text=f"Question {i}?")
             for i in range(n_questions)]
    runner = DrillRunner(session, manager, queue, on_end=on_end,
                         followup_mode=followup_mode)
    graded = []

    async def fake_grade():
        graded.append(True)
        runner.state = None
        runner.awaiting_verdict = True

    runner._grade_and_feedback = fake_grade
    return runner, session, graded


def test_early_pause_keeps_listening():
    async def run():
        runner, session, graded = make_runner()
        await runner.ask_next_question()
        says_before = len(session.spoken)
        runner.on_partial("The", is_final=True)
        await runner.on_turn_complete("The")
        assert not graded, "graded a one-word answer at the first pause"
        assert len(session.spoken) == says_before, \
            "spoke during an early thinking pause"
    asyncio.run(run())


def test_pause_deep_into_answer_still_waits():
    async def run():
        runner, session, graded = make_runner()
        await runner.ask_next_question()
        says_before = len(session.spoken)
        text = "So while working on a project I sketched two options."
        runner.on_partial(text, True)
        runner.answer_started = time.monotonic() - 100  # 100s in
        await runner.on_turn_complete(text)
        await asyncio.sleep(0.2)  # a long pause follows; nothing may happen
        assert not graded, "a pause ended the answer"
        assert len(session.spoken) == says_before, \
            "interviewer spoke mid-answer (probe, check, or grade)"
    asyncio.run(run())


def test_mvp_default_no_followups_straight_to_grading():
    async def run():
        from src.engine.state import ProbeCandidate, ProbeType
        runner, session, graded = make_runner()  # default mode: listen
        assert runner.max_followups == 0, \
            "listen mode must ask zero follow-ups"
        await runner.ask_next_question()
        runner.on_partial("We shipped the project as a team.", True)
        runner.state.queued_probes.append(ProbeCandidate(
            probe_type=ProbeType.OWNERSHIP, priority=4, confidence=1.0))
        runner.on_partial("That's my answer.", True)
        await runner.on_turn_complete("That's my answer.")
        assert graded, "cap 0 should grade immediately after the answer"
    asyncio.run(run())


def test_queued_probe_waits_until_done_then_follows_up(monkeypatch):
    monkeypatch.setattr(agent_mod.probes, "select_probe",
                        lambda cand, state, **kw: "What did you do next?")

    async def run():
        from src.engine.state import ProbeCandidate, ProbeType
        runner, session, graded = make_runner(followup_mode="probing")
        await runner.ask_next_question()
        says_before = len(session.spoken)
        runner.on_partial("We shipped the project as a team.", True)
        runner.state.queued_probes.append(ProbeCandidate(
            probe_type=ProbeType.OWNERSHIP, priority=4, confidence=1.0))
        # Mid-answer endpoints never surface the queued probe.
        await runner.on_turn_complete("We shipped the project as a team.")
        assert len(session.spoken) == says_before, "probe fired mid-answer"
        # Done: the probe is asked as a follow-up, not graded yet.
        runner.on_partial("That's my answer.", True)
        await runner.on_turn_complete("That's my answer.")
        assert session.spoken[-1] == "What did you do next?"
        assert not graded, "graded before the follow-up was answered"
        assert not runner.state.user_signaled_done, \
            "follow-up reply should be awaited like the main answer"
        # Reply to the follow-up, then done again: now it grades.
        reply = "I personally drove the rollout plan. That's my answer."
        runner.on_partial(reply, True)
        await runner.on_turn_complete(reply)
        assert graded, "did not grade after the follow-up was answered"
    asyncio.run(run())


def test_length_graded_on_main_answer_not_followups(monkeypatch):
    monkeypatch.setattr(agent_mod.probes, "select_probe",
                        lambda cand, state, **kw: "What did you do next?")

    async def run():
        from src.engine.state import ProbeCandidate, ProbeType
        runner, session, graded = make_runner(followup_mode="probing")
        await runner.ask_next_question()
        runner.on_partial("We shipped the project as a team.", True)
        runner.answer_started = time.monotonic() - 120  # 120s main answer
        runner.state.queued_probes.append(ProbeCandidate(
            probe_type=ProbeType.OWNERSHIP, priority=4, confidence=1.0))
        await runner.on_turn_complete("That's my answer.")
        assert 119 <= runner.main_answer_ms / 1000 <= 121
        # A slow follow-up reply must not move the graded duration.
        runner.answer_started = time.monotonic() - 300
        reply = "I drove the rollout personally. That's my answer."
        runner.on_partial(reply, True)
        await runner.on_turn_complete(reply)
        assert graded
        assert 119 <= runner.main_answer_ms / 1000 <= 121, \
            "follow-up time leaked into the graded answer duration"
    asyncio.run(run())


def test_internal_trigger_never_reaches_probe_prompt():
    from src.engine.probes import _trigger_context
    from src.engine.state import ProbeCandidate, ProbeType
    internal = ProbeCandidate(probe_type=ProbeType.DEPTH, priority=2,
                              confidence=1.0,
                              detail="action seen while situation not seen")
    text = _trigger_context(internal)
    assert "seen while" not in text
    assert "situation" in text and "action" in text
    verbatim = ProbeCandidate(probe_type=ProbeType.SPECIFICITY, priority=3,
                              confidence=1.0, detail="worked closely")
    assert _trigger_context(verbatim) == "worked closely"


def test_followup_cap_clears_queue(monkeypatch):
    monkeypatch.setattr(agent_mod.probes, "select_probe",
                        lambda cand, state, **kw: "Probe?")

    async def run():
        from src.engine.state import (ProbeCandidate, ProbeRecord,
                                      ProbeType)
        runner, session, graded = make_runner(followup_mode="probing")
        await runner.ask_next_question()
        runner.on_partial("We shipped it. That's my answer.", True)
        runner.state.probes_fired = [
            ProbeRecord(probe_type=ProbeType.QUANTIFY, fired_at_ms=1,
                        trigger="t", text="p1", interrupted=False),
            ProbeRecord(probe_type=ProbeType.DEPTH, fired_at_ms=2,
                        trigger="t", text="p2", interrupted=False),
        ]
        runner.state.queued_probes.append(ProbeCandidate(
            probe_type=ProbeType.OWNERSHIP, priority=4, confidence=1.0))
        await runner.on_turn_complete("We shipped it. That's my answer.")
        assert graded, "third follow-up asked past the cap"
    asyncio.run(run())


def test_done_phrase_grades_immediately():
    async def run():
        runner, session, graded = make_runner()
        await runner.ask_next_question()
        runner.on_partial("I fixed it. That's my answer.", is_final=True)
        await runner.on_turn_complete("I fixed it. That's my answer.")
        assert graded, "explicit done phrase should hand off to the grader"
    asyncio.run(run())


def test_repeat_request_reasks_and_leaves_no_trace():
    async def run():
        runner, session, graded = make_runner()
        await runner.ask_next_question()
        question_text = session.spoken[-1]
        runner.on_partial("Can you repeat the question?", is_final=True)
        await runner.on_turn_complete("Can you repeat the question?")
        assert session.spoken[-1] == question_text, "question not re-asked"
        assert not graded
        assert runner.state.transcript_partial == "", \
            "repeat request leaked into the answer transcript"
        assert runner.answer_started is None, \
            "answer clock started on a repeat request"
    asyncio.run(run())


def test_fragmented_repeat_request_fully_retracted():
    """STT splits one spoken turn into several final fragments; every
    fragment of the repeat request must leave the transcript (live leak
    2026-07-13: the request survived and became an evidence quote)."""
    async def run():
        runner, session, graded = make_runner()
        await runner.ask_next_question()
        question_text = session.spoken[-1]
        runner.on_partial("So my real answer starts here with content.", True)
        runner.on_partial("I'm sorry.", True)
        runner.on_partial("Can you repeat the question?", True)
        await runner.on_turn_complete(
            "I'm sorry. Can you repeat the question?")
        assert session.spoken[-1] == question_text, "question not re-asked"
        low = runner.state.transcript_partial.lower()
        assert "repeat" not in low and "sorry" not in low, \
            "repeat request fragments leaked into the transcript"
        assert "real answer starts here" in low, \
            "retraction destroyed real answer content"
        joined = " ".join(t for _, _, t in runner.transcript_log).lower()
        assert "repeat" not in joined, "fragments left in transcript_log"
    asyncio.run(run())


def test_rewrite_request_speaks_and_uses_last_rep(monkeypatch):
    from src.coach.rewrites import RewriteNote, RewriteResult

    captured = {}

    def fake_rewrite(question, answer, round, docs=None):
        captured.update(question=question, answer=answer, docs=docs)
        return RewriteResult(
            notes=[RewriteNote(dimension="i_vs_we",
                               problem="you said we shipped",
                               fix="say I drove the migration")],
            rewritten_answer="I drove the migration...")

    monkeypatch.setattr(agent_mod.coach_rewrites, "rewrite", fake_rewrite)

    answer_text = ("we shipped the migration together as a team over two "
                   "quarters and it went well overall despite some early "
                   "pushback from the platform group about the rollout order")

    class FakeCtx:
        question_text = "Tell me about a conflict."
        transcript = f"[  0.0s] CANDIDATE: {answer_text}"
        docs = []

    async def run():
        runner, session, graded = make_runner()
        await runner.ask_next_question()
        assert runner._last_rep is None
        await runner.send_rewrite()  # nothing graded yet: no-op
        says_before = len(session.spoken)
        runner._last_rep = FakeCtx()
        await runner.send_rewrite()
        assert len(session.spoken) == says_before + 1
        assert "on your screen" in session.spoken[-1]
        assert "say I drove the migration" not in session.spoken[-1], \
            "rewrite notes must not be read aloud; the user reads them"
        assert captured["question"] == "Tell me about a conflict."
        assert captured["answer"] == answer_text, \
            "rewrite should receive candidate speech, not transcript framing"
    asyncio.run(run())


def test_transcript_resets_between_questions():
    async def run():
        runner, session, graded = make_runner(n_questions=2)
        await runner.ask_next_question()
        runner.on_partial("My first answer content. That's my answer.", True)
        await runner.on_turn_complete("My first answer content. That's my answer.")
        await runner.on_turn_complete("Next.")
        joined = " ".join(t for _, _, t in runner.transcript_log)
        assert "first answer content" not in joined, \
            "previous answer leaked into the next question's transcript"
    asyncio.run(run())


def test_rewrite_refuses_empty_answer_only_without_docs(monkeypatch):
    """User rule 2026-07-13: thin answer + no docs -> honest refusal;
    thin answer + docs -> draft the answer from the docs."""
    from src.coach.rewrites import RewriteResult

    called = []

    def fake_rewrite(*a, **k):
        called.append(1)
        return RewriteResult(notes=[], rewritten_answer="From your docs...")

    monkeypatch.setattr(agent_mod.coach_rewrites, "rewrite", fake_rewrite)

    class EmptyCtx:
        question_text = "Tell me about a conflict."
        transcript = "[  0.0s] CANDIDATE: umm"
        docs = []

    class EmptyCtxWithDocs(EmptyCtx):
        docs = [("resume", "Led the migration of 12 services...")]

    async def run():
        runner, session, graded = make_runner()
        await runner.ask_next_question()
        runner._last_rep = EmptyCtx()
        await runner.send_rewrite()
        assert not called, "rewrite LLM called with no answer and no docs"
        assert "resume and stories" in session.spoken[-1], \
            "no-docs refusal should point at uploading documents"
        runner._last_rep = EmptyCtxWithDocs()
        await runner.send_rewrite()
        assert called, "docs present: the rewrite must draft, not refuse"
    asyncio.run(run())


def test_verdict_end_stops_session_without_regrading(monkeypatch):
    monkeypatch.setattr(agent_mod, "END_SHUTDOWN_DELAY_S", 0.01)

    async def run():
        ended = []
        runner, session, graded = make_runner(on_end=lambda: ended.append(True))
        await runner.ask_next_question()
        runner.on_partial("I fixed it. That's my answer.", True)
        await runner.on_turn_complete("I fixed it. That's my answer.")
        assert graded == [True]
        await runner.on_turn_complete("End.")
        assert graded == [True], "'end' triggered another grading pass"
        await asyncio.sleep(0.05)  # shutdown happens after the grace period
        assert ended, "'end' did not shut the session down"
    asyncio.run(run())


def test_mid_answer_end_session_aborts(monkeypatch):
    # Interrupt-then-abort flow (user request 2026-07-13): a short spoken
    # "end the session" works mid-rep, without waiting for the verdict.
    monkeypatch.setattr(agent_mod, "END_SHUTDOWN_DELAY_S", 0.01)

    async def run():
        ended = []
        runner, session, graded = make_runner(on_end=lambda: ended.append(True))
        await runner.ask_next_question()
        runner.on_partial("Actually, please end the session.", True)
        await runner.on_turn_complete("Actually, please end the session.")
        assert not graded, "abort must not grade a partial answer"
        await asyncio.sleep(0.05)
        assert ended, "spoken 'end the session' mid-answer did not end it"
    asyncio.run(run())


def test_answer_containing_end_words_keeps_going():
    async def run():
        runner, session, graded = make_runner()
        await runner.ask_next_question()
        text = ("Towards the end the session with stakeholders ran long, "
                "so I cut scope and shipped the pilot a week early anyway.")
        runner.on_partial(text, True)
        await runner.on_turn_complete(text)
        assert not graded, "a long answer must not end at a pause"
        assert runner.state is not None, \
            "an answer mentioning the end words aborted the session"
    asyncio.run(run())


def test_verdict_retry_reasks_same_question():
    async def run():
        runner, session, graded = make_runner()
        await runner.ask_next_question()
        question_text = session.spoken[-1]
        runner.on_partial("I fixed it. That's my answer.", True)
        await runner.on_turn_complete("I fixed it. That's my answer.")
        await runner.on_turn_complete("Retry, please.")
        assert session.spoken[-1] == question_text, "retry did not re-ask"
        assert runner.state is not None and \
            runner.state.transcript_partial == "", "retry state not fresh"
        assert not runner.awaiting_verdict
    asyncio.run(run())


def test_question_position_survives_retry():
    async def run():
        runner, session, graded = make_runner(n_questions=2)
        await runner.ask_next_question()
        assert (runner.question_number, runner.total_questions) == (1, 2)
        runner.on_partial("I fixed it. That's my answer.", True)
        await runner.on_turn_complete("I fixed it. That's my answer.")
        await runner.on_turn_complete("Retry.")
        assert runner.question_number == 1, "retry advanced the position"
        runner.on_partial("I fixed it better. That's my answer.", True)
        await runner.on_turn_complete("I fixed it better. That's my answer.")
        await runner.on_turn_complete("Next.")
        assert runner.question_number == 2
    asyncio.run(run())


# ---- simulation runner (spec 2.2) ----

def make_scores(weak=()):
    from src.grading.grader import DIMENSIONS, DimensionScore, RubricScores
    return RubricScores(
        dimensions={d: DimensionScore(level="Gap" if d in weak else "Solid")
                    for d in DIMENSIONS},
        spoken_summary=["One fix."])


def make_sim(monkeypatch, n_questions=2, duration_min=60, on_end=None,
             grade_fn=None, cloud=None):
    from src.session import planner
    cfg = SessionConfig(profile_id="pm", session_type="SIMULATION",
                        duration_min=duration_min)
    persona = resolve(PersonaTags(), overrides=cfg.persona_overrides,
                      selected_round=cfg.profile_id)
    manager = SessionManager(cfg, persona)
    session = FakeSession()
    queue = [Question(id=f"q{i}", text=f"Question {i}?")
             for i in range(n_questions)]
    plan = planner.plan(queue, duration_min, manager.round)
    runner = agent_mod.SimulationRunner(session, manager, queue, plan,
                                        on_end=on_end, cloud=cloud)
    published = []
    runner.publish_ui = lambda topic, payload: published.append(
        (topic, payload))
    monkeypatch.setattr(agent_mod, "grade",
                        grade_fn or (lambda *a, **k: make_scores()))
    monkeypatch.setattr(agent_mod, "missed_ammo", lambda *a, **k: [])
    monkeypatch.setattr(agent_mod, "save_session", lambda rec: None)
    return runner, session, published


async def speak_answer(runner, text="I fixed it. That's my answer."):
    runner.on_partial(text, True)
    await runner.on_turn_complete(text)


def test_simulation_no_feedback_between_questions(monkeypatch):
    async def run():
        runner, session, published = make_sim(monkeypatch, n_questions=2)
        await runner.ask_next_question()
        await speak_answer(runner)
        assert session.spoken[-1] == "Question 1?", \
            "simulation must move straight to the next question"
        assert not runner.awaiting_verdict, \
            "no retry/next/end loop between simulation questions"
        spoken = " ".join(session.spoken).lower()
        assert "score" not in spoken, "feedback spoken between questions"
        assert not any(t == "scorecard" for t, _ in published), \
            "per-question score card published during a simulation"
    asyncio.run(run())


def test_simulation_overrun_drops_questions_and_debriefs(monkeypatch):
    async def run():
        # 20-min plan fits 2 of the 3 queued questions up front.
        runner, session, published = make_sim(monkeypatch, n_questions=3,
                                              duration_min=20)
        assert runner.total_questions == 2, "planner should trim the queue"
        await runner.ask_next_question()
        # Seeded overrun: the first answer burned 900 of 1020 usable
        # seconds, so the remaining question no longer fits.
        runner.sim_started = time.monotonic() - 900
        await speak_answer(runner)
        assert runner.dropped == 1, "overrun did not drop the last question"
        topics = [t for t, _ in published]
        assert "debrief" in topics, "no debrief after the drop"
        payload = dict(published)["debrief"]
        assert payload["dropped"] == 1
        assert payload["dropped_questions"] == ["Question 1?"], \
            "the debrief must name the dropped question"
        assert len(payload["reps"]) == 1
        assert runner.awaiting_verdict
        assert "debrief is on the screen" in " ".join(session.spoken)
    asyncio.run(run())


def test_simulation_debrief_reports_cross_answer_patterns(monkeypatch):
    async def run():
        runner, session, published = make_sim(
            monkeypatch, n_questions=2,
            grade_fn=lambda *a, **k: make_scores(weak=("i_vs_we",)))
        await runner.ask_next_question()
        await speak_answer(runner)
        await speak_answer(runner)
        payload = dict(published)["debrief"]
        assert "we-heavy in 2 of 2 answers" in payload["patterns"]
        assert all(r["graded"] for r in payload["reps"])
        assert "we-heavy" in " ".join(session.spoken)
    asyncio.run(run())


def test_simulation_grading_failure_still_debriefs(monkeypatch):
    async def run():
        def broken_grade(*a, **k):
            raise RuntimeError("quota")

        runner, session, published = make_sim(monkeypatch, n_questions=1,
                                              grade_fn=broken_grade)
        await runner.ask_next_question()
        await speak_answer(runner)
        payload = dict(published)["debrief"]
        assert payload["reps"][0]["graded"] is False
        assert "could not score" in " ".join(session.spoken)
        assert runner.awaiting_verdict
    asyncio.run(run())


def test_simulation_verdict_accepts_only_end(monkeypatch):
    monkeypatch.setattr(agent_mod, "END_SHUTDOWN_DELAY_S", 0.01)

    async def run():
        ended = []
        runner, session, published = make_sim(
            monkeypatch, n_questions=1, on_end=lambda: ended.append(True))
        await runner.ask_next_question()
        await speak_answer(runner)
        assert runner.awaiting_verdict
        await runner.on_turn_complete("Retry.")
        assert "say end" in session.spoken[-1].lower(), \
            "retry has no meaning after a simulation debrief"
        assert not ended
        await runner.on_turn_complete("End.")
        await asyncio.sleep(0.05)
        assert ended, "'end' did not close the simulation"
    asyncio.run(run())


def test_verdict_next_on_last_question_ends(monkeypatch):
    monkeypatch.setattr(agent_mod, "END_SHUTDOWN_DELAY_S", 0.01)

    async def run():
        ended = []
        runner, session, graded = make_runner(on_end=lambda: ended.append(True))
        await runner.ask_next_question()  # only question in the queue
        runner.on_partial("I fixed it. That's my answer.", True)
        await runner.on_turn_complete("I fixed it. That's my answer.")
        await runner.on_turn_complete("Next.")
        await asyncio.sleep(0.05)  # shutdown happens after the grace period
        assert ended, "no questions left: 'next' should end the session"
    asyncio.run(run())


# ---- cloud persistence hooks (scope item 15) ----

class FakeCloud:
    """Stands in for CloudSession; records what the runners send it."""

    def __init__(self):
        self.answers = []
        self.rewrites = []
        self.finish_calls = []

    async def record_answer(self, **kw):
        self.answers.append(kw)

    async def attach_rewrite(self, rewrite):
        self.rewrites.append(rewrite)

    async def finish(self, **kw):
        self.finish_calls.append(kw)


def make_drill_with_cloud(monkeypatch, cloud, n_questions=1, on_end=None):
    cfg = SessionConfig(profile_id="pm", followup_mode="listen")
    persona = resolve(PersonaTags(), overrides=cfg.persona_overrides,
                      selected_round=cfg.profile_id)
    manager = SessionManager(cfg, persona)
    session = FakeSession()
    queue = [Question(id=f"q{i}", text=f"Question {i}?")
             for i in range(n_questions)]
    runner = DrillRunner(session, manager, queue, on_end=on_end,
                         cloud=cloud)
    monkeypatch.setattr(agent_mod, "grade", lambda *a, **k: make_scores())
    monkeypatch.setattr(agent_mod, "missed_ammo", lambda *a, **k: [])
    monkeypatch.setattr(agent_mod, "save_session", lambda rec: None)
    return runner, session


def test_drill_records_graded_answer_to_cloud(monkeypatch):
    monkeypatch.setattr(agent_mod, "END_SHUTDOWN_DELAY_S", 0.01)

    async def run():
        cloud = FakeCloud()
        runner, session = make_drill_with_cloud(monkeypatch, cloud)
        await runner.ask_next_question()
        await speak_answer(runner)
        assert len(cloud.answers) == 1, "graded drill rep not sent to cloud"
        row = cloud.answers[0]
        assert row["question"] == "Question 0?"
        assert row["scores"] is not None
        assert "That's my answer" in row["transcript"]
        await runner.on_turn_complete("End.")
        await asyncio.sleep(0.05)
        assert cloud.finish_calls, "session end did not close the cloud row"
    asyncio.run(run())


def test_drill_guest_runs_without_cloud(monkeypatch):
    # cloud=None is the guest/console path; grading must not touch it.
    async def run():
        runner, session = make_drill_with_cloud(monkeypatch, None)
        await runner.ask_next_question()
        await speak_answer(runner)
        assert runner.awaiting_verdict, "grading broke without cloud"
    asyncio.run(run())


def test_simulation_records_all_reps_then_finishes(monkeypatch):
    async def run():
        cloud = FakeCloud()
        runner, session, published = make_sim(monkeypatch, n_questions=2,
                                              cloud=cloud)
        await runner.ask_next_question()
        await speak_answer(runner)
        assert not cloud.answers, \
            "simulation must not write answers before the debrief"
        await speak_answer(runner)
        assert len(cloud.answers) == 2
        assert cloud.finish_calls and \
            cloud.finish_calls[0]["raw"]["type"] == "simulation"
    asyncio.run(run())


# --- Interrupt button + spoken command (live 2026-07-14: clicking Interrupt
# then saying "end" did not end; the agent spoke ahead over the user) ---

def test_interrupt_then_end_ends_session(monkeypatch):
    # The reported bug: interrupt mid-rep, then a bare "end" must end it,
    # even though we are not in the post-score verdict state.
    monkeypatch.setattr(agent_mod, "END_SHUTDOWN_DELAY_S", 0.01)

    async def run():
        ended = []
        runner, session, graded = make_runner(on_end=lambda: ended.append(True))
        await runner.ask_next_question()
        runner.note_interrupt()  # the web Interrupt button
        await runner.on_turn_complete("end")
        assert not graded, "interrupt + end must not grade a partial answer"
        await asyncio.sleep(0.05)
        assert ended, "interrupt + 'end' did not end the session"
    asyncio.run(run())


def test_interrupt_is_one_shot(monkeypatch):
    # After an interrupt, a non-command utterance clears the flag and normal
    # answering resumes; it must not be swallowed or mistaken for a command.
    monkeypatch.setattr(agent_mod, "END_SHUTDOWN_DELAY_S", 0.01)

    async def run():
        ended = []
        runner, session, graded = make_runner(on_end=lambda: ended.append(True))
        await runner.ask_next_question()
        runner.note_interrupt()
        await runner.on_turn_complete("So the project I want to talk about")
        assert not ended, "a normal utterance after interrupt ended the session"
        assert not runner._interrupted, "interrupt flag must be one-shot"
        assert runner.state is not None, "runner should resume listening"
    asyncio.run(run())


def test_interrupt_silences_feedback_but_opens_verdict(monkeypatch):
    # No speaking ahead: an interrupt during scoring suppresses the spoken
    # feedback and verdict prompt (a non-interruptible say would talk over
    # the user's "end"), while awaiting_verdict still opens retry/next/end.
    class DummyScores:
        spoken_summary = ["ok"]

        def model_dump(self):
            return {"dimensions": {}}

    monkeypatch.setattr(agent_mod, "grade", lambda *a, **k: DummyScores())
    monkeypatch.setattr(agent_mod, "missed_ammo", lambda *a, **k: [])
    monkeypatch.setattr(agent_mod, "save_session", lambda *a, **k: None)
    monkeypatch.setattr(agent_mod.report, "render_card", lambda *a, **k: "card")
    monkeypatch.setattr(agent_mod.report, "spoken_script",
                        lambda *a, **k: "your feedback here")

    async def run():
        cfg = SessionConfig(profile_id="pm")
        persona = resolve(PersonaTags(), overrides=cfg.persona_overrides,
                          selected_round=cfg.profile_id)
        manager = SessionManager(cfg, persona)
        session = FakeSession()
        queue = [Question(id="q0", text="Question 0?")]
        runner = DrillRunner(session, manager, queue)
        await runner.ask_next_question()
        runner.on_partial("I did the thing and it worked well.", True)
        runner.note_interrupt()
        await runner._grade_and_feedback()
        assert runner.awaiting_verdict, \
            "verdict path must still open so retry/next/end work"
        joined = " ".join(session.spoken)
        assert "your feedback here" not in joined, \
            "interrupt must silence the spoken feedback"
        assert "Say retry" not in joined, \
            "interrupt must silence the verdict prompt (no speaking ahead)"
    asyncio.run(run())
