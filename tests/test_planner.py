"""Simulation planner (spec 2.2): question count from depth_style
estimates with a wrap reserve, and live queue dropping on seeded overruns
(spec test: 20-min simulation plan drops questions correctly)."""

from pathlib import Path

from src.engine.state import Question, load_round_profile
from src.session import planner

ROOT = Path(__file__).resolve().parents[1]


def load_round(profile_id: str):
    return load_round_profile(ROOT / "config" / "rounds" / f"{profile_id}.yaml")


def make_queue(n: int) -> list[Question]:
    return [Question(id=f"q{i}", text=f"Question {i}?") for i in range(n)]


def test_20_min_breadth_plans_two_questions():
    plan = planner.plan(make_queue(6), 20, load_round("pm"))
    # 1200s minus the 180s wrap reserve leaves 1020s; at 360s per
    # BREADTH question that is 2 questions.
    assert plan.question_count == 2
    assert plan.wrap_reserve_s == 180


def test_20_min_one_story_deep_still_asks_one():
    plan = planner.plan(make_queue(6), 20, load_round("consulting"))
    # One deep story needs ~17.5 min; 17 usable minutes round to zero,
    # but a simulation with zero questions is not a session.
    assert plan.question_count == 1


def test_count_capped_by_queue_size():
    plan = planner.plan(make_queue(2), 60, load_round("pm"))
    assert plan.question_count == 2


def test_duration_clamped_to_spec_bounds():
    assert planner.plan(make_queue(6), 5, load_round("pm")).duration_s == 900
    assert planner.plan(make_queue(6), 90, load_round("pm")).duration_s == 3600


def test_overrun_drops_questions_as_time_runs_out():
    plan = planner.plan(make_queue(6), 20, load_round("pm"))
    # Fresh clock: the full usable window fits 3 more at the 300s floor.
    assert planner.on_overrun(plan, 0) == 3
    # One long answer ate 500s: only one more question fits.
    assert planner.on_overrun(plan, 500) == 1
    # Past the wrap reserve boundary: nothing more fits.
    assert planner.on_overrun(plan, 1050) == 0
    assert planner.on_overrun(plan, 5000) == 0
