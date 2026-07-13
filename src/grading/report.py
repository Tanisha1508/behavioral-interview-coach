"""Feedback rendering (spec 5.2): written card + spoken script, plus the
simulation debrief (spec 2.2: per-question grades, cross-answer patterns,
missed ammo across the set)."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.grading.ammo import AmmoItem
from src.grading.grader import DIMENSIONS, RubricScores

LEVEL_MARKS = {"Solid": "[SOLID]", "NeedsWork": "[NEEDS WORK]", "Gap": "[GAP]"}


def render_card(scores: RubricScores, ammo: list[AmmoItem]) -> str:
    lines = ["", "=" * 62, "ANSWER GRADE", "=" * 62]
    for dim in DIMENSIONS:
        s = scores.dimensions[dim]
        lines.append(f"{dim.replace('_', ' ').title():<16} {LEVEL_MARKS[s.level]}")
        for quote in s.evidence[:2]:
            lines.append(f'    evidence: "{quote}"')
        if s.note:
            lines.append(f"    fix: {s.note}")
    if ammo:
        lines += ["-" * 62, "MISSED AMMO (from your own docs):"]
        for item in ammo:
            lines.append(f'  - [{item.doc_source}] "{item.fact}"')
            if item.relevance:
                lines.append(f"      {item.relevance}")
    if scores.evidence_violations:
        lines += ["-" * 62,
                  f"({len(scores.evidence_violations)} non-verbatim quotes "
                  "dropped by the evidence check)"]
    lines.append("=" * 62)
    return "\n".join(lines)


def spoken_script(scores: RubricScores, ammo: list[AmmoItem]) -> str:
    """The ~10 second spoken feedback after a Drill answer. The card on
    screen carries the full breakdown; speech gives only the one fix. The
    [:1] cap holds even when the LLM ignores the one-line instruction
    (the Groq failover routinely does)."""
    lines = ["Your score card is on the screen."]
    lines += list(scores.spoken_summary)[:1]
    if ammo:
        lines.append(
            f"Also, {len(ammo)} thing{'s' if len(ammo) > 1 else ''} from your "
            "own docs never came up. The card has the list.")
    return " ".join(lines)


# ---------- simulation debrief ----------

@dataclass
class RepResult:
    """One simulation answer, banked for the end-of-session debrief.
    scores stays None when grading failed (quota); the debrief says so
    instead of dropping the question silently."""
    question: str
    duration_s: float
    transcript: str = ""
    scores: RubricScores | None = None
    ammo: list[AmmoItem] = field(default_factory=list)


# Cross-answer patterns speak the dimension's failure mode, not its name.
_PATTERN_PHRASES = {
    "structure": "hard to follow",
    "specificity": "short on specifics",
    "i_vs_we": "we-heavy",
    "quantification": "missing numbers",
    "length": "outside the length band",
    "reflection": "light on reflection",
}


def debrief_patterns(reps: list[RepResult]) -> list[str]:
    """Cross-answer patterns as exact counts computed in code, never LLM
    impressions: a dimension weak in at least two answers and at least
    half of the graded set is a pattern."""
    graded = [r.scores for r in reps if r.scores is not None]
    n = len(graded)
    if n < 2:
        return []
    patterns = []
    for dim in DIMENSIONS:
        weak = sum(1 for s in graded if s.dimensions[dim].level != "Solid")
        if weak >= 2 and weak * 2 >= n:
            patterns.append(f"{_PATTERN_PHRASES[dim]} in {weak} of {n} "
                            "answers")
    return patterns


def combined_ammo(reps: list[RepResult]) -> list[AmmoItem]:
    """Missed ammo across the whole set, deduplicated on the fact."""
    seen: set[str] = set()
    out: list[AmmoItem] = []
    for rep in reps:
        for item in rep.ammo:
            key = " ".join(item.fact.lower().split())
            if key not in seen:
                seen.add(key)
                out.append(item)
    return out


def render_debrief(reps: list[RepResult], patterns: list[str],
                   ammo: list[AmmoItem], dropped: int) -> str:
    lines = ["", "=" * 62, "SESSION DEBRIEF", "=" * 62]
    for i, rep in enumerate(reps, start=1):
        lines.append(f"Q{i} ({rep.duration_s:.0f}s): {rep.question}")
        if rep.scores is None:
            lines.append("    not scored (grading unavailable)")
            continue
        lines.append("    " + "  ".join(
            f"{d.replace('_', ' ')} {LEVEL_MARKS[rep.scores.dimensions[d].level]}"
            for d in DIMENSIONS))
    if patterns:
        lines += ["-" * 62, "PATTERNS ACROSS ANSWERS:"]
        lines += [f"  - {p}" for p in patterns]
    if ammo:
        lines += ["-" * 62, "MISSED AMMO ACROSS THE SET (from your own docs):"]
        for item in ammo:
            lines.append(f'  - [{item.doc_source}] "{item.fact}"')
    if dropped:
        lines += ["-" * 62,
                  f"({dropped} planned question{'s' if dropped > 1 else ''} "
                  "dropped: answers ran long)"]
    lines.append("=" * 62)
    return "\n".join(lines)


def spoken_debrief(reps: list[RepResult], patterns: list[str],
                   ammo: list[AmmoItem], dropped: int) -> str:
    """The short spoken close of a simulation. The screen carries the full
    breakdown; speech names the answer count and the first pattern."""
    n = len(reps)
    lines = [f"That's the session. You answered {n} "
             f"question{'s' if n != 1 else ''}; "
             "your full debrief is on the screen."]
    if dropped:
        lines.append(f"I dropped {dropped} planned "
                     f"question{'s' if dropped > 1 else ''} because your "
                     "answers ran long.")
    ungraded = sum(1 for r in reps if r.scores is None)
    if ungraded:
        lines.append(f"I could not score {ungraded} of them, my language "
                     "model quota ran short.")
    if patterns:
        lines.append(f"The pattern to fix first: you were {patterns[0]}.")
    if ammo:
        lines.append(f"And {len(ammo)} fact{'s' if len(ammo) > 1 else ''} "
                     "from your own docs never came up across the whole "
                     "set.")
    lines.append("Take your time with the debrief, then say end to finish.")
    return " ".join(lines)
