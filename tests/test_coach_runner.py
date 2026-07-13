"""Voice Coach session behavior (spec scope change 2026-07-12): pack and
coverage at start, spoken Q&A grounded in docs, end phrase shuts down."""

import asyncio

import src.agent as agent_mod
from src.agent import CoachRunner
from src.coach.coverage import CoverageEntry, CoverageReport
from src.coach.questions import PackQuestion, QuestionPack
from src.session.setup import SessionConfig


class FakeSession:
    def __init__(self):
        self.spoken: list[str] = []

    async def say(self, text, allow_interruptions=True):
        self.spoken.append(text)


def make_coach(materials, monkeypatch, reply="Use your migration story."):
    pack = QuestionPack(questions=[
        PackQuestion(text="Q one?", bucket="conflict", resume_line="led x"),
        PackQuestion(text="Q two?", bucket="failure", resume_line="shipped y"),
    ])
    coverage = CoverageReport(entries=[
        CoverageEntry(question="Q one?", strength="STRONG", covered_by="s"),
        CoverageEntry(question="Q two?", strength="GAP"),
    ])
    monkeypatch.setattr(agent_mod.coach_questions, "generate_pack",
                        lambda *a, **k: pack)
    monkeypatch.setattr(agent_mod.coach_coverage, "coverage_map",
                        lambda *a, **k: coverage)
    cfg = SessionConfig(profile_id="pm", mode="coach", materials=materials)
    session = FakeSession()
    ended = []
    runner = CoachRunner(session, cfg, on_end=lambda: ended.append(True),
                         reply_fn=lambda msg: reply)
    return runner, session, ended


def test_start_builds_pack_and_reports_gaps(monkeypatch):
    async def run():
        runner, session, _ = make_coach(
            {"resume": "led x and shipped y", "jd": "pm role",
             "stories": "my stories"}, monkeypatch)
        await runner.start()
        intro = session.spoken[-1]
        assert "2 questions" in intro
        assert "1 of them uncovered" in intro
        assert runner.pack is not None and runner.coverage is not None
    asyncio.run(run())


def test_start_without_resume_asks_for_it(monkeypatch):
    async def run():
        runner, session, _ = make_coach({}, monkeypatch)
        await runner.start()
        assert "resume" in session.spoken[-1].lower()
        assert runner.pack is None
    asyncio.run(run())


def test_turn_gets_spoken_reply(monkeypatch):
    async def run():
        runner, session, _ = make_coach(
            {"resume": "led x"}, monkeypatch, reply="Open with the metric.")
        await runner.start()
        await runner.on_turn_complete("How should I open my answer?")
        assert session.spoken[-1] == "Open with the metric."
        assert ("candidate", "How should I open my answer?") in runner.history
    asyncio.run(run())


def test_clicked_question_speaks_a_game_plan(monkeypatch):
    async def run():
        runner, session, _ = make_coach(
            {"resume": "led x"}, monkeypatch,
            reply="Use the Oracle story. Open with six of forty.")
        await runner.start()
        await runner.discuss_question("Q one?")
        assert session.spoken[-1] == "Use the Oracle story. Open with six of forty."
        assert any("game plan" in t for s, t in runner.history
                   if s == "candidate"), "click did not enter the history"
    asyncio.run(run())


def test_clicks_after_end_are_ignored(monkeypatch):
    monkeypatch.setattr(agent_mod, "END_SHUTDOWN_DELAY_S", 0.01)

    async def run():
        runner, session, _ = make_coach({"resume": "led x"}, monkeypatch)
        await runner.start()
        await runner.on_turn_complete("end session")
        says = len(session.spoken)
        await runner.discuss_question("Q one?")
        assert len(session.spoken) == says
    asyncio.run(run())


def test_parroted_openings_are_trimmed(monkeypatch):
    async def run():
        runner, session, _ = make_coach(
            {"resume": "led x"}, monkeypatch,
            reply="You're referring to Story 1.1, Cloud Transition "
                  "Diagnostic Tools at Oracle. Open with the six of forty "
                  "number.")
        await runner.start()
        await runner.on_turn_complete("How do I open?")
        assert session.spoken[-1] == "Open with the six of forty number."
    asyncio.run(run())


def test_repeated_opening_sentence_is_trimmed(monkeypatch):
    async def run():
        runner, session, _ = make_coach({"resume": "led x"}, monkeypatch)
        await runner.start()
        runner.reply_fn = lambda m: ("Use the Oracle diagnostics story "
                                     "for this one. Lead with the metric.")
        await runner.on_turn_complete("Which story for question one?")
        runner.reply_fn = lambda m: ("Use the Oracle diagnostics story "
                                     "for this one. Then pivot to impact.")
        await runner.on_turn_complete("And for question two?")
        assert session.spoken[-1] == "Then pivot to impact.", \
            "identical opening sentence was spoken twice in a row"
    asyncio.run(run())


def test_end_phrase_ends_session(monkeypatch):
    monkeypatch.setattr(agent_mod, "END_SHUTDOWN_DELAY_S", 0.01)

    async def run():
        runner, session, ended = make_coach({"resume": "led x"}, monkeypatch)
        await runner.start()
        await runner.on_turn_complete("Thanks, end session.")
        await asyncio.sleep(0.05)
        assert ended, "end phrase did not shut the coach session down"
        assert "luck" in session.spoken[-1].lower()
    asyncio.run(run())


def test_no_replies_after_end(monkeypatch):
    monkeypatch.setattr(agent_mod, "END_SHUTDOWN_DELAY_S", 0.01)

    async def run():
        runner, session, ended = make_coach({"resume": "led x"}, monkeypatch)
        await runner.start()
        await runner.on_turn_complete("Thanks, end session.")
        says_after_goodbye = len(session.spoken)
        # Echo or trailing speech during the shutdown grace period.
        await runner.on_turn_complete("Good luck out there.")
        await runner.on_turn_complete("Ending the session.")
        await asyncio.sleep(0.05)
        assert len(session.spoken) == says_after_goodbye, \
            "coach kept replying after the session ended"
    asyncio.run(run())


def test_speech_during_reply_is_batched_not_dropped(monkeypatch):
    async def run():
        runner, session, _ = make_coach({"resume": "led x"}, monkeypatch)
        await runner.start()
        seen: list[str] = []

        import threading
        gate = threading.Event()

        def slow_reply(msg):
            seen.append(msg)
            if len(seen) == 1:
                gate.wait(timeout=2)  # first reply generating...
            return f"reply to: {msg}"

        runner.reply_fn = slow_reply
        first = asyncio.create_task(
            runner.on_turn_complete("How should I answer"))
        await asyncio.sleep(0.05)
        # ...while the user keeps talking:
        await runner.on_turn_complete("the conflict question?")
        gate.set()
        await first
        await asyncio.sleep(0.1)
        assert seen[0] == "How should I answer"
        assert seen[1] == "the conflict question?", \
            "speech during reply generation was dropped"
    asyncio.run(run())
