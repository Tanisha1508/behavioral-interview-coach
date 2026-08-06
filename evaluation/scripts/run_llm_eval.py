"""Runs the 101-item golden set through the real grading pipeline
(src/grading/grader.grade) with real LLM calls. No source file is modified --
src.grading.grader.complete and src.llm.client._call_gemini are monkeypatched
at the module level purely to observe provider, latency, attempt count, and
raw pre-repair JSON; grade() runs its exact production code path.

Writes evaluation/results/llm_eval_results.json.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import src.grading.grader as grader_mod  # noqa: E402
import src.llm.client as client_mod  # noqa: E402
from src.grading.grader import DIMENSIONS, LEVELS, Timings  # noqa: E402
from src.engine.state import load_round_profile  # noqa: E402
from src.llm.client import DailyCapReached, LLMUnavailable  # noqa: E402
from evaluation.scripts.generate_golden_dataset import build_full_dataset  # noqa: E402

ROUND = load_round_profile(ROOT / "config" / "rounds" / "pm.yaml")
RESULTS_PATH = Path(__file__).resolve().parents[1] / "results" / "llm_eval_results.json"

call_log: list[dict] = []
gemini_attempt_timestamps: list[float] = []

_original_complete = grader_mod.complete
_original_call_gemini = client_mod._call_gemini


def _counted_call_gemini(*args, **kwargs):
    gemini_attempt_timestamps.append(time.perf_counter())
    return _original_call_gemini(*args, **kwargs)


client_mod._call_gemini = _counted_call_gemini  # instrumentation only


def _strict_schema_ok(raw) -> bool:
    if not isinstance(raw, dict):
        return False
    dims = raw.get("dimensions")
    if not isinstance(dims, dict):
        return False
    for d in DIMENSIONS:
        entry = dims.get(d)
        if not isinstance(entry, dict):
            return False
        if entry.get("level") not in LEVELS:
            return False
        if not isinstance(entry.get("evidence", []), list):
            return False
        if not isinstance(entry.get("note", ""), str):
            return False
    return isinstance(raw.get("spoken_summary"), list)


def _instrumented_complete(prompt_id, vars, json_schema=None):
    t0 = time.perf_counter()
    entry = {"prompt_id": prompt_id}
    try:
        result = _original_complete(prompt_id, vars, json_schema=json_schema)
        t1 = time.perf_counter()
        entry["latency_s"] = t1 - t0
        entry["provider"] = result.provider
        entry["failovers"] = result.failovers
        entry["success"] = True
        entry["schema_strict_valid"] = (
            _strict_schema_ok(result.parsed) if json_schema is not None else None)
        entry["gemini_attempts"] = sum(
            1 for t in gemini_attempt_timestamps if t0 <= t <= t1)
        call_log.append(entry)
        return result
    except Exception as exc:
        t1 = time.perf_counter()
        entry["latency_s"] = t1 - t0
        entry["success"] = False
        entry["error_type"] = type(exc).__name__
        entry["error"] = str(exc)[:300]
        entry["gemini_attempts"] = sum(
            1 for t in gemini_attempt_timestamps if t0 <= t <= t1)
        call_log.append(entry)
        raise


grader_mod.complete = _instrumented_complete  # instrumentation only, no logic change


def grade_item(item) -> dict:
    t0 = time.perf_counter()
    result = {"id": item.id, "category": item.category,
              "duration_s": item.duration_s, "word_count": item.word_count}
    try:
        scores = grader_mod.grade(item.rendered_transcript, [],
                                  Timings(duration_s=item.duration_s), ROUND)
        result["status"] = "success"
        result["dimensions"] = {d: scores.dimensions[d].level for d in DIMENSIONS}
        result["evidence_violations"] = list(scores.evidence_violations)
        result["evidence_count"] = sum(
            len(scores.dimensions[d].evidence) for d in DIMENSIONS)
    except DailyCapReached as exc:
        result["status"] = "daily_cap_reached"
        result["error"] = str(exc)
    except LLMUnavailable as exc:
        result["status"] = "llm_unavailable"
        result["error"] = str(exc)
    except Exception as exc:
        result["status"] = "other_error"
        result["error"] = f"{type(exc).__name__}: {exc}"
    result["wall_s"] = time.perf_counter() - t0
    return result


def main() -> None:
    items = build_full_dataset()
    print(f"golden set: {len(items)} items", flush=True)

    partial_path = RESULTS_PATH.parent / "llm_eval_partial.jsonl"
    RESULTS_PATH.parent.mkdir(exist_ok=True)

    print("running grading pass (real LLM calls)...", flush=True)
    grading_results = []
    with open(partial_path, "w") as pf:
        for i, item in enumerate(items, 1):
            r = grade_item(item)
            grading_results.append(r)
            pf.write(json.dumps(r) + "\n")
            pf.flush()
            print(f"  [{i}/{len(items)}] {item.id:16s} ({item.category:14s}) "
                  f"-> {r['status']} in {r['wall_s']:.2f}s", flush=True)

    by_cat: dict[str, list] = {}
    for it in items:
        by_cat.setdefault(it.category, []).append(it)
    consistency_items = [it for lst in by_cat.values() for it in lst[:2]]

    print(f"\nrunning consistency repeats on {len(consistency_items)} items "
          "(2 extra grade() calls each)...")
    consistency_results: dict[str, dict] = {}
    for item in consistency_items:
        first = next((r for r in grading_results if r["id"] == item.id), None)
        runs = [first["dimensions"]] if first and first["status"] == "success" else []
        for rep in range(2):
            r = grade_item(item)
            print(f"  repeat {rep + 1}/2 for {item.id} -> {r['status']}")
            if r["status"] == "success":
                runs.append(r["dimensions"])
        consistency_results[item.id] = {"category": item.category, "runs": runs}

    out = {
        "n_items": len(items),
        "grading_results": grading_results,
        "consistency_results": consistency_results,
        "call_log": call_log,
    }
    RESULTS_PATH.parent.mkdir(exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
