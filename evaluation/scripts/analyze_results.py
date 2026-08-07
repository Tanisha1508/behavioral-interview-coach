"""Loads llm_eval_results.json, probe_eval_results.json, and
voice_eval_results.json, computes every metric reported in
EVALUATION_REPORT.md, and writes evaluation/results/metrics_summary.json.

Pure analysis, no LLM/API calls -- safe to re-run any number of times.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from src.analytics import amplitude  # noqa: E402

load_dotenv(ROOT / ".env")

RESULTS_DIR = Path(__file__).resolve().parents[1] / "results"
DIMS = ["structure", "specificity", "i_vs_we", "quantification", "length", "reflection"]
LEVEL_SCORE = {"Gap": 0, "NeedsWork": 1, "Solid": 2}
CATEGORY_RANK = {"weak": 1, "average": 2, "excellent": 3}  # ordinal, for correlation only


def pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denx = sum((x - mx) ** 2 for x in xs) ** 0.5
    deny = sum((y - my) ** 2 for y in ys) ** 0.5
    if denx == 0 or deny == 0:
        return None
    return num / (denx * deny)


def cohens_kappa_from_pairs(pairs: list[tuple[str, str]]) -> float | None:
    """Unweighted Cohen's Kappa over (run_a_level, run_b_level) pairs."""
    if not pairs:
        return None
    labels = sorted({p[0] for p in pairs} | {p[1] for p in pairs})
    n = len(pairs)
    po = sum(1 for a, b in pairs if a == b) / n
    a_counts = Counter(p[0] for p in pairs)
    b_counts = Counter(p[1] for p in pairs)
    pe = sum((a_counts.get(l, 0) / n) * (b_counts.get(l, 0) / n) for l in labels)
    if pe == 1:
        return 1.0
    return (po - pe) / (1 - pe)


def main() -> None:
    llm = json.loads((RESULTS_DIR / "llm_eval_results.json").read_text())
    probe = json.loads((RESULTS_DIR / "probe_eval_results.json").read_text())
    voice = json.loads((RESULTS_DIR / "voice_eval_results.json").read_text())

    grading = llm["grading_results"]
    calls = llm["call_log"]
    consistency = llm["consistency_results"]

    summary: dict = {}

    # ---- reliability / success ----
    status_counts = Counter(g["status"] for g in grading)
    summary["grading_success_rate"] = {
        "value": status_counts.get("success", 0) / len(grading),
        "n": len(grading), "success": status_counts.get("success", 0),
        "statuses": dict(status_counts),
    }
    call_success = sum(1 for c in calls if c.get("success"))
    summary["llm_call_success_rate"] = {
        "value": call_success / len(calls), "n": len(calls), "success": call_success,
    }

    # ---- schema validity ----
    schema_flags = [c["schema_strict_valid"] for c in calls
                    if c.get("success") and c.get("schema_strict_valid") is not None]
    summary["json_schema_validity_pct"] = {
        "value": sum(schema_flags) / len(schema_flags) if schema_flags else None,
        "n": len(schema_flags), "valid": sum(schema_flags),
    }

    # ---- fallback / retry ----
    providers = Counter(c.get("provider") for c in calls if c.get("success"))
    non_primary = sum(1 for c in calls if c.get("success") and c.get("provider") != "gemini")
    summary["fallback_invocation_rate"] = {
        "value": non_primary / len(calls), "n": len(calls),
        "non_primary_calls": non_primary, "provider_distribution": dict(providers),
    }
    attempts = [c.get("gemini_attempts", 0) for c in calls if c.get("success")]
    multi_attempt = sum(1 for a in attempts if a and a > 1)
    summary["retry_rate"] = {
        "value": multi_attempt / len(attempts) if attempts else None,
        "n": len(attempts), "calls_with_gt1_gemini_attempt": multi_attempt,
        "mean_gemini_attempts_per_call": statistics.mean(attempts) if attempts else None,
        "note": ("counts total src.llm.client._call_gemini invocations per "
                "complete() call -- this spans both same-tier retry-on-transient-"
                "error AND the primary-then-lite two-step, since both call "
                "_call_gemini; see report for exact methodology"),
    }

    # ---- latency ----
    lat = [c["latency_s"] for c in calls if c.get("success")]
    lat_sorted = sorted(lat)
    def pctile(data, p):
        if not data:
            return None
        k = (len(data) - 1) * p
        f, c = int(k), min(int(k) + 1, len(data) - 1)
        return data[f] + (data[c] - data[f]) * (k - f)
    summary["grading_latency_s"] = {
        "n": len(lat), "mean": statistics.mean(lat), "median": statistics.median(lat),
        "min": min(lat), "max": max(lat),
        "p50": pctile(lat_sorted, 0.50), "p95": pctile(lat_sorted, 0.95),
        "stdev": statistics.stdev(lat) if len(lat) > 1 else 0.0,
        "note": "text-in/JSON-out grading call latency; NOT voice round-trip",
    }
    summary["ttft"] = {
        "value": None,
        "note": ("Not applicable: src/llm/client.py uses non-streaming "
                "generate_content / chat.completions.create calls throughout "
                "(complete() in src/llm/client.py). No token-level streaming "
                "exists in this codebase's LLM path to measure TTFT from."),
    }

    # ---- hallucination / evidence violations ----
    success_items = [g for g in grading if g["status"] == "success"]
    total_violations = sum(len(g.get("evidence_violations", [])) for g in success_items)
    total_evidence = sum(g.get("evidence_count", 0) for g in success_items)
    items_with_violation = sum(1 for g in success_items if g.get("evidence_violations"))
    summary["hallucination_rate"] = {
        "items_with_violation": items_with_violation, "n_items": len(success_items),
        "items_with_violation_pct": items_with_violation / len(success_items),
        "evidence_quotes_kept": total_evidence, "evidence_quotes_dropped": total_violations,
        "per_attempt_violation_rate": (total_violations / (total_violations + total_evidence)
                                       if (total_violations + total_evidence) else None),
    }

    # ---- rubric distribution by category ----
    by_cat = defaultdict(list)
    for g in success_items:
        by_cat[g["category"]].append(g["dimensions"])
    cat_summary = {}
    for cat, items in by_cat.items():
        dims_dist = {d: dict(Counter(it[d] for it in items)) for d in DIMS}
        solid_rate = sum(sum(1 for d in DIMS if it[d] == "Solid") for it in items) / (len(items) * 6)
        cat_summary[cat] = {"n": len(items), "dimensions": dims_dist, "solid_rate": solid_rate}
    summary["rubric_by_category"] = cat_summary

    # ---- construct validity: quality-rank vs measured score (Pearson) ----
    xs, ys = [], []
    for g in success_items:
        if g["category"] in CATEGORY_RANK:
            xs.append(CATEGORY_RANK[g["category"]])
            ys.append(sum(LEVEL_SCORE[g["dimensions"][d]] for d in DIMS) / 6)
    summary["quality_rank_correlation"] = {
        "n": len(xs), "pearson_r": pearson(xs, ys),
        "note": ("Pearson r between author-intended quality rank "
                "(weak=1, average=2, excellent=3) and mean dimension score "
                "(Gap=0, NeedsWork=1, Solid=2) per item. This is a construct-"
                "validity check against authoring intent, NOT a human-rater "
                "correlation."),
    }

    # ---- STAR order-invariance: excellent vs star_explicit vs non_star ----
    order_cats = {}
    for cat in ("excellent", "star_explicit", "non_star"):
        items = by_cat.get(cat, [])
        struct_solid = sum(1 for it in items if it["structure"] == "Solid")
        order_cats[cat] = {
            "n": len(items),
            "structure_solid_rate": struct_solid / len(items) if items else None,
            "overall_solid_rate": cat_summary.get(cat, {}).get("solid_rate"),
        }
    summary["star_order_invariance"] = order_cats

    # ---- consistency: modal agreement, span violations, Kappa, MAE ----
    total_slots = stable_slots = span_slots = 0
    kappa_pairs: list[tuple[str, str]] = []
    mae_diffs: list[int] = []
    for item_id, c in consistency.items():
        runs = c["runs"]
        for d in DIMS:
            levels = [r[d] for r in runs if d in r]
            if len(levels) < 2:
                continue
            total_slots += 1
            top, count = Counter(levels).most_common(1)[0]
            if count >= 2:
                stable_slots += 1
            if "Solid" in levels and "Gap" in levels:
                span_slots += 1
            for i in range(len(levels)):
                for j in range(i + 1, len(levels)):
                    kappa_pairs.append((levels[i], levels[j]))
                    mae_diffs.append(abs(LEVEL_SCORE[levels[i]] - LEVEL_SCORE[levels[j]]))
    summary["consistency"] = {
        "n_items": len(consistency), "n_dimension_slots": total_slots,
        "modal_stable_pct": stable_slots / total_slots if total_slots else None,
        "span_violation_pct": span_slots / total_slots if total_slots else None,
        "cohens_kappa_inter_run": cohens_kappa_from_pairs(kappa_pairs),
        "mae_inter_run": statistics.mean(mae_diffs) if mae_diffs else None,
        "n_pairwise_comparisons": len(kappa_pairs),
        "note": ("Kappa/MAE computed between repeated grade() calls on the "
                "SAME transcript (inter-run self-consistency), not model-vs-"
                "human agreement -- no independent human ratings exist in "
                "this repo (see report)."),
    }

    # ---- probe / follow-up ----
    probe_by_cat = defaultdict(list)
    for p in probe["probe_results"]:
        probe_by_cat[p["category"]].append(p)
    probe_summary = {}
    for cat, items in probe_by_cat.items():
        triggered = sum(1 for it in items if it["triggered_any"])
        types = Counter(t for it in items for t in (it["fired"] + it["queued"]))
        probe_summary[cat] = {"n": len(items), "triggered_rate": triggered / len(items),
                              "types": dict(types)}
    summary["probe_by_category"] = probe_summary
    summary["followup_precision_recall_f1"] = {
        "precision": probe["precision"], "recall": probe["recall"], "f1": probe["f1"],
        "n": probe["clean_label_n"], "confusion": probe["confusion"],
        "expected_trigger_map": probe["expected_trigger_map"],
    }

    # ---- voice ----
    v_success = [r for r in voice["results"] if r["status"] == "success"]
    v_errors = [r for r in voice["results"] if r["status"] != "success"]
    wers = [r["wer"] for r in v_success]
    cers = [r["cer"] for r in v_success]
    tts_lat = [r["tts_latency_s"] for r in v_success]
    stt_lat = [r["stt_latency_s"] for r in v_success]
    summary["voice"] = {
        "tts_model": voice["tts_model"], "stt_model": voice["stt_model"],
        "n_sampled": len(voice["results"]), "n_success": len(v_success),
        "n_error": len(v_errors), "errors": [e.get("error") for e in v_errors],
        "call_success_rate": len(v_success) / len(voice["results"]),
        "wer_mean": statistics.mean(wers) if wers else None,
        "wer_median": statistics.median(wers) if wers else None,
        "wer_max": max(wers) if wers else None,
        "cer_mean": statistics.mean(cers) if cers else None,
        "cer_median": statistics.median(cers) if cers else None,
        "cer_max": max(cers) if cers else None,
        "tts_latency_s_mean": statistics.mean(tts_lat) if tts_lat else None,
        "stt_latency_s_mean": statistics.mean(stt_lat) if stt_lat else None,
        "round_trip_s_mean": (statistics.mean(tts_lat) + statistics.mean(stt_lat))
                             if tts_lat and stt_lat else None,
        "note": ("WER/CER measured on a Deepgram-Aura-synthesized voice "
                "round-tripped through Deepgram nova-3 STT, not real human "
                "speech -- see report for what this can and cannot claim."),
    }

    out_path = RESULTS_DIR / "metrics_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"wrote {out_path}")
    print(json.dumps(summary, indent=2, default=str)[:3000])

    asyncio.run(track_eval_run(summary))


async def track_eval_run(summary: dict) -> None:
    """eval_run_completed (scope item 16, checkpoint 6): headline golden-
    dataset metrics as a trackable trend, not the full nested report --
    the deeply-nested breakdowns (rubric_by_category, probe_by_category,
    star_order_invariance) stay in metrics_summary.json/EVALUATION_REPORT.md
    for reading directly, not duplicated into Amplitude's flat property
    model. No-ops (like every other event in this project) if
    AMPLITUDE_API_KEY is unset."""
    voice = summary["voice"]
    consistency = summary["consistency"]
    followup = summary["followup_precision_recall_f1"]
    await amplitude.track(
        "eval_run_completed", device_id="golden-eval-suite",
        event_properties={
            "n_items": summary["grading_success_rate"]["n"],
            "grading_success_rate": summary["grading_success_rate"]["value"],
            "llm_call_success_rate": summary["llm_call_success_rate"]["value"],
            "json_schema_validity_pct": summary["json_schema_validity_pct"]["value"],
            "fallback_invocation_rate": summary["fallback_invocation_rate"]["value"],
            "retry_rate": summary["retry_rate"]["value"],
            "hallucination_items_with_violation_pct":
                summary["hallucination_rate"]["items_with_violation_pct"],
            "hallucination_per_attempt_violation_rate":
                summary["hallucination_rate"]["per_attempt_violation_rate"],
            "grading_latency_p50_s": summary["grading_latency_s"]["p50"],
            "grading_latency_p95_s": summary["grading_latency_s"]["p95"],
            "consistency_modal_stable_pct": consistency["modal_stable_pct"],
            "consistency_span_violation_pct": consistency["span_violation_pct"],
            "consistency_cohens_kappa": consistency["cohens_kappa_inter_run"],
            "followup_precision": followup["precision"],
            "followup_recall": followup["recall"],
            "followup_f1": followup["f1"],
            "voice_call_success_rate": voice["call_success_rate"],
            "voice_wer_mean": voice["wer_mean"],
            "voice_cer_mean": voice["cer_mean"],
        })
    print("posted eval_run_completed to Amplitude"
          if amplitude._api_key() else
          "AMPLITUDE_API_KEY unset; eval_run_completed skipped")


if __name__ == "__main__":
    main()
