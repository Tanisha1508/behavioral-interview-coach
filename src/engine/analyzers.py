"""Signal analyzers (spec 3.2). Local rules only, no LLM, hot-path safe.

Transcript partials carry no word timestamps, so trailing time windows are
approximated by word count at ~2.5 words per second (see DECISIONS.md).
"""

from __future__ import annotations

import re

from src.engine.state import (
    HSCARR_SECTIONS,
    RoundProfile,
    SectionStatus,
    SignalSet,
)

WORDS_PER_SECOND = 2.5

VAGUE_PHRASES = [
    "aligned stakeholders",
    "drove consensus",
    "worked closely",
    "took ownership",
    "communicated effectively",
    "collaborated cross-functionally",
]

WE_TOKENS = {"we", "our", "ours"}
WE_PHRASES = ["the team"]
I_TOKENS = {"i", "my", "mine"}

NUMBER_WORDS = {
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "twenty", "thirty", "forty", "fifty", "hundred",
    "thousand", "million", "billion", "percent", "half", "double", "triple",
}

SECTION_MARKERS: dict[str, list[str]] = {
    "situation": [
        "the situation was", "at the time", "i was working", "in my role",
        "for context", "last year", "a few months ago", "my team was",
    ],
    "complication": [
        "the challenge", "the problem was", "but then", "the complication",
        "it got worse", "the hard part", "the issue was", "we hit a wall",
    ],
    "action": [
        "so what i did", "so i ", "i decided", "my first step", "i started by",
        "what i did was", "i proposed", "i went to", "i wrote", "i built",
    ],
    "resolution": [
        "as a result", "in the end", "the outcome", "we ended up",
        "the result was", "ultimately", "it shipped", "we launched",
    ],
    "reflection": [
        "what i learned", "looking back", "i realized", "if i did it again",
        "in hindsight", "my takeaway", "i would do differently",
    ],
}

# Sections whose absence counts as a skip when a later one appears.
REQUIRED_ORDER = ["situation", "action", "resolution"]

_WORD_RE = re.compile(r"[a-zA-Z']+|\d[\d,.%]*")
_NUMERIC_RE = re.compile(r"\d")
_CONCRETE_RE = re.compile(r'\d|"|“|’s\b')


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _trailing_words(text: str, seconds: int) -> str:
    words = text.split()
    n = int(seconds * WORDS_PER_SECOND)
    return " ".join(words[-n:])


def _has_concrete_noun(window: str) -> bool:
    """Name, artifact, number, or quoted dialogue in the window."""
    if _CONCRETE_RE.search(window):
        return True
    # Capitalized token mid-sentence reads as a proper noun in transcripts.
    # Pronoun "I" and sentence-initial words after punctuation do not count.
    prev = ""
    for token in window.split()[1:]:
        clean = token.strip(",.;:!?")
        if (clean[:1].isupper() and clean not in ("I", "I'm", "I'd", "I'll", "I've")
                and not prev.endswith((".", "?", "!"))):
            return True
        prev = token
    return any(w in NUMBER_WORDS for w in _words(window))


def detect_vagueness(partial: str) -> tuple[bool, str | None]:
    lower = partial.lower()
    for phrase in VAGUE_PHRASES:
        idx = lower.find(phrase)
        if idx == -1:
            continue
        after = partial[idx + len(phrase):]
        window = " ".join(after.split()[:15])
        if not _has_concrete_noun(window):
            return True, phrase
    return False, None


def we_ratio(partial: str) -> float:
    recent = _trailing_words(partial, 60)
    words = _words(recent)
    we_count = sum(1 for w in words if w in WE_TOKENS)
    lower = recent.lower()
    for ph in WE_PHRASES:
        we_count += lower.count(ph)
    i_count = sum(1 for w in words if w in I_TOKENS)
    if we_count + i_count == 0:
        return 0.0
    return we_count / (we_count + i_count)


def track_hscarr(partial: str, progress: dict[str, SectionStatus]) -> dict[str, SectionStatus]:
    """Mark sections SEEN from discourse markers. Never unmarks."""
    updated = dict(progress)
    if partial.strip():
        updated["hook"] = SectionStatus.SEEN
    lower = partial.lower()
    for section, markers in SECTION_MARKERS.items():
        if updated.get(section) == SectionStatus.SEEN:
            continue
        if any(m in lower for m in markers):
            updated[section] = SectionStatus.SEEN
    return updated


def detect_skip(progress: dict[str, SectionStatus]) -> tuple[bool, str | None]:
    for later_i in range(len(REQUIRED_ORDER) - 1, 0, -1):
        later = REQUIRED_ORDER[later_i]
        if progress.get(later) != SectionStatus.SEEN:
            continue
        for earlier in REQUIRED_ORDER[:later_i]:
            if progress.get(earlier) != SectionStatus.SEEN:
                return True, f"{later} seen while {earlier} not seen"
    return False, None


def missing_numbers(partial: str, progress: dict[str, SectionStatus]) -> bool:
    active = (
        progress.get("action") == SectionStatus.SEEN
        or progress.get("resolution") == SectionStatus.SEEN
    )
    if not active:
        return False
    # Whole answer, not a trailing window: one quantified claim satisfies
    # the dimension for the whole story. The trailing window re-flagged
    # answers whose numbers came early (live rep 2026-07-10: "six of
    # forty respondents" at 40s, probe still fired at 83s).
    if _NUMERIC_RE.search(partial):
        return False
    return not any(w in NUMBER_WORDS for w in _words(partial))


_NO_RECALL_PHRASES = (
    "don't remember", "do not remember", "can't remember", "cannot remember",
    "don't recall", "do not recall", "can't recall", "cannot recall",
    "don't know the details", "no idea",
)


def check_deflection(pre_probe: str, reply: str, probe_text: str) -> bool:
    """Rehearsed non-answer after a probe (spec 3.2 REHEARSED_NON_ANSWER)."""
    reply_recent = set(_words(_trailing_words(reply, 30)))
    if not reply_recent:
        return False
    # A short explicit no-recall reply is a deflection even when it parrots
    # the probe's own words ("can you be more specific" answered with "I
    # don't recall the specifics"), which defeats the shared-content check
    # below (live miss 2026-07-12). Long replies stay exempt: "I don't
    # remember exactly, but..." followed by substance is engagement.
    if (len(reply.split()) <= 30
            and any(p in reply.lower() for p in _NO_RECALL_PHRASES)):
        return True
    pre_words = set(_words(pre_probe))
    overlap = len(reply_recent & pre_words) / len(reply_recent)
    if overlap <= 0.70:
        return False
    stop = {"what", "how", "why", "when", "who", "where", "the", "a", "you",
            "your", "did", "do", "was", "were", "me", "i", "to", "of", "in",
            "and", "that", "it", "on", "say", "tell"}
    probe_content = set(_words(probe_text)) - stop
    return not (probe_content & reply_recent)


def analyze(partial: str, clock_ms: int, round: RoundProfile,
            hscarr_progress: dict[str, SectionStatus] | None = None
            ) -> tuple[SignalSet, dict[str, SectionStatus]]:
    """Spec 5.2 signature plus the caller's HSCARR progress, which lives in
    AnswerState so SEEN marks persist across partials. Returns the signals
    and the updated progress; stalled/deflected are set by the decision loop
    because floor tracking and probe history live in AnswerState."""
    progress = track_hscarr(partial, hscarr_progress or
                            {s: SectionStatus.NOT_SEEN for s in HSCARR_SECTIONS})

    signals = SignalSet()
    signals.vague_claim, signals.vague_phrase = detect_vagueness(partial)
    signals.we_ratio = we_ratio(partial)
    signals.we_flag = (
        signals.we_ratio > round.we_ratio_threshold and clock_ms > 30_000
    )
    signals.missing_numbers = missing_numbers(partial, progress)
    signals.skipped_section, signals.skipped_detail = detect_skip(progress)

    soft_ms = round.time_budget_s * 1000
    resolution_missing = progress.get("resolution") != SectionStatus.SEEN
    signals.rambling = clock_ms > soft_ms and resolution_missing
    signals.overrun = clock_ms > soft_ms + 30_000

    return signals, progress
