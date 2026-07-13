"""Grading consistency eval (spec Section 6): grade the same recorded
answer 5 times with fresh LLM calls. Pass: at least 5 of 6 dimensions have
the same level in 4+ of 5 runs, and no dimension ever spans Solid to Gap.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from src.engine.state import ProbeRecord, ProbeType, load_round_profile
from src.grading.grader import DIMENSIONS, Timings, grade

ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPT = ROOT / "evals" / "fixtures" / "transcript_pm.txt"
DURATION_S = 125.0  # candidate speaking span in the fixture

PROBES = [ProbeRecord(
    probe_type=ProbeType.SPECIFICITY, fired_at_ms=74_100,
    trigger="aligned stakeholders",
    text="You said you aligned stakeholders. What exactly did you say to get growth on board?",
    interrupted=False)]


def run(n: int = 5) -> dict:
    round_profile = load_round_profile(ROOT / "config" / "rounds" / "pm.yaml")
    transcript = TRANSCRIPT.read_text()

    runs = []
    for i in range(n):
        scores = grade(transcript, PROBES, Timings(duration_s=DURATION_S),
                       round_profile)
        runs.append({d: scores.dimensions[d].level for d in DIMENSIONS})
        print(f"  run {i + 1}: " + ", ".join(
            f"{d}={runs[-1][d]}" for d in DIMENSIONS))

    stable_dims = 0
    span_violation = False
    per_dim = {}
    for d in DIMENSIONS:
        levels = [r[d] for r in runs]
        top, count = Counter(levels).most_common(1)[0]
        per_dim[d] = {"modal": top, "agreement": count}
        if count >= 4:
            stable_dims += 1
        if "Solid" in levels and "Gap" in levels:
            span_violation = True

    passed = stable_dims >= 5 and not span_violation
    return {"runs": runs, "per_dim": per_dim, "stable_dims": stable_dims,
            "span_violation": span_violation, "passed": passed}


if __name__ == "__main__":
    result = run()
    print(f"\nstable dimensions (4+/5 agreement): {result['stable_dims']}/6 (need 5)")
    print(f"Solid-to-Gap span violation: {result['span_violation']}")
    print("PASS" if result["passed"] else "FAIL")
