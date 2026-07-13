"""Engine unit tests: analyzers, decision gates, probe selection (item 3)."""

import random
from pathlib import Path

import pytest

from src.engine import analyzers, decision, probes
from src.engine.decision import ActionKind
from src.engine.state import (
    AnswerState,
    PersonaParams,
    ProbeRecord,
    ProbeType,
    Question,
    SectionStatus,
    load_round_profile,
)

ROOT = Path(__file__).resolve().parents[1]


def make_persona(**kw) -> PersonaParams:
    defaults = dict(
        persona_id="test", display_name="Test interviewer",
        round_profile="pm",
        probe_mix={"specificity": 0.4, "ownership": 0.3, "quantify": 0.3},
        intensity=3, interrupt_eagerness=1.0, interrupt_budget=2,
        patience_ms=600, time_budget_s=150)
    defaults.update(kw)
    return PersonaParams(**defaults)


def make_state(profile="pm", **kw) -> AnswerState:
    round_profile = load_round_profile(ROOT / "config" / "rounds" / f"{profile}.yaml")
    defaults = dict(
        question=Question(id="q1", text="Tell me about a conflict.",
                          expected_buckets=["conflict"]),
        round=round_profile, persona=make_persona(),
        interrupt_budget=2)
    defaults.update(kw)
    return AnswerState(**defaults)


# ---------- analyzers ----------

class TestVagueness:
    def test_vague_phrase_without_concrete_noun_flags(self):
        flagged, phrase = analyzers.detect_vagueness(
            "so basically i aligned stakeholders and then things moved forward "
            "and everyone was happier with the direction we took after that")
        assert flagged and phrase == "aligned stakeholders"

    def test_vague_phrase_with_number_nearby_passes(self):
        flagged, _ = analyzers.detect_vagueness(
            "i aligned stakeholders across 4 teams within two weeks")
        assert not flagged

    def test_vague_phrase_with_name_nearby_passes(self):
        flagged, _ = analyzers.detect_vagueness(
            "i worked closely with Priya from the payments side on it")
        assert not flagged

    def test_clean_answer_no_flag(self):
        flagged, _ = analyzers.detect_vagueness(
            "i rewrote the retry logic myself and shipped it on Tuesday")
        assert not flagged


class TestWeDensity:
    def test_we_heavy_ratio(self):
        text = "we decided that we should move and our team agreed we would"
        assert analyzers.we_ratio(text) > 0.7

    def test_i_heavy_ratio(self):
        text = "i decided i would take my plan and i presented my analysis"
        assert analyzers.we_ratio(text) < 0.3

    def test_flag_requires_30s(self):
        state_text = "we did it and we liked it and we shipped our thing"
        profile = load_round_profile(ROOT / "config/rounds/pm.yaml")
        signals, _ = analyzers.analyze(state_text, 20_000, profile)
        assert not signals.we_flag
        signals, _ = analyzers.analyze(state_text, 35_000, profile)
        assert signals.we_flag

    def test_consulting_threshold_is_lower(self):
        pm = load_round_profile(ROOT / "config/rounds/pm.yaml")
        consulting = load_round_profile(ROOT / "config/rounds/consulting.yaml")
        # Ratio around 0.5: above consulting's 0.45, below pm's 0.6.
        text = "we planned it and we shipped it but i led i drove my analysis " \
               "and i owned the number while we celebrated our win"
        ratio = analyzers.we_ratio(text)
        assert consulting.we_ratio_threshold < ratio <= pm.we_ratio_threshold
        s_pm, _ = analyzers.analyze(text, 40_000, pm)
        s_co, _ = analyzers.analyze(text, 40_000, consulting)
        assert not s_pm.we_flag and s_co.we_flag


class TestHscarr:
    def test_sections_marked_seen(self):
        progress = analyzers.track_hscarr(
            "the situation was rough. the problem was churn. so what i did "
            "was rebuild onboarding. as a result churn dropped. "
            "what i learned was to start with data.",
            {s: SectionStatus.NOT_SEEN for s in
             ["hook", "situation", "complication", "action", "resolution", "reflection"]})
        for section in ["situation", "complication", "action", "resolution", "reflection"]:
            assert progress[section] == SectionStatus.SEEN

    def test_skip_detected_resolution_without_action(self):
        progress = {s: SectionStatus.NOT_SEEN for s in
                    ["hook", "situation", "complication", "action", "resolution", "reflection"]}
        progress["situation"] = SectionStatus.SEEN
        progress["resolution"] = SectionStatus.SEEN
        skipped, detail = analyzers.detect_skip(progress)
        assert skipped and "action" in detail


class TestTimeBudget:
    def test_rambling_after_soft_limit_without_resolution(self):
        profile = load_round_profile(ROOT / "config/rounds/pm.yaml")
        signals, _ = analyzers.analyze("still setting up the story", 151_000, profile)
        assert signals.rambling and not signals.overrun

    def test_overrun_at_soft_plus_30(self):
        profile = load_round_profile(ROOT / "config/rounds/pm.yaml")
        signals, _ = analyzers.analyze("still going", 181_000, profile)
        assert signals.overrun


class TestDeflection:
    def test_repeat_answer_deflects(self):
        pre = "i aligned stakeholders and drove consensus across the org"
        reply = "well like i said i aligned stakeholders and drove consensus across the org"
        assert analyzers.check_deflection(pre, reply, "What exactly did you say to them?")

    def test_new_content_is_not_deflection(self):
        pre = "i aligned stakeholders and drove consensus"
        reply = "specifically i told Marcus the migration would slip two weeks unless he cut scope"
        assert not analyzers.check_deflection(pre, reply, "What exactly did you say to them?")

    def test_no_recall_echoing_probe_words_still_deflects(self):
        """Live miss 2026-07-12: parroting a probe word ("specific") made
        the shared-content check treat a flat refusal as engagement."""
        pre = "i was designing the reviews card i don't really remember the details"
        reply = "Yeah. Like I said, I just don't recall the specific. That's my answer."
        probe = ("You mentioned it was a couple of months back, can you be "
                 "more specific about the timeframe.")
        assert analyzers.check_deflection(pre, reply, probe)

    def test_no_recall_followed_by_substance_is_not_deflection(self):
        pre = "i aligned stakeholders and drove consensus"
        reply = ("I don't remember the exact words, but I told Marcus the "
                 "migration would slip two weeks unless he cut scope, and I "
                 "walked him through the dependency chart line by line until "
                 "he agreed to drop the reporting module from the release.")
        assert not analyzers.check_deflection(
            pre, reply, "What exactly did you say to them?")


# ---------- decision loop ----------

class TestDecisionGates:
    def test_never_interrupts_before_25s(self):
        state = make_state()
        state.clock_ms = 20_000
        state.transcript_partial = ("we did stuff and we aligned stakeholders "
                                    "and things went well for everyone involved")
        signals = decision.compute_signals(state)
        action = decision.on_partial(state, signals)
        assert action.kind == ActionKind.CONTINUE
        assert state.queued_probes == []

    def test_fires_after_25s(self):
        state = make_state()
        state.clock_ms = 40_000
        state.transcript_partial = ("i aligned stakeholders and things moved along "
                                    "and everyone felt good about direction generally speaking")
        signals = decision.compute_signals(state)
        action = decision.on_partial(state, signals)
        assert action.kind == ActionKind.INTERRUPT
        assert action.probe.probe_type == ProbeType.SPECIFICITY
        assert state.interrupt_budget == 1

    def test_cooldown_queues_instead(self):
        state = make_state()
        state.clock_ms = 50_000
        state.last_interrupt_ms = 30_000  # 20s ago, inside 40s cooldown
        state.transcript_partial = "i aligned stakeholders and stuff happened after that generally"
        signals = decision.compute_signals(state)
        action = decision.on_partial(state, signals)
        assert action.kind == ActionKind.CONTINUE
        assert state.queued_probes

    def test_no_budget_queues(self):
        state = make_state(interrupt_budget=0)
        state.clock_ms = 60_000
        state.transcript_partial = "i aligned stakeholders and stuff happened after that generally"
        signals = decision.compute_signals(state)
        action = decision.on_partial(state, signals)
        assert action.kind == ActionKind.CONTINUE
        assert state.queued_probes

    def test_overrun_ignores_budget(self):
        state = make_state(interrupt_budget=0)
        state.clock_ms = 185_000
        state.transcript_partial = "and then another thing happened and also"
        signals = decision.compute_signals(state)
        action = decision.on_partial(state, signals)
        assert action.kind == ActionKind.INTERRUPT
        assert action.probe.probe_type == ProbeType.REDIRECT_WRAP

    def test_low_eagerness_queues_low_confidence(self):
        # Recruiter-style eagerness 0.6 raises the bar to 1.0: nothing fires.
        state = make_state(persona=make_persona(interrupt_eagerness=0.6))
        state.clock_ms = 60_000
        state.transcript_partial = "i aligned stakeholders and stuff happened after that generally"
        signals = decision.compute_signals(state)
        action = decision.on_partial(state, signals)
        assert action.kind == ActionKind.CONTINUE
        assert state.queued_probes

    def test_high_eagerness_fires_low_confidence(self):
        state = make_state(persona=make_persona(interrupt_eagerness=1.3))
        state.clock_ms = 60_000
        state.transcript_partial = "i aligned stakeholders and stuff happened after that generally"
        signals = decision.compute_signals(state)
        action = decision.on_partial(state, signals)
        assert action.kind == ActionKind.INTERRUPT

    def test_priority_order_redirect_beats_specificity(self):
        state = make_state()
        state.clock_ms = 155_000  # past pm soft limit, before +30s overrun
        state.transcript_partial = "i aligned stakeholders and more setup and more context still"
        signals = decision.compute_signals(state)
        assert signals.rambling and signals.vague_claim
        action = decision.on_partial(state, signals)
        assert action.probe.probe_type == ProbeType.REDIRECT


class TestEndpoint:
    def test_queued_probe_asked_at_pause(self):
        state = make_state()
        state.clock_ms = 50_000
        state.last_interrupt_ms = 30_000
        state.transcript_partial = "i aligned stakeholders and stuff happened after that generally"
        decision.on_partial(state, decision.compute_signals(state))
        assert state.queued_probes
        action = decision.on_endpoint(state, rng=random.Random(1))
        assert action.kind == ActionKind.ASK

    def test_handoff_when_complete(self):
        state = make_state()
        state.transcript_partial = (
            "the situation was a failing launch. so what i did was rebuild "
            "the funnel. as a result signups doubled. what i learned was to "
            "instrument first.")
        decision.compute_signals(state)
        action = decision.on_endpoint(state, rng=random.Random(1))
        assert action.kind == ActionKind.HANDOFF_TO_GRADER

    def test_emotional_chain_on_consulting(self):
        state = make_state(profile="consulting")
        state.probes_fired.append(ProbeRecord(
            probe_type=ProbeType.OWNERSHIP, fired_at_ms=40_000,
            trigger="we_ratio", text="What did YOU do?"))
        state.pre_probe_transcript = ""
        # rng seeded to roll under 0.5 (Random(1).random() == 0.134...)
        assert random.Random(1).random() < 0.5
        action = decision.on_endpoint(state, rng=random.Random(1))
        assert action.kind == ActionKind.ASK
        assert action.probe.probe_type == ProbeType.EMOTIONAL

    def test_emotional_never_chains_on_pm(self):
        state = make_state(profile="pm")
        state.probes_fired.append(ProbeRecord(
            probe_type=ProbeType.OWNERSHIP, fired_at_ms=40_000,
            trigger="we_ratio", text="What did YOU do?"))
        for seed in range(10):
            state2 = state.model_copy(deep=True)
            action = decision.on_endpoint(state2, rng=random.Random(seed))
            assert (action.probe is None
                    or action.probe.probe_type != ProbeType.EMOTIONAL)

    def test_deflection_reasks_then_forces_gap(self):
        state = make_state()
        state.pre_probe_transcript = "i aligned stakeholders and drove consensus for the project"
        state.probes_fired.append(ProbeRecord(
            probe_type=ProbeType.SPECIFICITY, fired_at_ms=40_000,
            trigger="vague", text="What exactly did you say?"))
        state.transcript_partial = state.pre_probe_transcript + \
            " like i said i aligned stakeholders and drove consensus for the project"
        action = decision.on_endpoint(state, rng=random.Random(1))
        assert action.kind == ActionKind.ASK
        assert action.probe.detail == "reask_harder"
        assert state.deflect_count == 1

        action2 = decision.on_endpoint(state, rng=random.Random(1))
        assert action2.kind == ActionKind.FOLLOWUP_OR_NEXT
        assert any("Gap" in n for n in state.grader_notes)


# ---------- probes ----------

class TestProbes:
    def test_template_selection_no_llm(self):
        state = make_state()
        from src.engine.state import ProbeCandidate
        cand = ProbeCandidate(probe_type=ProbeType.SPECIFICITY, priority=3,
                              confidence=0.75)
        text = probes.select_probe(cand, state, rng=random.Random(1), use_llm=False)
        assert text and len(text) < 200

    def test_reask_harder_template(self):
        state = make_state()
        from src.engine.state import ProbeCandidate
        cand = ProbeCandidate(probe_type=ProbeType.SPECIFICITY, priority=0,
                              confidence=1.0, detail="reask_harder")
        assert (probes.select_probe(cand, state, use_llm=False)
                == probes.REASK_HARDER[ProbeType.SPECIFICITY])
        quant = ProbeCandidate(probe_type=ProbeType.QUANTIFY, priority=0,
                               confidence=1.0, detail="reask_harder")
        assert "number" in probes.select_probe(quant, state, use_llm=False)

    def test_nudge_is_non_leading(self):
        state = make_state()
        from src.engine.state import ProbeCandidate
        cand = ProbeCandidate(probe_type=ProbeType.NUDGE, priority=0, confidence=1.0)
        text = probes.select_probe(cand, state, rng=random.Random(1), use_llm=True)
        # NUDGE never goes through the LLM and never hints at content.
        assert "take your time" in text.lower()
        for banned in ("metric", "number", "mention", "result"):
            assert banned not in text.lower()

    def test_intensity_band_switches_templates(self):
        gentle = make_state(persona=make_persona(intensity=2))
        blunt = make_state(persona=make_persona(intensity=5))
        from src.engine.state import ProbeCandidate
        cand = ProbeCandidate(probe_type=ProbeType.OWNERSHIP, priority=4,
                              confidence=0.7)
        g = {probes.select_probe(cand, gentle, rng=random.Random(s), use_llm=False)
             for s in range(10)}
        b = {probes.select_probe(cand, blunt, rng=random.Random(s), use_llm=False)
             for s in range(10)}
        assert g.isdisjoint(b)


# ---------- grading auto-rule (local part) ----------

class TestLengthLevel:
    def test_length_bands(self):
        from src.grading.grader import length_level
        assert length_level(120, (90, 150)) == "Solid"
        assert length_level(170, (90, 150)) == "NeedsWork"   # within 25% over
        assert length_level(200, (90, 150)) == "Gap"
        assert length_level(75, (90, 150)) == "NeedsWork"    # within 25% under
        assert length_level(50, (90, 150)) == "Gap"
