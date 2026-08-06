# Evaluation Suite — Reproduction Guide

Everything in this directory was produced by running the scripts in `scripts/` against the live codebase in `src/` on 2026-08-04. This guide lets another engineer reproduce it from scratch.

## What's here

```
evaluation/
  README.md                    (this file)
  EVALUATION_REPORT.md          full technical report, all metrics + methodology
  EXECUTIVE_SUMMARY.md          1-page condensed version
  GOLDEN_DATASET.json / .csv    the 101-item golden set (author-authored, not human-sourced)
  scripts/
    generate_golden_dataset.py  builds the 101-item set (deterministic, no API calls)
    run_llm_eval.py             grades all 101 items via real LLM calls, writes results/llm_eval_results.json
    run_probe_eval.py           replays all 101 items through the rule-based probe engine (no LLM), writes results/probe_eval_results.json
    run_voice_eval.py           TTS->STT round trip on a 24-item sample, real Deepgram calls, writes results/voice_eval_results.json
    analyze_results.py          pure computation over the three results files -> results/metrics_summary.json
    make_charts.py              renders charts/*.png from metrics_summary.json
    measure_live_latency.py     NOT a runnable eval -- a documented stub for the one metric (true end-to-end voice latency) that needs a live LiveKit session, which this batch suite cannot exercise
  results/
    llm_eval_results.json       raw grading results, 133 calls
    probe_eval_results.json     raw probe-engine results, 101 items
    voice_eval_results.json     raw voice round-trip results, 24 items
    metrics_summary.json        every computed metric, machine-readable
    llm_eval_partial.jsonl      incremental checkpoint written during run_llm_eval.py (survives a killed process)
  charts/
    *.png                       6 charts referenced in EVALUATION_REPORT.md
```

## Prerequisites

- The product's existing Python venv, already set up per the repo root `README.md`:
  ```bash
  uv venv --python 3.12 .venv
  source .venv/bin/activate
  uv pip install -r requirements.txt
  ```
- A filled-in `.env` at the repo root with at minimum `GOOGLE_API_KEY`, `GROQ_API_KEY`, `DEEPGRAM_API_KEY` (all free-tier; see repo root README for where to get them). `run_llm_eval.py` and `run_probe_eval.py`/`generate_golden_dataset.py` don't need Deepgram; `run_voice_eval.py` doesn't need Google/Groq.
- `matplotlib` for chart regeneration only — **not** a product dependency, install it directly into the venv (does not touch `requirements.txt`):
  ```bash
  uv pip install matplotlib --python .venv/bin/python
  ```

## Running everything, in order

From the repo root, with the venv active:

```bash
# 1. Build the golden set (instant, deterministic, no API calls)
python -m evaluation.scripts.generate_golden_dataset

# 2. Probe/follow-up engine eval (instant, no API calls)
python -m evaluation.scripts.run_probe_eval

# 3. LLM grading eval (~133 real API calls, several minutes; unbuffered
#    output recommended so you can watch progress, and it checkpoints to
#    results/llm_eval_partial.jsonl every item in case it's interrupted)
python -u -m evaluation.scripts.run_llm_eval

# 4. Voice eval (~24 real Deepgram TTS+STT round trips, several minutes;
#    optional integer arg = items per category, default 3)
python -m evaluation.scripts.run_voice_eval 3

# 5. Compute every metric from the three results files (instant, no API calls)
python -m evaluation.scripts.analyze_results

# 6. Charts (instant, needs matplotlib -- see Prerequisites)
python -m evaluation.scripts.make_charts
```

## What will and won't match exactly on a re-run

- **Steps 1 and 2 are fully deterministic** — same golden set, same probe-engine results, every time, since they involve no randomness and no LLM calls.
- **Steps 3 and 4 will NOT reproduce identical numbers.** They call live Gemini/Groq/Deepgram APIs. Expect:
  - Different exact latencies every run.
  - Different fallback-tier distribution depending on the **daily LLM ledger state** (`data/llm_ledger.json`, keyed by date, capped at `config/settings.yaml`'s `daily_call_cap`) — running this suite on a day where the cap hasn't been touched yet will show more primary-Gemini traffic than the version reported here, which ran after the cap was already exhausted by earlier same-day testing. This is expected and is explained in `EVALUATION_REPORT.md` Section 6.1, not a bug.
  - Possible different WER/CER values on voice items, since TTS/STT models can have minor version-level behavior drift over time.
- **The qualitative findings should reproduce** even when exact numbers don't: the `non_star` vs `star_explicit` order-invariance gap (Section 6.5), the DEPTH-not-SPECIFICITY probe-priority finding (Section 6.7), and the `fabricated`-category grading gap (Section 6.3) are all structural properties of the code, not statistical flukes — they should appear on any re-run.

## If a run gets interrupted

`run_llm_eval.py` writes each grading result to `results/llm_eval_partial.jsonl` immediately (flushed to disk every item), before the final `results/llm_eval_results.json` is written at the end. If the process is killed partway through, the partial file has everything completed up to that point — read it directly (`[json.loads(l) for l in open(...)]`) rather than re-running the whole batch from scratch.

## Extending this suite for a future model update

- **New LLM provider or model version:** no changes needed to the eval scripts — `run_llm_eval.py` calls the real `src.grading.grader.grade()`, so it automatically picks up whatever `config/settings.yaml` points at.
- **Larger golden set:** add new categories or items directly in `evaluation/scripts/generate_golden_dataset.py` (see its docstring for the pattern — parameterized templates for structured variation, plain text lists for one-off scenarios like `fabricated`/`incomplete`).
- **Human-labeled subset (the biggest gap this report flags):** have 2+ independent raters score a sample against `config/rubric.yaml` directly, save their labels alongside `GOLDEN_DATASET.json` (e.g., `HUMAN_LABELS.json` keyed by item id), and extend `analyze_results.py`'s `cohens_kappa_from_pairs`/`pearson` helpers — they're already written generically enough to accept human-vs-model pairs, not just run-vs-run pairs.
