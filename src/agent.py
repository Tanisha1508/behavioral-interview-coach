"""LiveKit Agents entrypoint (spec 5.2): session wiring and turn callbacks.

Drill flow: ask question, listen to partials, run the probe engine on every
transcription event, interrupt or queue probes, grade at handoff, speak
feedback. The interviewer's context comes only from SessionManager's
InterviewerContext; no user doc ever reaches this file's live path.

Run: python -m src.agent console
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv

from livekit import agents
from livekit.agents import Agent, AgentSession, StopResponse
from livekit.agents.tts import FallbackAdapter
from livekit.plugins import deepgram, elevenlabs

from src.coach import coverage as coach_coverage
from src.coach import intel as coach_intel
from src.coach import questions as coach_questions
from src.coach import rewrites as coach_rewrites
from src.grading.grader import _candidate_text
from src.engine import decision, probes
from src.engine.decision import ActionKind
from src.engine.state import AnswerState, ProbeRecord, ProbeType, Question
from src.grading import report
from src.grading.ammo import missed_ammo
from src.grading.grader import Timings, grade
from src.llm.client import DailyCapReached, LLMUnavailable
from src.persona.resolve import VOICE_LIBRARY, load_preset, resolve
from src.persona.extract import PersonaTags
from src.session import planner
from src.session.manager import SessionManager
from src.session.planner import SimulationPlan
from src.session.queue import compile_queue
from src.session.setup import SessionConfig, SessionType
from src.session.cloud_store import CloudSession
from src.session.store import save_session

load_dotenv()
logger = logging.getLogger("interview-coach")

ROOT = Path(__file__).resolve().parents[1]
NEXT_SESSION_PATH = ROOT / "data" / "next_session.json"


def _max_followups() -> int:
    """Probes never interrupt (user rule 2026-07-10). This cap decides how
    many queue as post-answer follow-ups in probing mode; listen mode (the
    MVP default) always asks zero and goes straight to feedback."""
    import yaml
    with open(ROOT / "config" / "settings.yaml") as f:
        return int(yaml.safe_load(f)["engine"].get("max_followups", 2))


MAX_FOLLOWUPS = _max_followups()

# Grace period between telling the client the session ended and leaving
# the room, so the browser disconnects cleanly instead of reporting an
# unexpected agent departure.
END_SHUTDOWN_DELAY_S = 1.5


def publish_ui(room, topic: str, payload: dict) -> None:
    """Best-effort data message so the web client can render the question,
    score card, or coach pack; spoken audio stays the primary channel."""
    if room is None:
        return

    async def _send() -> None:
        try:
            await room.local_participant.publish_data(
                json.dumps(payload).encode(), reliable=True, topic=topic)
        except Exception:
            logger.debug("ui publish failed for %s", topic, exc_info=True)

    asyncio.create_task(_send())


def end_after_grace(on_end) -> None:
    """Run the shutdown callback after the client had time to leave."""
    if on_end is None:
        return

    async def _later() -> None:
        await asyncio.sleep(END_SHUTDOWN_DELAY_S)
        on_end()

    asyncio.create_task(_later())


def load_session_config() -> SessionConfig:
    """The wizard (python -m src.session.setup) writes data/next_session.json.
    Without one, default to a pm Drill with 2 bank questions."""
    if NEXT_SESSION_PATH.exists():
        return SessionConfig(**json.loads(NEXT_SESSION_PATH.read_text()))
    return SessionConfig(profile_id="pm")


async def wait_for_web_setup(ctx: agents.JobContext,
                             timeout_s: float = 15.0) -> SessionConfig | None:
    """The web client sends the setup form over RPC right after it joins:
    one set_doc call per pasted document, then start_interview with the
    config. Returns None on timeout so the caller can fall back."""
    docs: dict[str, str] = {}
    loop = asyncio.get_running_loop()
    fut: asyncio.Future[SessionConfig] = loop.create_future()

    def _handle_set_doc(data) -> str:
        payload = json.loads(data.payload)
        docs[str(payload["name"])] = str(payload["text"])
        return "ok"

    def _handle_start(data) -> str:
        try:
            raw = json.loads(data.payload)
            raw["materials"] = docs
            cfg = SessionConfig(**raw)
        except Exception as exc:
            logger.warning("bad web setup payload: %s", exc)
            return "error"
        if not fut.done():
            loop.call_soon_threadsafe(fut.set_result, cfg)
        return "ok"

    ctx.room.local_participant.register_rpc_method("set_doc", _handle_set_doc)
    ctx.room.local_participant.register_rpc_method(
        "start_interview", _handle_start)

    try:
        return await asyncio.wait_for(fut, timeout=timeout_s)
    except asyncio.TimeoutError:
        logger.warning("no web setup arrived in %ss; using default config",
                       timeout_s)
        return None


class DrillRunner:
    """Owns one Drill rep's state and the probe-engine callbacks."""

    def __init__(self, session: AgentSession, manager: SessionManager,
                 queue: list[Question], on_end=None,
                 followup_mode: str = "listen", room=None, cloud=None):
        self.session = session
        self.manager = manager
        self.queue = queue
        self.total_questions = len(queue)
        self.on_end = on_end
        self.room = room  # for UI data messages; None in unit tests
        self.cloud: CloudSession | None = cloud  # Supabase history; None for guests
        self.max_followups = 0 if followup_mode == "listen" else MAX_FOLLOWUPS
        self.state: AnswerState | None = None
        self.answer_started: float | None = None
        self.transcript_log: list[tuple[float, str, str]] = []  # (t, speaker, text)
        self.current_question: Question | None = None
        self.main_answer_ms: int | None = None
        self.awaiting_verdict = False
        self._last_rep = None  # grader context kept for rewrite requests
        self._rewrite_busy = False
        self._pregen_launched: set[str] = set()

    # ---- lifecycle ----

    async def ask_next_question(self) -> bool:
        if not self.queue:
            return False
        self.current_question = self.queue.pop(0)
        # One rep, one transcript: without this reset the grader and the
        # rewrite see every previous answer, and an unanswered question
        # gets a rewrite fabricated from old material (live 2026-07-12).
        self.transcript_log.clear()
        # Position stays correct across retries: the retried question goes
        # back into the queue before this pop restores the count.
        self.question_number = self.total_questions - len(self.queue)
        self.state = self.manager.new_answer_state(self.current_question)
        self.answer_started = None  # starts when the user starts speaking
        self.main_answer_ms: int | None = None
        self.awaiting_verdict = False
        self._last_rep = None
        self._pregen_launched.clear()
        self.publish_ui("question", {"text": self.current_question.text,
                                     "number": self.question_number,
                                     "total": self.total_questions})
        await self.say(self.current_question.text)
        return True

    def publish_ui(self, topic: str, payload: dict) -> None:
        publish_ui(self.room, topic, payload)

    async def say(self, text: str) -> None:
        # Non-interruptible: console mode has no echo cancellation, so
        # speaker audio loops into the mic and barge-in cuts interviewer
        # speech mid-sentence (live rep 2026-07-10). Printed too, so the
        # question is readable if TTS audio is missed.
        print(f"\nINTERVIEWER: {text}\n", flush=True)
        self.transcript_log.append((time.monotonic(), "INTERVIEWER", text))
        await self.session.say(text, allow_interruptions=False)

    def _clock_ms(self) -> int:
        if self.answer_started is None:
            return 0
        return int((time.monotonic() - self.answer_started) * 1000)

    # ---- turn callbacks ----

    def on_partial(self, transcript: str, is_final: bool) -> None:
        if self.state is None:
            return
        if self.answer_started is None and transcript.strip():
            self.answer_started = time.monotonic()
        if is_final:
            self.transcript_log.append((time.monotonic(), "CANDIDATE", transcript))
            self.state.transcript_partial += " " + transcript
        else:
            # Interim: analyze appended view without committing text.
            pass
        self.state.clock_ms = self._clock_ms()

        view = (self.state.transcript_partial + " " + transcript
                if not is_final else self.state.transcript_partial)
        saved = self.state.transcript_partial
        self.state.transcript_partial = view
        signals = decision.compute_signals(self.state)
        action = decision.on_partial(self.state, signals)
        self.state.transcript_partial = saved

        if action.kind == ActionKind.INTERRUPT and action.probe:
            # User rule 2026-07-10: never interrupt mid-answer. A probe the
            # engine would have fired live becomes a post-answer follow-up.
            # Redirects (rambling, overrun wrap) only make sense live, so
            # they drop; the length auto-rule already scores overruns.
            already = {q.probe_type for q in self.state.queued_probes} | \
                      {p.probe_type for p in self.state.probes_fired}
            if (action.probe.probe_type not in already
                    and action.probe.probe_type not in
                    (ProbeType.REDIRECT, ProbeType.REDIRECT_WRAP)):
                self.state.queued_probes.append(action.probe)
        if self.state.queued_probes:
            self._maybe_pregenerate()

    def _maybe_pregenerate(self) -> None:
        assert self.state
        for cand in self.state.queued_probes:
            key = cand.probe_type.value
            if key not in self._pregen_launched:
                self._pregen_launched.add(key)
                asyncio.get_event_loop().run_in_executor(
                    None, probes.pregenerate, cand, self.state)

    def _retract_utterance(self, text: str) -> None:
        """Remove a non-answer utterance (e.g. a repeat request) so it
        never reaches the analyzers or the grader. STT delivers one spoken
        turn as several final fragments ("I'm sorry." + "Can you repeat
        the question?"), so this pops trailing candidate entries while
        they form a word-suffix of the turn text, then rebuilds the
        analyzer view from what is left (live leak 2026-07-13: the
        single-entry pop kept the request in the graded transcript and it
        surfaced as an evidence quote)."""
        assert self.state

        def words(s: str) -> list[str]:
            return re.sub(r"[^\w']+", " ", s.lower()).split()

        target = words(text)
        removed: list[str] = []
        while (self.transcript_log
               and self.transcript_log[-1][1] == "CANDIDATE"
               and len(removed) < len(target)):
            entry_words = words(self.transcript_log[-1][2])
            expected = target[max(0, len(target) - len(removed)
                                  - len(entry_words)):
                              len(target) - len(removed)]
            if entry_words != expected:
                break
            self.transcript_log.pop()
            removed = entry_words + removed
        # Rebuild the analyzer view from the log so both stay consistent.
        remaining = [t for _, spk, t in self.transcript_log
                     if spk == "CANDIDATE"]
        self.state.transcript_partial = (
            " " + " ".join(remaining) if remaining else "")
        if not self.state.transcript_partial.strip():
            self.state.transcript_partial = ""
            self.answer_started = None  # clock restarts with the real answer

    async def on_turn_complete(self, final_text: str) -> None:
        if self.awaiting_verdict:
            await self._handle_verdict(final_text)
            return
        if self.state is None:
            return
        low = final_text.lower()
        # A spoken abort works at any point in the rep (user request
        # 2026-07-13: interrupt button then "end session" must end it).
        # Explicit phrases only, and only in a short utterance, so an
        # answer that merely contains the words never ends the session.
        end_phrases = ("end session", "end the session", "stop the session",
                       "end the interview", "stop the interview")
        if len(low.split()) <= 8 and any(p in low for p in end_phrases):
            await self.say("Understood. Ending the session. Good work today.")
            self._end_session()
            return
        repeat_phrases = ("repeat the question", "repeat that",
                          "say that again", "say it again", "come again")
        if (self.current_question and len(low.split()) <= 8
                and any(p in low for p in repeat_phrases)):
            self._retract_utterance(final_text)
            await self.say(self.current_question.text)
            return
        if final_text.strip():
            done_phrases = ("i'm done", "i am done", "that's my answer",
                            "that's it")
            if any(p in final_text.lower() for p in done_phrases):
                self.state.user_signaled_done = True
                if self.main_answer_ms is None:
                    # First done phrase closes the main answer; length is
                    # graded on this, not on time spent in follow-ups.
                    self.main_answer_ms = self._clock_ms()
        self.state.clock_ms = self._clock_ms()
        if not self.state.user_signaled_done:
            # Wait, like a real interviewer. Endpoints fire at every burst
            # gap, candidates may pause for a minute before continuing, and
            # nothing (probe, nudge, grade) is allowed mid-answer. Only the
            # done phrase moves the rep forward (user rules 2026-07-10).
            return

        # Answer finished: ask follow-ups first, then grade.
        self.state.queued_probes = [
            q for q in self.state.queued_probes
            if q.probe_type not in (ProbeType.REDIRECT,
                                    ProbeType.REDIRECT_WRAP)]
        if len(self.state.probes_fired) >= self.max_followups:
            self.state.queued_probes.clear()
        action = decision.on_endpoint(self.state)

        if action.kind == ActionKind.ASK and action.probe:
            text = probes.select_probe(action.probe, self.state)
            self.state.pre_probe_transcript = self.state.transcript_partial
            self.state.probes_fired.append(ProbeRecord(
                probe_type=action.probe.probe_type,
                fired_at_ms=self.state.clock_ms,
                trigger=action.probe.detail or action.probe.probe_type.value,
                text=text, interrupted=False))
            # The reply to a follow-up ends the same way the answer does.
            self.state.user_signaled_done = False
            await self.say(text)
            return

        await self._grade_and_feedback()

    # ---- retry / next / end ----

    async def _handle_verdict(self, text: str) -> None:
        words = set(text.lower().replace(",", " ").replace(".", " ").split())
        if "retry" in words and self.current_question:
            self.queue.insert(0, self.current_question)
            await self.ask_next_question()
        elif "next" in words:
            if not await self.ask_next_question():
                await self.say("That was the last question. Good work today.")
                self._end_session()
        elif "end" in words or "stop" in words:
            await self.say("Good work today. Ending the session.")
            self._end_session()
        else:
            await self.say("Say retry, next, or end." if self.queue
                           else "Say retry or end.")

    def _end_session(self) -> None:
        self.awaiting_verdict = False
        self.state = None
        self.publish_ui("session_ended", {})
        if self.cloud:
            # Fire and forget: the shutdown grace period gives it time.
            asyncio.create_task(self.cloud.finish())
        end_after_grace(self.on_end)

    # ---- grading handoff ----

    async def _grade_and_feedback(self) -> None:
        assert self.state and self.current_question
        duration_s = (self.main_answer_ms
                      if self.main_answer_ms is not None
                      else self.state.clock_ms) / 1000
        gctx = self.manager.grader_context(
            self.current_question, self._rendered_transcript(),
            self.state, duration_s)
        # Close the answer: mic input during scoring and spoken feedback
        # (including speaker echo) must not re-enter the decision loop.
        self.state = None
        self._last_rep = gctx  # kept for a possible rewrite request

        await self.say("Thanks. Give me a few seconds to score that.")
        try:
            scores = await asyncio.to_thread(
                grade, gctx.transcript, gctx.probes,
                Timings(duration_s=gctx.duration_s), self.manager.round,
                gctx.grader_notes)
        except (DailyCapReached, LLMUnavailable):
            # Grading needs the LLM; quota exhaustion must leave the user a
            # spoken way forward, not a dead session (live 2026-07-12).
            logger.exception("grading failed: LLM unavailable")
            await self.say("I could not score that answer, my language "
                           "model quota is exhausted right now. Say retry "
                           "to answer it again, next to move on, or end "
                           "to stop.")
            self.awaiting_verdict = True
            return
        except Exception:
            # Anything else is a scoring bug, not quota; blaming quota here
            # sent the user chasing limits that were fine (live 2026-07-13,
            # TEST-LOG finding 4).
            logger.exception("grading failed")
            await self.say("Something went wrong while scoring that "
                           "answer on my side. Say retry to answer it "
                           "again, next to move on, or end to stop.")
            self.awaiting_verdict = True
            return
        try:
            ammo = await asyncio.to_thread(
                missed_ammo, gctx.transcript, gctx.docs, gctx.question_text)
        except Exception:
            # Missed ammo is an enhancement; the card stands without it.
            logger.exception("missed-ammo pass failed; continuing without")
            ammo = []

        card = report.render_card(scores, ammo)
        print(card)
        self.publish_ui("scorecard", {
            "question": self.current_question.text,
            "dimensions": scores.model_dump()["dimensions"],
            "spoken_summary": scores.spoken_summary,
            "ammo": [a.model_dump() for a in ammo],
        })
        save_session({
            "question": self.current_question.text,
            "transcript": gctx.transcript,
            "probes": [p.model_dump() for p in gctx.probes],
            "scores": scores.model_dump(),
            "ammo": [a.model_dump() for a in ammo],
            "duration_s": duration_s,
        })
        if self.cloud:
            await self.cloud.record_answer(
                question=self.current_question.text,
                transcript=gctx.transcript, duration_s=duration_s,
                scores=scores.model_dump())
        await self.say(report.spoken_script(scores, ammo)
                       + " To improve the answer, click Show me the "
                       "rewrite on the card.")
        if self.queue:
            await self.say(
                f"That was question {self.question_number} of "
                f"{self.total_questions}. Say retry to redo it, next for "
                "the next question, or end to stop here.")
        else:
            await self.say("That was the last question. Say retry to redo "
                           "it, or end to finish.")
        self.awaiting_verdict = True

    async def send_rewrite(self) -> None:
        """Score-card button: dimension-tagged rewrite notes plus a full
        rewritten answer for the last graded rep, built from the user's
        transcript and documents."""
        if self._last_rep is None or self._rewrite_busy:
            return
        self._rewrite_busy = True
        try:
            gctx = self._last_rep
            answer = _candidate_text(gctx.transcript) or gctx.transcript
            # A rewrite needs material: your answer, or documents to draft
            # from. With documents it always drafts, even from a thin or
            # empty answer (user rule 2026-07-13); with neither, refusing
            # honestly beats inventing a story.
            if len(answer.split()) < 20 and not gctx.docs:
                msg = ("You barely answered that one, and I have no "
                       "documents to draft from. Say retry and give it "
                       "a real attempt, or start a session with your "
                       "resume and stories uploaded so I can build a "
                       "specific answer for you.")
                self.publish_ui("rewrite", {
                    "question": gctx.question_text, "notes": [],
                    "rewritten_answer": "", "message": msg,
                })
                await self.say(msg)
                return
            result = await asyncio.to_thread(
                coach_rewrites.rewrite, gctx.question_text, answer,
                self.manager.round, gctx.docs)
            self.publish_ui("rewrite", {
                "question": gctx.question_text,
                "notes": [n.model_dump() for n in result.notes],
                "rewritten_answer": result.rewritten_answer,
            })
            if self.cloud:
                await self.cloud.attach_rewrite(result.rewritten_answer)
            # Speak only a pointer: the user reads the notes themselves.
            await self.say("The rewrite is on your screen. Work through "
                           "the notes, then say retry to deliver the "
                           "stronger version.")
        except Exception:
            logger.exception("rewrite failed")
            await self.say("I could not build the rewrite. Ask once more.")
        finally:
            self._rewrite_busy = False

    def _rendered_transcript(self) -> str:
        if not self.transcript_log:
            return ""
        t0 = self.transcript_log[0][0]
        return "\n".join(f"[{t - t0:6.1f}s] {speaker}: {text}"
                         for t, speaker, text in self.transcript_log)


class SimulationRunner(DrillRunner):
    """Timed simulation (spec 2.2). Differs from the Drill in exactly
    three ways: the planner paces the queue against the clock and drops
    questions when answers overrun; zero feedback between questions; one
    end-of-session debrief with per-question grades, cross-answer
    patterns, and missed ammo across the set. Everything else (done
    phrases, repeat requests, follow-up policy) is inherited."""

    def __init__(self, session: AgentSession, manager: SessionManager,
                 queue: list[Question], plan: SimulationPlan, on_end=None,
                 followup_mode: str = "listen", room=None, cloud=None):
        super().__init__(session, manager, queue[:plan.question_count],
                         on_end=on_end, followup_mode=followup_mode,
                         room=room, cloud=cloud)
        self.plan = plan
        self.sim_started: float | None = None
        self.reps: list[report.RepResult] = []
        self.dropped = 0
        self.dropped_questions: list[str] = []
        self._grading_tasks: list[asyncio.Task] = []

    async def ask_next_question(self) -> bool:
        if self.sim_started is None:
            self.sim_started = time.monotonic()  # clock starts with Q1
        return await super().ask_next_question()

    def _elapsed_s(self) -> int:
        if self.sim_started is None:
            return 0
        return int(time.monotonic() - self.sim_started)

    async def _grade_and_feedback(self) -> None:
        # No feedback between questions: bank the rep, grade it in the
        # background while the candidate answers the next question, and
        # move on like a real interviewer would.
        assert self.state and self.current_question
        duration_s = (self.main_answer_ms
                      if self.main_answer_ms is not None
                      else self.state.clock_ms) / 1000
        gctx = self.manager.grader_context(
            self.current_question, self._rendered_transcript(),
            self.state, duration_s)
        self.state = None
        rep = report.RepResult(question=self.current_question.text,
                               duration_s=duration_s,
                               transcript=gctx.transcript)
        self.reps.append(rep)
        self._grading_tasks.append(
            asyncio.create_task(self._grade_rep(gctx, rep)))

        # Live queue dropping: after every answer, keep only as many
        # remaining questions as the clock still allows.
        fits = planner.on_overrun(self.plan, self._elapsed_s())
        if fits < len(self.queue):
            dropped_now = len(self.queue) - fits
            self.dropped += dropped_now
            self.total_questions -= dropped_now
            self.dropped_questions += [q.text for q in self.queue[fits:]]
            del self.queue[fits:]
            logger.info("simulation dropped %d question(s) at %ds elapsed",
                        dropped_now, self._elapsed_s())

        if self.queue:
            await self.say("Thank you. Next question.")
            await self.ask_next_question()
        else:
            await self._debrief()

    async def _grade_rep(self, gctx, rep: report.RepResult) -> None:
        try:
            rep.scores = await asyncio.to_thread(
                grade, gctx.transcript, gctx.probes,
                Timings(duration_s=gctx.duration_s), self.manager.round,
                gctx.grader_notes)
        except Exception:
            # One failed grade must not kill the set; the debrief says
            # which answers went unscored.
            logger.exception("simulation grading failed for one answer")
        try:
            rep.ammo = await asyncio.to_thread(
                missed_ammo, gctx.transcript, gctx.docs, gctx.question_text)
        except Exception:
            logger.exception("missed-ammo pass failed; continuing without")

    async def _debrief(self) -> None:
        await self.say("That was the last question. Give me a moment to "
                       "put your debrief together.")
        if self._grading_tasks:
            await asyncio.gather(*self._grading_tasks,
                                 return_exceptions=True)
        patterns = report.debrief_patterns(self.reps)
        ammo = report.combined_ammo(self.reps)
        print(report.render_debrief(self.reps, patterns, ammo, self.dropped))
        self.publish_ui("debrief", {
            "reps": [{
                "question": r.question,
                "duration_s": r.duration_s,
                "graded": r.scores is not None,
                "dimensions": (r.scores.model_dump()["dimensions"]
                               if r.scores else {}),
            } for r in self.reps],
            "patterns": patterns,
            "ammo": [a.model_dump() for a in ammo],
            "dropped": self.dropped,
            "dropped_questions": self.dropped_questions,
        })
        record = {
            "type": "simulation",
            "duration_planned_s": self.plan.duration_s,
            "elapsed_s": self._elapsed_s(),
            "dropped": self.dropped,
            "dropped_questions": self.dropped_questions,
            "patterns": patterns,
            "ammo": [a.model_dump() for a in ammo],
            "reps": [{
                "question": r.question,
                "transcript": r.transcript,
                "duration_s": r.duration_s,
                "scores": r.scores.model_dump() if r.scores else None,
                "ammo": [a.model_dump() for a in r.ammo],
            } for r in self.reps],
        }
        save_session(record)
        if self.cloud:
            for r in self.reps:
                await self.cloud.record_answer(
                    question=r.question, transcript=r.transcript,
                    duration_s=r.duration_s,
                    scores=r.scores.model_dump() if r.scores else None)
            await self.cloud.finish(dropped=self.dropped,
                                    patterns=patterns, raw=record)
        await self.say(report.spoken_debrief(self.reps, patterns, ammo,
                                             self.dropped))
        self.awaiting_verdict = True

    async def _handle_verdict(self, text: str) -> None:
        # After the debrief the only move is end: retry and next belong to
        # the Drill's per-question loop, not a finished timed set.
        words = set(text.lower().replace(",", " ").replace(".", " ").split())
        if "end" in words or "stop" in words:
            await self.say("Good work today. Ending the session.")
            self._end_session()
        else:
            await self.say("Say end when you are done with the debrief.")


class CoachRunner:
    """Voice Coach session (spec scope change 2026-07-12): pack and
    coverage map generated at start and pushed to the screen, then a spoken
    conversation grounded in the user's documents. Reuses the item 6
    engines; replies go through the llm client (ledger + failover)."""

    END_PHRASES = ("end session", "end the session", "i'm done",
                   "i am done", "that's all for today", "goodbye")

    def __init__(self, session, cfg: SessionConfig, room=None, on_end=None,
                 reply_fn=None):
        self.session = session
        self.cfg = cfg
        self.room = room
        self.on_end = on_end
        self.reply_fn = reply_fn or self._llm_reply
        self.history: list[tuple[str, str]] = []
        self.pack = None
        self.coverage = None
        self.ended = False
        self._busy = False
        self._pending: list[str] = []

    def on_partial(self, transcript: str, is_final: bool) -> None:
        pass  # the coach has no mid-speech analyzers

    async def say(self, text: str) -> None:
        print(f"\nCOACH: {text}\n", flush=True)
        self.history.append(("coach", text))
        await self.session.say(text, allow_interruptions=False)

    async def start(self) -> None:
        resume = self.cfg.materials.get("resume", "")
        jd = self.cfg.materials.get("jd", "")
        stories = self.cfg.materials.get("stories", "")
        if not resume.strip():
            await self.say("I coach from your documents, and I don't have "
                           "your resume. End this session and start again "
                           "with it uploaded.")
            return

        await self.say("Give me a moment to read your materials.")
        try:
            self.pack = await asyncio.to_thread(
                coach_questions.generate_pack, resume, jd,
                self.cfg.round_profile())
        except Exception:
            # LLM quota exhaustion must end the session with words, not an
            # unhandled crash the client reads as "agent left unexpectedly"
            # (live 2026-07-12, both providers rate-limited).
            logger.exception("coach pack generation failed")
            await self.say("I could not reach my language model, most "
                           "likely a quota limit. Please end this session "
                           "and try again in a few minutes.")
            publish_ui(self.room, "session_ended", {})
            end_after_grace(self.on_end)
            return
        if stories.strip() and self.pack.questions:
            try:
                self.coverage = await asyncio.to_thread(
                    coach_coverage.coverage_map, stories, self.pack)
            except Exception:
                # Coverage is an enhancement; the pack alone is a session.
                logger.exception("coverage map failed; continuing without")

        publish_ui(self.room, "coachpack", {
            "questions": [q.model_dump() for q in self.pack.questions],
            "coverage": ([e.model_dump() for e in self.coverage.entries]
                         if self.coverage else []),
        })

        intro = (f"I prepared {len(self.pack.questions)} questions you are "
                 "likely to get; they are on your screen.")
        if self.coverage:
            gaps = len(self.coverage.gaps)
            intro += (f" Your stories leave {gaps} of them uncovered."
                      if gaps else " Your stories cover all of them.")
        intro += (" Here is how this works: click any question on your "
                  "screen and I will give you a game plan for it, or just "
                  "ask me anything about your materials. I answer, I do "
                  "not quiz you. Take your time when you speak, I wait "
                  "for real pauses. Say end session when you are done.")
        await self.say(intro)

    async def discuss_question(self, question_text: str) -> None:
        """A question clicked on screen: speak a game plan and publish it
        to the panel."""
        if self.ended or not question_text.strip():
            return
        while self._busy:
            await asyncio.sleep(0.1)
        self._busy = True
        try:
            message = (f'Give me your game plan for: "{question_text}". '
                       "Which story to use, the opening line, and the one "
                       "number or fact from my documents to include.")
            print(f"\nYOU (clicked): {question_text}\n", flush=True)
            self.history.append(("candidate", message))
            reply = await asyncio.to_thread(self.reply_fn, message)
            if self.ended:
                return
            publish_ui(self.room, "gameplan",
                       {"question": question_text, "plan": reply})
            await self.say(self._trim_echo_opening(reply))
        finally:
            self._busy = False

    async def on_turn_complete(self, final_text: str) -> None:
        if self.ended or not final_text.strip():
            return
        low = final_text.lower()
        if any(p in low for p in self.END_PHRASES):
            self.ended = True
            self._pending.clear()
            publish_ui(self.room, "session_ended", {})
            await self.say("Good luck out there. Ending the session.")
            end_after_grace(self.on_end)
            return
        # Buffer instead of replying per endpoint: speech that arrives
        # while a reply is being generated joins the next message rather
        # than being dropped, and burst fragments merge into one question.
        self._pending.append(final_text)
        if self._busy:
            return
        await self._reply_cycle()

    async def _reply_cycle(self) -> None:
        self._busy = True
        try:
            while self._pending and not self.ended:
                message = " ".join(self._pending)
                self._pending.clear()
                print(f"\nYOU: {message}\n", flush=True)
                self.history.append(("candidate", message))
                reply = await asyncio.to_thread(self.reply_fn, message)
                if self.ended:
                    break
                await self.say(self._trim_echo_opening(reply))
        finally:
            self._busy = False

    def _trim_echo_opening(self, reply: str) -> str:
        """Drop a parroted first sentence. Prompt rules ask for this, but
        the failover model ignores them and opened nearly every reply with
        "You're referring to Story 1.1..." (live session 2026-07-12)."""
        parts = re.split(r"(?<=[.?!])\s+", reply.strip())
        if len(parts) < 2:
            return reply
        first = parts[0].lower()
        if first.startswith(("you're referring to", "you are referring to",
                             "you mentioned", "so you said")):
            return " ".join(parts[1:])
        first_words = set(first.split())
        for speaker, text in self.history[-6:]:
            if speaker != "coach":
                continue
            prev_first = re.split(r"(?<=[.?!])\s+", text.strip())[0].lower()
            prev_words = set(prev_first.split())
            overlap = len(first_words & prev_words)
            if first_words and overlap / len(first_words) > 0.7:
                return " ".join(parts[1:])
        return reply

    def _llm_reply(self, user_message: str) -> str:
        from src.llm.client import complete

        pack_summary = "\n".join(
            f"- {q.text} (bucket: {q.bucket}; resume line: {q.resume_line})"
            for q in (self.pack.questions if self.pack else []))
        coverage_summary = "\n".join(
            f"- {e.question}: {e.strength}"
            + (f", covered by: {e.covered_by}" if e.covered_by else "")
            for e in (self.coverage.entries if self.coverage else []))
        history = "\n".join(
            f"{speaker}: {text}" for speaker, text in self.history[-9:-1])
        try:
            result = complete("coach_chat", {
                "resume": self.cfg.materials.get("resume", ""),
                "jd": self.cfg.materials.get("jd", ""),
                "stories": self.cfg.materials.get("stories", ""),
                "pack_summary": pack_summary or "(no pack available)",
                "coverage_summary": coverage_summary or "(no stories doc)",
                "history": history or "(start of conversation)",
                "user_message": user_message,
            }, json_schema=None)
            text = (result.text or "").strip()
        except Exception:
            logger.exception("coach reply failed")
            text = ""
        return text or ("I hit a snag answering that. Give me that "
                        "question once more.")


class InterviewerAgent(Agent):
    """The live interviewer. Its instructions come exclusively from
    InterviewerContext (question + persona + live transcript)."""

    def __init__(self, runner: DrillRunner | None, instructions: str):
        super().__init__(instructions=instructions)
        # None while the session warms up: the session must start (and
        # speak) before pack/intel generation, which is when the runner
        # gets built; anything the user says before then is not an answer.
        self.runner = runner

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        if self.runner is not None:
            text = getattr(new_message, "text_content", None) or ""
            await self.runner.on_turn_complete(text)
        # The probe engine owns all interviewer speech; never let a chat LLM
        # generate a reply on its own.
        raise StopResponse()


def build_tts(voice: dict) -> FallbackAdapter:
    """Deepgram Aura primary, ElevenLabs fallback (DECISIONS.md 2026-07-13).
    The order was ElevenLabs-first until its quota ran out on 2026-07-12:
    every utterance then paid ~2.6s of doomed retries before switching, and
    on LiveKit Cloud the mid-stream switch to the fallback TTS hung without
    audio or error, leaving the interviewer permanently silent (live failure
    2026-07-13, reproduced in empty rooms). Aura-first avoids the switch
    path entirely. Keys are read from the environment, never hardcoded."""
    return FallbackAdapter([
        deepgram.TTS(model=voice["deepgram_voice"],
                     api_key=os.environ["DEEPGRAM_API_KEY"]),
        # The plugin's env fallback is ELEVEN_API_KEY; our .env uses
        # ELEVENLABS_API_KEY, so pass the key explicitly.
        elevenlabs.TTS(voice_id=voice["elevenlabs_voice_id"],
                       api_key=os.environ["ELEVENLABS_API_KEY"]),
    ])


def _register_interrupt_rpc(ctx: agents.JobContext, session: AgentSession,
                            loop: asyncio.AbstractEventLoop) -> None:
    """Web 'Interrupt' button: agent speech is deliberately immune to
    voice interruption (user rule 2026-07-10), so an explicit button is
    the only way to cut a long game plan or feedback short
    (user request 2026-07-13). force=True overrides the protection."""

    def _handle_interrupt(data) -> str:
        def _do() -> None:
            try:
                session.interrupt(force=True)
            except Exception:
                logger.debug("interrupt ignored", exc_info=True)

        loop.call_soon_threadsafe(_do)
        return "ok"

    ctx.room.local_participant.register_rpc_method(
        "interrupt", _handle_interrupt)


async def entrypoint(ctx: agents.JobContext) -> None:
    await ctx.connect()

    # Console mode configures via data/next_session.json; browser sessions
    # send the setup form over RPC after joining.
    setup_missed = False
    if ctx.room.name.startswith("console"):
        cfg = load_session_config()
    else:
        web_cfg = await wait_for_web_setup(ctx)
        setup_missed = web_cfg is None
        cfg = web_cfg or load_session_config()

    if cfg.mode == "coach":
        session = AgentSession(
            stt=deepgram.STT(model="nova-3", interim_results=True),
            tts=build_tts(VOICE_LIBRARY["warm_slower"]),
            # People phrase questions in bursts; 0.8s made the coach answer
            # fragments (live session 2026-07-12). Wait for a real pause.
            min_endpointing_delay=2.0,
        )
        runner = CoachRunner(
            session, cfg, room=ctx.room,
            on_end=lambda: ctx.shutdown(reason="coach session ended"))

        loop = asyncio.get_running_loop()

        def _handle_discuss(data) -> str:
            try:
                text = str(json.loads(data.payload).get("text", ""))
            except Exception:
                return "error"
            loop.call_soon_threadsafe(
                lambda: asyncio.create_task(runner.discuss_question(text)))
            return "ok"

        ctx.room.local_participant.register_rpc_method(
            "discuss_question", _handle_discuss)
        _register_interrupt_rpc(ctx, session, loop)

        await session.start(
            agent=InterviewerAgent(
                runner, "Voice coach. All speech comes from CoachRunner."),
            room=ctx.room)
        await runner.start()
        return

    bio = cfg.materials.get("bio", "")
    if bio:
        from src.persona.extract import extract_tags
        tags = extract_tags(bio)
    else:
        tags = PersonaTags()
    persona = resolve(tags, overrides=cfg.persona_overrides,
                      selected_round=cfg.profile_id)
    if bio:
        logger.info("persona tags: firm=%s function=%s seniority=%s signals=%s",
                    tags.firm_type, tags.function, tags.seniority,
                    [(s.tag, s.phrase) for s in tags.signals_found])
    logger.info("persona resolved: voice=%s intensity=%s round=%s",
                persona.voice_preset, persona.intensity, cfg.profile_id)

    manager = SessionManager(cfg, persona)

    voice = VOICE_LIBRARY.get(persona.voice_preset,
                              VOICE_LIBRARY["brisk_neutral"])

    session = AgentSession(
        stt=deepgram.STT(model="nova-3", interim_results=True),
        tts=build_tts(voice),
        min_endpointing_delay=manager.round.patience_ms / 1000,
    )

    # The session starts and speaks BEFORE any slow work. Pack/intel
    # generation reads the user's documents with the LLM and 30s on the
    # free tier is normal; when it ran before session.start, the room had
    # no audio track the whole time, the client sat on "your interviewer
    # is joining" and gave up (live failure 2026-07-13, TEST-LOG finding
    # 2). The runner does not exist yet, so it is attached to the agent
    # after the queue is built; until then user speech is not an answer.
    interviewer = InterviewerAgent(None, "")
    await session.start(agent=interviewer, room=ctx.room)
    if cfg.source.use_pack or cfg.source.intel_text.strip():
        await session.say("Give me a moment while I read your documents.",
                          allow_interruptions=False)

    # Pack and intel questions are generated here, by their owning modules
    # (they may read user docs; the queue and interviewer never do). This
    # was only ever wired for the coach; the interview path compiled an
    # empty queue for pack/intel sources (live dead-end 2026-07-12).
    pack_qs = None
    intel_qs = None
    try:
        if cfg.source.use_pack:
            pack = await asyncio.to_thread(
                coach_questions.generate_pack,
                cfg.materials.get("resume", ""),
                cfg.materials.get("jd", ""), manager.round)
            # A drill rep is a handful of questions, not a full prep list.
            pack_qs = [Question(id=f"pack_{i + 1:02d}", text=q.text,
                                source="pack")
                       for i, q in enumerate(pack.questions[:6])]
        if cfg.source.intel_text.strip():
            intel_qs = await asyncio.to_thread(
                coach_intel.extract_questions, cfg.source.intel_text)
    except Exception:
        # LLM quota exhaustion (both providers rate-limited, live
        # 2026-07-12) lands in the empty-queue bank fallback below with a
        # spoken note instead of crashing the job.
        logger.exception("pack/intel generation failed; using bank fallback")
        pack_qs = intel_qs = None
    queue = compile_queue(cfg, topic_emphasis=persona.topic_emphasis,
                          pack_questions=pack_qs, intel_questions=intel_qs)
    fallback_note = ""
    if setup_missed:
        # The user filled a setup form that never arrived; running a default
        # drill without saying so reads as the app ignoring their choices.
        fallback_note = (" Heads up: your setup did not reach me, so this "
                         "is a default practice drill.")
    if not queue:
        # Zero grounded pack questions or empty intel extraction must not
        # dead-end the session; fall back to the round's question bank and
        # say so instead of going silent.
        cfg.source.use_pack = False
        cfg.source.bank_count = max(cfg.source.bank_count, 2)
        queue = compile_queue(cfg, topic_emphasis=persona.topic_emphasis)
        fallback_note = (" I could not build questions from your documents "
                         "this time, so I picked standard ones for this "
                         "round.")

    if cfg.session_type == SessionType.SIMULATION:
        sim_plan = planner.plan(queue, cfg.duration_min or 20, manager.round)
        logger.info("simulation plan: %d of %d questions in %d min "
                    "(%ds per question, %ds wrap reserve)",
                    sim_plan.question_count, len(queue),
                    sim_plan.duration_s // 60, sim_plan.per_question_s,
                    sim_plan.wrap_reserve_s)
        cloud = CloudSession.create_if_configured(
            ctx.room, "simulation", cfg.profile_id)
        runner: DrillRunner = SimulationRunner(
            session, manager, queue, sim_plan,
            on_end=lambda: ctx.shutdown(reason="user ended"),
            followup_mode=cfg.followup_mode, room=ctx.room, cloud=cloud)
    else:
        cloud = CloudSession.create_if_configured(
            ctx.room, "drill", cfg.profile_id)
        runner = DrillRunner(
            session, manager, queue,
            on_end=lambda: ctx.shutdown(reason="user ended"),
            followup_mode=cfg.followup_mode, room=ctx.room, cloud=cloud)

    loop = asyncio.get_running_loop()

    def _handle_rewrite(data) -> str:
        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(runner.send_rewrite()))
        return "ok"

    ctx.room.local_participant.register_rpc_method(
        "get_rewrite", _handle_rewrite)
    _register_interrupt_rpc(ctx, session, loop)

    @session.on("user_input_transcribed")
    def _on_transcribed(event) -> None:
        runner.on_partial(event.transcript, event.is_final)

    # The session is already live (started above, before generation);
    # handing the runner to the agent is what turns user speech into
    # answers from here on.
    interviewer.runner = runner

    if isinstance(runner, SimulationRunner):
        await runner.say(
            f"This is a timed simulation: {runner.total_questions} "
            f"question{'s' if runner.total_questions != 1 else ''} in "
            f"{runner.plan.duration_s // 60} minutes. No feedback between "
            "answers; you get a full debrief at the end. Take your time, "
            "pauses are fine. When you finish an answer, say that's my "
            f"answer.{fallback_note} Let's begin.")
    else:
        await runner.say("Ready. Take your time with each answer; pauses "
                         "are fine, I will wait. When you finish one, say "
                         f"that's my answer.{fallback_note} Let's begin.")
    if not await runner.ask_next_question():
        await runner.say("No questions compiled. Check the session config.")


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
