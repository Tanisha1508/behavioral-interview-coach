"""Simulation planner (spec 2.2): per-question time estimates from the
profile's depth_style, a wrap reserve, question count for the chosen
duration, live queue dropping when answers overrun. Reads RoundProfile
values only; never branches on a profile name.
"""

from __future__ import annotations

from dataclasses import dataclass

WRAP_RESERVE_S = 180  # spec 2.2: keep 3 minutes to close the session

# Spec 2.2: ONE_STORY_DEEP runs 15 to 20 min per story with probing;
# BREADTH runs 5 to 7 min per question. The midpoint plans the initial
# count; the low end decides live whether one more question still fits.
ESTIMATES_S = {
    "ONE_STORY_DEEP": (1050, 900),
    "BREADTH": (360, 300),
}


@dataclass
class SimulationPlan:
    duration_s: int
    wrap_reserve_s: int
    per_question_s: int  # midpoint estimate, plans the initial count
    min_question_s: int  # low estimate, gates asking one more live
    question_count: int


def plan(queue: list, duration_min: int, round) -> SimulationPlan:
    """How many of the queued questions fit the session. Always at least
    one: a simulation with zero questions is not a session."""
    mid, low = ESTIMATES_S.get(round.depth_style, ESTIMATES_S["BREADTH"])
    duration_s = max(15, min(60, duration_min)) * 60  # spec bounds: 15-60
    usable = duration_s - WRAP_RESERVE_S
    count = max(1, min(len(queue), usable // mid))
    return SimulationPlan(duration_s=duration_s,
                          wrap_reserve_s=WRAP_RESERVE_S,
                          per_question_s=mid, min_question_s=low,
                          question_count=count)


def on_overrun(plan: SimulationPlan, elapsed_s: int) -> int:
    """How many more questions still fit right now. The runner calls this
    after every completed answer; when fewer fit than remain in the queue,
    the overflow drops (spec 2.2 live queue dropping)."""
    remaining = plan.duration_s - plan.wrap_reserve_s - elapsed_s
    if remaining <= 0:
        return 0
    return int(remaining // plan.min_question_s)
