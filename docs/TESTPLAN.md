# Web test plan

Seven manual runs covering every workflow on the web surface, run by the user
at http://localhost:3000. Status and findings live here; one-line summaries
also go to PROGRESS.md at each checkpoint. Diagnosis sources: the worker log
(scratchpad `agent_worker.log`) and `data/sessions/*.json` transcripts.

| Run | What it covers | Status |
|-----|----------------|--------|
| 1 | Core drill: listen mode, score card, rewrite, retry/end | PASSED 2026-07-12 |
| 2 | Probing: follow-ups, dodge loop, length isolation | PASSED 2026-07-12 |
| 3 | Resume pack source + form validation | PASSED 2026-07-12 |
| 4 | Own questions + pasted intel | PASSED 2026-07-12 |
| 5 | Persona bio | PASSED 2026-07-13 |
| 6 | Coach full loop + Practice-in-Drill + state reset | PASSED 2026-07-13 |
| 7 | Rage checks | PASSED 2026-07-13 (with fix) |
| 8 | Simulation: timed set, queue dropping, end debrief (M6 done-criterion) | PASSED 2026-07-13 |

Fixes shipped from runs 1-2 (details in PROGRESS.md): done-phrase hint on
banner, one-line spoken feedback, strict quantification applicability,
rewrite tabs + copy button, question counter, rubric.yaml parse regression
test, TTS FallbackAdapter (ElevenLabs -> Groq Orpheus) + sample-rate patch,
coach coverage legend, no-recall deflection detection.

## Run 1 — Core drill (defaults) — PASSED

Setup: Practice interview · Product Management · Listen · Question bank · 2
questions · no documents.

1. Answer Q1; pause 5+ seconds mid-answer (must stay silent); say "that's my
   answer".
2. Score card: 6 dimensions with evidence quotes; spoken feedback is one fix
   line plus rewrite-button mention.
3. Press "Show me the rewrite": notes tab + full answer tab + copy button.
4. Say "retry", re-answer, then "end". Clean exit, no warning toast.

Checks: question pinned with "Question 1 of 2" and done-phrase hint; no
interruptions; verdict prompt states position; "next" not offered on the
last question.

## Run 2 — Probing mode — PASSED

Setup: Practice interview · Product Management · Probing · Question bank · 1
question · no documents.

1. Weak answer on purpose: all "we", no numbers, one vague claim ("I aligned
   stakeholders"). Pause 5+ seconds once. Say "that's my answer".
2. Follow-up 1 must arrive only after done, and target something actually
   said.
3. Dodge it ("I don't really remember, honestly. That's my answer.") ->
   expect one harder re-ask of the same probe.
4. Dodge again -> expect give-up (different follow-up or scoring), never a
   third identical probe.
5. One combined card; Specificity forced to Gap by the double dodge; Length
   graded on the main answer only.
6. Say "end".

## Run 3 — Resume pack + validation

Setup: Practice interview · your real target round · Listen · Questions
from: "My resume (pack)".

1. VALIDATION FIRST: leave Resume empty, press start -> must be blocked with
   a clear message, no connection attempt.
2. Upload your resume (.pdf) -> field collapses to a filename chip with View
   text / Remove. Press View text once: extracted text must look like your
   resume, not garbage.
3. Optionally add the JD (improves question relevance and enables ammo
   against it).
4. Start. First question should visibly trace to a real line on your resume.
5. Answer one question about a real project, deliberately leaving out a
   fact your resume states (a number, a named system). Say "that's my
   answer".
6. Score card: "Missed ammo" section must quote that fact verbatim from the
   resume with its doc source.
7. Say "next" through one more question to confirm pack questions vary, then
   "end".

Checks: every pack question grounded in a resume line; ammo quotes are
verbatim; the live interviewer never mentions resume content unprompted
(context wall: only grader and coach see documents).

## Run 4 — Own questions + pasted intel

Part A setup: Practice interview · any round · Listen · Questions from: "My
own questions" · type 2 questions, one per line · no documents.

1. Validation: with the textarea empty, start must be blocked.
2. Start. The exact questions you typed are asked, in order, verbatim.
3. Quick answer + done + "next" + answer + "end".

Part B setup (fresh session): Questions from: "Pasted intel" · paste a messy
forum-style block, e.g. "Interviewed at X last week. They asked me about a
time I disagreed with my manager, and something about a failed project.
Recruiter said expect a conflict question."

4. Validation: empty intel must block start.
5. Start. Extracted questions must be real interview questions from the
   paste (disagreed-with-manager, failed project, conflict), not the
   surrounding chatter.

## Run 5 — Persona bio

Setup: Practice interview · Consulting · Probing · Question bank · 1
question · paste a real LinkedIn "About" text into Interviewer bio.

1. Start. Interviewer style/voice should feel shaped by the bio (firm type,
   seniority).
2. Complete one rep normally.
3. Objective check afterwards: ask Claude to pull the extracted persona tags
   from the worker log; every tag must cite a verbatim phrase from the bio.

## Run 6 — Coach full loop

Setup: Coach session · Resume (required) + JD + stories doc.

1. Panel renders: 8-12 questions, coverage badges with the legend box
   (STRONG / PARTIAL / GAP = does your stories doc cover it).
2. Click a question: resume line + covering story (or the no-story
   explanation on a GAP) shown.
3. Get game plan: coach speaks it once, plan text lands in the panel.
4. Voice consult: ask "which story fits question three?" -> answer grounded
   in your documents; coach never quizzes you back.
5. On a GAP question press "Practice this in Drill" -> session restarts as a
   1-question listen-mode rep, documents carried over (missed ammo should
   appear on the card).
6. Finish the rep, say "end".
7. STATE RESET: start any fresh session immediately; it must not instantly
   end or show a stale coach panel.

## Run 7 — Rage checks

Setup: Practice interview · defaults · 1 bank question.

1. Say "repeat the question" mid-thought -> re-asked, transcript unpolluted
   (the repeat request must not appear in your answer).
2. Give a one-word answer, then "that's my answer" -> graded without crash;
   low scores are honest.
3. Use "umm... that's it" as the done phrase -> recognized.
4. After the card, mumble something that is not retry/next/end -> gentle
   re-prompt ("Say retry, next, or end"), no crash, no re-grade.
5. Say "end". Clean exit.

## Run 8 — Simulation mode (M6 done-criterion)

Setup: Practice interview · Product Management · Session type: Simulation ·
Duration: 15 minutes · Listen · Question bank · 4 questions · optionally add
your resume so the debrief has missed ammo.

The 15-min plan fits 2 questions up front (12 usable minutes at ~6 min per
question), so the intro should say "2 questions in 15 minutes".

1. Intro states the timed format, the question count, and that feedback
   waits for the end debrief.
2. Answer Q1 normally, say "that's my answer" -> the agent must say only
   "Thank you. Next question." and ask Q2. NO score card, NO spoken
   feedback between questions.
3. QUEUE DROPPING: to see a live drop, stretch Q1 past ~7 minutes (slow
   answer, long pauses are fine). If Q1 used up the remaining budget, Q2 is
   dropped and the debrief starts after Q1 instead.
4. Debrief: spoken summary (answer count, dropped count if any, first
   pattern, ammo count) and the debrief panel on screen: patterns across
   answers, per-question dimension chips (click to expand notes), missed
   ammo across the set.
5. After reading, say "retry" once -> must be told "Say end when you are
   done with the debrief" (no re-asking in a simulation).
6. Say "end". Clean exit.

Checks: no feedback or verdict prompt between questions; drop happens
silently mid-session and shows up as a dropped count in the debrief; the
session file is saved as type "simulation" with all reps.

## Findings log

- 2026-07-12 Run 1: five UX fixes + rubric.yaml parse crash (all fixed same
  day, see PROGRESS.md).
- 2026-07-12 Run 2: ElevenLabs quota exhaustion mid-run (fallback wired);
  Groq garble (sample-rate patch); deflection miss on probe-word echo
  (detector fixed). Loop behavior itself passed.
- 2026-07-12 Run 3 attempt 1: FAILED. Pack source compiled an empty queue: the
  interview entrypoint never called generate_pack/extract_questions (only the
  coach did), so the agent said "No questions compiled", pinned no question,
  and "repeat" had nothing to repeat. Fixed: pack (capped at 6) and intel
  questions now generated in the entrypoint and passed to compile_queue; an
  empty compile now falls back to 2 bank questions with a spoken note instead
  of a dead end. Affected web AND console for both pack and intel sources.
- 2026-07-12 TTS fallback saga resolved: Groq Orpheus garble was the model
  itself (autoregressive drift on longer utterances, proven from raw API
  output with user listening at each pipeline stage). Fallback swapped to
  Deepgram Aura (aura-2 voices); user confirmed live audio "all smooth
  perfect". Chain: ElevenLabs -> Deepgram. Groq is LLM failover only.
- 2026-07-12 Run 4A (own questions): PASSED, verified in logs (verbatim
  scripted questions in order, position prompts, both graded via the new
  gemini-3.1-flash-lite tier, rewrites on both, clean end). Earlier stuck-at-
  scoring failure led to: graceful grading-failure path (spoken retry/next/end
  instead of dead session), flash-lite middle tier in the LLM chain, graceful
  pack/coach startup failures. Minor watch: flash-lite sometimes speaks a
  strength instead of the fix line.
- 2026-07-12 Run 4B (pasted intel): extraction PASSED (all three real
  questions from a messy paste, chatter excluded; verified in session files).
  User caught a real bug on the unanswered last question: the rewrite
  fabricated an answer from earlier answers. Root cause: transcript_log was
  never cleared between questions, so grading and rewrite saw every prior
  answer (cross-question contamination, visible in all saved sessions).
  Fixed: transcript resets per question; and a <20-word answer now gets an
  honest refusal (spoken + on the card) pointing at retry or uploading
  documents, instead of an invented rewrite. 99 tests passing.
- 2026-07-12 Run 3 retest: PASSED, verified in logs. 6-question pack from
  resume (cap works), questions grounded in real resume lines, missed ammo
  quoted 5 + 4 verbatim resume facts, transcript isolation held between
  questions, context wall intact (no resume content in interviewer speech),
  clean end. Graded on the lite tier after the ledger-cap gating fix.
- 2026-07-13 Run 5 (persona bio, Consulting, probing): PASSED, verified in
  logs. Consulting length band live (99.5s answer -> NeedsWork, note cites
  120-210s band), Consulting probe mix live (OWNERSHIP then EMOTIONAL probe,
  both referencing the answer), cap respected, clean end. Persona tag
  grounding is enforced in code (uncited tags dropped); tags were not logged
  this run, persona logging added for future audits (item 14 will use it).
- 2026-07-13 Run 7 (rage checks): PASSED after one fix. Verified: one-word
  answer graded honestly (all Gap, evidence quotes all genuine), rewrite
  refusal fired live (no-docs variant), mumbled verdicts re-prompted without
  re-grading, umm-that's-it done phrase recognized, clean end, no crashes.
  Bug found: STT splits a repeat request into fragments; single-entry
  retraction left "I'm sorry. Can you repeat the question?" in the graded
  transcript (it surfaced as an evidence quote). Fixed with word-suffix
  multi-fragment retraction + transcript rebuild; regression test added.
  101 tests passing.
- 2026-07-13 Run 6 complete: coach loop verified across sessions (pack +
  coverage, game plans, voice consult, Practice-in-Drill with docs carried:
  5 ammo items on the handoff card, empty-answer rewrite drafted from docs
  live), state-reset confirmed by a clean fresh session (new 10-question
  pack, no stale panel, no instant end). ALL 7 RUNS PASSED.
  Post-pass addition: Interrupt button (web) + interrupt RPC with
  force=True, since agent speech is voice-interruption-proof by design.
- 2026-07-13 Run 8 (simulation, 15 min, PM, bank x4): PASSED, verified in
  logs and session file. Planner trimmed 4 requested to 2 ("simulation plan:
  2 of 4 questions in 15 min"), intro spoke the planned count, Q1 ran 544s
  and the drop fired live ("dropped 1 question(s) at 554s elapsed"), no
  feedback between questions, debrief spoken with dropped + ammo counts
  (6 verbatim resume facts across the set), non-end verdict re-prompted,
  clean end. Session saved as type simulation with the full rep. M6
  done-criterion met. UX feedback fixed same day: debrief rows looked
  clickable but gave no affordance; redesigned to need no clicks (notes +
  evidence auto-shown for non-Solid dimensions, Solid stays a green chip)
  and the debrief now lists the dropped questions' text ("Dropped for
  time"). 117 tests passing.
