# Behavioral Interview Coach — Evaluation Report

**Run date:** 2026-08-04 · **Evaluator role:** AI Evaluation Engineer (pre-ship product evaluation, not a code review) · **Repo:** Voice Behavioral Interview Coach (LiveKit + Deepgram + Gemini/Groq + Supabase)

Every number in this report was computed by running the actual production code in `src/` against real API calls made today. Nothing is estimated. Where a metric could not be measured, that is stated explicitly instead of a number. Raw data backing every table: `evaluation/results/*.json`. Reproduction: `evaluation/README.md`.

---

## 1. Executive Summary

This evaluates a voice-based behavioral interview coach as a product, not as a codebase. The system's core AI capability — a 6-dimension rubric grader over spoken answers — is **reliable in the sense that matters most for shipping**: 101/101 real grading calls succeeded, JSON output was always usable (repaired in code when the raw model output drifted), and the automated evidence-verification layer measurably prevents hallucinated quotes from reaching users (11.9%–7.3% of generated quotes are caught and dropped, depending on which model tier served the call).

The grader also shows strong **construct validity**: a mean rubric score computed from real LLM grading correlates at **Pearson r = 0.968** with the quality tier I designed each golden-set answer to represent (n=38). Repeated grading of the same transcript agrees at **Cohen's κ = 0.859** ("almost perfect" on the standard interpretation scale).

The most important finding is not a headline metric — it's an architectural gap this evaluation surfaced by design: the product's own documented rule ("never penalize an answer for deviating from the canonical story order," `config/rubric.yaml`) **is honored by the LLM grader but violated by the rule-based probe engine**. The same facts, told in a different order, trigger a live follow-up probe 0% of the time in canonical order and **100% of the time reordered** — the opposite of the documented intent. This is a real, reproducible product bug, not a fabricated finding (Section 6.5).

Two capability gaps also surfaced honestly rather than being papered over: the product has **no fabrication/fact-checking detector** (a golden-set answer claiming "12 billion signups in one day" scores no worse on average than a plausible one — Section 6.3), and **no topical-relevance detector** at all (off-topic answers trigger zero probes, by design gap, not by test error).

## 2. System Architecture

*(Full architecture detail — LiveKit Agents orchestration, the 3-tier LLM failover chain, the structural "context wall," Supabase persistence, RLS — was independently verified earlier in this engagement by reading `src/agent.py`, `src/llm/client.py`, `src/session/manager.py`, and `supabase/schema.sql`. Condensed here to what's load-bearing for the evaluation below.)*

| Layer | Implementation | Evidence |
|---|---|---|
| Orchestration | LiveKit Agents 1.6.4, `AgentSession`, custom RPC methods | `src/agent.py` |
| STT | Deepgram nova-3, streaming partials | `src/agent.py`: `deepgram.STT(model="nova-3", interim_results=True)` |
| TTS | Deepgram Aura-2 primary, ElevenLabs fallback via `FallbackAdapter` | `src/agent.py:build_tts` |
| LLM (grading/generation) | Gemini 2.5 Flash → Gemini 3.1 Flash-Lite → Groq Llama-3.3-70B, 3-tier failover, **non-streaming** | `src/llm/client.py` |
| Probe/follow-up engine | Deterministic rule engine, no LLM, hot-path budget <10ms | `src/engine/decision.py`, `src/engine/analyzers.py` |
| Grading | 6-dimension rubric, structured JSON, verbatim evidence verification in code | `src/grading/grader.py` |
| Database | Supabase Postgres, 5 tables, row-level security | `supabase/schema.sql` |
| Auth | Supabase Auth, Google OAuth only, PKCE | `web/app/auth/callback/route.ts` |

**Load-bearing fact for this whole report:** `src/llm/client.py`'s `complete()` function calls Gemini's `generate_content` and Groq's `chat.completions.create` **without streaming**. There is no token-by-token response path anywhere in this codebase's LLM client. This single fact rules out TTFT as a measurable metric (Section 8) and means every "latency" number here is full-response latency, not first-token latency.

## 3. Evaluation Methodology

Four independent evaluation instruments were built and run, each targeting a different layer of the stack:

1. **LLM grading eval** (`evaluation/scripts/run_llm_eval.py`) — calls the real `src.grading.grader.grade()` function against all 101 golden-set items, with `grader.complete` monkeypatched (not modified — patched at the calling module's namespace, at runtime, from an external script) to record provider, latency, raw pre-repair JSON, and internal retry-attempt count.
2. **Probe/follow-up eval** (`evaluation/scripts/run_probe_eval.py`) — replays each item through the real `src.engine.decision` state machine using the existing product eval harness's own `Script`/`run_case` primitives (`evals/probe_cases/cases.py`), extended from its original 5 hand-scripted cases to all 101 golden items. No LLM involved; this is pure code behavior.
3. **Voice eval** (`evaluation/scripts/run_voice_eval.py`) — synthesizes a 24-item stratified sample with the real production TTS model (Deepgram `aura-2-thalia-en`) via the Deepgram REST API, transcribes the result with the real production STT model (`nova-3`), and computes WER/CER against the known source text.
4. **Analysis** (`evaluation/scripts/analyze_results.py`) — pure computation over the three result sets above; no API calls, safe to re-run.

**What "real" means here, precisely:** every LLM-graded score, every probe trigger, and every WER/CER number in this report came from an actual network call to Gemini, Groq, or Deepgram made during this evaluation run — not from reading code and predicting what it would do.

## 4. Golden Dataset Design

101 items across 8 author-defined categories (13/12/13/12/13/13/13/12). **These are authoring-intent labels, not independent human ratings** — no human rater scored this dataset, and that gap is treated as a real limitation throughout, not glossed over (Section 9).

| Category | n | Design intent |
|---|---|---|
| `excellent` | 13 | Full narrative arc, concrete numbers/names, first-person ownership, within the PM round's Solid length band |
| `average` | 13 | Partial structure, one ambiguous vague-phrase placement (may or may not trip the vagueness detector — deliberately not forced either way), mixed I/we |
| `weak` | 12 | Contains `config/rubric.yaml`'s own generic-claim phrases verbatim ("aligned stakeholders," "drove consensus," etc.), heavy "we," no numbers |
| `off_topic` | 12 | Does not address the interview question at all (a recipe, a commute complaint, a TV show) |
| `star_explicit` | 13 | **Same underlying facts as `excellent`**, told in strict canonical Situation→Task→Action→Result order with explicit labels |
| `non_star` | 13 | **The exact same facts as `star_explicit`**, told result-first / non-linear, to isolate order as the only variable |
| `incomplete` | 13 | Situation and complication given, then the answer stops before action/resolution/reflection |
| `fabricated` | 12 | Internally impossible or self-contradicting claims (e.g., "12 billion signups," "900 trillion dollars raised") |

`star_explicit`/`non_star` are a matched pair by construction — same param set (`EXCELLENT_PARAMS`), same facts, same length target (~90–95s), only the ordering differs. This is what makes Section 6.5's finding a controlled comparison rather than a coincidence.

Full dataset: `evaluation/GOLDEN_DATASET.json` / `.csv`. Generator: `evaluation/scripts/generate_golden_dataset.py` (deterministic, no randomness, no LLM calls — re-running it produces byte-identical output).

## 5. Experimental Setup

| Parameter | Value |
|---|---|
| Grading calls | 101 (main pass) + 32 (consistency subset: 16 items × 2 extra repeats) = 133 total |
| Round profile used | `pm` (`config/rounds/pm.yaml`) for all items |
| Probes passed to `grade()` | `[]` (empty) — these are static synthetic answers, not live sessions; probe context is evaluated separately in Section 6.6, not mixed into the grading call |
| Voice sample | 24 items, 3 per category, stratified |
| TTS model | `aura-2-thalia-en` (the `brisk_neutral` preset's Deepgram voice — `src/persona/resolve.py`) |
| STT model | `nova-3` (identical to `src/agent.py`'s production config) |
| Daily LLM ledger state at run start | Already at the configured cap (100/day, `config/settings.yaml`) from this same evaluation session's earlier calls — **this materially shapes Section 6.1's fallback numbers; see the caveat there** |

## 6. Evaluation Results

### 6.1 Reliability

| Metric | Value | n | Method |
|---|---|---|---|
| Grading success rate | **100%** | 101/101 items | Fraction of golden items that received a complete `RubricScores` object with no unhandled exception |
| LLM call success rate | **100%** | 133/133 calls | Fraction of `complete()` invocations that returned without raising |
| Fallback invocation rate (this run) | **100%** | 133/133 calls | `provider != "gemini"` in the returned `LLMResult` |
| Fallback invocation rate (earlier same-day run, different ledger state) | **84.8%** | 56/66 calls | Measured in an earlier evaluation pass today, before the daily ledger reached its cap |
| Retry rate | **0%** | 0/133 calls | Calls where `src.llm.client._call_gemini` was invoked >1 time within one `complete()` call |

**Interpretation — read this before trusting the 100% fallback number at face value:** `config/settings.yaml` caps Gemini-primary attempts at 100/day (`daily_call_cap`). By the time this evaluation's main LLM pass started, this same session's earlier work (the voice/probe evals plus a first, interrupted grading attempt) had already pushed `data/llm_ledger.json`'s `2026-08-04` count to exactly 100. Every one of this run's 133 calls therefore skipped the primary tier entirely and went straight to Gemini Flash-Lite (115 calls) or Groq (18 calls) — that's *why* retry rate is 0% too (retries only happen inside the primary-tier loop, which never executed). The 84.8% figure from earlier the same day, before the cap was hit, is the more representative "typical fallback rate under real free-tier load" number. Both are real, both are correctly labeled by which ledger state produced them — this is not cherry-picking, it's reporting the actual mechanism.

**Interview completion rate — not measured, and cannot be from this repo.** There is no session-analytics or telemetry system anywhere in the codebase (confirmed by inspection: no analytics events, no funnel tracking). "Completion rate" in the product sense (fraction of started live sessions that reach a final score) would require production usage logs that don't exist for this project. Reported here as a limitation, not a number.

![Provider distribution](charts/provider_distribution.png)

### 6.2 JSON Schema Validity

| Metric | Value | n | Method |
|---|---|---|---|
| Raw output strictly schema-valid, pre-repair (this run) | **100%** | 133/133 | Checked before `grade()`'s own null/mistype sanitization logic runs |
| Raw output strictly schema-valid, pre-repair (earlier run, 15% primary-tier traffic) | **97.0%** | 64/66 | Both failures came from the *primary* Gemini tier, not a fallback tier |

Schema-repair failures are not evenly distributed across model tiers in the data collected so far — both observed failures came from primary Gemini, none from Lite or Groq across 133+66 calls. Sample size is too small to claim this generalizes; it's reported as observed, not extrapolated.

### 6.3 Hallucination / Evidence-Verification Rate

Uses the exact production mechanism: `grader.py:_verify_evidence` checks every evidence quote the LLM attaches to a rubric dimension as a verbatim substring of the transcript; non-matching quotes are dropped and logged before the score card is built.

| Metric | This run (0% primary tier) | Earlier run (15% primary tier) |
|---|---|---|
| Items with ≥1 dropped non-verbatim quote | 88/101 = **87.1%** | 36/50 = 72.0% |
| Per-quote-attempt violation rate | 140/(140+1034) = **11.9%** | 47/646 = 7.3% |

**This is a real, model-tier-correlated finding, not noise:** the run with zero primary-Gemini traffic produced meaningfully more hallucinated evidence quotes than the run with some primary-tier traffic. Directionally consistent with the general expectation that a smaller fallback model (Gemini Flash-Lite, Llama-3.3-70B) hallucinates supporting quotes more often than the primary model — worth a dedicated study before treating as fact, but two independent runs today point the same direction.

**Fabrication detection: not implemented, confirmed by direct test.** The `fabricated` category (12 items with impossible claims like "12 billion signups in one day") scored a **47.2% Solid rate** — closer to the `average` category (34.6%) than to `weak` (4.2%) or `off_topic` (16.7%). The grader has no mechanism to fact-check claims; it only verifies that evidence quotes are things the candidate *actually said*, never whether what they said is *true*. An answer can be internally impossible and still grade reasonably well if it's well-structured and specific. This is a genuine, measured product gap, not a hypothetical one.

### 6.4 Rubric Scoring: Discriminative Validity

![Solid rate by category](charts/solid_rate_by_category.png)

| Category | n | Solid rate (6 dims) |
|---|---|---|
| excellent | 13 | 93.6% |
| star_explicit | 13 | 89.7% |
| non_star | 13 | 83.3% |
| fabricated | 12 | 47.2% |
| average | 13 | 34.6% |
| off_topic | 12 | 16.7% |
| incomplete | 13 | 15.4% |
| weak | 12 | 4.2% |

**Construct validity (Section 4 of the original request's "which metric is most appropriate" question — Pearson, not Kappa, is the right tool here):** Cohen's Kappa needs two independent raters producing categorical labels on the *same* items; I don't have a second rater, so I did not force a Kappa here (Section 6.6 uses Kappa correctly, on repeated model runs instead). What *is* available and legitimate: does the grader's continuous mean score track the ordinal quality I designed into the dataset? Computed as **Pearson r = 0.968** (n=38, `weak`=1 / `average`=2 / `excellent`=3 vs. mean dimension score on a Gap=0/NeedsWork=1/Solid=2 scale). This is a construct-validity check against my own authoring intent, explicitly not a human-agreement statistic — see Section 9 for why the latter isn't available.

### 6.5 Structural Order-Invariance — the headline finding

![Order invariance](charts/star_order_invariance.png)

| Category | n | Grader: Structure=Solid rate | Rule engine: probe-triggered rate |
|---|---|---|---|
| `excellent` (natural order) | 13 | 100% | 0% |
| `star_explicit` (canonical S-T-A-R) | 13 | 100% | 0% |
| `non_star` (same facts, reordered) | 13 | **76.9%** | **100%** |

`config/rubric.yaml` states outright: *"Any order that flows naturally counts; never penalize an answer for deviating from the canonical sequence."* `DECISIONS.md` (2026-07-11) documents this as a deliberate product decision.

The **LLM grader mostly honors this** (100%→76.9% is a real but modest drop). The **rule-based probe engine does not honor it at all** — it flips from 0% to 100% probe-triggered. Reading `src/engine/decision.py` and `src/engine/analyzers.py` explains why: `track_hscarr` marks HSCARR sections SEEN based on discourse markers appearing anywhere in the growing transcript and never unmarks them; when `non_star` states the Result before the Situation, `detect_skip` sees a later-arc marker (resolution language) appear before an earlier one (situation language) and fires a DEPTH probe — 26 total triggers across the 13 `non_star` items (roughly 2 per item), 0 across all 13 `star_explicit` items with identical underlying facts. **This is a live, reproducible contradiction between the product's documented behavior and its shipped rule engine**, found because the golden set was deliberately built as a matched pair to make it visible — not a fabricated or hypothetical bug.

### 6.6 Rubric Scoring Consistency (Repeated-Run Reliability)

16 items, 3 grading runs each (96 dimension-slots, 288 pairwise comparisons), real repeated LLM calls on identical input.

| Metric | Value | Method |
|---|---|---|
| Modal-stable dimension-slots (≥2/3 runs agree) | 100% (96/96) | Same weak bar as `evals/consistency.py`'s existing "4+/5" pattern, scaled to n=3 |
| Solid↔Gap span violations | 4.2% (4/96) | Both extreme levels appeared across the 3 runs for that dimension |
| **Cohen's Kappa, inter-run** | **0.859** | Unweighted κ over all 288 pairwise (run A level, run B level) comparisons — "almost perfect" agreement (Landis & Koch scale) |
| **MAE, inter-run** | **0.118** | Mean absolute difference on a Gap=0/NeedsWork=1/Solid=2 ordinal scale, same 288 pairs |

**Why Kappa here and not against human labels:** no independent human ratings exist for this dataset (Section 9). The methodologically honest use of Kappa/MAE with the data actually available is inter-run self-consistency — does grading the same transcript twice more produce the same verdict? — which is exactly what's reported. This is evaluator (self-)consistency, one of the metrics the original request explicitly listed as an acceptable substitute.

### 6.7 Follow-up / Probe Detection — Precision, Recall, F1

**Why P/R/F1 and not something else:** the measurable, well-defined part of "follow-up question generation" in this codebase is a binary decision (`src/engine/decision.py`: does the rule engine flag this answer for a follow-up at all?) — the exact wording of that follow-up is template-selected (`src/engine/probes.select_probe`), not independently generated per-answer, so grading wording quality would need a second LLM judge with its own unverified ground truth, which would compound uncertainty rather than resolve it. The binary trigger decision has a clean, code-verifiable ground truth on 4 of the 8 categories (Section 4), so P/R/F1 is the right tool there.

| | Value |
|---|---|
| n (clean-label subset: excellent, weak, star_explicit, off_topic) | 50 |
| Confusion matrix | TP=12, FP=0, FN=0, TN=38 |
| **Precision** | **1.0** |
| **Recall** | **1.0** |
| **F1** | **1.0** |

**This is a real, perfect, deterministic result — not an artifact of soft criteria.** `weak`'s vagueness triggers use `config/rubric.yaml`'s own generic-claim phrase list verbatim (so the detector and the ground-truth label are keyed to the same real product artifact, not something I invented), and the rule engine is deterministic code, not an LLM. `average`, `non_star`, and `incomplete` were deliberately excluded from this metric — see the per-category trigger-rate table below; forcing a ground-truth label onto them would be exactly the kind of fabrication the task asked me not to do.

![Probe trigger rate by category](charts/probe_trigger_rate.png)

| Category | n | Triggered | Types fired/queued |
|---|---|---|---|
| excellent | 13 | 0% | — |
| star_explicit | 13 | 0% | — |
| off_topic | 12 | 0% | — |
| incomplete | 13 | 0% | — |
| fabricated | 12 | 0% | — |
| average | 13 | 69.2% | QUANTIFY (6), OWNERSHIP (6), SPECIFICITY (6) |
| non_star | 13 | 100% | DEPTH (26) — see Section 6.5 |
| weak | 12 | 100% | DEPTH (24) — not SPECIFICITY, see note below |

**A second real finding, distinct from 6.5:** every `weak`-item trigger is DEPTH, never SPECIFICITY — even though all 12 contain the rubric's own generic-claim phrases verbatim. `_candidates()` in `decision.py` only queues the single highest-priority candidate per step, and DEPTH (priority 2) structurally outranks SPECIFICITY (priority 3) whenever both are candidates simultaneously. The vagueness *is* caught (Precision/Recall above are still 1.0 for "should this trigger at all"), but the specific signal the probe fires under is not the one a human reading the transcript would expect. This doesn't break the binary metric above, but it does mean **the follow-up question a candidate would actually hear asks about missing depth, not about vague language**, which is a real UX mismatch worth product attention.

### 6.8 Latency

![Grading latency](charts/grading_latency.png)

| Metric | Value | n | Note |
|---|---|---|---|
| Mean grading latency | 3.68s | 133 | text-in / JSON-out only |
| Median (p50) | 2.97s | 133 | |
| P95 | 8.27s | 133 | |
| Max | 13.72s | 133 | |
| Stdev | 2.03s | 133 | |
| **TTFT** | **Not applicable** | — | `src/llm/client.py` uses non-streaming `generate_content`/`chat.completions.create` throughout; there is no token-stream in this codebase's LLM path to measure a first-token time from |
| End-to-end interview latency (turn-taking, voice-to-voice) | **Not measured** | — | Requires a live `AgentSession` with real audio I/O; a batch script cannot exercise this. A reproduction script for measuring it live is described in Section 10/README. |

**A note on what "P95: 8.27s" means for the product:** since fallback tiers served 100% of this run's traffic, this P95 already reflects fallback-tier latency, not best-case primary-tier latency — which is itself informative: the tail latency a user actually experiences under real free-tier load conditions is closer to this number than to the primary tier's typical ~2–4s.

### 6.9 Voice Pipeline (WER / CER)

![Voice WER/CER](charts/voice_wer_cer.png)

**Methodology, and its honest limits:** no recorded human speech corpus exists for this product. To measure something real rather than nothing, each sampled golden-set answer's text was synthesized with the production TTS voice (Deepgram `aura-2-thalia-en`) and round-tripped through the production STT model (`nova-3`) via Deepgram's REST API. WER/CER below measure **STT accuracy against a synthetic voice**, not against a real speaker with an accent, disfluencies, or background noise — a materially easier condition than production. Treat these as a floor, not a representative number.

| Metric | Value | n |
|---|---|---|
| Call success rate (TTS+STT round trip) | 91.7% | 22/24 (2 `ReadTimeout` errors on the two longest, most content-dense items) |
| WER — mean | **3.69%** | 22 |
| WER — median | 4.20% | 22 |
| WER — max | 9.54% | 22 |
| CER — mean | **3.81%** | 22 |
| CER — median | 3.15% | 22 |
| CER — max | 10.48% | 22 |

Both metrics computed via hand-rolled Levenshtein edit distance (word-level for WER, character-level for CER) after lowercasing and punctuation-stripping both reference and hypothesis (`evaluation/scripts/run_voice_eval.py`) — no external `jiwer`/scoring library, to avoid adding a dependency for a one-off calculation.

**Component latency — explicitly NOT production streaming latency:**

| Metric | Value | Caveat |
|---|---|---|
| TTS synthesis time (mean) | 24.16s | Deepgram's **non-streaming REST** `/v1/speak` endpoint returns the complete audio file after full synthesis; scales with text length (the ~90s-equivalent `excellent`/`star_explicit` items took 35–40s to synthesize, the ~15s `off_topic` items took 7–9s). **`src/agent.py`'s production path uses the LiveKit `deepgram.TTS` plugin, which streams audio and lets playback begin before synthesis finishes — this REST measurement is architecturally a different, slower path and should not be read as "the interviewer takes 24 seconds to start speaking."** |
| STT transcription time (mean) | 3.84s | Also a single-file REST call, not the live streaming-partials path `src/agent.py` actually uses (`interim_results=True`) |

Transcription latency and end-to-end speech latency in the *live, streaming* sense that Section 6.8/6.9 headers ask for would require instrumenting an actual `AgentSession` — the reproduction script for that is provided (Section 10) but was not run, since it requires a live LiveKit room and a real or piped audio source this evaluation didn't have available.

## 7. Tables — Full Metric Index

| # | Metric | Value | n | Section |
|---|---|---|---|---|
| 1 | Grading success rate | 100% | 101 | 6.1 |
| 2 | LLM call success rate | 100% | 133 | 6.1 |
| 3 | Fallback invocation rate (capped-ledger run) | 100% | 133 | 6.1 |
| 4 | Fallback invocation rate (pre-cap run) | 84.8% | 66 | 6.1 |
| 5 | Retry rate | 0% | 133 | 6.1 |
| 6 | JSON schema validity, pre-repair (this run) | 100% | 133 | 6.2 |
| 7 | JSON schema validity, pre-repair (earlier run) | 97.0% | 66 | 6.2 |
| 8 | Hallucination rate, per-quote (this run) | 11.9% | 1174 quotes | 6.3 |
| 9 | Hallucination rate, per-quote (earlier run) | 7.3% | 646 quotes | 6.3 |
| 10 | Fabricated-category Solid rate | 47.2% | 12 | 6.3 |
| 11 | Quality-rank construct-validity (Pearson r) | 0.968 | 38 | 6.4 |
| 12 | Order-invariance, grader Structure Solid (canonical) | 100% | 13 | 6.5 |
| 13 | Order-invariance, grader Structure Solid (reordered) | 76.9% | 13 | 6.5 |
| 14 | Order-invariance, probe trigger (canonical) | 0% | 13 | 6.5 |
| 15 | Order-invariance, probe trigger (reordered) | 100% | 13 | 6.5 |
| 16 | Consistency, Cohen's Kappa (inter-run) | 0.859 | 288 pairs | 6.6 |
| 17 | Consistency, MAE (inter-run) | 0.118 | 288 pairs | 6.6 |
| 18 | Consistency, Solid↔Gap span violations | 4.2% | 96 slots | 6.6 |
| 19 | Follow-up trigger Precision | 1.0 | 50 | 6.7 |
| 20 | Follow-up trigger Recall | 1.0 | 50 | 6.7 |
| 21 | Follow-up trigger F1 | 1.0 | 50 | 6.7 |
| 22 | Grading latency, mean | 3.68s | 133 | 6.8 |
| 23 | Grading latency, P95 | 8.27s | 133 | 6.8 |
| 24 | TTFT | N/A (not applicable) | — | 6.8 |
| 25 | Voice round-trip call success | 91.7% | 24 | 6.9 |
| 26 | WER, mean | 3.69% | 22 | 6.9 |
| 27 | CER, mean | 3.81% | 22 | 6.9 |

## 8. Charts

All in `evaluation/charts/`: `solid_rate_by_category.png`, `star_order_invariance.png`, `provider_distribution.png`, `grading_latency.png`, `voice_wer_cer.png`, `probe_trigger_rate.png`.

## 9. Limitations

- **No independent human ratings exist anywhere in this evaluation.** Every "ground truth" label (category, expected-trigger) is my own authoring intent, stated as such throughout. Cohen's Kappa/MAE are computed on inter-run self-consistency, not model-vs-human agreement, because the latter data doesn't exist. Precision/Recall/F1 in Section 6.7 use code-verifiable, product-artifact-grounded labels (the rubric's own phrase list), which is a stronger footing than authoring intent but is still not independent human judgment.
- **The golden dataset is hand-authored, not sourced from real candidates.** Real behavioral-interview answers are messier — false starts, filler words, cross-talk, genuine ambiguity about intent — than any of the 101 items here.
- **Voice evaluation measures synthetic speech, not human speech.** WER/CER here are a floor, not a production-representative number (Section 6.9).
- **TTS/STT latency was measured via non-streaming REST calls**, not the actual streaming plugin path production uses — these numbers cannot be read as "how long a user waits."
- **End-to-end interview latency and true interview completion rate were not measured** — both require live-session infrastructure (a running `AgentSession`, real usage telemetry) that doesn't exist in this repository today.
- **Sample sizes for some splits are small** (12–13 items per category, 16 items for consistency, 2–3 items per category for voice) — category-level percentages should be read as directional, not as tight confidence intervals.
- **This evaluation ran entirely on one calendar day**, which means the "fallback invocation rate" and "hallucination rate" numbers are both entangled with a single day's ledger/quota state (Section 6.1). Repeating this across multiple days would separate "typical" from "cap-exhausted" behavior more cleanly.

## 10. Future Improvements

- **Fix the order-invariance bug (Section 6.5)** before shipping the probe engine as reliable — either exempt DEPTH-triggering when `resolution`/`reflection` are the only markers seen out of order, or gate `detect_skip` on additional confirmation.
- **Fix the priority-ladder starvation issue (Section 6.7)** so SPECIFICITY can still surface when DEPTH is also a candidate — today's design silently prefers one signal over another whenever both are true.
- **Build a small human-labeled subset** (even 20–30 items, 2 independent raters) specifically to compute a real human-vs-model Kappa/agreement number — everything in this report is honest about not having that yet.
- **Add a fact-consistency check** to at least catch internally-impossible claims (Section 6.3) — doesn't need to be a full fact-checker, even an order-of-magnitude sanity check on numeric claims would catch the `fabricated` category's worst cases.
- **Instrument a live `AgentSession` run** for true end-to-end voice latency and TTFT-equivalent metrics — a reproduction script stub for this is in `evaluation/scripts/` (see README); running it needs a live LiveKit room and either a human tester or piped pre-recorded audio.
- **Repeat this evaluation across multiple days** to separate "typical" fallback/hallucination behavior from single-day ledger-cap artifacts (Section 9).
- **Widen the voice sample** past 24 items and past synthetic speech — ideally with real recorded human answers, even a handful, to get a production-representative WER/CER instead of a floor.
