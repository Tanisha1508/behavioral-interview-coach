# Constraints (non-negotiable)

These are pulled in substance from `Behavioral_Interview_Coach_Spec.md`. If any planned code would violate one of these, stop and reconsider before writing it, regardless of what seems locally convenient.

## Stack
- Free-tier or open-source only. No paid APIs, ever, for any reason, including "just to test."
- LiveKit Agents is the orchestration and turn-taking foundation. Do not hand-roll raw audio capture, VAD wiring, or barge-in logic as a substitute or workaround.
- Gemini 2.5 Flash (Google AI Studio free tier) for probing and grading LLM calls. Groq free tier is the failover on 429s, not a replacement primary.
- STT/TTS: Deepgram + ElevenLabs plugins at launch tier, faster-whisper + Kokoro as local fallback nodes. Swapping between them is a config change, never a rewrite.

## Round profiles
- Exactly five profile names, spelled exactly this way: `pm`, `consulting`, `mba_admissions`, `tech`, `others`.
- The engine reads `RoundProfile` config values (time budget, we-ratio threshold, emotional-probe weight, patience, length band, depth style). It never branches on a format name in code (no `if profile == "consulting"` anywhere in engine logic). Adding a new format must only require a new config file.
- Consulting-style specifics (emotional probing, one-story-deep, lower we-ratio threshold) are values inside `consulting.yaml`, not special-cased architecture.

## Persona and round composition
- Round profile owns format rules. Persona owns interviewer style within those rules. Neither overrides the other's fields.
- Bio-tag extraction: every tag must cite a verbatim phrase from the pasted bio or default to UNKNOWN. No inference from absence.
- Persona parameter adjustments from firm_type/seniority are bounded: max 0.10 weight shift, max 0.2 eagerness shift.

## Context partitioning (hard architecture rule)
- The live interviewer sees only: question + persona + live transcript. Never the user's resume, JD, or stories/brag doc.
- The grader and Coach may see whatever docs the user supplied this session, any subset, no fixed requirement.
- This wall must be implemented in `session/manager.py` (or equivalent), not left to prompt instructions alone.

## Non-goals (do not build these)
- No technical/case interview practice (coding, system design, case math).
- No live scraping of question sites or interviewer profiles. User pastes intel only.
- No voice cloning of real individuals. Preset voices only, no audio-sample input path.
- No end-user accounts or billing. (Scope change 2026-07-09: hosting IS in scope; a hosted browser client is part of the MVP. Free tiers only: LiveKit Cloud free tier for the agent worker, a free static host for the frontend.)
- No multi-agent frameworks (LangGraph, CrewAI, etc.). One interviewer, one grader, one coach, sequential handoffs. The probe hot path must run under 10ms on local rules, not through an agent framework.

## Grading and probing
- Probe-logic and grading-logic never share code. The probe engine never grades; it only logs `ProbeRecord`s and analyzer flags.
- Grading evidence quotes must be verbatim string matches to the transcript. Missed-ammo items must be verbatim string matches to the source doc. No paraphrased "evidence."
- Engine never interrupts before 25 seconds into an answer, never twice within 40 seconds, never leads the witness during silence.

## Writing and documentation style (applies to README, DECISIONS.md, code comments)
- Direct, active voice. No em dashes. No "not X but Y" constructions.
- Banned words: delve, landscape, synergy, leverage, robust, streamline, cutting-edge.

## Usage discipline
- This is running against limited weekly usage. If a task requires far more iteration than expected (repeated failed attempts on the same problem), stop and report rather than retrying indefinitely.
- Prefer targeted edits over regenerating whole files.
