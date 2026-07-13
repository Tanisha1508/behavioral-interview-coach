# Behavioral Interview Coach

Portable mirror of `CLAUDE.md` for coding agents that read AGENTS.md instead of or alongside CLAUDE.md. Content is identical in substance.

A voice-native mock interviewer, built on LiveKit Agents, that probes candidates mid-answer and grades spoken delivery against a 6-dimension rubric. Full implementation detail is in `Behavioral_Interview_Coach_Spec.md` at this repo root.

## Read order, every session (new or resumed)

1. This file.
2. `docs/PROGRESS.md` — what is actually done and tested, not what a prior summary claimed.
3. `docs/DECISIONS.md` — ambiguities already resolved; do not re-decide them.
4. `docs/CONSTRAINTS.md` — non-negotiables, check every plan against this before writing code.
5. `docs/FALLBACKS.md` — known risk points and the prescribed action for each.
6. `Behavioral_Interview_Coach_Spec.md` — the full spec.

If PROGRESS.md shows items already done-and-tested, do not redo or "clean up" them unless the current task explicitly asks for it.

## The rules that always apply

- **Checkpoint discipline.** Work is organized into numbered scope items. For each: build it, run it, fix what's broken, confirm its done-criteria, update `docs/PROGRESS.md`, then stop and summarize before starting the next. Do not chain unverified items together.
- **Compact at checkpoints, not on a schedule.** Run `/compact` at the end of a verified checkpoint, not mid-task. State that matters belongs in the docs files on disk, not in conversational memory.
- **Credentials.** Never hardcode secrets. If a key or account is needed, stop and name exactly which one and why, then wait.
- **When something fails or is ambiguous**, check `docs/FALLBACKS.md` for a prescribed action before improvising. Full detail, including the recovery protocol for a regression, is there and in `docs/CONSTRAINTS.md`.

Everything else (detailed constraints, fallback-by-risk mapping, decision log format) lives in `docs/` and is read on demand, not repeated here.
