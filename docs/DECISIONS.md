# Decisions log

Record every place the spec was genuinely ambiguous and you picked a simple default. One entry per decision, in this format:

```
## [date] — [short title]
**Item:** which scope item or spec section this relates to
**Ambiguity:** what exactly was underspecified
**Decision:** what you chose
**Why:** why this was the simplest option that satisfies CONSTRAINTS.md
```

Do not log decisions that the spec already made explicitly. This file is for genuine gaps only. If unsure whether something counts as a gap versus something already decided, re-check the spec section before logging.

---

## 2026-07-09 — interrupt_eagerness gate direction
**Item:** Scope item 3, spec 3.3 step 4 vs spec 4.3 field semantics.
**Ambiguity:** The pseudocode says threshold = base_confidence * eagerness with fire-when-above, which makes eagerness above 1 interrupt LESS. Spec 4.3 states the opposite: above 1 interrupts sooner.
**Decision:** threshold = base_confidence / eagerness. The 4.3 field semantics win over the pseudocode arithmetic.
**Why:** 4.3 is the stated product behavior and the 4.4 mapping table depends on it (consulting partner eagerness 1.3 is meant to be aggressive; recruiter 0.6 is meant to be gentle). The multiplication reading breaks both.
**Update 2026-07-09:** User approved correcting the spec itself. Section 3.3 step 4 now reads base_confidence / persona.interrupt_eagerness with a clarifying comment. Spec and implementation agree; this entry stays as the record of the original conflict.

## 2026-07-09 — trailing time windows without word timestamps
**Item:** Scope item 3, spec 3.2 analyzers (trailing 60s, 45s, 30s windows).
**Ambiguity:** Partial transcripts carry no per-word timestamps, so time windows over transcript text are unmeasurable directly.
**Decision:** Approximate trailing windows by word count at 2.5 words per second.
**Why:** Standard speaking-rate constant, no extra dependencies, and thresholds stay tunable in one place (analyzers.WORDS_PER_SECOND).

## 2026-07-09 — candidate confidence constants
**Item:** Scope item 3, spec 3.3 step 4 (best.confidence never defined).
**Ambiguity:** The pseudocode gates on candidate confidence but never assigns confidences.
**Decision:** Fixed per-type constants following the priority ladder: REDIRECT 0.90, DEPTH 0.80, SPECIFICITY 0.75, OWNERSHIP 0.70, QUANTIFY 0.65, base gate 0.6.
**Why:** With base 0.6 and eagerness bounds 0.6 to 1.3, this makes neutral personas fire all rule-confirmed probes, low-eagerness personas queue instead, high-eagerness fire everything. Matches the 4.4 table behavior with the fewest moving parts.

## 2026-07-09 — where probe_mix applies
**Item:** Scope item 3, spec 3.3 highest_priority vs spec 4.3 probe_mix sampling.
**Ambiguity:** 3.3 picks live-interrupt probes by strict priority; 4.3 calls probe_mix "sampling weights when multiple probe types are eligible". Both cannot govern the same choice.
**Decision:** Live interrupts use the 3.3 priority ladder. probe_mix weights the choice among queued probes at a natural pause, and bank sampling via topic emphasis.
**Why:** Keeps 3.3 pseudocode intact where it is explicit, and gives probe_mix the exact role 4.3 describes in the remaining eligible-set decisions.

## 2026-07-10 — what the Drill does on FOLLOWUP_OR_NEXT
**Item:** Scope item 5, spec 3.3 on_endpoint pseudocode.
**Ambiguity:** The pseudocode returns ASK(FOLLOWUP_OR_NEXT) for an incomplete answer at an endpoint, but never says what that ask contains or how a single-question Drill rep maps it. The first implementation mapped it to grading, so any patience_ms pause (600ms on pm) sent the answer to the grader. Live rep 2026-07-10 graded a one-word answer 0.8s in.
**Decision:** In the Drill runner: a pause inside the first 25s keeps listening silently. A later pause asks one neutral wrap check ("Anything you want to add, or is that your answer?"). A pause after the wrap check, an explicit done phrase, a spec-complete answer, or a second deflection hands off to the grader.
**Why:** 25s reuses the never-interrupt-the-hook constant instead of a new threshold. One wrap check resolves "pausing" versus "finished" without leading the witness, and the double-deflection path keeps its spec 3.4 move-on behavior. Tests: tests/test_agent_runner.py.
**Update 2026-07-10 (second live rep):** Firing the wrap check at the first post-25s endpoint still cut the candidate off, because endpoints arrive at every speech-burst gap (every 1 to 3s in practice). Briefly revised to a 4s sustained-silence timer. The same rep showed the retry/next/end prompt had no reply handler, so "end" re-entered the answer loop and graded again; the runner now has a verdict mode after grading (retry re-asks the same question, next advances or ends when the queue is empty, end shuts the session down via ctx.shutdown).
**Update 2026-07-10 (user rule, final):** User rejected the silence timer: candidates may pause for a minute mid-answer, and any time-based end-of-answer rule breaks the natural feel. The rule is now: no timer of any kind decides an answer is over. The interviewer waits through pauses indefinitely. An answer ends only on an explicit done phrase ("that's my answer", "I'm done", "that's it"), a spec-complete answer (resolution and reflection seen), or spec 3.4 double deflection. The session opening tells the candidate the done-phrase convention. Do not reintroduce end-of-answer timers in the web client either.

## 2026-07-12 — Coach mode is voice-native
**Item:** Coach mode (built as CLI in item 6), web client (item 11). User product decision; spec updated (features list, wizard flow, MVP demo).
**Ambiguity:** None; the spec had Coach as written-output-only and the user corrected that: Coach is a voice agent too, grounded in the user's documents.
**Decision:** Top-level mode choice INTERVIEW | COACH in the web setup. A Coach session reuses the item 6 engines untouched: generate_pack and coverage_map run at session start, results publish to the browser as a coachpack data message and render on screen, the coach speaks a short summary, then holds a voice conversation. Each user turn goes through the existing llm client (ledger + Groq failover) with resume, JD, stories, pack, coverage, and recent history in the prompt; replies stay short to protect the ElevenLabs credit cap. The Coach sees all supplied docs (spec context table already says so). "End session" ends it like the Drill verdict path.
**Why:** Reusing the drill session plumbing (same STT/TTS, same RPC setup handshake, same runner pattern with StopResponse) makes voice Coach an additive runner, not a second architecture. The CLI stays for offline use.

## 2026-07-11 — MVP interview shape: listen fully, then feedback
**Item:** Scope items 5 and 9. User product decision.
**Ambiguity:** None; this supersedes the follow-up flow for the MVP. User direction: the agent listens to the whole answer, then gives feedback; probing felt rigid because behavioral answers do not follow a fixed sequence; invest in the rubric instead.
**Decision:** engine.max_followups in settings.yaml, 0 for the MVP: after the done phrase the runner grades immediately, and queued probes drop. The probe engine, analyzers, and follow-up flow stay built and tested behind the flag; raising the number re-enables post-answer follow-ups. The structure rubric row now grades followability (context, what you faced, what you did, how it ended, in any order that flows) and forbids penalizing deviation from the canonical arc. All interviewer speech also prints to the CLI so the question can be read, not just heard.
**Why:** One config value keeps the MVP simple without deleting spec machinery, matching how every earlier scope decision was kept reversible. The rubric carries the evaluation weight the probes used to.
**Update 2026-07-11:** User chose two selectable modes instead of a single fixed shape. SessionConfig.followup_mode ("listen" default, "probing") is asked in the setup wizard. listen always asks zero follow-ups; probing asks up to engine.max_followups (2) after the answer. The runner resolves the cap per session.

## 2026-07-10 — no mid-answer probes: follow-ups only, after the answer
**Item:** Scope item 5, spec 3.3 live-interrupt machinery. This is a user product decision, not a spec gap.
**Ambiguity:** None in the spec; the spec prescribes mid-answer interrupts. The third live rep showed why they fail in practice: a QUANTIFY probe interrupted at 83s even though the candidate said "six of forty respondents" at 40s (trailing-window false positive), the candidate's trailing words got judged as a deflection within 3s, and the reask used a specificity template on a quantify probe. User verdict: interruption is not working; answer fully first, follow-ups after.
**Decision:** The runner never interrupts. INTERRUPT actions from the engine queue as follow-ups (deduped by type). Mid-answer endpoints do nothing at all. After the done phrase, queued probes are asked one at a time (cap MAX_FOLLOWUPS = 2, replies awaited under the same done-phrase rule), then grading. The engine's interrupt machinery stays intact and tested; the policy lives in src/agent.py.
**Why:** Runner-level policy keeps the spec engine unchanged and reversible while matching how the user wants the interview to feel. Related fixes from the same rep: missing_numbers now scans the whole answer instead of a trailing 45s window, REASK_HARDER is per probe type, grader evidence is verbatim-checked against continuous candidate speech (STT fragment boundaries were dropping every quote), and the quantification rubric row grades on applicability so stories without natural metrics are not forced to Gap. The spec text still describes mid-answer probing; update it when the user confirms.

## 2026-07-09 — length_band_s for non-pm profiles
**Item:** Scope item 2, spec Section 3 RoundProfile.
**Ambiguity:** The spec states the length band only for pm (90 to 150s). Consulting, mba_admissions, tech, and others have no stated band.
**Decision:** Consulting [120, 210], mba_admissions [100, 180], tech and others reuse pm's [90, 150]. Band top equals the profile's time_budget_s where one was stated.
**Why:** time_budget_s is the spec's own soft limit per profile, so ending the scoring band there is the simplest consistent rule and needs no new parameters.

## 2026-07-09 — depth_style for stub profiles
**Item:** Scope item 2, spec Section 3 RoundProfile.
**Ambiguity:** The spec assigns ONE_STORY_DEEP behavior to consulting and describes BREADTH as the default many-stories style, but never states depth_style for mba_admissions, tech, others.
**Decision:** BREADTH for all three.
**Why:** Those loops ask many questions per session in practice, and BREADTH is the spec's default framing. Config-only change if wrong.

## 2026-07-12 — TTS quota fallback: Groq Orpheus, not Kokoro, not multi-account
**Item:** Web test pass; agent went silent mid-run (ElevenLabs key quota 8500 exhausted, quota_exceeded surfaced as "no audio frames pushed").
**Ambiguity:** FALLBACKS.md prescribed stopping and asking before wiring any TTS fallback.
**Decision:** LiveKit FallbackAdapter with ElevenLabs primary and Groq Orpheus (canopylabs/orpheus-v1-english) secondary, per user. User explicitly ruled out local Kokoro ("no local"). Rotating multiple free ElevenLabs accounts was proposed by user and rejected: violates ElevenLabs ToS and puts the real account at ban risk; two-provider failover gives the same resilience legitimately.
**Why:** Groq key already exists (LLM failover), plugin swap is small, and the hosted demo needs TTS that degrades instead of going silent. Voice preset mapping: George→daniel, Sarah→autumn, Matilda→hannah, Adam→troy (all verified synthesizing 2026-07-12). Orpheus caps requests at 200 chars; the agents framework feeds sentences, which stays under. Terms acceptance on the Groq console was required once (done).

## 2026-07-13 — simulation planner numbers and underrun behavior
**Item:** M6 Simulation, spec 2.2 session planner.
**Ambiguity:** The spec gives per-question estimates as ranges (BREADTH 5 to 7 min, ONE_STORY_DEEP 15 to 20 min per story) and says the planner computes a question count and drops questions on overruns. It never states which number inside the range plans the count, nor what happens when answers run short.
**Decision:** The midpoint (360s / 1050s) plans the initial count; the low end (300s / 900s) is the live gate for whether one more question still fits after each answer. Wrap reserve is exactly the spec's 3 minutes. When answers run short the session simply ends early; no reserve questions are pulled in beyond the planned set.
**Why:** Midpoint planning plus low-end live checks needs no new parameters and makes dropping conservative (a question is only dropped when even its fastest realistic version no longer fits). Ending early on fast answers matches real loops, where the interviewer does not invent questions to fill time, and keeps the planner one function pair (plan, on_overrun) as the spec file layout prescribes.

## 2026-07-13 — simulation debrief mechanics
**Item:** M6 Simulation, spec 2.2 end-of-session debrief.
**Ambiguity:** The spec names the debrief contents (per-question grades, cross-answer patterns, missed ammo across the set) but not how grading is scheduled, how patterns are derived, or how the session closes after the debrief.
**Decision:** Each answer is graded in a background task while the candidate answers the next question; the debrief awaits them all. A failed grade marks that answer "not scored" and the debrief says so. Cross-answer patterns are exact counts computed in code (a dimension weak in at least two answers and at least half the graded set), never LLM impressions. Missed ammo deduplicates on the fact text across answers. After the spoken debrief the session waits and the only accepted verdict is end; retry and next are Drill moves and stay disabled. No rewrite button in simulation.
**Why:** Background grading makes the debrief near-instant at session end with the same total LLM calls. Code-computed counts follow the same principle as the verbatim evidence check: numbers shown to the user are verified, not generated. Holding the room open until "end" lets the user read the debrief panel, which clears on disconnect by design.

## 2026-07-12 — TTS fallback provider: Deepgram Aura replaces Groq Orpheus
**Item:** TTS fallback (same day as the FallbackAdapter decision above).
**Ambiguity:** Groq Orpheus audio was garbled live. Bisected with the user listening to each pipeline stage: direct API output itself is intermittently garbled and degrades as utterances grow (autoregressive drift; raw curl output confirmed broken before any LiveKit code). Interview mode mostly survived (short lines); coach mode (long paragraphs) was unusable. Not fixable client-side.
**Decision:** Fallback chain is ElevenLabs -> Deepgram Aura (aura-2 voices; George->apollo, Sarah->thalia, Matilda->helena, Adam->arcas, all verified). Deepgram key already in the stack for STT; its signup credit covers TTS. Groq stays LLM-failover only; the livekit groq plugin and its 24k sample-rate patch were removed.
**Why:** Deepgram Aura is non-autoregressive-drifting production TTS, needs no new account or key, and one clean sample was verified by ear against the same sentence that garbled on Orpheus.

## 2026-07-13 — accounts and hosting stack (scope item 15, user-approved)
**Item:** New scope item 15 (user login, saved docs, saved rewrites/gaps, activity log) plus item 12 hosting.
**Ambiguity:** The spec has no accounts layer; the user requested one, and hosting providers were open.
**Decision:** Supabase (free) for auth + Postgres, Google sign-in only, Vercel Hobby for the web app, LiveKit Cloud Build plan for the agent worker (verified: 1 agent deployment, 5 concurrent, 1,000 agent min/month free). Guest mode stays: unauthenticated visitors can run sessions, signing in unlocks saving and history. Agent writes sessions/answers via the service role key over plain REST (no new Python SDK); the browser reads with the anon key under RLS (every table user-private). Local data/sessions JSON stays as debug record and guest fallback. One new web dependency allowed: @supabase/supabase-js + @supabase/ssr. Execution order and steps are pinned in docs/RUNBOOK-DEPLOY.md (Phase A deploy baseline, B Supabase setup, C six wiring steps).
**Why:** One free account covers login, database, and history. Google-only sign-in avoids password handling entirely. Guest mode keeps the portfolio link frictionless for recruiters. REST-from-agent avoids adding an SDK to the worker image. User approved the accounts and sign-in method in chat 2026-07-13; deploy-first order chosen so the riskiest unknown (hosted worker) is retired while the app is small.

## 2026-07-13 — design pass identity (item 13, first slice)
**Item:** Item 13 design pass; user asked for "nice color, look" and the interrupt button beside END CALL.
**Decision:** Token-level restyle in globals.css: indigo primary (oklch hue 275) on warm paper light theme, deep navy dark theme; semantic score colors (green/amber/red) untouched. Interrupt is an amber pill with a hand icon, identical shape to END CALL and placed immediately before it: amber signals "pause the interviewer", red stays reserved for ending the session. Implemented by threading an onInterrupt prop through the template control bar rather than overlaying a floating button.
**Why:** Changing tokens restyles every shadcn component at once with zero component rewrites, the lowest-risk way to reskin a tested surface. The control-bar placement was an explicit user instruction; amber-vs-red is standard severity coding.

## 2026-07-13: brand identity (item 13, user-approved)

- Mascot: a wise owl interviewer (round glasses, ear tufts, amber beak),
  hand-drawn SVG in web/components/app/owl-mascot.tsx. Colors ride the
  theme tokens (var(--primary), var(--card)) so it adapts to dark mode;
  the favicon (app/icon.svg) and OG image use literal hex equivalents.
  User picked owl over robot/abstract/mic options.
- Vibe: calm professional; the indigo + warm paper palette stays.
- Landing: slim hero above the setup card (owl, name, tagline, three
  feature chips), not a separate marketing page; zero clicks to the form.
  User picked this over a full scrolling landing page.
- Header: owl + wordmark replaces the LiveKit logo; "Built with LiveKit
  Agents" stays as a muted credit (true, and it reads well for a
  portfolio piece).
