# Behavioral Interview Coach

Voice-native mock interviewer that probes mid-answer and grades spoken delivery on a 6-dimension rubric with verbatim evidence. Built on LiveKit Agents. Free-tier and open-source stack only.

Full product spec: `Behavioral_Interview_Coach_Spec.md`. Session operating rules: `CLAUDE.md` and `docs/`.

## What it does

- **Drill mode**: ask a question by voice, listen, interrupt with targeted probes (specificity, ownership, quantify, redirect), grade the answer on 6 dimensions plus a missed-ammo report, deliver spoken feedback.
- **Coach mode**: paste a resume and JD, get a tailored question pack, a story-coverage map, and rubric-aligned answer rewrites.
- **Persona layer**: paste an interviewer bio; the tool extracts tags with a verbatim-evidence rule and tunes probe mix, intensity, pacing, and voice within bounds.

## Privacy

Pasted docs (resume, JD, stories) transit the Gemini API on the free tier. Fine for personal use, disclosed here for anyone else. The live interviewer never sees your docs; only the grader and Coach do. No voice cloning: preset voices only, and there is no audio-sample input path.

## Setup

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env   # fill in your own keys
```

Keys needed (all free tier): `GOOGLE_API_KEY` (AI Studio), `GROQ_API_KEY`, `DEEPGRAM_API_KEY`, `ELEVENLABS_API_KEY`, LiveKit credentials if using Cloud.

## Run

```bash
python -m src.agent console   # Drill session in console mode
python -m src.coach.cli       # Coach mode: pack + coverage + rewrites
```

## Eval results

Run 2026-07-09 against gemini-2.5-flash (spec Section 6). Reproduce with
`python -m evals.probe_cases.cases`, `python -m evals.consistency`,
`python -m evals.ammo_check`.

| Metric | Result | Pass bar |
|---|---|---|
| Grading consistency (clean answer) | 6/6 dimensions stable across 5 runs, no Solid-to-Gap span | 5/6 stable, no span |
| Grading consistency (borderline answer) | 6/6 dimensions stable across 5 runs, no Solid-to-Gap span | 5/6 stable, no span |
| Probe cases: correct type | 5/5 (Vague, We-heavy, Rambling, Strong, Silent) | 5/5 |
| Probe cases: within timing window | 5/5 (consulting fires OWNERSHIP at 32s vs pm 40s on the same script) | 4/5 |
| Missed-ammo accuracy | 4/4 absent facts flagged, all verbatim, 0 hallucinated | exactly 4, 0 hallucinated |
| Probe hot path | 0.19 ms mean per partial | under 10 ms |
| Pre-25s interrupts (20 randomized runs) | 0 | 0 |
| LLM failover | Gemini 429 hands off to Groq in-call; ledger cap routes directly to Groq | no dropped turn |
| Human agreement | pending (needs a scored live session) | 4/6 exact match |
| Turn latency p50 / p95, barge-in yield | pending (measured during live Drill rep) | under 2s / report; under 200ms |
