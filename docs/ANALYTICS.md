# Analytics (scope item 16)

Every event this project sends to Amplitude, kept in sync with the code by
hand. If you add, rename, or remove a `track()`/`amplitude.track()` call,
update this file in the same change. `docs/PROGRESS.md` has the checkpoint
narrative (what was built, when, how it was verified); this file is the
lookup table — what exists right now, and exactly where it fires from.

## Identity model

Every event carries a `device_id` (always present, one per LiveKit
room/browser session, guest or signed-in) and, when the user is signed in,
a `user_id` (the Supabase user id). Amplitude drops any id under 5
characters (`min_id_length`); short ones are padded (web room name) or
omitted (short `user_id`) rather than sent and silently rejected. Guests
are tracked deliberately — engagement counts should include people who
never sign in, matching the product's guest-mode design
(`docs/DECISIONS.md` 2026-07-13 accounts entry).

Two independent SDKs write to the same Amplitude project:

- **Web** (`web/lib/amplitude/client.ts`): `@amplitude/analytics-browser`,
  browser-side, `autocapture: false` (which also disables Amplitude's
  default page-view/session auto-tracking — see DECISIONS.md 2026-08-07).
- **Agent** (`src/analytics/amplitude.py`): plain HTTP API V2 calls from
  the Python LiveKit agent process, no SDK dependency (matches how
  `src/session/cloud_store.py` talks to Supabase — plain REST, not a
  vendor SDK). Env-gated on `AMPLITUDE_API_KEY`; unset means analytics is
  silently disabled and the session continues normally.

## Web events

| Event | Fired from | Properties | Notes |
|---|---|---|---|
| `Viewed Home Page` | `web/components/app/app.tsx:27`, `AppSetup` `useEffect`, on mount | `prompt_version` | Checkpoint-1 verification event. Fires once per page load, before sign-in. Safe to remove `prompt_version` once you don't need to eyeball it in the live feed anymore. |
| `Signed In` | `web/components/app/signed-in-tracker.tsx`, mounted once in `web/app/layout.tsx` | none | OAuth completes server-side in `web/app/auth/callback/route.ts` (a Route Handler — no browser SDK there), so that route redirects with `?signed_in=1`; this client component fires the event on landing and strips the param via `router.replace` so a refresh never double-counts it. This same component now also calls `initAmplitude()` unconditionally on every page (not just `signed_in=1`) — it's the only place guaranteed to mount on every route, which every other web event below depends on. |
| `Saved Document` | `web/lib/supabase/documents.ts:21-40`, `saveDocuments()`, after a successful upsert | `kinds` (array of which of resume/jd/stories/bio were saved) | One hook covers all three call sites: `setup-form.tsx`, `setup-wizard.tsx`, `app/profile/page.tsx`. Deliberately never sends document content, only which kinds. |
| `Saved Suggestion` | `web/components/app/save-item-button.tsx`, `SaveItemButton.save()`, after a successful insert | `kind` (`rewrite` \| `answer` \| `gap`) | The `kind` prop already distinguishes the two placements in `interview-overlay.tsx` (score-card rewrite vs. coach gap), so one hook covers both. Renders `null` for guests — this event is sign-in-only by construction. |
| `Started Session` | `web/components/app/setup-form.tsx`, `start()`, both the coach-mode and interview-mode exit paths | `app_mode` (interview/coach), `session_type` (drill/simulation — interview only), `round_profile`, `followup_mode` (interview only), `source_kind` (interview only), `guest` | Fires client-side at submit, **before** `onStartCall()` hands off to the LiveKit connection — deliberately not gated on the agent-side `session_started` (which only fires once the room actually connects). This is what makes "drop rate before the mock actually starts" measurable: compare `Started Session` counts against `session_started` counts. See DECISIONS.md 2026-08-07. |
| `History Tab Changed` | `web/app/history/page.tsx:482`, the tab button `onClick` | `tab` (`sessions` \| `saved` \| `performance`) | |

## Agent events (Python, `src/agent.py`)

### `session_started`

Fired once per session, at runner construction.

| Source | session_type |
|---|---|
| `DrillRunner.__init__` (`src/agent.py:204`) | `"drill"` (default) |
| `SimulationRunner.__init__` → `super().__init__(..., session_type="simulation")` | `"simulation"` |
| `CoachRunner.__init__` (`src/agent.py:824`) | `"coach"` |

Properties: `session_type`, `round_profile` (pm/consulting/mba_admissions/
tech/others), `followup_mode` (drill/sim only — listen/probing), `guest`
(bool).

### `session_ended`

| Source | Fired when |
|---|---|
| `DrillRunner._end_session` (`src/agent.py:467`, inherited by SimulationRunner) | Verdict "next" with empty queue, or "end"/"stop" |
| `CoachRunner._track_ended("pack_generation_failed")` (helper at `src/agent.py:848`) | Document pack generation failed (LLM quota, etc.) — session never really started |
| `CoachRunner._track_ended("end_phrase")` (helper at `src/agent.py:848`) | User said an END_PHRASE ("end session", "goodbye", etc.) |

Properties: `session_type`, `round_profile`, `duration_s` (wall clock from
runner construction to end), `guest`. Drill/simulation also carry
`questions_total`, `questions_answered`, `dropped` (simulation only, 0
otherwise). Coach carries `reason` instead of question counts.

### `answer_graded`

Fired from `DrillRunner._track_graded` (`src/agent.py:489`), called by:
- `DrillRunner._grade_and_feedback` (drill: fires right after a successful
  `grade()` call, before the missed-ammo pass)
- `SimulationRunner._grade_rep` (simulation: same, but grading happens in
  the background while the next question plays)

Properties: `session_type`, `round_profile`, `question_number`,
`duration_s` (answer length), **`evidence_violations`** (count of
non-verbatim quotes the grader tried to cite and `grader.py
_verify_evidence` dropped — the closest thing this codebase has to a
hallucination-rate metric; 0 in the common case), `dimension_levels`
(dict of the 6 rubric dimensions → Solid/NeedsWork/Gap).

### `answer_grading_failed`

Fired from `DrillRunner._track_grading_failed` (`src/agent.py:502`), same
two call sites as above, on the exception paths.

Properties: `session_type`, `round_profile`, `reason` — one of
`"llm_unavailable"` (`DailyCapReached`/`LLMUnavailable`, i.e. both LLM
providers are out) or `"error"` (anything else — a scoring bug, not
quota).

### `stt_metrics` / `tts_metrics`

Fired from `register_voice_metrics()` (`src/agent.py:~103`), which hooks
LiveKit's own `session.on("metrics_collected")` event — not hand-timed.
Registered once per `AgentSession`, for both the coach path
(`session_type: "coach"`) and the interview/drill/simulation path
(`session_type: "interview"` — this hook doesn't distinguish drill from
simulation, since the STT/TTS pipeline itself doesn't differ between them).

`stt_metrics` properties: `session_type`, `provider` (the STT plugin's
label, e.g. `deepgram.STT`), `duration_s`, `audio_duration_s`, `streamed`.

`tts_metrics` properties: `session_type`, `provider` (the TTS plugin's
label — this is how a `FallbackAdapter` switch between Deepgram Aura and
ElevenLabs, DECISIONS.md 2026-07-13, becomes visible without any extra
code), `ttfb_s` (time to first byte — the latency that actually matters
for "does the interviewer feel slow"), `duration_s`, `audio_duration_s`,
`characters_count`, `cancelled` (bool — true if a barge-in cut the
utterance short).

### `session_abandoned`

Fired when the room closes for a reason that means the participant
actually left — LiveKit's `AgentSession` emits its own `"close"` event
with a `CloseReason`; this fires only on `PARTICIPANT_DISCONNECTED`, never
on `JOB_SHUTDOWN` (our own explicit `ctx.shutdown()` path, which already
produces `session_ended` and must not double-count as an abandonment).

- `register_abandonment_tracking(session)` (`src/agent.py:~106`) registers
  the `session.on("close", ...)` handler and returns a `bind(runner)`
  setter, since on the interview path the runner doesn't exist yet at
  `AgentSession` construction time (it's built later, after queue
  compilation). `bind()` is called right after each runner is constructed
  — `DrillRunner`/`SimulationRunner` and `CoachRunner` alike.
- `DrillRunner.mark_abandoned()` / `CoachRunner.mark_abandoned()`: each
  runner knows its own shape of properties. Both guard on a shared
  `self._ended_explicitly` flag (set by `_end_session`/`_track_ended` on
  the normal path, and by `mark_abandoned` itself so a second close event
  can't double-fire).

Drill/simulation properties: `session_type`, `round_profile`, `duration_s`,
`questions_total`, `questions_answered`, `mid_answer` (bool — whether
`self.state` was still set, i.e. the candidate had started but not
finished their current answer). Coach properties: `session_type: "coach"`,
`round_profile`, `duration_s`, `turns` (length of the coach's own
conversation history), `guest` on both.

Tested directly (not just build-verified): `tests/test_agent_runner.py`
(`test_mark_abandoned_fires_once_with_mid_answer_context`,
`test_mark_abandoned_noop_after_explicit_end`,
`test_close_event_binding_only_fires_on_participant_disconnected`) and
`tests/test_coach_runner.py`
(`test_coach_mark_abandoned_fires_once_and_noops_after_explicit_end`).

### `tts_fallback_triggered` / `tts_fallback_recovered`

Fired from `register_tts_fallback_tracking()` (`src/agent.py`, next to
`register_voice_metrics`), which hooks `FallbackAdapter`'s own
`tts_availability_changed` event — the exact moment a provider goes down
or recovers, not inferred after the fact from a `provider` label changing
between two `tts_metrics` events. `tts_fallback_triggered` fires when a
provider becomes unavailable (`available: False` on the underlying
event), `tts_fallback_recovered` when it comes back. Registered on both
`AgentSession` paths (coach and interview) right after `build_tts()`, on
the `FallbackAdapter` instance itself (captured into a local variable
first, since `AgentSession(tts=...)` previously took the adapter inline
with nothing holding a reference to it).

Properties: `session_type` (`coach`/`interview`), `provider` (the TTS
plugin's label that changed availability, e.g. `elevenlabs.TTS`).

STT-only note: this app has no STT `FallbackAdapter` — both `AgentSession`
paths use raw `deepgram.STT(...)` directly — so there is no STT
equivalent of this event today.

Tested: `tests/test_agent_runner.py`
`test_tts_fallback_tracking_fires_triggered_and_recovered`.

### `eval_run_completed`

Fired from `track_eval_run()` in `evaluation/scripts/analyze_results.py`,
called at the end of `main()` right after `metrics_summary.json` is
written. Uses `src/analytics/amplitude.py` directly (this script isn't
part of the running product, so it imports the same module the agent
uses rather than duplicating the HTTP call) with a fixed
`device_id="golden-eval-suite"` — there's no LiveKit room or user for an
offline batch eval run, so no `user_id` either.

Deliberately flattened to headline scalars only, not the full nested
`metrics_summary.json` — the per-category rubric distributions,
per-category probe breakdowns, and STAR order-invariance detail stay in
the JSON file and `EVALUATION_REPORT.md` for reading directly, since
Amplitude's chart model works on flat properties, not nested breakdowns.

Properties: `n_items`, `grading_success_rate`, `llm_call_success_rate`,
`json_schema_validity_pct`, `fallback_invocation_rate`, `retry_rate`,
`hallucination_items_with_violation_pct`,
`hallucination_per_attempt_violation_rate`, `grading_latency_p50_s`,
`grading_latency_p95_s`, `consistency_modal_stable_pct`,
`consistency_span_violation_pct`, `consistency_cohens_kappa`,
`followup_precision`, `followup_recall`, `followup_f1`,
`voice_call_success_rate`, `voice_wer_mean`, `voice_cer_mean`.

This script isn't run by anything automatically (no CI wired to
`evaluation/`, confirmed by checking `.github/workflows/` — only web
build/deploy workflows exist) — it only fires when someone runs
`python -m evaluation.scripts.analyze_results` by hand, deliberately
re-running the golden-dataset suite. No debounce/opt-out flag was added on
purpose: unsetting `AMPLITUDE_API_KEY` in the shell already suppresses it,
same as everywhere else in this project.

Verified live: ran the real script against the existing checked-in result
files (`llm_eval_results.json`/`probe_eval_results.json`/
`voice_eval_results.json`) — printed `posted eval_run_completed to
Amplitude`, and re-ran with `AMPLITUDE_API_KEY=` to confirm the no-op path
prints `AMPLITUDE_API_KEY unset; eval_run_completed skipped` instead of
erroring.

## Deliberately not tracked yet

Per-LLM-call (Gemini/Groq/Gemini-lite) provider and latency, per call to
`src/llm/client.py`'s `complete()` — every grading, probing, coach-reply,
and question-generation call goes through it. Scoped out of checkpoint 2
on purpose: see DECISIONS.md 2026-08-07 ("Checkpoint 2 scope: no
per-LLM-call analytics yet"). This is the last known gap in the scope-16
wishlist as of checkpoint 6.
