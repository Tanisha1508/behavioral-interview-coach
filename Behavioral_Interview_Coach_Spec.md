# Behavioral Interview Coach: Product Spec

Voice-native mock interviewer that probes in real time and grades spoken delivery. One generic engine; `pm`, `consulting`, `mba_admissions`, `tech`, and `others` ship as bundled round profiles, and users can add their own.
Owner: Tanisha Garg. Target hardware: MacBook Air M5, 16GB RAM. Constraint: free-tier or open-source only. Built to scale from day one: local single-user today, browser and multi-user on the same architecture.

**Top features, ranked by what wins the user**
1. Mid-answer probing (the moat): interrupts with targeted probes based on live analysis. Nothing else does this.
2. Drill mode: question, probe, grade, feedback, retry or next. The rep volume machine.
3. 6-dimension grading with verbatim evidence: every score backed by the user's actual words.
4. Missed ammo report: facts in the user's own docs that the spoken answer left out.
5. Question sources: scripted, pack, bank, pasted intel, blendable per session.
6. Interviewer persona from a pasted bio: tunes probe mix, intensity, pacing, voice.
7. Simulation mode: timed 15 to 60 minutes, feedback held to an end debrief.
8. Coach mode, voice-native (scope change 2026-07-12): a spoken coaching session grounded in the user's documents. The coach generates the tailored pack and coverage map at session start, shows them on screen, and converses by voice: the user asks which story fits a question, where the gaps are, or how to phrase an answer, and the coach answers from their actual resume, JD, and stories.

---

## 1. STRATEGY

**Problem.** Behavioral answers fail in delivery: rambling past 2.5 minutes, losing structure under interruption, collapsing when probed. Text-based practice cannot surface any of this. Candidates walk into behavioral rounds of every kind (PM loops, consulting PEI, MBA admissions, engineering loops among them) having rehearsed written stories they have never defended out loud against a live interruption.

**User.** Anyone facing a behavioral round. Job switchers, consulting candidates, MBA applicants, PM candidates, and engineers are all the same user to the engine; their formats differ only in round-profile parameters. First user is the builder: 40+ reps across the pm and consulting profiles needed by September 2026.

**Trigger moment.** An interview is scheduled 3 to 14 days out. The candidate has stories written but has never spoken them under pressure. They search for practice that talks back.

**Competition.**

| Tool | What it does | Where it falls short |
|---|---|---|
| Interviewing.io | Human mock interviews | Engineer-focused, scheduling friction, cost per session; no consulting or PEI-style coverage |
| ChatGPT voice | Conversational voice AI | Waits politely for you to finish; never interrupts; no structured rubric; no persona targeting |
| Pramp / Exponent peers | Peer mocks | Peer quality varies; peers rarely probe; no delivery grading |
| IGotAnOffer | Coaching + question banks | Human coaching at premium price; question banks are text-first |
| HelloInterview | AI-guided prep for software engineers | Behavioral content is real (Story Builder, AI practice) but built for SWE/EM loops and FAANG engineering competencies only; nothing for consulting, MBA, or non-technical candidates; live 1:1 mocks discontinued May 2026 |

The shared gap: none interrupt mid-answer with targeted probes, and none grade the six things that decide behavioral rounds (structure, specificity, I vs we, numbers, length, reflection) from spoken audio. The `tech` profile competes head-to-head with HelloInterview's probe-free content on their home turf.

**Positioning.** The only free practice tool that behaves like a skeptical interviewer: it cuts you off, asks "what exactly did you say to him," and grades the recording. Built by a real-time voice engineer, which shows in the turn-taking.

**Business value.**
- TAM: AI career coach market, ~$6.69B in 2026, ~22% CAGR (figures as provided).
- SAM: interview-preparation slice of that market delivered via software. [ASSUMED: 15 to 25% of TAM, roughly $1.0B to $1.7B; no reliable public split exists, verify at build time.]
- SOM: English-language behavioral voice practice for MBA, consulting, PM, and tech candidates in year one. [ASSUMED: low single-digit millions; sized bottom-up from ~250K annual US MBA applicants plus consulting and tech applicants, single-digit % adoption, $10 to $20 price point.]
- ROI anchor: human behavioral coaching runs ~$234/hr. Twenty voice reps with probing and grading at $0 marginal cost replaces 3 to 5 coached hours for the delivery-practice portion.

**Non-goals.**
- No technical interview practice (coding, system design, case math). Behavioral rounds only, in any format.
- No live scraping of question sites or interviewer profiles. User pastes intel; behavioral questions are stable for years, scraping fights ToS and the free-tier constraint for little gain.
- No voice cloning of real individuals. Preset voices only.
- No accounts or billing in v1. Multi-user is a supported scale path, monetization is deferred.
- No multi-agent frameworks (LangGraph, CrewAI). One interviewer, one grader, one coach with sequential handoffs; the probe hot path must run in under 10ms on local rules, and a framework in that loop adds latency for zero benefit.

---

## 2. PLANNING

### 2.1 Setup wizard (60 to 90 seconds)

```
mode [INTERVIEW | COACH]                (scope change 2026-07-12)
   COACH: resume required, JD recommended, stories optional -> voice coaching session
profile [pm | consulting | mba_admissions | tech | others]
   -> session type [DRILL | SIMULATION]
        SIMULATION only: duration 15-60 min -> planner computes question count
   -> materials: resume | JD | interviewer bio | stories/brag doc
        (all optional except resume when pack source is chosen;
         bio pasted -> extracted tags shown -> user corrects/confirms)
   -> question source [scripted | pack | bank | pasted intel | blend]
   -> QuestionQueue compiled -> "Ready. Interviewer will begin."
```

### 2.2 Session types

**Drill** (the core rep, and the August tool):

```
ask question (voice)
   -> user speaks
        [every ~2s: partials -> analyzers -> probe candidates -> gates]
   -> INTERRUPT with probe            (mid-answer, within budget)
      | probe at natural pause        (queued)
      | stay silent
   -> answer complete -> grade 6 dims + missed ammo
   -> spoken feedback (30s) + written card
   -> [retry same question | next | end]
```

Retry matters: hearing "your I-vs-We was a Gap" and immediately re-answering the same question is the fastest learning loop in the product.

**Simulation** differs in exactly three ways: the planner paces the queue against the clock and drops questions live if answers run long; zero feedback between questions, because real interviewers do not coach mid-loop; one end-of-session debrief with per-question grades, cross-answer patterns ("we-heavy in 3 of 4 answers"), and missed ammo across the set.

**Session planner**: per-question time estimate from the profile's depth_style (ONE_STORY_DEEP runs 15 to 20 min per story with probing; BREADTH runs 5 to 7 min per question), a 3-minute wrap reserve, live queue dropping when answers overrun.

### 2.3 Question sourcing

Everything compiles into a **QuestionQueue** at session start; the interviewer pops from the queue, sources feed it.
1. **Scripted**: user pastes an ordered list. Covers known-question formats (consulting PEI dimensions, recruiter-flagged questions).
2. **Pack**: Coach-generated from resume + JD.
3. **Bank**: each round profile ships a built-in question bank, sampled with persona topic-emphasis weighting.
4. **Pasted intel**: user pastes a forum thread or interview report they found; an extractor pulls questions into a temporary bank.
Blending is allowed: one known opener plus two bank surprises is a realistic loop.

### 2.4 Stack: LiveKit Agents as the foundation

Time budget rules this decision. LiveKit Agents is open source, self-hostable at zero cost, and deletes the riskiest custom work (turn detection, interruption handling, audio transport) while exposing the turn-taking internals the probe engine hooks into. Build effort shifts from roughly 60% plumbing / 40% product to 20% / 80%.

| Criterion | Fully custom | Vapi | LiveKit Agents (chosen) |
|---|---|---|---|
| Turn-taking + barge-in | Weeks of the riskiest work | Built-in, internals closed | Built-in, open source, hookable |
| Cost | $0 | Trial then per-minute billing | $0 self-hosted; Cloud free tier for multi-user |
| Probe engine hook access | Total | Limited orchestration access | Turn callbacks, full access |
| Scale path | Rebuild for web/multi-user | Vendor-bound | Console -> browser (WebRTC) -> Cloud, same code |
| Time to working voice loop | Weeks | Days | Days |

Vapi and LiveKit solve the same problem, so it is either/or; LiveKit wins on openness, cost, and hook access. Fully custom loses on time budget alone.

**STT/TTS as swappable plugins, speed-first then cost-safe.** Launch with managed free tiers via first-class LiveKit plugins, swap to local nodes when free limits bite; each swap is a config change.

| Layer | Launch (managed, fast to wire) | Fallback (local, unlimited) |
|---|---|---|
| STT | Deepgram plugin, free credits | faster-whisper `small.en` int8 custom node (~500MB RAM) |
| TTS | ElevenLabs plugin, free tier | Kokoro-82M custom node (~400MB RAM) |
| VAD | Silero (LiveKit plugin) | same |
| LLM | Gemini 2.5 Flash, AI Studio free tier | Groq free tier on 429s |

Interviewer speech is short (questions and probes, roughly 1 to 2 minutes per 10-minute session), so ElevenLabs free minutes stretch further than they sound. [NEED: verify at build time: Deepgram free credit terms, ElevenLabs free-tier minutes, LiveKit Cloud free-tier session limits, custom local STT/TTS node support, console-mode maturity, Gemini free-tier RPM and daily caps.]

Local fallback models total under 2GB resident RAM. Comfortable on the M5 / 16GB with a browser open. [ASSUMED: CTranslate2 runs CPU-only on Apple Silicon; if latency disappoints, whisper.cpp with Metal is the swap, same node interface.]

**Latency.** End-to-end target: interviewer audio begins within 1.5s of the user finishing a sentence. LiveKit owns endpointing and transport stages (measured, not decomposed by us). Stages we own: probe decision under 10ms (local rules, pre-computed on partials), probe text 400 to 800ms (Gemini first-sentence streaming, speculative pre-generation when a candidate clears priority before gates). The SIP principle stands: never do work at the endpoint that you could have done during speech.

**Scale posture.** Console mode is the development loop; a hosted, designed browser client is part of the MVP deliverable (scope change 2026-07-09), not a post-MVP step. Multi-user means deploying the same agent worker to LiveKit Cloud free tier. Zero architectural rework at any step.

**Browser client approach.** Start from LiveKit's own published web client template (React) as the functional base, wire it to the same agent worker, then apply a real design pass on top: intentional palette, typography, and layout over the template's structure. Not a from-scratch custom rebuild at this stage; deeper refinement comes later as incremental passes.

**Voice UX decisions.**
- Thinking signal: a short breath or "mm" filler within 300ms of endpoint when probe text is still generating. Silence past ~1s reads as a broken app.
- Crosstalk: user speech during a probe triggers LiveKit interruption handling; interviewer yields within 200ms and the barge-in is logged.
- Endpointing: 600ms silence default; the round profile can extend it (the consulting profile uses 900ms because reflective pauses are legitimate there). Never endpoint mid-filler.
- Interrupt delivery: probes that interrupt start with the user's name or "sorry, quick pause" so the cut-in sounds human.

**Build order.**

| Milestone | Scope | Done when |
|---|---|---|
| M1: Agent skeleton | LiveKit agent, full voice loop, scripted question | Ask-answer-respond loop live in console mode, end-to-end turn under 2s |
| M2: Probe | Probe engine wired into turn callbacks | 5 scripted test behaviors trigger correct probe types (Section 6) |
| M3: Grade | Grading engine + rubric output + missed ammo | Same recording graded 5x within variance threshold |
| M4: Profiles + persona | 5 round profiles, persona layer, bio parser | Pasted consulting-partner bio selects consulting profile and shifts probe mix; all adjustments within bounds |
| M5: Coach | Resume + JD -> pack; docs ingestion; coverage map | One tailored pack plus coverage map generated end to end |
| M6: Simulation | Planner, timed sessions, end debrief | One 20-min simulation runs to debrief with live queue dropping |
| MVP demo | One Drill rep | Spoken answer, probed twice, graded on 6 dimensions plus missed ammo, feedback by voice; plus one Coach pack |

---

## 3. PROBE-DECISION ENGINE

Design principles: probe logic and grading logic never share code, and the engine is format-agnostic. It reads round-format rules from a `RoundProfile` config and never branches on a format name. Five profiles ship bundled; adding a format means writing a config file, never touching engine code. The engine runs inside LiveKit agent turn callbacks; the hot path is local rules under 10ms, no LLM and no framework in the loop.

```
RoundProfile:
  profile_id: str                 # "pm" | "consulting" | "mba_admissions" | "tech" | "others" | custom
  time_budget_s: int              # soft answer limit (bundled: pm 150, consulting 210, mba 180, tech 150, others 150)
  we_ratio_threshold: float       # ownership sensitivity (bundled: 0.6; consulting 0.45)
  emotional_probe_weight: float   # 0 disables (bundled: 0; consulting 0.5, mba 0.3)
  patience_ms: int                # endpointing silence threshold (600; consulting 900)
  length_band_s: [int, int]       # rubric dimension 5 scoring band
  depth_style: BREADTH | ONE_STORY_DEEP   # many stories vs chained follow-ups on one
  probe_bias: {}                  # optional per-profile weight nudges (tech: quantify and depth up)
```

### 3.1 State model

```
AnswerState:
  question: Question              # id, text, expected_buckets, source
  round: RoundProfile             # format rules, above
  clock_ms: int                   # elapsed since user began answering
  transcript_partial: str         # rolling, updated ~every 2s
  hscarr_progress: {              # detected sections, updated by tracker
    hook: NOT_SEEN | SEEN,
    situation: ..., complication: ..., action: ...,
    resolution: ..., reflection: ...
  }
  signals: SignalSet              # output of analyzers, below
  probes_fired: [ProbeRecord]     # type, timestamp, what triggered it
  interrupt_budget: int           # max interrupts remaining (default 2 per answer)
  floor: USER | INTERVIEWER | SILENCE
  last_interrupt_ms: int
  persona: PersonaParams          # Section 4; modifies thresholds below
```

### 3.2 Analyzers (run on partial transcript every ~2s, all local rules, no LLM)

```
analyze(partial, clock_ms, round) -> SignalSet:

  VAGUENESS:
    match phrases: "aligned stakeholders", "drove consensus", "worked closely",
    "took ownership", "communicated effectively", "collaborated cross-functionally"
    AND no concrete noun (name, artifact, number, quoted dialogue) within 15 words
    -> vague_claim = true, store the offending phrase

  WE_DENSITY:
    count "we"/"our"/"the team" vs "I"/"my" over trailing 60s of transcript
    we_ratio = we_count / (we_count + i_count)
    -> we_flag = (we_ratio > round.we_ratio_threshold AND clock_ms > 30s)

  NUMBER_ABSENCE:
    action or resolution section active AND no numeric token in trailing 45s
    -> missing_numbers = true

  HSCARR_TRACKER:
    lightweight classifier on partials (keyword + discourse markers:
    "the situation was", "the challenge", "so what I did", "as a result",
    "what I learned"). Marks sections SEEN.
    -> skipped_section = true if a later section is SEEN while an earlier
       required one is NOT_SEEN (e.g., resolution detected, action never seen)

  TIME_BUDGET:
    soft_limit = round.time_budget_s
    -> rambling = (clock_ms > soft_limit AND hscarr_progress.resolution == NOT_SEEN)
    -> overrun  = (clock_ms > soft_limit + 30s) regardless of progress

  SILENCE:
    floor == SILENCE for > 4000ms mid-answer
    -> stalled = true

  REHEARSED_NON_ANSWER:
    fires only as a probe RESPONSE check: after a probe, if the reply's
    trailing 30s has > 70% token overlap with pre-probe transcript
    (same phrases repeated) and answers none of the probe's question words
    -> deflected = true
```

### 3.3 Decision loop

```
on_partial_update(state):
  signals = analyze(state.transcript_partial, state.clock_ms, state.round)

  # 1. Hard interrupts (fire even mid-sentence, at next clause boundary)
  if signals.overrun:
      return INTERRUPT(probe = REDIRECT_WRAP)          # always allowed, ignores budget

  # 2. Soft interrupt candidates, priority-ordered
  candidates = []
  if signals.rambling:        candidates.add(REDIRECT, priority=1)
  if signals.skipped_section: candidates.add(DEPTH,    priority=2)
  if signals.vague_claim:     candidates.add(SPECIFICITY, priority=3)
  if signals.we_flag:         candidates.add(OWNERSHIP, priority=4)
  if signals.missing_numbers: candidates.add(QUANTIFY, priority=5)

  if candidates.empty: return CONTINUE_LISTENING

  best = highest_priority(candidates)

  # 3. Gate checks before interrupting
  if state.interrupt_budget == 0:            queue_for_end(best); return CONTINUE
  if clock_ms - last_interrupt_ms < 40_000:  queue_for_end(best); return CONTINUE
  if clock_ms < 25_000:                      return CONTINUE     # never interrupt the hook
  if hscarr_progress.reflection == SEEN:     queue_for_end(best); return CONTINUE

  # 4. Persona modulation (Section 4). Eagerness divides the bar: above 1
  #    lowers the threshold and interrupts sooner, matching 4.3 semantics.
  threshold = base_confidence / persona.interrupt_eagerness
  if best.confidence < threshold:            queue_for_end(best); return CONTINUE

  # 5. Fire
  state.interrupt_budget -= 1
  return INTERRUPT(probe = select_probe(best, state))

on_endpoint(state):                          # user finished naturally
  if queued_probes.nonempty:
      return ASK(select_probe(queued_probes.pop(), state))   # probe without interrupting
  if answer_complete(state):                 # resolution + reflection seen, or user signals done
      return HANDOFF_TO_GRADER
  if signals.stalled:
      return ASK(NUDGE)                      # non-leading: "take your time. where were you?"
  return ASK(FOLLOWUP_OR_NEXT)
```

### 3.4 Probe selection

```
select_probe(trigger, state) -> ProbeText:
  type_map = {
    SPECIFICITY:  templates.specificity,   # "What exactly did you say to him?"
                                           # "Walk me through that conversation."
    OWNERSHIP:    templates.ownership,     # "You said 'we' a few times. What did YOU do?"
    QUANTIFY:     templates.quantify,      # "How much? Put a number on it."
    DEPTH:        templates.depth,         # "Why that approach and what else did you consider?"
    COUNTERFACTUAL: templates.counterfactual, # "What if she had refused?"
    REDIRECT:     templates.redirect,      # "Let me stop you. Jump to what happened in the end."
    EMOTIONAL:    templates.emotional,     # "How did that make you feel in the moment?"
    NUDGE:        templates.nudge,
  }
  # If round.emotional_probe_weight > 0: after any SPECIFICITY or OWNERSHIP
  # probe resolves, roll that weight as the chance to chain one EMOTIONAL probe.
  # A weight of 0 (default pm profile) disables emotional probes entirely.
  # Template is a seed; Gemini rewrites it referencing the user's actual words
  # (pass the offending phrase + trailing 2 sentences as context).
  # Speculative generation: when a candidate clears priority but not yet gates,
  # pre-generate its text so firing costs ~0 LLM latency.

handle_deflection(state):                  # rehearsed non-answer after a probe
  if signals.deflected and deflect_count == 1:
      re-ask same probe, harder template: "That's the same answer. I'm asking
      specifically: what were the words you used?"
  if deflect_count >= 2:
      note_for_grader(dimension=SPECIFICITY, force=GAP); move on
```

### 3.5 What the engine never does
- Never interrupts twice inside 40 seconds. Real interviewers do not machine-gun.
- Never interrupts during the first 25 seconds (the hook gets its shot).
- Never leads the witness on silence ("were you going to mention the metrics?" is banned; "take your time" is the ceiling).
- Never sees the user's resume, stories, or brag doc (Section 5.3).
- Never grades. It only logs `ProbeRecord`s and analyzer flags for the grader to consume.

---

## 4. INTERVIEWER PERSONA LAYER

A config layer that parameterizes the probe engine. No separate logic, no forked code paths. One engine, many parameter sets.

### 4.1 Input paths
1. **Structured fields**: firm, role/title, function (PM, consulting, engineering leadership), stated focus areas.
2. **Pasted bio**: free text the user copies from a public professional bio. The tool never fetches profiles itself. Extracted tags are shown for user correction before the session (the setup wizard's confirm step).

### 4.2 Bio signal extraction

One Gemini call maps pasted text to tags. Prompt returns strict JSON, nothing else.

```
extract(bio_text) -> {
  firm_type:    MBB | BIG_TECH | STARTUP | FINANCE | OTHER | UNKNOWN,
  function:     CONSULTING_PARTNER | CONSUMER_PM | TECHNICAL_PM | PLATFORM_PM
                | ENG_LEADER | RECRUITER | UNKNOWN,
  seniority:    PARTNER_DIRECTOR | SENIOR | MID | UNKNOWN,
  domain_tags:  [e.g., "voice", "infra", "growth", "marketplace", "healthcare"],
  signals_found: [verbatim phrases that drove each tag]     # audit trail
}
```

Reliability rules:
- Every tag must cite a `signals_found` phrase or it defaults to UNKNOWN. No inference from absence.
- UNKNOWN tags inherit the defaults of whichever round profile the user selected. Thin bios degrade gracefully to defaults rather than guessing.
- The user sees the extracted tags and can override any of them before the session. This is the correction loop and the trust mechanism.
- `domain_tags` only shift topic emphasis, never probe intensity. A bio saying "loves mentoring" must not soften the interviewer; that mapping is banned as unreliable.

### 4.3 Parameter schema

```json
{
  "persona_id": "consulting_partner",
  "display_name": "Senior consulting partner",
  "round_profile": "consulting",
  "probe_mix": {
    "specificity": 0.30,
    "ownership": 0.25,
    "emotional": 0.25,
    "counterfactual": 0.10,
    "depth": 0.10
  },
  "intensity": 4,
  "interrupt_eagerness": 1.3,
  "interrupt_budget": 3,
  "patience_ms": 900,
  "time_budget_s": 210,
  "topic_emphasis": ["personal_impact", "inclusive_leadership", "entrepreneurial_drive"],
  "opening_style": "warm_then_sharp",
  "voice_preset": "kokoro_af_low_measured",
  "speaking_rate": 0.95
}
```

Field semantics:
- `probe_mix`: sampling weights when multiple probe types are eligible; sums to 1.
- `intensity` (1 to 5): scales how hard re-asks get after deflection and how blunt templates are.
- `interrupt_eagerness`: multiplier on the engine's confidence gate. Above 1 interrupts sooner, below 1 lets answers run.
- `patience_ms`: endpointing silence threshold. Reflective personas wait longer.
- `topic_emphasis`: steers follow-up question selection and Coach-mode question generation, never the rubric.

### 4.4 Mapping rules (tags -> parameters)

| Extracted profile | Probe mix shifts | Other |
|---|---|---|
| Consulting partner | ownership + emotional heavy | eagerness 1.3, budget 3, round: consulting |
| Consumer PM | specificity + depth (user insight, "how did you know users wanted that") | eagerness 1.0, round: pm, topic: product sense adjacents |
| Technical PM | depth + counterfactual (tradeoffs, "what broke") | eagerness 1.1, round: pm, topic: execution, quantify up |
| Eng leader | quantify + depth (untested tradeoffs punished) | eagerness 0.9 (lets answers develop), round: tech |
| Recruiter screen | specificity light, no counterfactual | eagerness 0.6, budget 1, intensity 2 |
| UNKNOWN / thin bio | neutral default preset | user prompted to pick a round profile |

Composition rule: function sets the base preset, firm_type and seniority apply bounded adjustments (each shifts any weight by at most 0.10 and eagerness by at most 0.2). Bounded adjustment keeps a weird bio from producing a broken interviewer.

Division of labor: the round profile owns format rules (time budget, thresholds, length band, depth style); the persona owns interviewer style within those rules (probe mix, eagerness, intensity, voice, topics). They compose; neither overrides the other's fields.

### 4.5 Voice presets
Fixed library of preset voices (ElevenLabs or Kokoro voice IDs), each tagged with pace and delivery character: measured-low, brisk-neutral, warm-slower, clipped-fast. Mapping table assigns one per persona preset. No cloning of individuals, no accepting audio samples, stated in the README and enforced by simply having no such input path.

---

## 5. IMPLEMENTATION SPEC FOR CLAUDE CODE

Spec only. Language: Python 3.11+. LiveKit Agents worker; console mode is the development loop, and a hosted browser client on the same worker is part of the MVP (scope change 2026-07-09).

### 5.1 Repo structure

```
interview-coach/
├── README.md
├── requirements.txt
├── config/
│   ├── rubric.yaml               # 6 dimensions, level descriptors, auto-rules
│   ├── settings.yaml             # plugin selection (managed vs local), thresholds
│   ├── rounds/                   # RoundProfile configs (Section 3); add a file, add a format
│   │   ├── pm.yaml
│   │   ├── consulting.yaml
│   │   ├── mba_admissions.yaml
│   │   ├── tech.yaml
│   │   └── others.yaml
│   ├── banks/                    # per-profile question banks
│   │   ├── pm.yaml
│   │   ├── consulting.yaml
│   │   ├── mba_admissions.yaml
│   │   ├── tech.yaml
│   │   └── others.yaml
│   └── personas/
│       ├── schema.json           # Section 4.3
│       ├── default_neutral.json
│       ├── default_pm.json
│       └── consulting_partner.json
├── src/
│   ├── agent.py                  # LiveKit Agents entrypoint: session wiring, turn callbacks
│   ├── nodes/
│   │   ├── stt_local.py          # faster-whisper custom node (fallback to Deepgram plugin)
│   │   └── tts_local.py          # Kokoro custom node (fallback to ElevenLabs plugin)
│   ├── engine/
│   │   ├── state.py              # AnswerState + RoundProfile dataclasses (3, 3.1)
│   │   ├── analyzers.py          # SignalSet rules (3.2)
│   │   ├── decision.py           # decision loop (3.3), called from turn callbacks
│   │   └── probes.py             # templates + selection + speculative gen (3.4)
│   ├── persona/
│   │   ├── extract.py            # bio -> tags (4.2)
│   │   └── resolve.py            # tags -> PersonaParams (4.4), bounds enforcement
│   ├── grading/
│   │   ├── grader.py             # final transcript + probe history -> scores
│   │   ├── ammo.py               # missed ammo: user docs vs spoken answer
│   │   └── report.py             # written + spoken feedback rendering; simulation debrief
│   ├── coach/
│   │   ├── questions.py          # resume + JD -> tailored question pack
│   │   ├── coverage.py           # stories vs question set -> coverage map + gaps
│   │   ├── intel.py              # pasted text -> extracted questions (temp bank)
│   │   └── rewrites.py           # answer text -> rubric-aligned rewrite notes
│   ├── llm/
│   │   ├── client.py             # Gemini wrapper: retry, backoff, Groq failover, call ledger
│   │   └── prompts/              # all prompt files, versioned, no prompts inline in code
│   └── session/
│       ├── setup.py              # wizard: profile, type, duration, materials, source -> SessionConfig
│       ├── queue.py              # QuestionQueue compile + blend
│       ├── planner.py            # simulation pacing, live queue dropping, wrap reserve
│       ├── manager.py            # orchestrates a session; enforces context partitioning
│       └── store.py              # user library: resume, docs, packs, session history -> ./data/
├── evals/
│   ├── consistency.py            # grade same audio 5x (Section 6)
│   ├── probe_cases/              # 5 scripted behavior scripts + expected outcomes
│   ├── ammo_check.py             # missed ammo accuracy (Section 6)
│   └── agreement.py              # human vs system scoring comparison
└── tests/                        # unit tests per module
```

### 5.2 Key function signatures

```python
# agent.py (LiveKit)
async def entrypoint(ctx)                       # wires session, registers callbacks
def on_user_turn(partial: PartialTranscript)    # -> engine.decision.on_partial
def on_endpoint(final: str)                     # -> engine.decision.on_endpoint

# engine/analyzers.py
def analyze(partial: str, clock_ms: int, round: RoundProfile) -> SignalSet

# engine/decision.py
def on_partial(state: AnswerState, signals: SignalSet) -> Action
def on_endpoint(state: AnswerState) -> Action
# Action: CONTINUE | INTERRUPT(probe) | ASK(probe) | HANDOFF_TO_GRADER

# engine/probes.py
def select_probe(trigger: Trigger, state: AnswerState) -> ProbeText
def pregenerate(candidate: Trigger, state: AnswerState) -> None   # speculative

# session/setup.py
def run_wizard() -> SessionConfig     # profile, type, duration, materials, source

# session/queue.py
def compile_queue(cfg: SessionConfig) -> QuestionQueue   # blend of 4 sources

# session/planner.py
def plan(queue: QuestionQueue, duration_min: int, round: RoundProfile) -> SessionPlan
def on_overrun(plan: SessionPlan, elapsed_s: int) -> SessionPlan   # live dropping

# persona/extract.py
def extract_tags(bio_text: str) -> PersonaTags        # one LLM call, strict JSON

# persona/resolve.py
def resolve(tags: PersonaTags, overrides: dict) -> PersonaParams  # bounded merge

# grading/grader.py
def grade(transcript: str, probes: list[ProbeRecord],
          timings: Timings, round: RoundProfile) -> RubricScores
# RubricScores: {dimension: {level: Solid|NeedsWork|Gap, evidence: [quotes], note: str}}

# grading/ammo.py
def missed_ammo(transcript: str, user_docs: list[Doc]) -> [AmmoItem]
# AmmoItem: {fact: verbatim from doc, doc_source, absent_from_answer: bool}

# coach/questions.py
def generate_pack(resume_text: str, jd_text: str, round: RoundProfile) -> QuestionPack

# coach/coverage.py
def coverage_map(stories_doc: str, questions: QuestionPack) -> CoverageReport  # gaps flagged

# coach/intel.py
def extract_questions(pasted_text: str) -> [Question]   # temp bank

# llm/client.py
def complete(prompt_id: str, vars: dict, json_schema: dict | None) -> LLMResult
# handles: Gemini primary, 429 -> Groq failover, daily call ledger to respect free caps
```

### 5.3 Context partitioning (architecture rule)

| Context | Sees |
|---|---|
| Interviewer (live) | question + persona + live transcript. Never the user's docs: an interviewer that probes with "what about the Orange France incident?" is an oracle, and practicing against an oracle teaches nothing about defending under genuine ignorance |
| Grader | final transcript + probe log + rubric + whatever docs the user supplied this session |
| Coach | resume + JD + whatever the user supplied this session (stories doc, banks, pasted intel are all optional; any subset works, and one document can serve both as stories source and question source) |

`session/manager.py` enforces the partition; it is the only module that assembles LLM contexts. Privacy note for the README: pasted docs transit the Gemini API; fine for personal use, disclosed for others.

### 5.4 Prompt designs

**Interviewer system prompt** (`prompts/interviewer_system.txt`):
- Role: senior interviewer conducting a {round.profile_id} round.
- Round profile injection block: format rules rendered from the RoundProfile (time budget, depth_style, whether emotional probing is on). The bundled pm profile reads as professional, time-conscious, structure-and-numbers; consulting chains follow-ups on one story and probes personal role and feelings; tech pushes tradeoffs and quantification; new profiles need only a config file.
- Persona injection: `{persona.display_name}` framing, `{topic_emphasis}`, intensity descriptor mapped from `persona.intensity`.
- Hard rules in-prompt: one question at a time; never answer for the candidate; never coach mid-interview; probes reference the candidate's actual words (provided as `{recent_context}`); max 2 sentences per probe.
- Output: plain text of the next utterance only.

**Grading system prompt** (`prompts/grading_system.txt`):
- Input: full transcript with speaker labels and timestamps, probe history, timing stats.
- Rubric embedded from `rubric.yaml` with level descriptors per dimension.
- Auto-rules stated explicitly: generic-claim list forces Specificity to Needs Work; we_ratio above the round's threshold unresolved after an ownership probe forces I-vs-We to Gap; Length scores by distance from round.length_band_s (bundled pm band: 90s to 150s).
- Output: strict JSON matching `RubricScores` schema, evidence quotes must be verbatim from transcript, one improvement note per dimension, then a 3-line spoken summary script.

**Missed ammo prompt**: user docs + transcript in; verbatim doc facts absent from the answer out; every flagged fact must string-match the source doc.

**Coach question-gen prompt**: resume + JD in, 8 to 12 questions out, each tagged with the story bucket it targets and why this JD makes it likely.

### 5.5 Dependencies (all free or open source)

`livekit-agents` + plugins (`deepgram`, `elevenlabs`, `silero`), `faster-whisper`, `kokoro`, `google-genai` (AI Studio key), `groq` (free key), `ragas`, `pydantic`, `pyyaml`, `rich` (CLI wizard). No paid APIs anywhere; managed services used only within free tiers with local fallbacks configured.

### 5.6 Done-criteria per module

| Module | Done when |
|---|---|
| agent + nodes | Full voice loop in console mode; end-to-end turn under 2s; barge-in yields under 200ms; STT/TTS swap managed-to-local via config only |
| engine/ | All 5 scripted probe cases pass (Section 6); no interrupt before 25s in 20 test runs |
| persona/ | Presets load; pasted consulting-partner bio selects consulting round and shifts probe mix; thin bio falls back with round-profile prompt; all adjustments within bounds |
| grading/ | Consistency eval passes threshold; every evidence quote string-matches transcript; every ammo item string-matches source doc |
| coach/ | One resume + JD pair yields a pack where every question maps to a real resume line; coverage map flags at least the known gaps in a seeded test |
| session/ | Wizard produces valid SessionConfig; queue blends sources; 20-min simulation plan drops questions correctly on seeded overruns |
| llm/ | 429 triggers Groq failover in-session without dropping the turn; ledger blocks calls past daily cap |

### 5.7 MVP demo

One Drill rep, recorded: candidate speaks an answer, gets interrupted twice with on-point probes, receives 6-dimension grades with verbatim evidence plus a missed ammo report, hears spoken feedback. Plus one voice Coach session (scope change 2026-07-12): pack and coverage map generated from an uploaded resume and JD, rendered on screen, and at least one spoken question about the materials answered from their actual text.

The MVP also includes a hosted, designed browser client (scope change 2026-07-09): LiveKit's published web client template wired to this agent, the setup wizard as web forms, a design pass over the template (palette, typography, layout for wizard, live session view, and grading results), deployed on free tiers (agent worker on LiveKit Cloud, frontend on a free static host), and verified against this same demo definition at the hosted URL. The recording plus the hosted link are the portfolio artifacts. Simulation (M6) demos after MVP.

---

## 6. EVAL DESIGN

**Grading consistency.** Grade the same recorded answer 5 times (fresh LLM calls, temperature as configured).
- Metric: per-dimension modal agreement. Pass: at least 5 of 6 dimensions have the same level in 4+ of 5 runs, and no dimension ever spans Solid to Gap across runs.
- Fail action: tighten rubric descriptors and auto-rules until pass; auto-rules exist precisely to pull judgment calls out of the LLM.

**Probe-quality cases.** 5 scripted answers, delivered by recording or live read, each with an expected engine response:

| Case | Script behavior | Expected | Pass condition |
|---|---|---|---|
| Vague | "I aligned stakeholders and drove consensus," no names or numbers, 60s | SPECIFICITY probe | Correct type, fires between 25s and 90s |
| We-heavy | "we" ratio > 0.7 throughout | OWNERSHIP probe | Correct type; a profile with a lower we-ratio threshold (consulting) fires earlier than pm |
| Rambling | Passes round.time_budget_s with no resolution (150s in pm) | REDIRECT | Fires within 15s of soft limit |
| Strong | Tight HSCARR, names, numbers, 2:10 | No interrupt | Zero interrupts; at most one queued end-probe |
| Silent | 6s silence mid-answer | NUDGE, non-leading | Nudge text contains no content hint |

Pass: 5/5 correct probe type; 4/5 also within timing windows. All cases run against the pm profile; the We-heavy case reruns against consulting to verify profile-driven threshold behavior.

**Missed ammo accuracy.** Seeded test: a doc with 10 known facts, a scripted answer using 6. Pass: report flags exactly the 4 absent facts, every flagged fact string-matches the doc, zero hallucinated items.

**End-to-end agreement.** One full session scored independently by a human (self or a Booth peer using the printed rubric) and by the system.
- Pass: 4 of 6 dimensions match exactly; disagreements documented with both rationales.
- This is a floor for trusting the tool for real prep, and the number goes in the README.

**README metrics table**: consistency agreement rate, probe case pass rate (n/5), ammo accuracy, human agreement (n/6), median end-to-end turn latency ms, p95 turn latency ms, barge-in yield time ms.

---

## 7. USER-VALIDATION PLAN

**Recruiting 15 to 20 testers.**
- Booth admitted-students channels (Slack/GroupMe) once on campus: offer a free Drill session in their target format in exchange for 10 minutes of feedback. Consulting-bound classmates are the highest-value testers because PEI-style rounds are the scarier ones.
- Booth Management Consulting Group and PM Group intro events (September): live Drill demo, sign-up sheet.
- 2 to 3 non-Booth job switchers from personal network for the non-MBA read; at least one engineer for the tech profile.
- [ASSUMED: campus channels open by late August; if earlier testers are needed, r/MBA and Poets&Quants applicant communities are the fallback.]

**Feedback captured per session (4 questions, verbatim quotes kept).**
1. Liked: what felt most like a real interviewer?
2. Confused: where did you not know what the tool wanted?
3. Didn't trust: any grade or probe that felt wrong? Which one?
4. Changed: what will you do differently in your next answer because of this session?

Question 4 is the value question. If testers cannot name a change, the grading feedback is decoration.

**Secondary logs**: sessions per tester (did anyone come back unprompted), probe barge-ins that testers talked over vs yielded to, dimension most frequently scored Gap across testers, Drill retry rate (did people re-answer the same question).

**"One paying user" definition.** One person, unprompted by friendship, pays a nominal amount ($10 to $15) for a persona-tuned mock pack (their target interviewer's bio, 3 sessions, written report) before a real interview, and reports afterward whether a probed question actually came up. Payment plus a post-interview report is the bar; a Venmo from a friend as a favor does not count.

---

## 8. README OUTLINE (PM portfolio piece)

1. **Why a voice tool, and why me.** Four years on Oracle Session Border Controllers: latency budgets, endpointing, and turn-taking in SIP media are the same problems as making an AI interviewer interrupt naturally. One paragraph, the hook of the whole repo.
2. **The problem.** Behavioral answers fail in delivery; text practice cannot catch it. Three failure modes named.
3. **What it does.** 90-second demo video or GIF: a real Drill rep with an interruption. Setup wizard, Drill, and Coach, one screenshot each.
4. **Build vs buy, decided upfront.** Under a hard time budget, LiveKit Agents was chosen over Vapi and over building the transport layer raw, with the comparison table and the reasoning. SBC/SIP depth shows in evaluating LiveKit's turn-taking internals rather than rebuilding them, and in knowing which layer deserved the custom hours.
5. **How it decides to interrupt.** The probe-decision engine, with the state diagram and the "never do work at the endpoint" principle. This is where the build hours went, and this section carries the technical PM story.
6. **Persona layer and context partitioning.** Bio in, parameters out, bounded adjustments, audit trail; the interviewer-never-sees-your-docs wall. Product judgment on reliability and guardrails (no scraping, no cloning).
7. **Results.** Eval tables from Section 6: consistency, probe cases, ammo accuracy, human agreement, latency p50/p95. Real numbers only; [NEED: populate after M3 and M6 evals run.]
8. **What I'd build next.** Adaptive targeting, multi-user deploy on the same worker; Voice Agent Eval Harness as the follow-on project. (Browser client moved into the MVP, 2026-07-09.)
9. **Tester evidence.** 3 to 5 verbatim tester quotes and the "one paying user" outcome, whichever way it went.

---

## POST-MVP (v1.1 note)

Adaptive targeting: bank sampling upweights questions hitting dimensions the user scored Gap on in past sessions and suppresses questions drilled to Solid; built on session history in `store.py`. Multi-user via LiveKit Cloud free tier deploy of the same worker. (Browser client moved from this section into the MVP, 2026-07-09.) [ASSUMED: adaptive targeting is post-MVP since it needs session history to exist and the August need is Drill mode.]

---

## Self-review against writing rules

Checked: active voice throughout, recommendations lead each section, no em dashes, banned words absent, no "not X but Y" constructions, one idea per table row, engine never branches on format (all profile specifics live in round configs), context partition requires no fixed doc set (coach takes any subset the user supplied). Open flags: 5 [NEED] items (build-time verification bundle in Section 2.4, SAM split, README results, tester-channel timing) and 4 [ASSUMED] items, all inline above. HelloInterview positioning verified July 2026. No locked metrics touched.
