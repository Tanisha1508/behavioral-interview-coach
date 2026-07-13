# Fallbacks: known risks and prescribed actions

If one of these situations happens, do the prescribed action. Do not improvise a different fix, and do not silently route around the problem.

## LLM calls

**Gemini returns 429 (rate limited) mid-session.**
→ Fail over to Groq per the spec's `llm/client.py` design. Log the failover in the session, do not drop the turn. If Groq also fails, stop and report; do not retry Gemini in a tight loop.

**Gemini free-tier daily cap is hit.**
→ Stop. Report exactly what was being attempted and how many calls were made. Ask before continuing, do not switch to a paid tier or a different provider without asking.

## STT/TTS

**Deepgram or ElevenLabs free-tier credits run out during build or testing.**
→ Stop. Report current usage if visible. Ask before wiring the local fallback node (faster-whisper/Kokoro) early, since that's a larger change than it looks and should be a deliberate decision, not an automatic reaction.

**LiveKit's support for custom local STT/TTS nodes turns out immature or undocumented.**
→ Do not hand-roll low-level audio plumbing as a workaround. Report the specific limitation found and ask how to proceed. This was flagged as a [NEED: verify at build time] item in the spec; hitting it is expected, not a failure.

**Console-mode LiveKit agent won't run locally for environment reasons.**
→ Report the exact error. Do not switch frameworks or fall back to a fully custom pipeline without asking; that reverses a deliberate architecture decision.

## Probe engine

**An analyzer (vagueness, we-density, time-budget, etc.) produces obvious false positives during testing.**
→ Tune thresholds only within bounds the spec already documents (e.g., we_ratio_threshold per profile). Do not redesign the detection logic or add new analyzer types without asking; that's a spec change, not a bug fix.

**A probe fires that violates a hard rule (before 25s, twice within 40s, leads on silence).**
→ This is a real bug in the decision loop, not a tuning issue. Fix it as its own checkpoint per the recovery protocol in CLAUDE.md.

## Grading

**Grading consistency eval fails the threshold (Section 6 of the spec).**
→ Tighten rubric descriptors and auto-rules in `rubric.yaml` first, per the spec's stated fail-action. Do not change the grading prompt's core structure without asking.

**Missed-ammo report flags something not verbatim in the source doc (hallucinated item).**
→ This fails the eval by design and is a real bug. Fix the extraction logic; do not loosen the string-match requirement to make the eval pass.

## Spec ambiguity

**A [NEED] item in the spec turns out false, unverifiable, or contradicted by what's actually available (e.g., a free-tier limit is lower than assumed).**
→ Stop. Do not silently build around it with an assumption. Report what you found and ask whether to proceed with a workaround, wait, or change scope.

**Something is genuinely underspecified and none of the above apply.**
→ Pick the simplest option that satisfies `CONSTRAINTS.md`, record it in `DECISIONS.md` with reasoning, and proceed. This is the one case where you don't need to stop and ask, since the spec explicitly authorizes this pattern.

## Budget

**A single scope item is taking many more iterations than expected with no clear progress.**
→ Stop after a few failed attempts at the same fix. Report what's failing, what's been tried, and what you think the actual blocker is. Ask before continuing. Do not keep retrying variations indefinitely.
