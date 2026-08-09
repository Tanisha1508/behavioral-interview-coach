"""Runs the golden set through the real pipeline (no source files modified):
  - probe/decision engine (src/engine): reused via evals.probe_cases.cases,
    no LLM, run on all 50 items.
  - grading (src/grading/grader.grade): real LLM calls, instrumented via a
    module-level monkeypatch of grader.complete so provider/latency/schema-
    validity are captured without touching src/llm/client.py or grader.py.

Writes evals/golden/results.json. Re-running appends nothing; it overwrites.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import src.grading.grader as grader_mod
from src.grading.grader import DIMENSIONS, LEVELS, Timings
from src.engine.state import load_round_profile
from src.llm.client import DailyCapReached, LLMUnavailable
from evals.golden.dataset import build_golden_set
from evals.probe_cases.cases import Script, run_case

ROOT = Path(__file__).resolve().parents[2]
ROUND = load_round_profile(ROOT / "config" / "rounds" / "pm.yaml")
RESULTS_PATH = Path(__file__).resolve().parent / "results.json"

call_log: list[dict] = []
_original_complete = grader_mod.complete


def _strict_schema_ok(raw) -> bool:
    """Pre-repair schema check: does the raw LLM JSON already conform,
    before grade()'s own null/mistype sanitization runs?"""
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


def _instrumented_complete(prompt_id, vars, json_schema=None, **kwargs):
    t0 = time.perf_counter()
    entry = {"prompt_id": prompt_id}
    try:
        result = _original_complete(prompt_id, vars, json_schema=json_schema,
                                    **kwargs)
        entry["latency_s"] = time.perf_counter() - t0
        entry["provider"] = result.provider
        entry["failovers"] = result.failovers
        entry["success"] = True
        entry["schema_strict_valid"] = (
            _strict_schema_ok(result.parsed) if json_schema is not None else None)
        call_log.append(entry)
        return result
    except Exception as exc:
        entry["latency_s"] = time.perf_counter() - t0
        entry["success"] = False
        entry["error_type"] = type(exc).__name__
        entry["error"] = str(exc)[:300]
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
    items = build_golden_set()
    print(f"golden set: {len(items)} items")

    print("running probe/decision engine (no LLM, all 50 items)...")
    probe_results = [probe_check(it) for it in items]

    print("running grading pass (real LLM calls, 50 items)...")
    grading_results = []
    for i, item in enumerate(items, 1):
        r = grade_item(item)
        grading_results.append(r)
        print(f"  [{i}/{len(items)}] {item.id:16s} ({item.category:10s}) "
              f"-> {r['status']} in {r['wall_s']:.2f}s")

    by_cat: dict[str, list] = {}
    for it in items:
        by_cat.setdefault(it.category, []).append(it)
    consistency_items = [it for lst in by_cat.values() for it in lst[:2]]

    print(f"\nrunning consistency repeats on {len(consistency_items)} items "
          "(2 extra grade() calls each, reusing the first run above)...")
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
        "probe_results": probe_results,
        "grading_results": grading_results,
        "consistency_results": consistency_results,
        "call_log": call_log,
    }
    RESULTS_PATH.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
