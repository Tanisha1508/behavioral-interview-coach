"""Grading engine (spec 5.2, 5.4). Consumes the final transcript and the
probe log; never shares code with the probe engine. Auto-rules run in code
so the LLM cannot drift on them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from src.engine.analyzers import we_ratio as compute_we_ratio
from src.engine.state import ProbeRecord, ProbeType, RoundProfile
from src.llm.client import complete

ROOT = Path(__file__).resolve().parents[2]
RUBRIC_PATH = ROOT / "config" / "rubric.yaml"

DIMENSIONS = ["structure", "specificity", "i_vs_we", "quantification",
              "length", "reflection"]
LEVELS = ["Solid", "NeedsWork", "Gap"]


@dataclass
class Timings:
    duration_s: float


class DimensionScore(BaseModel):
    level: str
    evidence: list[str] = Field(default_factory=list)
    note: str = ""


class RubricScores(BaseModel):
    dimensions: dict[str, DimensionScore]
    spoken_summary: list[str]
    evidence_violations: list[str] = Field(default_factory=list)


def load_rubric() -> dict:
    return yaml.safe_load(RUBRIC_PATH.read_text())


def length_level(duration_s: float, band: tuple[int, int]) -> str:
    low, high = band
    if low <= duration_s <= high:
        return "Solid"
    if duration_s < low:
        return "NeedsWork" if duration_s >= low * 0.75 else "Gap"
    return "NeedsWork" if duration_s <= high * 1.25 else "Gap"


def _candidate_text(transcript: str) -> str:
    """Candidate speech as one continuous string. STT emits the answer as
    timestamped fragments; a verbatim quote often spans two fragments, so
    matching against raw transcript lines drops legitimate evidence."""
    parts = []
    for line in transcript.splitlines():
        _, sep, rest = line.partition("CANDIDATE:")
        if sep:
            parts.append(rest.strip())
    return " ".join(" ".join(parts).split())


def _verify_evidence(scores: dict, transcript: str) -> list[str]:
    violations = []
    haystacks = (" ".join(transcript.split()), _candidate_text(transcript))
    for dim, entry in scores.items():
        kept = []
        for quote in entry.get("evidence", []):
            needle = " ".join(str(quote).split())
            if any(needle in h for h in haystacks):
                kept.append(quote)
            else:
                violations.append(f"{dim}: non-verbatim quote dropped: {quote!r}")
        entry["evidence"] = kept
    return violations


def _apply_auto_rules(scores: dict, probes: list[ProbeRecord],
                      grader_notes: list[str], transcript: str,
                      timings: Timings, round: RoundProfile) -> None:
    # Length is computed, never judged (rubric auto-rule).
    lvl = length_level(timings.duration_s, round.length_band_s)
    scores.setdefault("length", {})["level"] = lvl

    # we_ratio above threshold, unresolved after an OWNERSHIP probe -> Gap.
    ownership_fired = any(p.probe_type == ProbeType.OWNERSHIP for p in probes)
    final_ratio = compute_we_ratio(transcript)
    if ownership_fired and final_ratio > round.we_ratio_threshold:
        scores["i_vs_we"]["level"] = "Gap"
        scores["i_vs_we"]["note"] = (
            f"we-ratio {final_ratio:.2f} stayed above the "
            f"{round.we_ratio_threshold} threshold after an ownership probe. "
            + scores["i_vs_we"].get("note", ""))

    # Engine-forced levels (double deflection).
    for note in grader_notes:
        if "force Specificity to Gap" in note:
            scores["specificity"]["level"] = "Gap"


def grade(transcript: str, probes: list[ProbeRecord], timings: Timings,
          round: RoundProfile, grader_notes: list[str] | None = None) -> RubricScores:
    grader_notes = grader_notes or []
    rubric = load_rubric()

    probe_history = "; ".join(
        f"{p.probe_type.value} at {p.fired_at_ms // 1000}s "
        f"({'interrupt' if p.interrupted else 'at pause'}): {p.text}"
        for p in probes) or "none"

    band = round.length_band_s
    vars = {
        "transcript": transcript,
        "probe_history": probe_history,
        "grader_notes": "; ".join(grader_notes) or "none",
        "duration_s": f"{timings.duration_s:.0f}",
        "length_band_low": str(band[0]),
        "length_band_high": str(band[1]),
        "profile_id": round.profile_id,
        "we_ratio_threshold": str(round.we_ratio_threshold),
        "we_ratio": f"{compute_we_ratio(transcript):.2f}",
        "rubric": yaml.dump(rubric["dimensions"], sort_keys=False),
        "auto_rules": yaml.dump(rubric["auto_rules"], sort_keys=False),
    }

    result = complete("grading_system", vars, json_schema={"type": "object"})
    raw = result.parsed
    scores = raw["dimensions"]

    for dim in DIMENSIONS:
        scores.setdefault(dim, {"level": "NeedsWork", "evidence": [],
                                "note": "grader returned no entry"})
        if scores[dim].get("level") not in LEVELS:
            scores[dim]["level"] = "NeedsWork"
        # Models under failover return null or mistyped fields inside a
        # dimension; one null note crashed scoring and the user heard a
        # false "quota exhausted" (live 2026-07-13, TEST-LOG finding 4).
        if not isinstance(scores[dim].get("note"), str):
            scores[dim]["note"] = ""
        evidence = scores[dim].get("evidence")
        scores[dim]["evidence"] = ([str(e) for e in evidence if e is not None]
                                   if isinstance(evidence, list) else [])

    violations = _verify_evidence(scores, transcript)
    _apply_auto_rules(scores, probes, grader_notes, transcript, timings, round)

    return RubricScores(
        dimensions={d: DimensionScore(**scores[d]) for d in DIMENSIONS},
        spoken_summary=[str(s) for s in raw.get("spoken_summary", [])][:1],
        evidence_violations=violations,
    )
