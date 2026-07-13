<p align="center">
  <img src="web/app/icon.svg" alt="Owl mascot" width="72" />
</p>

# Behavioral Interview Coach

**Live demo: [behavioral-interview-coach-psi.vercel.app](https://behavioral-interview-coach-psi.vercel.app)** (sign in with Google, allow the mic, speak your answers)

A voice-native mock interviewer that asks real behavioral questions, listens to your spoken answer, probes it the way a trained interviewer would, and grades your delivery on a 6-dimension rubric with verbatim evidence. Built on LiveKit Agents. Free-tier and open-source stack only.

![Behavioral Interview Coach](https://behavioral-interview-coach-psi.vercel.app/opengraph-image)

## What it does

- **Drill mode**: one question at a time. Speak a full answer, get a scored card after each one: 6 rubric dimensions (structure, specificity, I vs we, quantification, length, reflection), missed ammo from your own documents, and an on-demand rewrite of the answer you gave.
- **Simulation mode**: a timed set. The interviewer paces questions against the clock, drops questions when answers run long (and tells you), then delivers one debrief with per-answer grades and cross-answer patterns.
- **Coach mode**: upload a resume and JD. Get a tailored question pack, a story-coverage map (which questions your prepared stories already answer), spoken game plans, and rubric-aligned rewrites.
- **Probing engine**: mid-answer signals (vagueness, we-heavy phrasing, missing numbers, rambling) queue targeted follow-up probes that fire after your answer, never over it.
- **Persona layer**: paste an interviewer bio; the tool extracts tags with a verbatim-evidence rule and tunes probe mix, intensity, pacing, and voice within bounds.
- **Animated interviewer**: an owl mascot is who you talk to. It breathes and blinks while it listens, tilts into a thinking state while it scores, and its beak and halo move in time with its real voice while it speaks. Theme-aware and reduced-motion friendly.
- **One-time setup and profile**: a skippable first-run wizard captures your background, target round, and documents once. A Profile page edits them later, and the New Session form pre-selects your round and reuses your saved documents. Your background and goal tune the questions you are asked and the coaching you get, never the live interviewer.
- **Accounts and history**: Google sign-in, with a guest mode for a quick try. Sessions, per-answer scores, transcripts, rewrites, and saved documents persist to your account; a history page tracks progress over time. Close a score card by accident and a control reopens it until the next question.

## Architecture

| Piece | Stack | Hosting |
|---|---|---|
| Voice agent | Python, LiveKit Agents 1.6 (Deepgram nova-3 STT, Gemini 2.5 Flash grading with Groq failover, Deepgram Aura / ElevenLabs TTS, Silero VAD) | LiveKit Cloud |
| Web app | Next.js, LiveKit components, Tailwind | Vercel |
| Accounts and data | Supabase (Google auth, Postgres with row-level security) | Supabase |

Design rule worth knowing: a context wall. The live interviewer never sees your documents, background, or goal; only question generation, the grader, the missed-ammo pass, and the coach do. What shapes the interview is which questions get generated, not text fed to the interviewer at runtime (the interview path has no LLM). The agent writes history rows over the Supabase REST API with a service key; the browser reads them with the anon key under row-level security.

## Privacy

Pasted docs (resume, JD, stories) transit the Gemini API on the free tier. Fine for personal use, disclosed here for anyone else. No voice cloning: preset voices only, and there is no audio-sample input path.

## Run it yourself

Agent:

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env   # fill in your own keys
python -m src.agent console   # Drill session in console mode, no web needed
python -m src.coach.cli       # Coach mode: pack + coverage + rewrites
```

Web app:

```bash
cd web
npm install
cp .env.example .env.local    # LiveKit + Supabase keys
npm run dev
```

Keys needed (all free tier): `GOOGLE_API_KEY` (AI Studio), `GROQ_API_KEY`, `DEEPGRAM_API_KEY`, `ELEVENLABS_API_KEY`, LiveKit credentials, and a Supabase project (run `supabase/schema.sql` in its SQL editor) if you want accounts.

Tests: `python -m pytest tests/` (130 tests cover the turn-end decision loop, probe queueing, the interrupt-then-command flow, grading handoff, simulation pacing, and cloud persistence).

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

Full product spec: `Behavioral_Interview_Coach_Spec.md`. Session operating rules: `CLAUDE.md` and `docs/`.
