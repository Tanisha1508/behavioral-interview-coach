"""Runs the golden set through the real probe/decision engine
(src/engine/decision.py, src/engine/analyzers.py) -- no LLM, deterministic.
Reuses evals/probe_cases/cases.Script and run_case exactly as the existing
product-level eval does, applied to all 101 golden items instead of the
original 5 scripted cases.

This doubles as the "follow-up question" evaluation (Part 5): whether the
engine decides to ask a follow-up at all is the measurable, well-defined
part of "follow-up question generation" in this codebase (the follow-up's
exact wording is template-based, not independently gradable without a
second LLM judge, which would itself need ground truth this repo doesn't
have -- see the report for that reasoning).

Writes evaluation/results/probe_eval_results.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from evaluation.scripts.generate_golden_dataset import build_full_dataset  # noqa: E402
from evals.probe_cases.cases import Script, run_case  # noqa: E402

RESULTS_PATH = Path(__file__).resolve().parents[1] / "results" / "probe_eval_results.json"

# Author-intended ground truth for "should the rule engine flag this answer"
# -- only defined where the intent is unambiguous by design (see report).
EXPECTED_TRIGGER = {
    "excellent": False,
    "weak": True,
    "star_explicit": False,
    "off_topic": False,
    # deliberately excluded (ambiguous / undefined by the current detector
    # set): average, non_star, incomplete, fabricated
}


def probe_check(item) -> dict:
    script = Script(name=item.id, segments=item.segments,
                    end_s=max(int(item.duration_s) + 2, 2))
    r = run_case(script, profile="pm")
    fired_types = sorted({t.value for _, t in r.fired})
    queued_types = sorted({t.value for t in r.queued})
    return {"id": item.id, "category": item.category,
            "fired": fired_types, "queued": queued_types,
            "triggered_any": bool(r.fired or r.queued)}


def main() -> None:
    items = build_full_dataset()
    print(f"golden set: {len(items)} items")
    results = [probe_check(it) for it in items]

    # Precision / Recall / F1 on the clean-label subset only.
    labeled = [r for r in results if r["category"] in EXPECTED_TRIGGER]
    tp = sum(1 for r in labeled if EXPECTED_TRIGGER[r["category"]] and r["triggered_any"])
    fp = sum(1 for r in labeled if not EXPECTED_TRIGGER[r["category"]] and r["triggered_any"])
    fn = sum(1 for r in labeled if EXPECTED_TRIGGER[r["category"]] and not r["triggered_any"])
    tn = sum(1 for r in labeled if not EXPECTED_TRIGGER[r["category"]] and not r["triggered_any"])
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * precision * recall / (precision + recall)
          if precision is not None and recall is not None and (precision + recall) > 0
          else None)

    print(f"\nclean-label subset: n={len(labeled)} "
          f"(excellent/weak/star_explicit/off_topic)")
    print(f"  TP={tp} FP={fp} FN={fn} TN={tn}")
    print(f"  precision={precision} recall={recall} f1={f1}")

    out = {
        "n_items": len(items),
        "probe_results": results,
        "expected_trigger_map": EXPECTED_TRIGGER,
        "clean_label_n": len(labeled),
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "precision": precision, "recall": recall, "f1": f1,
    }
    RESULTS_PATH.parent.mkdir(exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
