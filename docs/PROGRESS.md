# Progress tracker

Update this file at the end of every checkpoint, before running `/compact` or stopping. Status values: `not-started`, `in-progress`, `done-and-tested`, `blocked`, `regression`.

Do not mark `done-and-tested` unless the item was actually run and its done-criteria confirmed. If a later session finds a `done-and-tested` item is actually broken, change its status to `regression`, add a note explaining what broke, and follow the recovery protocol in `CLAUDE.md`.

| # | Scope item | Status | Tested? | Notes |
|---|---|---|---|---|
| 1 | Repo structure per spec file layout | done-and-tested | yes | Tree matches spec 5.1. uv venv Python 3.12.13 (system is 3.9). All deps install; livekit-agents 1.6.4, plugins, google-genai, groq, faster-whisper, kokoro-onnx, ragas all import. ragas needed langchain pinned to 0.3 line, recorded in requirements.txt. rubric/rounds/banks/personas configs land in their own checkpoints. |
| 2 | Round profiles: pm + consulting full, mba_admissions/tech/others stubbed | done-and-tested | yes | 5 round yamls with spec values; pm bank 16 questions, consulting 12, stubs 2 each in valid format. RoundProfile/Question pydantic models + loaders in engine/state.py. 14 tests pass (tests/test_configs.py). Two gaps logged in DECISIONS.md (length bands, depth_style for stubs). |
| 3 | Core modules: agent entrypoint, probe engine, grading engine + missed-ammo, persona extract/resolve, session setup + QuestionQueue | done-and-tested | local logic yes; LLM paths built, live-verified at items 5-8 | 64 tests pass. Probe hot path 0.19ms (limit 10ms). 0 pre-25s interrupts in 20 randomized runs. Probe/grading code fully separate (engine/ vs grading/, no shared module). Auto-rules enforced in code, verbatim evidence + ammo string-match enforced in code. agent.py imports against livekit-agents 1.6.4. 4 decisions logged. |
| 4 | Docs ingestion + context partitioning wall | done-and-tested | yes | Wall is structural in session/manager.py: InterviewerContext has no doc-capable field; tests prove doc content cannot appear in interviewer context or prompt while grader/coach get the supplied subset (bio excluded as persona input). Wizard stages config + docs via store.py to data/, agent loads it. 68 tests pass. |
| 5 | Drill session, one full live rep | in-progress | no | Code built (src/agent.py). Credential blocker cleared 2026-07-10: Deepgram STT and ElevenLabs TTS smoke-tested with one real call each, Groq already proven live during item 8 failover. All 4 VOICE_LIBRARY presets are premade voices on this account. Remaining: run the live rep with the user at the mic. |
| 6 | Coach mode: pack + coverage map + rewrites | done-and-tested | yes | Live-verified with Gemini on seeded fixtures (evals/fixtures/). Pack: 11 questions, 0 dropped, every resume_line verified verbatim in code. Coverage: STRONG/PARTIAL/GAP per question, 3 gaps flagged incl. the seeded high-stakes-pressure gap; covered_by spans verbatim-checked, non-matching claims downgraded to GAP. Rewrites: 6 dimension-tagged notes quoting the answer's actual words + full rewrite pulling real doc facts. CLI: python -m src.coach.cli. Done before item 5, which stays blocked on Deepgram/ElevenLabs keys. |
| 7 | Persona layer: bio extraction, bounded resolution, voice preset | done-and-tested | yes | Live-verified: McKinsey partner bio -> MBB/CONSULTING_PARTNER/PARTNER_DIRECTOR all citing verbatim phrases (checked in code), resolves to consulting_partner preset, mix shifts all <=0.10, eagerness capped at exactly +0.2 (1.3->1.5), intensity 4->5, voice measured_low. Thin bio -> all UNKNOWN -> default_neutral with user-selected round; 'mentoring' mention softened nothing (banned mapping respected). Composition covered by unit tests (round owns format, persona owns style). |
| 8 | Eval harness: consistency, 5 probe cases, missed-ammo accuracy | done-and-tested | yes | Probe cases 5/5 type AND timing. Ammo PASS: exactly 4/4 absent facts, verbatim, zero hallucinated. Consistency PASS on both fixtures (clean 6/6, borderline 6/6 stable, no Solid-Gap span). Failover verified: real 429 handoff observed live, cap-routing unit-tested, Groq JSON mode confirmed. Results table written to README. Quota finding revised: 2.5-flash free tier 429s after ~20-call burst but recovers same day (rolling window); ledger cap now 100 with straight-to-Groq routing at cap. |
| 9 | End-to-end run, fix until MVP demo works clean | not-started | no | |
| 10 | Done-criteria verification against spec Section 5.6 | not-started | no | |
| 11 | Web client: LiveKit published web client template (React) wired to this agent; setup wizard rebuilt as web forms (profile, session type, duration, materials, question source) | in-progress | no | Resequenced 2026-07-11 by user: web UI pulled forward as the test surface for all workflows (CLI iteration too slow). 11a done: agent-starter-react cloned to web/, builds clean (one upstream type fix), .env.local wired, agent worker registers with LiveKit Cloud (voiceagent1 project, auto-dispatch), Next dev server serves localhost:3000. Pending: live browser rep, then 11b web setup form (profile, mode, materials, source -> room metadata -> SessionConfig), 11c session view (question text, transcript, score card + ammo). |
| 12 | Hosting: agent worker on LiveKit Cloud free tier, frontend on free static host (e.g. Vercel); hosted URL runs a live Drill rep end to end | not-started | no | After 11. Stop and ask before creating any hosting account. |
| 13 | Design pass on web client: load frontend-design skill first; intentional palette, typography, clean layout for wizard + live session view (transcript, probe indicator, grading results). Visual pass on item 11's screens and components only; no new libraries or frameworks | not-started | no | After 12. Few focused hours, not a polished rebuild. |
| 14 | Verify hosted demo against the same MVP definition as console (one Drill rep, 2 probes, 6-dim grading + missed ammo, spoken feedback, one Coach pack); README gets hosted link + screenshot | not-started | no | After 13. |

## Action items (beyond this session's scope)

- [ ] SUPERSEDED 2026-07-09 by scope items 11-14: LiveKit Cloud deployment moved from "when external testers arrive" into the MVP (item 12). Still applies: verify Cloud free-tier session limits before relying on them (spec Section 2.4 [NEED] item), and LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET land in .env when the Cloud project is created at item 12.

## Session log

Add a short entry per work session: date, items touched, blockers hit, whether `/compact` was run.

- 2026-07-09: Session 1 start. Item 1 done-and-tested (repo tree, venv, deps verified by import). Blocker note: system Python is 3.9.6, used uv-managed CPython 3.12.13 instead. No /compact yet, context still small.
- 2026-07-09 (cont.): Items 2, 3, 4 done-and-tested. 68 tests pass. Hot path 0.19ms, 0 pre-25s interrupts in 20 runs, context wall proven by tests. 6 decisions logged. Items 5-8 blocked on API keys (Gemini, Deepgram, ElevenLabs, Groq); stopped and asked per credentials rule. Good /compact point.
- 2026-07-09 (cont. 3): All 4 keys now in .env (Gemini AQ. key verified working; Groq, Deepgram, ElevenLabs added by user, not yet smoke-tested). ElevenLabs key scoped to TTS + Voices read + Models only, 8500 credit cap, no voice-generation scope. NEXT STEPS, in order: (a) smoke-test Groq, Deepgram, ElevenLabs with one minimal call each; (b) re-run borderline consistency eval (evals/fixtures/transcript_pm_weak.txt, DURATION_S=138.0, PROBES=[], 5 runs) which will exercise Groq failover while Gemini's 20/day quota is spent, completing item 8; (c) write README eval results table (probe cases 5/5, ammo PASS, consistency clean-fixture 6/6 PASS + borderline result); (d) item 5 live Drill rep (needs ~5 fresh Gemini calls, tomorrow's quota if today's is gone); (e) items 9, 10. Reminder: ledger cap now 18/day in settings.yaml.
- 2026-07-10 (cont.): First live rep attempt, two failures found and fixed. (1) Startup crash: elevenlabs plugin wants ELEVEN_API_KEY env var, .env uses ELEVENLABS_API_KEY; agent.py now passes the key explicitly. (2) Premature grading: runner mapped FOLLOWUP_OR_NEXT to grading, so a 600ms pause graded a one-word answer (data/sessions/session_20260710_195635.json). Fixed per new DECISIONS.md entry: listen through pauses under 25s, one wrap check after, grade on done phrase, complete answer, ignored wrap check, or double deflection. 3 new runner tests, 72 total pass. (3) Garbled question: console mode lacks echo cancellation, speaker audio looped into the mic and barge-in cut the question mid-sentence; interviewer speech is now non-interruptible and the phantom CANDIDATE "The" in the session log was leaked TTS audio, not the user. (4) Added a repeat handler: "repeat the question" and variants re-ask and get retracted from transcript and clock, never reaching analyzers or grader. 73 tests pass. Live rep still pending; user should wear headphones in console mode.
- 2026-07-10 (cont. 2): Second live rep attempt, two more failures found and fixed. (5) Wrap check cut the answer at 36s: endpoints arrive at every 1-3s speech-burst gap, so first-post-25s-endpoint was the wrong trigger; end-of-answer now needs 4s sustained silence (WRAP_SILENCE_S timer, cancelled on any speech), short wrap-check replies grade, long ones re-arm. (6) "end" after grading triggered a second scoring pass because retry/next/end had no handler; runner now enters a verdict mode after grading (retry re-asks, next advances or ends, end calls ctx.shutdown), and the answer state closes before scoring so echo during feedback is ignored. 79 tests pass. Live rep still pending, headphones still required.
- 2026-07-10 (cont. 3): User rule replaces the silence timer: no time-based end-of-answer rules, ever. The interviewer waits through any pause; answers end only on done phrase, spec-complete structure, or double deflection. Timer code removed, opening line now states the done-phrase convention, DECISIONS.md updated (rule also binds the future web client). 76 tests pass. Live rep still pending.
- 2026-07-10 (cont. 4): Third live rep reached grading end to end (transcript, 2 probes, scores, spoken feedback all ran) but surfaced 4 quality bugs, all fixed: (a) irrelevant mid-answer QUANTIFY interrupt caused by trailing-45s window missing numbers said earlier; analyzer now scans the whole answer; (b) user rule: no mid-answer probes at all; runner queues them as post-answer follow-ups, max 2, asked after the done phrase, replies awaited under the same rule; (c) deflection reask used a specificity template for a quantify probe; REASK_HARDER now per type; (d) feedback generic because every evidence quote spanning STT fragments failed the verbatim check; grader now also matches against continuous candidate speech; quantification rubric row now grades on applicability and spelled-out numbers count; spoken_summary shape requires quoting this answer. 78 tests pass. Spec still describes mid-answer probing; user has not yet confirmed a spec edit.
- 2026-07-11: Fourth live rep, best yet: full 158s answer heard uninterrupted, 2 DEPTH follow-ups only after the done phrase, evidence quotes survived verbatim checks, 4 of 6 dimensions graded with grounded notes. Four fixes from it: (a) follow-up opener spoke analyzer-internal jargon ("You mentioned action seen while situation not seen"); probes now translate internal triggers to human phrasing before the rewrite prompt, and the prompt distinguishes candidate quotes from gap descriptions; (b) length dimension counted follow-up time (276s -> Gap for a 158s answer); graded duration now stops at the first done phrase; (c) deflection check received the whole transcript as the reply, letting pre-probe words dominate the overlap ratio; it now gets only post-probe text; (d) queued REDIRECT/REDIRECT_WRAP probes could be spoken as post-answer follow-ups ("wrap up" after the answer ended); redirects now drop since they only make sense live. 80 tests pass.
- 2026-07-11 (cont.): User set the MVP interview shape: listen to the full answer, then feedback, no probing. engine.max_followups added to settings.yaml (0 for MVP; follow-up flow stays behind the flag, tested). Structure rubric graded on followability instead of canonical arc order. Interviewer speech now also prints to the CLI so questions are readable. 81 tests pass. Next: live rep to validate the simplified flow, then items 9-10.
- 2026-07-11 (cont. 2): Two interview modes, user-selectable in the wizard: listen (default, full answer then feedback, zero follow-ups) and probing (up to engine.max_followups=2 follow-ups after the answer). SessionConfig.followup_mode carries the choice; the runner resolves the cap per session. 81 tests pass; config JSON roundtrip verified. The web client (item 11) should surface the same mode choice.
- 2026-07-11 (cont. 3): User resequenced: web UI now, as the faster test surface; design pass (item 13) confirmed wanted; deploy after workflows verified. Checkpoint 11a: LiveKit Cloud creds verified live (0 rooms, India South region), agent-starter-react cloned into web/ (template git history stripped), npm install (548 packages), one upstream type error fixed (ease as const in view-controller.tsx), production build compiles, worker registered via python -m src.agent dev, web client at localhost:3000. Browser rep by user pending; then 11b/11c. Console mode stays available for regression checks.
- 2026-07-11 (cont. 4): First browser rep worked (user note: micro-stutter at start of interviewer speech, watching it; likely per-utterance TTS stream warmup). Checkpoint 11b built: setup form (round, listen/probing mode, question source incl. pack/scripted/intel, collapsible resume/JD/stories paste boxes, 12k char cap each) replaces the welcome view; config travels over RPC after connect (set_doc per document, then start_interview; retry loop covers the registration race; 15KiB payload cap respected). Agent: wait_for_web_setup registers RPC handlers, 60s timeout falls back to file config; console rooms skip straight to file config. 81 py tests pass, next build passes (template tree prettier-normalized). Pending: user browser test of form -> agent config, resume -> missed-ammo live, then 11c score card UI.
- 2026-07-11 (cont. 5): Document upload added per user request: resume/JD/stories accept .pdf/.md/.txt uploads; PDFs extract text in the browser via pdfjs-dist (lazy-loaded), nothing leaves the machine except the extracted text over RPC; extracted text lands in the editable textarea, trims to 12k chars with a notice, scanned-PDF and parse failures fall back to paste with a message. Build passes. Ops note: never run npm run build while next dev is up, they share .next and the dev server 500s (hit once, cleaned and restarted).
- 2026-07-11 (cont. 6): Resume workflow verified live by user in the browser: 3 verbatim resume facts in missed ammo, all genuinely absent from the answer, wall held. Two UX bugs from that rep fixed as checkpoint 11c: (a) spoken feedback referenced "the written card" which the browser never showed; (b) question not visible on screen. Agent now publishes data messages (topic question at each ask, topic scorecard after grading with dimensions, summary, ammo); web renders a pinned question banner and a score card modal (levels color-coded, one evidence quote per dimension, ammo list, retry/next/end hint); spoken line now says the card is on screen. Setup form got display labels (Product Management etc.) and upload collapses to a filename chip with view/edit. 81 py tests, tsc clean. Remaining for item 11: user validates 11c live, probing mode rep, scripted/intel sources spot-check.
- 2026-07-12: Session polish from user feedback: (a) required/optional document rules now explicit per question source (hint under the source select, per-field labels, pack auto-opens docs, scripted/intel validated); (b) template's "Agent is listening, ask it a question" pre-connect line replaced with interview copy; chat input, video, and screenshare disabled; app renamed in config; (c) graceful end: agent publishes session_ended and waits 1.5s before shutdown, client leaves first with a "Session complete" toast, no more "agent left unexpectedly" warning; (d) interviewer bio field added to the form (materials.bio -> existing item 7 persona extraction). 81 py tests, tsc clean. NOT built anywhere: SIMULATION session type (timed full mock, wizard collects it but the runner only implements Drill) and a web surface for Coach mode (CLI only; item 14 expects one Coach pack in the hosted demo).
- 2026-07-12 (cont.): Voice Coach built (user product decision, spec updated in 3 places: features list, wizard flow, MVP demo; DECISIONS.md entry). SessionConfig.mode (interview | coach), top-level mode choice in the web form (coach form: resume required, JD recommended, stories optional, round for bucket taxonomy). CoachRunner reuses item 6 engines: generate_pack + coverage_map at start (in a thread), coachpack data message renders an on-screen pack panel with coverage badges, spoken intro summarizes count and gaps, then voice Q&A: each turn through llm client (ledger + failover) with docs, pack, coverage, and last 8 history lines in the coach_chat prompt; replies capped short to protect TTS credits; "end session" uses the graceful-end path. Setup form scroll bug fixed (overflow-y-auto; tall forms could not scroll). 85 py tests (4 new coach tests), tsc clean, worker restarted. Coach CLI unchanged. Pending: user live test of coach mode; Simulation still unbuilt.
- 2026-07-12 (cont. 2): First live coach session surfaced 3 turn-handling bugs, all fixed: (a) coach replied at every 0.8s speech gap, answering question fragments; endpointing now 2.0s for coach; (b) speech arriving while a reply was generating was dropped; turns now buffer and batch into the next message (_reply_cycle loop); (c) no ended state, so echo and trailing speech after "good luck" kept producing replies during the shutdown grace; ended flag now hard-stops all processing. Intro now states the contract (you ask, I answer from your documents, I will not quiz you). 87 tests (2 new). Worker now logs to scratchpad agent_worker.log so future live sessions have a readable transcript.
- 2026-07-12 (cont. 3): Second coach session transcript reviewed (turn handling now clean). Two reply-quality bugs fixed in the coach_chat prompt: the coach interrogated the user ("can you elaborate") instead of giving answers, and re-cited the full story title plus resume line every turn. Prompt now: expert gives direct guidance and suggested wording, max one clarifying question, short references after first mention, varied openings. User turns now print to the worker log (YOU: lines) for two-sided transcripts. Session finding: 46 Gemini 429s, most replies served by Groq/llama failover which is noticeably weaker; expect better coach replies when Gemini quota is fresh. 87 tests pass.
- 2026-07-12 (cont. 5): Coach v1 shape settled with user (brainstorm first, then build): panel + clickable questions + discuss-by-voice; the gap-workshop idea (coach asks, user answers) dropped for v1 as too Drill-like; resume-improvement explicitly out of scope; "practice this in Drill" handoff deferred to v1.1. Built: panel questions expand on click (resume line, covered-by story), "Get game plan" button sends a discuss_question RPC, agent speaks the plan and publishes it back (gameplan topic) so it persists in the panel; clicks queue behind ongoing replies and are ignored after session end. Intro copy points at the panel. 91 tests (2 new), tsc clean, worker restarted.
- 2026-07-12 (cont. 6): "Practice this in Drill" added per user (pulled forward from v1.1): per-question button in the coach panel; restarts the session as a one-question listen-mode Drill (scripted source) keeping the same documents so missed ammo works; overlays consolidated into ViewController for the restart flow; session UI state (pack, plans, ended flag) now resets on disconnect, fixing a latent bug where a stale ended flag would instantly kill the next session. Agent side needed zero changes (scripted source already existed). 91 py tests, tsc clean.
- 2026-07-12 (cont. 7): docs/WORKFLOWS.md created (13 workflows, mermaid map, session rules, not-built list). Rewrite added to the web score card per user: "Show me the rewrite" button -> get_rewrite RPC -> DrillRunner.send_rewrite reuses coach rewrites.py with the kept grader context (candidate-only speech, docs included), publishes notes + full rewritten answer to the card, speaks only the biggest fix. Cleared on new question and disconnect. 92 py tests, tsc clean, worker restarted. WORKFLOWS.md gains workflow 7b, CLI-only note removed.
- 2026-07-12 (cont. 8): Agreed plan with user: (1) user runs the 7-run web test pass solo (plan given in chat: core drill + card features, probing, pack, scripted/intel, persona bio, coach full loop incl. practice-in-drill and state reset, rage checks) and reports; (2) fix whatever surfaces; (3) build Simulation (item on the not-built list, largest remaining design task: planner pacing, live queue dropping, end debrief); (4) then items 12-14: deploy (ask before Vercel account), design pass, hosted verification + README. All on Fable per user. Both servers running; worker logs to scratchpad agent_worker.log.
- 2026-07-12 (cont. 4): Repetition enforced in code, not just prompt: _trim_echo_opening drops a parroted first sentence ("You're referring to Story 1.1...", "You mentioned...") and any opening sentence with >70 percent word overlap against the last coach replies; prompt additionally bans restating openers outright. 89 tests (2 new). Worker restarted.
- 2026-07-10: Session resume. Smoke-tested the two untested keys with one minimal call each: Deepgram nova-2 transcribed the sample spacewalk audio (HTTP 200), ElevenLabs flash_v2_5 produced valid mp3 with premade voice Sarah (HTTP 200). Finding: ElevenLabs free tier returns 402 for library voices via API; only the account's 21 premade voices work. All four VOICE_LIBRARY preset IDs (George, Sarah, Matilda, Adam) verified present in that premade list, so item 5 has no voice risk. Item 5 moved to in-progress; the live rep itself needs the user speaking. No /compact.
- 2026-07-09 (cont. 2): Gemini key arrived (new AQ. auth-key format; first key was bad, second works). Items 6 and 7 done-and-tested live. Item 8 partial: probe cases 5/5, ammo PASS, consistency PASS on clean fixture; borderline-fixture run halted by VERIFIED FREE-TIER LIMIT: gemini-2.5-flash free tier is 20 requests/day on this key (spec [NEED] item, assumed far higher). Ledger showed 18 tracked calls at halt. Groq failover fired correctly but GROQ_API_KEY is empty. Stopped per FALLBACKS.md; asked user how to proceed. Client gained 503-retry/backoff logic during this block.

## Web test pass (2026-07-12, user-run)
- Run 1 (core drill, listen, bank x2): PASSED after fixes, re-verified live by user.
  Fixes shipped during the run: done-phrase hint in question banner; spoken feedback
  cut to one fix line (rubric + [:1] cap in grader/report); quantification rubric
  tightened (strict definition of measurable stakes; qualitative outcomes earn Solid);
  rewrite panel got Improvement notes / Full answer tabs + Copy button; agent mentions
  the rewrite button after scoring and no longer reads notes aloud; question counter
  ("Question 1 of 2") on banner and in spoken verdict prompt, "next" not offered on
  the last question. rubric.yaml YAML syntax error (unquoted mid-sentence colon)
  crashed grading live; fixed and pinned by test_rubric_yaml_parses_and_is_complete.
  Suite: 94 passing.
- Runs 2-7: pending.
- Run 2 (probing, bank x1): PASSED, verified live by user twice plus session-file
  audit. Confirmed: no mid-answer probes, relevant OWNERSHIP/QUANTIFY follow-ups,
  reask-harder on first dodge, give-up (no loop) on second dodge, length graded on
  main answer only (97s graded vs ~170s total with follow-up).
  Bug found in audit: second dodge echoing a probe word ("specific") escaped
  check_deflection, so the double-deflection auto-rule (Specificity -> Gap) never
  fired (card showed NeedsWork). Fixed: short explicit no-recall replies now count
  as deflections regardless of word overlap; two regression tests added. 97 passing.
  Also this session: TTS FallbackAdapter (ElevenLabs -> Groq Orpheus) wired after
  ElevenLabs quota exhaustion, groq plugin sample-rate patched 48k->24k (garble fix),
  coach coverage legend + GAP explanations added to web panel.
- Runs 3-7 completed 2026-07-12/13: ALL 7 RUNS PASSED (details in
  docs/TESTPLAN.md). 8+ live bugs found and fixed during the pass, each with
  a regression test where testable: pack/intel queue wiring, transcript
  contamination between questions, fragmented repeat-request retraction,
  no-recall deflection detection, rewrite policy (draft from docs vs refuse),
  graceful LLM-quota failure paths, TTS fallback (ElevenLabs->Deepgram Aura),
  gemini-3.1-flash-lite middle LLM tier, Interrupt button + RPC.
  Suite: 101 passing. Web surface is DONE pending deploy + design pass.
  Next: Simulation mode (scope item for full timed mock), then items 12-14.

## Simulation mode (M6), built 2026-07-13 — done-and-tested
- Live-verified same day (Run 8 in TESTPLAN.md, user at the mic): planner
  trimmed 4 requested questions to 2 for 15 min, live drop fired at 554s
  elapsed after a 544s answer, zero feedback between questions, spoken +
  on-screen debrief, only "end" accepted after it, clean exit, session file
  type "simulation". M6 done-criterion MET. Debrief panel redesigned after
  user feedback: no click-to-expand (notes + evidence auto-shown for
  non-Solid dimensions), dropped questions listed by text, per-answer
  duration shown. 117 tests passing.
- src/session/planner.py implemented per spec 2.2: plan() computes the
  question count from depth_style estimates (BREADTH 360s mid / 300s low,
  ONE_STORY_DEEP 1050s / 900s) minus a 180s wrap reserve; on_overrun()
  returns how many more questions still fit, checked after every answer.
  Two decisions logged (planner numbers + underrun; debrief mechanics).
- SimulationRunner (src/agent.py) subclasses DrillRunner and changes only
  the spec's three differences: answers bank silently ("Thank you. Next
  question."), each is graded in a background task during the next answer,
  and the session ends in one debrief: per-question grades, code-computed
  cross-answer patterns ("we-heavy in 2 of 2 answers"), missed ammo
  deduplicated across the set, dropped-question count. Failed grades show
  "not scored" instead of killing the set. After the debrief only "end"
  is accepted; retry/next stay Drill-only. No rewrite in simulation.
- Web: setup form gained Session type (Drill | Simulation) + duration
  (15-60 min); new debrief data topic renders a DebriefPanel (patterns,
  per-question dimension chips expanding to notes, missed ammo across the
  set). tsc + lint clean. Session file saved as type "simulation".
- Next: items 12-14 (deploy: ASK before creating any hosting account,
  design pass, hosted verification + README).

## 2026-07-13 — item 13 first pass (palette + interrupt button) and item 12/15 groundwork

- User approved (in chat): Vercel + Supabase accounts (both free, Google
  sign-up under tanishag1508@gmail.com), Google sign-in for app users, and a
  NEW scope item 15 (accounts + history): saved resume/stories per user, save
  buttons for rewrites/answers/coach gaps, and a per-session activity log
  (questions, scores, transcript, rewrite) on a /history page.
- Design pass, first slice (done, verified tsc + lint + prettier clean):
  - Palette moved from all-neutral gray to indigo primary on warm paper
    (light) / deep navy (dark), token-level in web/styles/globals.css so all
    shadcn components inherit it. Score-level greens/ambers/reds unchanged.
  - Setup form: card container, eyebrow + larger title, mode-picker buttons
    show active state in primary. app-config accent hexes matched (#4f46e5 /
    #a5b4fc).
  - Interrupt button moved from a floating pill into the control bar: amber
    pill (HandIcon + INTERRUPT), same shape as END CALL, placed right before
    it. Threaded onInterrupt through AgentControlBar -> AgentSessionView_01 ->
    ViewController (existing 'interrupt' RPC; no agent change). NOT yet
    verified in a live session: needs a browser look + one live click.
- Item 12/15 groundwork (docs only, no accounts created yet):
  - docs/RUNBOOK-DEPLOY.md: mechanical step-by-step for Vercel deploy, LiveKit
    Cloud agent deploy (Dockerfile + lk agent create + secrets), Supabase
    setup (schema, Google OAuth, key placement), then the 6-step item-15 code
    wiring order. Verified 2026-07-13: LiveKit free Build plan includes 1
    agent deployment, 5 concurrent sessions, 1,000 agent min/month.
  - supabase/schema.sql: documents, sessions, answers, saved_items with RLS
    (user-private via anon key; agent writes via service role key). Not yet
    run anywhere.
- Spoken abort added (user question: interrupt then "end session" must end
  it). DrillRunner.on_turn_complete now ends the session on an explicit
  phrase ("end session", "end/stop the session/interview") when the
  utterance is 8 words or fewer; longer answers containing the words are
  untouched. Simulation inherits it; Coach already had END_PHRASES. Two
  regression tests added; 119 pass. Worker restarted (AW_FXxtA7GsCtYR).
  Not yet live-verified: interrupt click + spoken abort in a browser rep.
- Live verification of the interrupt button (browser, 2026-07-13): in a
  healthy session the button renders enabled in the control bar and the
  RPC reaches the agent with no errors; session.interrupt(force=True) is
  valid in this livekit-agents version and force-cancels even
  non-interruptible speech. The user's "not clickable" report was a wedged
  dev state, not the button: (a) Next.js hot reload while a tab sits on a
  session leaves the client half-connected with ALL controls disabled
  (END CALL too), and (b) the dev worker's server link went stale after a
  quick end-then-start reconnect loop and stopped receiving jobs; two
  session starts failed until the worker was restarted (now
  AW_v8qhK7NrhUxX). Recovery: restart worker + refresh page. Neither
  applies to the hosted deployment (no HMR, managed worker).
- Watch: quick END CALL -> Start interview within ~2s can reconnect with
  the cached token to the dying room (zombie loop, controls disabled).
  Waiting a few seconds or refreshing avoids it. Candidate fix later:
  block the start button until the previous room fully closes.
## 2026-07-13 — item 12 DONE and verified: hosted deploy (Runbook Phase A)

- **Hosted URL: https://behavioral-interview-coach-psi.vercel.app**
- Web app on Vercel (project behavioral-interview-coach, account
  tg1508ai-7301s-projects): env vars LIVEKIT_URL/API_KEY/API_SECRET set as
  encrypted production vars via CLI. Fixes needed: removed the template's
  dev-only guard in app/api/token/route.ts (open guest-mode tokens are the
  decided demo behavior; 15-min single-room random-identity grants), and
  removed the template's pnpm-lock.yaml + packageManager pin (we develop
  with npm; the pnpm 9/10 mismatch broke Vercel's install).
- Agent worker on LiveKit Cloud agent hosting: agent CA_XArKCjMhUecZ,
  region ap-south, status Running, config in livekit.toml (repo root).
  Built remotely from the new Dockerfile + requirements-agent.txt (slim
  runtime deps; ~=1.6 pin because the cloud build check reads the spec
  literally and rejected ~=1.0; venv runs 1.6.4). Secrets (GOOGLE, GROQ,
  DEEPGRAM, ELEVENLABS keys) injected via --secrets-file; .dockerignore
  keeps .env out of the image. Redeploy after code changes:
  `lk agent deploy` from repo root.
- Verified live 2026-07-13 (browser, hosted URL, no local processes): full
  connect, cloud worker CAW_8Le89Cn3oFZZ received the job, spoke intro +
  question 1, question banner + enabled interrupt/end controls, clean end.
- Local worker STOPPED (pkill "src.agent dev"): the cloud agent also
  serves localhost sessions now (same project, automatic dispatch).
  Restart the local worker only when iterating on agent code, and prefer
  pausing the cloud agent then (lk agent update / dashboard) to avoid two
  workers racing for jobs.
- lk CLI authenticated non-interactively via `lk project add` with the
  .env credentials; Vercel CLI via device-code login.
- Next: Runbook Phase B (user runs supabase/schema.sql in the Supabase SQL
  editor + enables Google sign-in; needs a Google Cloud OAuth client),
  then Phase C accounts wiring (items 15: login, saved docs, save buttons,
  /history), then design pass over the new pages, hosted verification +
  README (items 13-14).

## 2026-07-13 (later): Phase B done; Phase C steps 1-2 built, sign-in verify pending

Phase B (Supabase groundwork):
- User ran supabase/schema.sql in the SQL editor (destructive-op warning is
  expected: the script drops/recreates its own RLS policies, nothing else).
- Keys placed: NEXT_PUBLIC_SUPABASE_URL + NEXT_PUBLIC_SUPABASE_ANON_KEY in
  web/.env.local and Vercel production env; SUPABASE_URL +
  SUPABASE_SERVICE_ROLE_KEY in root .env and LiveKit agent secrets.
- Gotcha hit: `lk agent update-secrets --overwrite` REPLACES the whole
  secret set. It wiped the four model keys; re-pushed all six from .env in
  one secrets file. Verify with `lk agent secrets` after any update.
- Google provider: user is setting up the Google Cloud OAuth client
  (runbook Phase B step 3). Reminder given: also set Site URL + redirect
  URLs (vercel.app domain and http://localhost:3000) under
  Authentication -> URL Configuration.

Phase C step 1 (web auth) built:
- npm install @supabase/supabase-js @supabase/ssr (the allowed new dep).
- New: web/lib/supabase/client.ts (browser client + isSupabaseConfigured
  guard so guest-only deployments never break), web/lib/supabase/server.ts
  (cookie-backed server client), web/middleware.ts (session refresh, no-op
  without env), web/app/auth/callback/route.ts (PKCE code exchange),
  web/hooks/useUser.ts, web/components/app/account-menu.tsx.
- Account strip sits at the top of the setup card (all screen sizes,
  disappears during a session): signed-out shows "Sign in with Google",
  signed-in shows name + sign out. Toasts on failure/sign-out.
- Verified in browser (localhost): strip renders; click correctly reaches
  the Supabase authorize endpoint with PKCE challenge + callback URL.
  Supabase returns "provider is not enabled" because the Google OAuth
  client is still being created. This is the expected boundary; real
  sign-in verification blocked on Phase B step 3.

Phase C step 2 (token route identity) built:
- app/api/token/route.ts: when a Supabase session cookie exists, the
  participant identity is the Supabase user id, participant name is the
  Google display name, and attributes carry {"user_id": <id>}. Guests keep
  the random voice_assistant_user_* identity. Supabase lookup failure
  falls back to a guest token (never blocks a session).
- Verified: tsc clean; POST /api/token with no cookie returns a token
  whose JWT sub is a random guest identity.

Next: user finishes Google provider -> verify real sign-in end to end
(sign in, start a session, confirm identity/attributes on the agent side)
-> then Phase C step 3 (agent persistence to Supabase via REST).

## 2026-07-13 (later): Phase C steps 1-2 VERIFIED end to end

- Google provider enabled (Google Cloud OAuth client "interview-coach-web",
  consent screen "Behavioral Interview Coach", scopes email+profile only).
- Live sign-in verified in browser on localhost: Sign in with Google ->
  account chooser -> consent -> /auth/callback code exchange -> back on the
  app with "Signed in as Tanisha Garg" strip + working Sign out link.
- Token route verified while signed in: /api/token JWT has sub = Supabase
  user uuid, name = Google display name, attributes.user_id = same uuid.
  Guest path (no cookie) still issues voice_assistant_user_* identities.
- Two flaky-looking things during verification, neither a product bug:
  (1) dev-mode hydration is slow; clicks in the first ~5s after load do
  nothing (button not yet wired). (2) one "OAuth state has expired" error
  from mixing a stale consent page (browser back/bfcache) with a newer
  flow; a clean pass worked. Retrying sign-in always recovers.
- Done-criteria for runbook Phase C steps 1 and 2: met.

Next: Phase C step 3 - agent persistence (save_session writes sessions +
answers rows to Supabase via httpx REST when env + participant user_id
are present; local JSON stays as fallback), then step 4 saved documents.

## 2026-07-13 (later): Phase C steps 3-4 DONE and verified

Step 3 (agent persistence to Supabase):
- New src/session/cloud_store.py: CloudSession writes one sessions row
  (lazily, on the first graded answer; zero-answer sessions leave no row)
  plus answers rows over PostgREST with httpx (already a dependency).
  attach_rewrite patches the last answer; finish patches duration/dropped/
  patterns/raw. Every call swallows its own errors: persistence can never
  take down a live session. Activates only when SUPABASE_URL +
  SUPABASE_SERVICE_ROLE_KEY are set AND the participant carried a user_id
  attribute; guests/console stay local-JSON only (which also still writes
  for signed-in users as the debug record).
- Wiring: DrillRunner/SimulationRunner take cloud=None; drill records each
  graded answer in _grade_and_feedback and the rewrite in send_rewrite;
  simulation records all reps at debrief then finishes with patterns +
  full record as raw; _end_session fires finish() as a task inside the
  shutdown grace period.
- Tests: 127 passing (8 new: tests/test_cloud_store.py covers activation
  gating, exact REST payloads via httpx.MockTransport, 500s swallowed,
  no-row-for-empty-session, orphan rewrite no-op; test_agent_runner.py
  gained FakeCloud integration tests for drill record+finish, guest path,
  and simulation bank-then-debrief timing).
- Smoke-tested against the REAL Supabase project with the real user id:
  insert session+answer, rewrite patch, finish patch, read back, cascade
  delete cleanup. All green.
- Cloud agent redeployed with this code: version x4Xjf2xVEUDP, Running.
  Full voice-loop persistence check (signed-in drill rep -> rows appear)
  still pending: needs a real spoken session, do with the user next rep.

Step 4 (saved documents):
- web/lib/supabase/documents.ts: loadDocuments / saveDocuments (upsert on
  user_id+kind, kinds resume/jd/stories/bio, anon key + RLS).
- Setup form: signed-in users get saved docs prefilled on load (never
  overwrites text already typed this visit; toast "Loaded your saved
  documents."), and a "Save documents to my account" button in the docs
  panel (toasts on success/failure). Guests see no change.
- Verified in browser on localhost signed in as the real user: typed a
  test resume, saved (success toast), fresh reload -> prefill toast and
  the resume textarea contains the saved text.

Next: step 5 (save buttons: rewrite/answer/coach gaps -> saved_items),
step 6 (/history page), then Vercel deploy of all web changes + hosted
verification, PROGRESS close-out.

## 2026-07-13 (later): Phase C steps 5-6 built, verified on localhost

Step 5 (save buttons -> saved_items):
- New web/components/app/save-item-button.tsx: insert into saved_items
  (kinds rewrite/answer/gap) with idle/saving/saved states and toasts;
  renders nothing for guests so placements are guest-safe.
- Placed: score card rewrite panel ("Save rewrite" next to Copy answer)
  and coach pack panel ("Save this gap" on GAP-coverage questions; content
  packs question + gap note + game plan when present).

Step 6 (/history):
- New web/app/history/page.tsx (client page, anon key + RLS): sessions
  list newest-first with type/round/date/duration/answer count/dropped and
  a solid-dimensions summary chip; expands to patterns + per-answer cards
  (dimension chips in the semantic score colors, transcript toggle,
  rewrite block); saved-items section below. Signed-out and empty states
  covered. Round ids map to display names (pm -> Product Management).
- Account strip gained a History link (signed-in state).
- Verified in browser signed in as the real user: seeded a marked test
  session over the real REST path, /history rendered summary chip
  (10/12 dimensions solid), patterns, both answers with correct chip
  colors, transcript toggle, and the rewrite block; seed deleted after.

Remaining for item 15: Vercel production deploy of all web changes
(running), hosted sign-in + history check, and one real spoken drill rep
by the user to verify agent -> Supabase persistence live. Watch item: if
hosted sign-in redirects wrongly, Supabase Authentication -> URL
Configuration needs the vercel.app domain as Site URL / redirect URL.

## 2026-07-13 (later): item 15 hosted verification DONE

- Vercel production deploy succeeded on the second attempt (first failed on
  prettier lint errors in the new files; `npx prettier --write` + clean
  `next lint`, redeployed).
- User set Supabase Authentication -> URL Configuration: Site URL =
  https://behavioral-interview-coach-psi.vercel.app, redirect list has
  http://localhost:3000/**. Before that fix, hosted sign-in bounced the
  OAuth code back to localhost (Site URL fallback) - documented so nobody
  re-debugs it.
- Verified on the HOSTED site signed in as the real user: Google sign-in
  completes (one bad_oauth_state retry, same transient as localhost;
  second attempt clean), strip shows name + History + Sign out, /history
  loads under RLS with correct empty states (the seeded test session was
  deleted earlier, as intended).
- Item 15 done-criteria met on production. Sole remaining live check:
  one real spoken drill rep while signed in, then confirm the session and
  its answers appear on /history (agent CA_XArKCjMhUecZ version
  x4Xjf2xVEUDP is Running with the persistence code + secrets).
- Next after that: item 13 (design pass over login strip/history/coach
  panels), item 14 (README, hosted screenshot, persona-tag audit, MBA
  spot check).

## 2026-07-13 (later): item 13 design pass, second slice (brand identity)

- New owl mascot (web/components/app/owl-mascot.tsx, theme-token colors);
  used in header wordmark, landing hero, and history empty states.
- Landing hero above the setup card: mascot, eyebrow, title, tagline,
  three feature chips (probes / 6-dimension rubric / coach mode). The
  title moved out of the card; the card keeps the account strip, the
  mode-specific hint line, and the form.
- app/icon.svg replaces the template favicon.ico (owl head, literal hex);
  app/opengraph-image.tsx rewritten as a self-contained brand card (owl +
  name + tagline on paper background), replacing the LiveKit-branded
  template version that loaded logo/font files.
- Verified in browser, light and dark (owl re-colors via tokens).
- Deploying to Vercel production. Remaining polish candidates for a third
  slice if wanted: session-screen banner styling, mobile header (hidden
  below md), coach panel visual pass.

## 2026-07-13 (later): item 13 third slice, app shell (user feedback)

- User feedback on the deployed landing: after sign-in the marketing hero
  must go away; signed-in screens need a proper app shell with a left
  panel (home, history, account), main area focused on the session.
- New web/components/app/side-nav.tsx: fixed desktop sidebar (owl
  wordmark, New session / History nav with active states, account block
  with Google avatar/name/email, sign out, LiveKit credit) and a slim
  mobile top bar. Session views still render without it: a live
  interview keeps the full screen.
- Setup form now has three states: auth resolving (blank, no flash),
  signed out (marketing hero + SignInCard + credit, no form), signed in
  (SideNav + "New practice session" heading + compact form card, no
  hero, no account strip). History page wraps in the same shell.
- Global fixed header removed from layout.tsx (each view carries its own
  identity now; header was overlapping the sidebar).
- Verified in browser signed in on localhost: sidebar + focused form,
  history in shell with active nav, saved-docs prefill toast still fires.
- Also this slice: sign-in gate itself (form only after sign-in) was
  added on user feedback earlier today, deployed and verified hosted.

## 2026-07-13 (later): GitHub public repo + README (item 14 part 1)

- Public repo live: https://github.com/Tanisha1508/behavioral-interview-coach
  (gh CLI installed via brew, user authenticated as Tanisha1508).
- Pre-commit secrets audit caught a REAL Google API key pasted into
  .env.example; blanked before the first commit ever existed, so nothing
  was exposed and no rotation was needed. Broad entropy sweep after:
  clean. .claude/ added to .gitignore.
- Three commits pushed: initial codebase, design pass + app shell,
  README rewrite.
- README now leads with the hosted demo link, uses the live
  /opengraph-image as its hero (verified 200), covers all three modes +
  accounts/history, an architecture table, run-it-yourself for agent and
  web, test count, and keeps the eval table.
- Remaining for item 14: live spoken drill rep by the user to verify
  agent -> Supabase persistence end to end (then human-agreement +
  latency eval rows), persona-tag audit, MBA spot check.

## 2026-07-13 (later): silent-interviewer fix (user's live drill failed)

- User's hosted drill: agent joined but never spoke and never asked a
  question. Two independent causes found from lk agent logs plus local
  probes (scratchpad tts_probe.py):
  1. TTS dead in cloud: ElevenLabs quota-exhausted ("no audio frames
     were pushed"), and the FallbackAdapter's mid-stream switch to
     Deepgram Aura hung on the cloud worker (agents 1.6.5 image, built
     today from the ~=1.6 spec) — no audio, no error, session.say never
     returned, so ask_next_question never ran. Reproduced twice in empty
     debug rooms. The identical switch works locally on 1.6.4 AND 1.6.5,
     and Deepgram Aura synthesizes fine with our key (curl 200 + probe).
  2. Her setup form RPC never reached the agent ("no web setup arrived
     in 60.0s"); she was connected the whole 4 minutes, so the send
     failed client-side. Suspected: set_doc payload over the 15KiB RPC
     cap (form's 12000-char cap only holds for ASCII; pasted PDFs carry
     3-byte bullets), and any one doc failure aborted start_interview.
- Fixes: build_tts order flipped to Aura-first (DECISIONS.md entry);
  livekit-agents pinned ==1.6.4; wait_for_web_setup timeout 60s -> 15s
  and the greeting now says when setup was missed; web sendSetup
  byte-trims each set_doc payload, survives per-doc failures, always
  sends start_interview, and reports dropped docs via toast.
- 127 tests pass; prettier + next lint clean on the two web files.
- Deployed: agent (lk agent deploy) and web (vercel --prod).
- Verified in cloud after deploy (room verify-voice-room, lk room join
  as probe-user): agent published 1 audio track, spoke the greeting with
  the new setup-missed note, and asked the first bank question, zero TTS
  failures in the logs. Empty-room caveat found on the way: the agent
  defers audio linking until a participant joins, so empty debug rooms
  always stall at the greeting by design; cloud voice checks need
  lk room join.
- Watch item: ~15 LiveKit agent minutes spent on today's debugging rooms
  (counts against the 1000/month cap).

## 2026-07-13 (night): six-run user test round -> four fixes (deployed, cloud-verified)

- User ran 6 live scenarios on the hosted app; every finding, root cause,
  and fix is logged in docs/TEST-LOG.md (new file, the running test log).
  Three findings were by design (coach read time, speech queuing, Aura as
  primary voice); four produced fixes:
  1. Resume-pack "agent not joining": pack/intel generation (an LLM call,
     ~26s on free tier) ran BEFORE session.start, so the room had no audio
     track and the client gave up. Entrypoint reordered: session starts
     and speaks first ("Give me a moment while I read your documents"),
     generation runs after, runner attaches to the live InterviewerAgent
     when the queue is ready (runner=None guard during warmup). The old
     interviewer_context/instructions computation was removed with the
     reorder: the interview AgentSession has no LLM and InterviewerAgent
     always raises StopResponse, so instructions were inert.
  2. False "quota exhausted" on scoring: the LLM returned "note": null in
     one rubric dimension, pydantic crashed at grader.py, and the catch-all
     blamed quota. grade() now sanitizes null/mistyped note+evidence per
     dimension; _grade_and_feedback distinguishes DailyCapReached /
     LLMUnavailable (real quota message) from other errors (honest
     "something went wrong on my side", same retry/next/end options).
  3. Rewrite swapping the user's story for a doc story: answer_rewrite
     prompt hardened — substantive answers keep THEIR story (docs only add
     facts to it); a better-fitting doc story becomes a labeled
     "alternative story" note; thin-answer doc drafts must match the
     question's specific competency and name the story used. UI renders
     unknown dimension labels as-is, no web change needed.
  4. Setup-form cold-start race ("no web setup arrived in 15.0s" on the
     worker's first job): web rpcWithRetry window lengthened ~2s -> ~10s
     (10 tries, 1s apart).
- 127 tests pass; web tsc --noEmit clean.
- Deployed: agent version PfXrtLFZnXtn (lk agent deploy) and web
  (vercel --prod, Ready).
- Cloud-verified via lk room join (room verify-fix-round2): agent joined,
  published audio, spoke greeting + first question with no stall. Pack
  mode with real docs needs the user's re-test to be fully verified;
  TEST-LOG.md statuses stay FIX BUILT until then.
- Still gated on the user: after her re-test passes, commit + push the
  whole batch, then start the onboarding wizard (DECISIONS.md 2026-07-13).

## 2026-07-14: onboarding wizard built (web side, tsc + lint clean, not yet live-tested)

Six-run test round closed and committed/pushed (311af70) in the prior
session; this checkpoint is the onboarding wizard per DECISIONS.md
2026-07-13. Supabase `profiles` table run by the user in the SQL editor
(user_id PK, background, goal, target_round with the five-round check,
onboarded_at, updated_at; RLS "own profile" mirroring the other tables).
schema.sql updated to match.

Web work done:
- lib/supabase/profiles.ts: loadProfile / saveProfile (partial upsert on
  user_id) / markOnboarded + ROUNDS/ROUND_NAMES, mirroring documents.ts.
- components/app/doc-input.tsx: DocInput + Field + DOC_LIMIT extracted from
  setup-form so the wizard, profile page, and setup form share one input.
- components/app/setup-wizard.tsx + app/setup/page.tsx: four screens
  (welcome, about you, round, documents), skippable at every step; skip and
  finish both stamp onboarded_at; prefills from any saved profile/docs so
  re-running is not a reset; docs write to the existing documents table.
- app/profile/page.tsx: edit background, goal, default round, and all four
  documents; same shell + sign-in gate as history.
- setup-form.tsx: first-run redirect to /setup when no profile row or
  onboarded_at is null (held behind a load gate so the form never flashes;
  fails open on error), round preselected from target_round, saved docs
  collapsed to a "Your documents: ... Edit" line linking to /profile.
- side-nav.tsx: Profile link added (desktop + mobile).

Verify: web `npx tsc --noEmit` exit 0; `next lint` on all touched files
clean.

NOT done yet (next checkpoints):
- Live click-through by the user on the hosted app (needs a vercel --prod
  deploy first). Status stays build-verified, not live-tested.

## 2026-07-14: background/goal wired into generation + coach (built, tests pass, not live-tested)

The "interviewer knows your background" path, context-wall-respecting.
background and goal travel from the saved profile through the setup RPC and
into the two places that already read the user's documents. The live
interviewer never receives them (it has no LLM; the wall in
session/manager.py is untouched).

- src/session/setup.py: SessionConfig gains background/goal (default ""),
  so the start_interview RPC carries them into the agent automatically.
- Pack generation: generate_pack(resume, jd, round, background, goal); both
  agent call sites (coach start, interview pack) pass cfg.background/goal;
  coach_questions.txt aims the pack at the stated level/target, ignored when
  the lines add nothing. Empty -> "(not provided)".
- Coach chat: coach_chat.txt gets who-they-are / what-they-prep-for lines and
  a rule to pitch advice at that level without reading it back;
  _llm_reply passes background/goal.
- Web: InterviewSetup + DEFAULT_SETUP gain background/goal; setup-form loads
  them from the profile and sends them in both interview and coach payloads.
- Grader deliberately NOT wired (see DECISIONS.md 2026-07-14): scoring stays
  blind to self-described background for consistency.

Verify: 127 Python tests pass; web tsc --noEmit exit 0; next lint clean;
load_prompt smoke test confirms no leftover {background}/{goal} placeholders
and JSON braces preserved.

Ready to deploy in one shot (agent + web) so the whole onboarding flow tests
at once, per the user's batching request.

## 2026-07-14 (later): deployed onboarding + background/goal; then interrupt fix

- Deployed both: agent version qjpSvfsee47W (Running), web vercel --prod
  READY. User tested: onboarding flow good; found the Interrupt button
  broken (click Interrupt + say "end" did not end; agent spoke ahead).
- Interrupt fix (agent-only, TEST-LOG round 2026-07-14 finding 7): Interrupt
  now routes through the runner (note_interrupt), silences the rest of the
  spoken feedback instead of playing on, and honors the next short "end" in
  any state. 130 tests pass (3 new). Redeployed the agent; web unchanged.
- Committed with the rest of the session in 88a4514 (see the closing note
  below).

## 2026-07-14 (later still): score-card reopen + animated owl session UI

- Score card reopen: closing the card no longer destroys it. useInterviewState
  splits card (data) from cardOpen (visibility); a "View score card" pill sits
  directly under the question card and reopens the same card (with its rewrite)
  until the next question. Web-only, deployed.
- Animated owl session screen: the agent tile is now the owl mascot that
  listens / thinks / speaks. New components/app/speaking-owl.tsx reads
  useVoiceAssistant() (state + audioTrack) and useMultibandTrackVolume for live
  amplitude; beak, mouth, halo rings and head-bob ride --amp, breathe/tilt/
  blink ride the state (styles in styles/globals.css, .owl-*). The vendored
  agent tile visualizer (agent-session-view-01/.../audio-visualizer.tsx) now
  renders SpeakingOwl instead of the bar/wave/etc.; the audioVisualizer* props
  are kept for API compatibility but unused. Style approved via an artifact
  mockup first (subtle & tasteful). Respects prefers-reduced-motion. Web tsc +
  lint clean; deployed.

## 2026-07-14 (close): session batch committed and pushed

All of the above (onboarding wizard + profile page + slimmed New Session form,
background/goal into generation + coach, interrupt fix, score-card reopen,
animated owl session UI, and the owl "thinking" during scoring) was verified
live by the user and committed as a single commit 88a4514, pushed to
origin/main (311af70..88a4514). 130 Python tests pass; web tsc + lint clean.
Agent version 8NG4qbvy9h8R and the Vercel production web are the live build.
TEST-LOG round 2026-07-14 findings 7, 8, 9 are FIXED+VERIFIED.
