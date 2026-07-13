# Test log

User-run test rounds on the hosted app, with the diagnosed root cause and the
fix for each finding. Newest round first. Status values: OPEN, FIX BUILT,
FIXED+VERIFIED (verified means re-tested live by the user), BY DESIGN.

## Round 2026-07-13 (evening, post silent-interviewer fix)

Six runs on behavioral-interview-coach-psi.vercel.app. Agent-side evidence
captured live via `lk agent logs` during the runs.

### 1. Question bank, 1 question — failed once, then worked

- Symptom: first run appeared dead, immediate retry worked.
- Root cause: cold-start race on the setup form send. Agent log shows
  "no web setup arrived in 15.0s; using default config". The web client
  retries the setup RPC for only ~2s (4 tries, 600ms apart); on the first
  job after a cold worker start the agent registers its RPC handlers later
  than that, so the setup send gives up before the agent can hear it.
- Fix: lengthen the web retry window to ~10s (web/lib/interview-setup.ts).
- Status: FIXED+VERIFIED (user re-test 2026-07-14)

### 2. Resume pack — "agent not joining", session ends itself

- Symptom: no voice, UI stuck on "your interviewer is joining", session ends.
  Flaky: same setup sometimes worked.
- Root cause: the agent joined within 1s every time (rooms 5937/2883 in the
  log), but in pack mode it generates questions from the resume with an LLM
  call BEFORE session.start(). Free-tier Gemini took ~26s; until
  session.start() no audio track exists, so the UI never shows the agent and
  the session gives up. Works or fails depending on how fast that one LLM
  call returns.
- Fix: mirror the coach pattern in the interview path — start the voice
  session first, speak "Give me a moment while I read your documents", then
  generate pack/intel questions (src/agent.py entrypoint).
- Status: FIXED+VERIFIED (user re-test 2026-07-14)

### 3. Own questions — scorecard slow; rewrite told an unrelated story

- Symptom A: scorecard took long to load. Root cause: free-tier LLM latency
  on the grading call; the agent already says "give me a few seconds".
  Status: BY DESIGN (watch: latency eval row in item 14).
- Symptom B: the full rewritten answer was unrelated to the question and to
  the actual spoken answer, even though the answer was substantive. Root
  cause: the answer_rewrite prompt says both "keep the candidate's true
  story" and "pull real facts from the docs into the rewrite"; with resume +
  stories doc attached the second instruction wins and the model swaps in a
  doc story wholesale. The rule (new story only when the answer has nothing
  tangible) was in the prompt but not enforced strongly enough.
- Fix: rewrite prompt hardened — a substantive answer's rewrite MUST retell
  the same story (docs may only add facts to it); a better-fitting doc story
  becomes a labeled "alternative story" note instead of replacing the
  rewrite (src/llm/prompts/answer_rewrite.txt).
- Status: FIXED+VERIFIED (user re-test 2026-07-14)

### 4. Pasted intel — agent said "my language model quota is exhausted"

- Symptom: answer given, then the agent claimed quota exhaustion and skipped
  scoring. User expectation: daily limits + LLM fallbacks should absorb this.
- Root cause: NOT quota. The fallback chain worked and the LLM call
  succeeded, but the model returned `"note": null` for one rubric dimension
  and pydantic validation crashed at grader.py:145. The except handler in
  _grade_and_feedback blames every failure on quota, so the spoken message
  was wrong.
- Fix: (a) sanitize null/wrong-typed fields inside each returned dimension
  so a sloppy model response cannot crash scoring; (b) only claim quota when
  the error is actually quota, otherwise say scoring hit a snag and offer
  retry/next/end (src/grading/grader.py, src/agent.py).
- Status: FIXED+VERIFIED (user re-test 2026-07-14)

### 5. Coach mode — slow to read materials; game plan queued behind speech; voice tone

- Slow read: two big LLM calls (question pack + coverage map) on free tier;
  the coach already says "Give me a moment to read your materials."
  Status: BY DESIGN.
- Game plan waited until the previous spoken answer finished: one voice,
  speech requests queue. Status: BY DESIGN.
- Tone sounded like "the fallback": it is not a failover artifact. Since the
  2026-07-13 TTS flip, Deepgram Aura IS the primary voice everywhere
  (ElevenLabs is out of quota until its monthly reset), so the coach's voice
  preset changed with it. Status: BY DESIGN (revisit when EL quota resets,
  per DECISIONS.md).

### 6. Own question, 1-word answer — scored with gaps; rewrite mismatched the question

- Scoring "teamwork, that's my answer" with gaps across dimensions is
  correct behavior. Status: BY DESIGN.
- Rewrite drafted from docs (correct per the user rule for empty/trivial
  answers) but picked a general-disagreement story for a question
  specifically about disagreeing with feedback. Root cause: the prompt never
  told it to match the question's specific competency or to name the story
  it chose.
- Fix: docs-draft mode must pick the story matching the question's specific
  competency (quoting the question's key phrase) and add a note naming which
  story it used and why (src/llm/prompts/answer_rewrite.txt).
- Status: FIXED+VERIFIED (user re-test 2026-07-14)

### Follow-up 2026-07-14: missed ammo relevance confirmed, prompt tightened

- User asked whether missed ammo matches the question asked. Verified from
  the re-test logs: all three scored cards showed on-topic ammo, and the
  influence-leadership card stayed inside the story the user told (Oracle),
  surfacing exactly its missing numbers. The verbatim filter also visibly
  dropped one paraphrased item in code.
- Relevance was prompt-enforced only (same gap class as findings 3/6), so
  the missed_ammo prompt got the same tightening on user request: match the
  question's specific competency, prefer facts from the story the candidate
  told, and drop any item whose relevance line cannot be written
  convincingly (src/llm/prompts/missed_ammo.txt).

## Round 2026-07-14 (onboarding + background/goal deploy)

### 7. Interrupt button then "end" did not end; agent spoke ahead

- Symptom: during spoken feedback the user clicks Interrupt and says "end";
  the session does not end and the agent keeps talking.
- Root cause: three compounding issues. (a) The Interrupt RPC only
  force-stopped the CURRENT non-interruptible say; _grade_and_feedback
  chains several says (feedback, then the verdict prompt), so cutting one
  advanced to the next ("speaking ahead"). (b) The user's "end" landed while
  that next say played, and agent speech is interruption-immune, so the mic
  turn was dropped. (c) Bare "end" only ends in the post-score verdict
  state; mid-feedback self.state is None and on_turn_complete early-returned.
- Fix: route Interrupt through the runner (note_interrupt). It sets a
  one-shot flag that (1) silences the rest of the feedback chain in
  _grade_and_feedback while still opening awaiting_verdict, so the agent goes
  quiet instead of talking over the user, and (2) makes the next short
  "end"/"stop" end the session in any state (_handle_interrupt_command);
  retry/next still flow through the verdict path. The score card is already
  on screen, so nothing visible is lost (src/agent.py).
- Tests: 3 added in tests/test_agent_runner.py (interrupt+end ends;
  one-shot; feedback silenced but verdict opened). 130 tests pass.
- Status: FIXED+VERIFIED (user re-test 2026-07-14).

### 8. No way to reopen the score card after closing it

- Symptom: closing the score card (Close, or an accidental backdrop feel)
  removed it with no way to bring it back; the scores were gone until the
  next question.
- Root cause: dismissCard set the card data to null, so the card and its
  rewrite were destroyed, not just hidden.
- Fix: split visibility from data in useInterviewState (card vs cardOpen).
  Close now only hides; a centered "View score card" pill reopens the same
  card (with its rewrite) until the next question clears it. Interrupt +
  finding 7 unaffected (web/hooks/useInterviewState.ts,
  web/components/app/view-controller.tsx). Web-only change.
- Status: FIXED+VERIFIED (user re-test 2026-07-14).

### 9. Owl showed "listening" while it was scoring

- Symptom: during grading the animated owl read Listening, not Thinking.
- Root cause: the interview AgentSession has no LLM and grading runs in a
  background thread, so LiveKit's voice-assistant state (which the owl reads)
  stays "listening" through scoring.
- Fix: the runner publishes an "agent_phase" data message ("thinking" when
  grading starts, "idle" at every exit); SpeakingOwl listens for it and
  overrides idle/listening with thinking (speaking still wins). Both sides
  deployed (src/agent.py, web/components/app/speaking-owl.tsx).
- Status: FIXED+VERIFIED (user re-test 2026-07-14).

### Watch items from this round

- Persona extraction (`extract_tags`) also runs an LLM call before
  session.start when a bio document is present. Small today, but it is the
  same stall shape as finding 2 if bios get long. Not changed in this round.
- Deepgram is now the single provider for both STT and TTS on one credit
  balance; revisit below ~$50 (DECISIONS.md 2026-07-13).


===

1. Resume-pack stall (src/agent.py): the voice session now starts and publishes audio immediately; if your setup uses documents, the interviewer says "Give me a moment while I read your documents" and only then runs the slow question generation. The runner attaches to the live agent once the queue is ready.
2. Grader crash + false quota message (src/grading/grader.py, src/agent.py): null or mistyped fields inside a returned rubric dimension are sanitized instead of crashing, and the spoken error now only blames quota when the failure really is quota; anything else says scoring hit a snag on my side, with the same retry/next/end options.
3. Rewrite story rules (src/llm/prompts/answer_rewrite.txt): a substantive answer's rewrite must retell your story — docs can only add facts to it; a better-fitting doc story appears as a labeled "alternative story" note. Thin-answer drafts must match the question's specific competency and name the story they used.
4. Setup send race (web/lib/interview-setup.ts): retry window lengthened from ~2s to ~10s so cold worker starts stop losing the setup form.

Everything is also logged in docs/TEST-LOG.md — all six of your findings with symptom, root cause, fix, and status (including the three that turned out to be by design: coach reading time, speech queuing, and the Aura voice, which is now the primary everywhere until ElevenLabs' quota resets).

==