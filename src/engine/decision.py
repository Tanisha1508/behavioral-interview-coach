"""Probe decision loop (spec 3.3). Local rules, hot-path under 10ms.

This module never grades and never sees user docs. It only reads the live
AnswerState and logs ProbeRecords for the grader to consume later.
"""

from __future__ import annotations

import enum
import random
from typing import Optional

from pydantic import BaseModel

from src.engine import analyzers
from src.engine.state import (
    AnswerState,
    Floor,
    ProbeCandidate,
    ProbeType,
    SectionStatus,
    SignalSet,
)

# Hard rules (spec 3.5), also mirrored in config/settings.yaml.
MIN_INTERRUPT_CLOCK_MS = 25_000
INTERRUPT_COOLDOWN_MS = 40_000
SILENCE_STALL_MS = 4_000
BASE_CONFIDENCE = 0.6

# Per-trigger confidence: how sure the local rules are that a probe is
# warranted. Ordering mirrors the priority ladder in spec 3.3.
CONFIDENCE = {
    ProbeType.REDIRECT: 0.90,
    ProbeType.DEPTH: 0.80,
    ProbeType.SPECIFICITY: 0.75,
    ProbeType.OWNERSHIP: 0.70,
    ProbeType.QUANTIFY: 0.65,
}


class ActionKind(str, enum.Enum):
    CONTINUE = "CONTINUE"
    INTERRUPT = "INTERRUPT"
    ASK = "ASK"
    HANDOFF_TO_GRADER = "HANDOFF_TO_GRADER"
    FOLLOWUP_OR_NEXT = "FOLLOWUP_OR_NEXT"


class Action(BaseModel):
    kind: ActionKind
    probe: Optional[ProbeCandidate] = None


def _candidates(signals: SignalSet) -> list[ProbeCandidate]:
    out = []
    if signals.rambling:
        out.append(ProbeCandidate(probe_type=ProbeType.REDIRECT, priority=1,
                                  confidence=CONFIDENCE[ProbeType.REDIRECT]))
    if signals.skipped_section:
        out.append(ProbeCandidate(probe_type=ProbeType.DEPTH, priority=2,
                                  confidence=CONFIDENCE[ProbeType.DEPTH],
                                  detail=signals.skipped_detail or ""))
    if signals.vague_claim:
        out.append(ProbeCandidate(probe_type=ProbeType.SPECIFICITY, priority=3,
                                  confidence=CONFIDENCE[ProbeType.SPECIFICITY],
                                  detail=signals.vague_phrase or ""))
    if signals.we_flag:
        out.append(ProbeCandidate(probe_type=ProbeType.OWNERSHIP, priority=4,
                                  confidence=CONFIDENCE[ProbeType.OWNERSHIP],
                                  detail=f"we_ratio={signals.we_ratio:.2f}"))
    if signals.missing_numbers:
        out.append(ProbeCandidate(probe_type=ProbeType.QUANTIFY, priority=5,
                                  confidence=CONFIDENCE[ProbeType.QUANTIFY]))
    return out


def _queue(state: AnswerState, cand: ProbeCandidate) -> None:
    if all(q.probe_type != cand.probe_type for q in state.queued_probes):
        state.queued_probes.append(cand)


def compute_signals(state: AnswerState) -> SignalSet:
    signals, progress = analyzers.analyze(
        state.transcript_partial, state.clock_ms, state.round,
        state.hscarr_progress,
    )
    state.hscarr_progress = progress
    if (state.floor == Floor.SILENCE and state.silence_started_ms is not None
            and state.clock_ms - state.silence_started_ms > SILENCE_STALL_MS):
        signals.stalled = True
    state.signals = signals
    return signals


def on_partial(state: AnswerState, signals: SignalSet) -> Action:
    # 1. Hard interrupt: overrun ignores budget and cooldown.
    if signals.overrun:
        state.last_interrupt_ms = state.clock_ms
        return Action(kind=ActionKind.INTERRUPT, probe=ProbeCandidate(
            probe_type=ProbeType.REDIRECT_WRAP, priority=0, confidence=1.0))

    # 2. Soft candidates, priority ordered.
    candidates = _candidates(signals)
    if not candidates:
        return Action(kind=ActionKind.CONTINUE)
    best = min(candidates, key=lambda c: c.priority)

    # 3. Gates.
    if state.clock_ms < MIN_INTERRUPT_CLOCK_MS:
        return Action(kind=ActionKind.CONTINUE)  # the hook gets its shot
    if state.interrupt_budget <= 0:
        _queue(state, best)
        return Action(kind=ActionKind.CONTINUE)
    if state.clock_ms - state.last_interrupt_ms < INTERRUPT_COOLDOWN_MS:
        _queue(state, best)
        return Action(kind=ActionKind.CONTINUE)
    if state.hscarr_progress.get("reflection") == SectionStatus.SEEN:
        _queue(state, best)
        return Action(kind=ActionKind.CONTINUE)

    # 4. Persona modulation. Spec 4.3 semantics: eagerness above 1 interrupts
    # sooner, so it lowers the confidence bar (see DECISIONS.md on the
    # pseudocode conflict).
    threshold = BASE_CONFIDENCE / max(state.persona.interrupt_eagerness, 0.01)
    if best.confidence < threshold:
        _queue(state, best)
        return Action(kind=ActionKind.CONTINUE)

    # 5. Fire.
    state.interrupt_budget -= 1
    state.last_interrupt_ms = state.clock_ms
    return Action(kind=ActionKind.INTERRUPT, probe=best)


def _answer_complete(state: AnswerState) -> bool:
    return state.user_signaled_done or (
        state.hscarr_progress.get("resolution") == SectionStatus.SEEN
        and state.hscarr_progress.get("reflection") == SectionStatus.SEEN
    )


def on_endpoint(state: AnswerState, rng: random.Random | None = None) -> Action:
    rng = rng or random.Random()

    # Deflection check on the reply to the last probe (spec 3.4).
    if state.probes_fired and state.pre_probe_transcript:
        last = state.probes_fired[-1]
        # Only the text spoken after the probe is the reply; passing the
        # whole transcript let pre-probe words dominate the overlap ratio
        # and flag genuine replies as deflections.
        reply = state.transcript_partial
        if reply.startswith(state.pre_probe_transcript):
            reply = reply[len(state.pre_probe_transcript):]
        deflected = analyzers.check_deflection(
            state.pre_probe_transcript, reply, last.text)
        if deflected:
            state.deflect_count += 1
            state.signals.deflected = True
            if state.deflect_count == 1:
                return Action(kind=ActionKind.ASK, probe=ProbeCandidate(
                    probe_type=last.probe_type, priority=0, confidence=1.0,
                    detail="reask_harder"))
            state.grader_notes.append(
                "deflected twice on "
                f"{last.probe_type.value}: force Specificity to Gap")
            state.queued_probes.clear()
            return Action(kind=ActionKind.FOLLOWUP_OR_NEXT)

    # Emotional chaining (spec 3.4): after a SPECIFICITY or OWNERSHIP probe
    # resolves, roll the round's emotional weight once.
    if (state.probes_fired
            and state.round.emotional_probe_weight > 0
            and state.probes_fired[-1].probe_type in
            (ProbeType.SPECIFICITY, ProbeType.OWNERSHIP)
            and not any(p.probe_type == ProbeType.EMOTIONAL
                        for p in state.probes_fired)
            and rng.random() < state.round.emotional_probe_weight):
        return Action(kind=ActionKind.ASK, probe=ProbeCandidate(
            probe_type=ProbeType.EMOTIONAL, priority=0, confidence=1.0))

    if state.queued_probes:
        # probe_mix applies here (spec 4.3): when several probe types are
        # eligible at a pause, the persona's sampling weights pick one.
        # Live interrupts keep the strict priority ladder of spec 3.3.
        weights = [
            max(state.persona.probe_mix.get(c.probe_type.value.lower(), 0.05), 0.01)
            for c in state.queued_probes]
        chosen = rng.choices(state.queued_probes, weights=weights, k=1)[0]
        state.queued_probes.remove(chosen)
        return Action(kind=ActionKind.ASK, probe=chosen)

    if _answer_complete(state):
        return Action(kind=ActionKind.HANDOFF_TO_GRADER)

    if state.signals.stalled:
        return Action(kind=ActionKind.ASK, probe=ProbeCandidate(
            probe_type=ProbeType.NUDGE, priority=0, confidence=1.0))

    return Action(kind=ActionKind.FOLLOWUP_OR_NEXT)
