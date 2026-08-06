# Executive Summary — Behavioral Interview Coach Evaluation

**Full report:** `EVALUATION_REPORT.md` · **Run date:** 2026-08-04 · **All numbers measured, none estimated.**

## What was evaluated

A live voice AI behavioral interview coach (LiveKit + Deepgram + Gemini/Groq + Supabase) was evaluated across four independent instruments, all run against real API calls today: a 101-item golden-set grading pass, a rule-engine probe/follow-up replay, a 24-item voice round-trip (TTS→STT), and a 16-item repeated-grading consistency check.

## Top-line numbers

| Metric | Result |
|---|---|
| Grading pipeline success rate | **100%** (101/101 items, 133/133 LLM calls) |
| Follow-up trigger detection (Precision / Recall / F1) | **1.0 / 1.0 / 1.0** (n=50, code-verifiable ground truth) |
| Repeated-grading agreement (Cohen's κ, inter-run) | **0.859** — "almost perfect" |
| Grader construct validity vs. authored quality tier (Pearson r) | **0.968** (n=38) |
| Voice pipeline WER / CER (synthetic-speech round trip) | **3.69% / 3.81%** (n=22) |
| Grading latency, mean / P95 | **3.68s / 8.27s** (n=133, non-streaming) |
| Evidence-hallucination rate (caught and dropped in code) | **7.3%–11.9%** of generated quotes, depending on which LLM tier served the call |

## The one finding that matters most

The product explicitly documents a design rule: *"never penalize an answer for deviating from the canonical story order"* (`config/rubric.yaml`). A controlled test — the exact same facts told in canonical order vs. reordered — found the **LLM grader mostly honors this rule (Structure=Solid rate: 100% → 76.9%)**, but the **rule-based probe engine violates it completely (probe-triggered rate: 0% → 100%)**. Reordering a strong answer causes the live follow-up engine to flag it every time, the opposite of documented intent. This is a real, reproducible bug, found by design, not discovered by accident.

## Two other honest gaps found (not fixed, since fixing wasn't the task)

- **No fabrication detection anywhere in the pipeline.** Answers with impossible claims ("12 billion signups in one day") scored a 47.2% Solid rate — closer to a mediocre real answer than to a clearly weak one. The grader verifies quotes are *said*, never that they're *true*.
- **No topical-relevance detection in the rule engine.** Off-topic answers (recipes, commute complaints) triggered zero follow-up probes, by design gap — only the LLM grader's Structure dimension catches these, and imperfectly.

## What could not be measured, and why

- **TTFT** — not applicable; the LLM client has no streaming code path anywhere.
- **True end-to-end voice latency and interview completion rate** — require a live session with real audio and production telemetry that doesn't exist in this repo; a reproduction script for the former is provided, not run.
- **Human-vs-model agreement (Kappa/MAE against real raters)** — no independent human labels exist for this dataset; every reported Kappa/MAE is inter-run self-consistency instead, clearly labeled as such.

## Reproduction

`evaluation/README.md` has full instructions. Every script is deterministic except the three that make real API calls (`run_llm_eval.py`, `run_probe_eval.py` — deterministic, no API — and `run_voice_eval.py`), which will reproduce the same *pipeline behavior* but not byte-identical numbers, since they depend on live model responses and the day's quota state.
