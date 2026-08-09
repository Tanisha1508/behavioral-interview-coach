# Executive Summary — Behavioral Interview Coach Evaluation

**Full report:** `EVALUATION_REPORT.md` · **Run dates:** 2026-08-04 (all four instruments) + 2026-08-09 (LLM grading pass independently re-run in full) · **All numbers measured, none estimated.**

## What was evaluated

A live voice AI behavioral interview coach (LiveKit + Deepgram + Gemini/Groq + Supabase) was evaluated across four independent instruments, run against real API calls: a 101-item golden-set grading pass (run twice, five days apart, on real LLM traffic), a rule-engine probe/follow-up replay, a 24-item voice round-trip (TTS→STT), and a 16-item repeated-grading consistency check. Numbers below are from the most recent (2026-08-09) grading run unless noted; the probe/follow-up and voice instruments were not re-run and still reflect 2026-08-04.

## Top-line numbers

| Metric | Result |
|---|---|
| Grading pipeline success rate | **100%** (101/101 items, 133/133 LLM calls) |
| Follow-up trigger detection (Precision / Recall / F1) | **1.0 / 1.0 / 1.0** (n=50, code-verifiable ground truth) |
| Repeated-grading agreement (Cohen's κ, inter-run) | **0.869** — "almost perfect" |
| Grader construct validity vs. authored quality tier (Pearson r) | **0.974** (n=38) |
| Voice pipeline WER / CER (synthetic-speech round trip) | **3.69% / 3.81%** (n=22) |
| Grading latency, mean / p50 / p95 / p99 | **4.38s / 4.06s / 4.76s / 17.79s** (n=133, non-streaming) |
| Evidence-hallucination rate (caught and dropped in code) | **10.4%** of generated quotes this run; 7.3%–11.9% across two 2026-08-04 passes — varies with which LLM tier served the call (Section 6.3) |

## New this pass: accuracy vs latency, by provider

Free-tier quota routed 130/133 calls to Gemini Flash-Lite and only 3 to primary Gemini Flash this run (real rate-limiting, not a design choice). First look at the raw numbers appeared to show Gemini-lite scoring far less accurately (49% Solid rate vs Gemini's 100%) — but that comparison was confounded: Gemini's 3 calls all happened to be `excellent`-category items, while Gemini-lite covered the whole category mix including every intentionally-low-quality category. Controlling for category (the one category both providers actually covered, `excellent`): **Gemini 100% (n=3) vs Gemini-lite 93.3% (n=10)** — close, though Gemini's n is too small to call this conclusive. On latency, the gap is unambiguous: Gemini-lite's p50/p95/p99 (4.17s / 4.71s / 6.63s) is roughly 4–5x faster than Gemini's (18.29s / 20.59s / 20.79s). See `charts/accuracy_vs_latency_by_provider.png` and Section 6.8 of the full report.

## The one finding that matters most

The product explicitly documents a design rule: *"never penalize an answer for deviating from the canonical story order"* (`config/rubric.yaml`). A controlled test — the exact same facts told in canonical order vs. reordered — found the **LLM grader mostly honors this rule (Structure=Solid rate: 100% → 76.9%)**, but the **rule-based probe engine violates it completely (probe-triggered rate: 0% → 100%)**. Reordering a strong answer causes the live follow-up engine to flag it every time, the opposite of documented intent. This is a real, reproducible bug, found by design, not discovered by accident.

## Two other honest gaps found (not fixed, since fixing wasn't the task)

- **No fabrication detection anywhere in the pipeline.** Answers with impossible claims ("12 billion signups in one day") scored a 61.1% Solid rate this run (47.2% on 2026-08-04 — the day-to-day swing is itself informative: this is not a stable, reliably-low score the way `weak`'s is). The grader verifies quotes are *said*, never that they're *true*.
- **No topical-relevance detection in the rule engine.** Off-topic answers (recipes, commute complaints) triggered zero follow-up probes, by design gap — only the LLM grader's Structure dimension catches these, and imperfectly.

## What could not be measured, and why

- **TTFT** — not applicable; the LLM client has no streaming code path anywhere.
- **True end-to-end voice turn latency** — production now tracks LLM/TTS/STT latency separately (Amplitude, added after this report's original run) but nothing yet stitches those into one mic-stop-to-audio-start number; a reproduction script for measuring it live is provided, not run. **Interview completion rate**, unlike at the original run date, is now measurable in production (Amplitude session funnel) — just not by this offline batch suite, which grades static transcripts.
- **Human-vs-model agreement (Kappa/MAE against real raters)** — no independent human labels exist for this dataset; every reported Kappa/MAE is inter-run self-consistency instead, clearly labeled as such.

## Reproduction

`evaluation/README.md` has full instructions. Every script is deterministic except the three that make real API calls (`run_llm_eval.py`, `run_probe_eval.py` — deterministic, no API — and `run_voice_eval.py`), which will reproduce the same *pipeline behavior* but not byte-identical numbers, since they depend on live model responses and the day's quota state.
