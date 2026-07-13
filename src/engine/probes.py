"""Probe templates, selection, and speculative generation (spec 3.4).

Templates are the seed. When an LLM client is available, Gemini rewrites the
seed referencing the candidate's actual words; on any LLM failure the seed
ships as-is, so the hot path never blocks on a network call.
"""

from __future__ import annotations

import random
import re

from src.engine.state import AnswerState, ProbeCandidate, ProbeType

# Two bands per type: index 0 for intensity 1-3, index 1 for intensity 4-5.
TEMPLATES: dict[ProbeType, list[list[str]]] = {
    ProbeType.SPECIFICITY: [
        ["What exactly did you say to them in that conversation?",
         "Walk me through that conversation. What were the actual words?"],
        ["Stop there. What exactly did you say to him?",
         "Give me the exact words you used."],
    ],
    ProbeType.OWNERSHIP: [
        ["You said 'we' a few times there. What did you personally do?",
         "Which part of that was yours alone?"],
        ["You keep saying 'we'. What did YOU do?",
         "Strip the team out of it. What was your contribution?"],
    ],
    ProbeType.QUANTIFY: [
        ["Can you put a number on that?",
         "How much, roughly? Give me a figure."],
        ["How much? Put a number on it.",
         "Numbers. What moved, and by how much?"],
    ],
    ProbeType.DEPTH: [
        ["Why that approach? What else did you consider?",
         "What was the alternative you rejected, and why?"],
        ["Why that approach and what else did you consider?",
         "That skipped a step. What did you actually do before the result?"],
    ],
    ProbeType.COUNTERFACTUAL: [
        ["What if they had refused? What was your plan?",
         "Suppose that hadn't worked. What then?"],
        ["What if she had refused?",
         "And if that bet had failed?"],
    ],
    ProbeType.REDIRECT: [
        ["Let me pause you there. Jump to what happened in the end.",
         "In the interest of time, take me straight to the outcome."],
        ["Let me stop you. Jump to what happened in the end.",
         "I have what I need on the setup. The ending, please."],
    ],
    ProbeType.REDIRECT_WRAP: [
        ["Sorry, quick pause. We're over time on this one. One sentence: how did it end?"],
        ["I need to stop you there. Wrap it up in one sentence."],
    ],
    ProbeType.EMOTIONAL: [
        ["How did that make you feel in the moment?",
         "What was going through your head right then?"],
        ["How did that feel, honestly?",
         "In that moment, what were you afraid of?"],
    ],
    ProbeType.NUDGE: [
        ["Take your time. Where were you?"],
        ["Take your time."],
    ],
}

# Per-type reask templates: a deflected probe re-asks in its own terms.
# One generic reask sent quantify deflections a specificity line
# (live rep 2026-07-10).
REASK_HARDER = {
    ProbeType.SPECIFICITY: ("That's the same answer. I'm asking "
                            "specifically: what were the words you used?"),
    ProbeType.QUANTIFY: ("Same question, and I do want a number: how much, "
                         "how many, or how long?"),
    ProbeType.OWNERSHIP: "I'll ask again: what did you, personally, do?",
    ProbeType.DEPTH: "Again: why that approach, and what did you rule out?",
    ProbeType.EMOTIONAL: "I'll ask once more: how did that actually feel?",
}
REASK_HARDER_DEFAULT = "Let me ask that once more, directly."

# Speculative pre-generation cache (spec 3.4): keyed by question id and
# probe type, filled while the user is still speaking.
_speculative: dict[tuple[str, str], str] = {}


def _band(intensity: int) -> int:
    return 1 if intensity >= 4 else 0


def _seed(probe_type: ProbeType, state: AnswerState, rng: random.Random) -> str:
    bands = TEMPLATES[probe_type]
    variants = bands[min(_band(state.persona.intensity), len(bands) - 1)]
    return rng.choice(variants)


def _recent_context(state: AnswerState, sentences: int = 2) -> str:
    parts = [p.strip() for p in state.transcript_partial.replace("?", ".")
             .replace("!", ".").split(".") if p.strip()]
    return ". ".join(parts[-sentences:])


_SECTION_SKIP_RE = re.compile(r"(\w+) seen while (\w+) not seen")


def _trigger_context(candidate: ProbeCandidate) -> str:
    """Human framing of what fired the probe. Analyzer-internal wording
    must never be spoken back to the candidate as if they said it: a
    skipped-section detail like 'action seen while situation not seen'
    became 'You mentioned action seen while situation not seen' in a live
    rep (2026-07-11). Only candidate-verbatim details pass through."""
    detail = candidate.detail or ""
    m = _SECTION_SKIP_RE.fullmatch(detail)
    if m:
        return (f"the candidate jumped to the {m.group(1)} without ever "
                f"describing the {m.group(2)}")
    return detail


def _llm_rewrite(seed: str, candidate: ProbeCandidate, state: AnswerState) -> str | None:
    try:
        from src.llm.client import complete
        result = complete("probe_rewrite", {
            "seed": seed,
            "probe_type": candidate.probe_type.value,
            "offending_phrase": _trigger_context(candidate),
            "recent_context": _recent_context(state),
            "intensity": str(state.persona.intensity),
        }, json_schema=None)
        text = (result.text or "").strip().strip('"')
        # Guard: a probe is at most 2 sentences (spec 5.4 hard rule).
        if text and text.count(".") + text.count("?") <= 3 and len(text) < 300:
            return text
    except Exception:
        pass
    return None


def select_probe(candidate: ProbeCandidate, state: AnswerState,
                 rng: random.Random | None = None, use_llm: bool = True) -> str:
    rng = rng or random.Random()

    if candidate.detail == "reask_harder":
        return REASK_HARDER.get(candidate.probe_type, REASK_HARDER_DEFAULT)

    cached = _speculative.pop((state.question.id, candidate.probe_type.value), None)
    if cached:
        return cached

    seed = _seed(candidate.probe_type, state, rng)

    # NUDGE stays non-leading and template-only: never let a rewrite add
    # content hints (spec 3.5). REDIRECT_WRAP stays instant.
    if candidate.probe_type in (ProbeType.NUDGE, ProbeType.REDIRECT_WRAP):
        return seed

    if use_llm:
        rewritten = _llm_rewrite(seed, candidate, state)
        if rewritten:
            return rewritten
    return seed


def pregenerate(candidate: ProbeCandidate, state: AnswerState) -> None:
    """Speculative generation: fill the cache so firing costs ~0 LLM latency."""
    key = (state.question.id, candidate.probe_type.value)
    if key in _speculative:
        return
    seed = _seed(candidate.probe_type, state, random.Random())
    text = _llm_rewrite(seed, candidate, state)
    if text:
        _speculative[key] = text
