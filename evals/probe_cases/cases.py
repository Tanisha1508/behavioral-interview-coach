"""The 5 scripted probe-quality cases (spec Section 6). All local rules,
no LLM: each case feeds timed partials through the real decision loop and
checks probe type and timing against the spec's pass conditions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.engine import decision
from src.engine.decision import ActionKind
from src.engine.state import (
    AnswerState,
    Floor,
    PersonaParams,
    ProbeRecord,
    ProbeType,
    Question,
    load_round_profile,
)

ROOT = Path(__file__).resolve().parents[2]


def neutral_persona() -> PersonaParams:
    return PersonaParams(
        persona_id="eval_neutral", display_name="Eval interviewer",
        round_profile="pm",
        probe_mix={"specificity": 0.3, "ownership": 0.3, "quantify": 0.2, "depth": 0.2},
        intensity=3, interrupt_eagerness=1.0, interrupt_budget=2,
        patience_ms=600, time_budget_s=150)


@dataclass
class Script:
    name: str
    segments: list[tuple[int, str]]        # (start_s, chunk spoken from there)
    end_s: int
    silence: tuple[int, int] | None = None  # (start_s, end_s) mid-answer silence


@dataclass
class CaseResult:
    name: str
    fired: list[tuple[int, ProbeType]] = field(default_factory=list)
    queued: list[ProbeType] = field(default_factory=list)
    endpoint_action: str = ""
    endpoint_probe: ProbeType | None = None
    endpoint_text: str = ""


def _text_at(script: Script, t_ms: int) -> str:
    return " ".join(chunk for start_s, chunk in script.segments
                    if start_s * 1000 <= t_ms)


def run_case(script: Script, profile: str = "pm") -> CaseResult:
    round_profile = load_round_profile(ROOT / "config" / "rounds" / f"{profile}.yaml")
    state = AnswerState(
        question=Question(id=f"eval_{script.name}", text="Tell me about it."),
        round=round_profile, persona=neutral_persona(), interrupt_budget=2)
    result = CaseResult(name=script.name)

    for t_ms in range(2000, script.end_s * 1000 + 1, 2000):
        state.clock_ms = t_ms
        state.transcript_partial = _text_at(script, t_ms)
        if script.silence and script.silence[0] * 1000 <= t_ms <= script.silence[1] * 1000:
            state.floor = Floor.SILENCE
            if state.silence_started_ms is None:
                state.silence_started_ms = script.silence[0] * 1000
        else:
            state.floor = Floor.USER
            state.silence_started_ms = None
            # stalled resets when speech resumes
        signals = decision.compute_signals(state)
        action = decision.on_partial(state, signals)
        if action.kind == ActionKind.INTERRUPT and action.probe:
            result.fired.append((t_ms, action.probe.probe_type))
            state.probes_fired.append(ProbeRecord(
                probe_type=action.probe.probe_type, fired_at_ms=t_ms,
                trigger=action.probe.detail or "", text="(eval)",
                interrupted=True))
            state.pre_probe_transcript = ""  # eval scripts keep talking fresh

    # Re-apply silence state for the endpoint check when the script ends in
    # silence (the Silent case endpoints out of the stall).
    if script.silence and script.silence[1] * 1000 >= script.end_s * 1000 - 2000:
        state.floor = Floor.SILENCE
        state.silence_started_ms = script.silence[0] * 1000
        state.clock_ms = script.end_s * 1000
        decision.compute_signals(state)

    result.queued = [c.probe_type for c in state.queued_probes]
    import random
    endpoint = decision.on_endpoint(state, rng=random.Random(0))
    result.endpoint_action = endpoint.kind.value
    if endpoint.probe:
        result.endpoint_probe = endpoint.probe.probe_type
        from src.engine import probes as probes_mod
        result.endpoint_text = probes_mod.select_probe(
            endpoint.probe, state, rng=random.Random(0), use_llm=False)
    return result


# ---------- the 5 scripts ----------

VAGUE = Script(
    name="Vague",
    segments=[
        (0, "so in my last role there was a big project around the quarterly "
            "planning process and honestly it needed a lot of alignment work"),
        (10, "and what i did mostly was i aligned stakeholders and drove "
             "consensus around the direction we needed to take"),
        (22, "and i communicated effectively with everybody involved so that "
             "things kept moving along nicely without too much friction"),
        (35, "and i took ownership of the overall outcome and kept alignment "
             "going through the whole cycle basically"),
        (48, "and yeah it came together in the end after plenty of alignment "
             "and everyone felt pretty good about the process overall"),
    ],
    end_s=60)

WE_HEAVY = Script(
    name="We-heavy",
    segments=[
        (0, "last year the team picked up the payments migration and i was "
            "part of the group running it day to day"),
        (12, "we scoped the work and i split the milestones and i tracked "
             "the risks and we set up the reviews"),
        (26, "we ran the pilots and i fixed the issues and i briefed the "
             "leads while we kept the plan moving"),
        (40, "we handled the cutover and we watched the dashboards and we "
             "cleared the backlog and we told our sponsors"),
        (54, "and then we celebrated because we hit our date and we kept our "
             "quality bar and we felt our process worked and we documented "
             "what we learned and we shared our writeup"),
    ],
    end_s=70)

RAMBLING = Script(
    name="Rambling",
    segments=[
        (0, "for context i was working on the vendor platform at the time and "
            "the situation was that renewals were coming up"),
        (30, "and there is a lot of background here because the contracts had "
             "history going back years with custom terms in each region"),
        (60, "and the problem was the pricing model did not fit the newer "
             "usage patterns which meant every conversation started from "
             "scratch with each vendor"),
        (95, "and there were also internal considerations because finance "
             "wanted predictability while the field teams wanted flexibility "
             "and both had fair points honestly"),
        (125, "and i should also explain the regional differences because "
              "europe had different terms than asia and that shaped "
              "everything about how the discussions went"),
        (150, "and another piece of background worth mentioning is the "
              "procurement cycle timing which pushed conversations into the "
              "quarter boundaries"),
    ],
    end_s=164)

STRONG = Script(
    name="Strong",
    segments=[
        (0, "at the time i was the pm for checkout at a grocery app with 2 "
            "million weekly orders and the situation was cart abandonment "
            "sat at 31 percent for 3 straight quarters and i had been "
            "tracking my funnel numbers weekly"),
        (20, "the problem was mobile users hit a 9 field address form right "
             "before payment and the challenge was design wanted a full "
             "redesign which i knew would need 2 quarters i did not have"),
        (40, "so what i did was pull 14 session recordings and i built a case "
             "for a single page flow and i went to Sana our design lead with "
             "3 specific cut lines"),
        (60, "i decided to ship behind a flag to 5 percent of users and i "
             "wrote the rollout plan myself with 2 rollback triggers at 15 "
             "minute intervals"),
        (80, "as a result abandonment fell from 31 to 22 percent in 6 weeks "
             "and the result was 40 thousand more completed orders a month "
             "which we verified across 2 regions"),
        (105, "and what i learned was to size the fix to the evidence i had "
              "because the 1 page version i almost overruled turned out to "
              "be the winner and i have used that rule 3 times since"),
    ],
    end_s=130)

SILENT = Script(
    name="Silent",
    segments=[
        (0, "i was running the search relevance work and the situation was "
            "our click through rate had dropped 12 percent after a ranking "
            "change we had shipped 2 weeks earlier"),
        (20, "so i started by pulling the query logs and i compared the top "
             "200 queries before and after the change and i noticed the "
             "drop concentrated in long tail queries"),
    ],
    end_s=46,
    silence=(40, 46))


def evaluate() -> list[dict]:
    """Run all 5 cases and return pass/fail rows per spec pass conditions."""
    rows = []

    r = run_case(VAGUE, "pm")
    types = [t for _, t in r.fired]
    type_ok = types[:1] == [ProbeType.SPECIFICITY]
    timing_ok = bool(r.fired) and 25_000 <= r.fired[0][0] <= 90_000
    rows.append({"case": "Vague", "expected": "SPECIFICITY 25-90s",
                 "got": f"{types} at {[t for t, _ in r.fired]}",
                 "type_pass": type_ok, "timing_pass": timing_ok})

    r_pm = run_case(WE_HEAVY, "pm")
    r_co = run_case(WE_HEAVY, "consulting")
    pm_own = [t for t, ty in r_pm.fired if ty == ProbeType.OWNERSHIP]
    co_own = [t for t, ty in r_co.fired if ty == ProbeType.OWNERSHIP]
    type_ok = bool(pm_own) and bool(co_own)
    timing_ok = bool(pm_own) and bool(co_own) and co_own[0] < pm_own[0]
    rows.append({"case": "We-heavy", "expected": "OWNERSHIP; consulting earlier than pm",
                 "got": f"pm at {pm_own}, consulting at {co_own}",
                 "type_pass": type_ok, "timing_pass": timing_ok})

    r = run_case(RAMBLING, "pm")
    types = [ty for _, ty in r.fired]
    redirects = [t for t, ty in r.fired if ty == ProbeType.REDIRECT]
    type_ok = ProbeType.REDIRECT in types
    timing_ok = bool(redirects) and redirects[0] <= 165_000  # within 15s of 150s
    rows.append({"case": "Rambling", "expected": "REDIRECT within 15s of 150s",
                 "got": f"{types} at {[t for t, _ in r.fired]}",
                 "type_pass": type_ok, "timing_pass": timing_ok})

    r = run_case(STRONG, "pm")
    type_ok = len(r.fired) == 0
    timing_ok = len(r.queued) <= 1
    rows.append({"case": "Strong", "expected": "no interrupt; <=1 queued",
                 "got": f"fired {len(r.fired)}, queued {len(r.queued)}",
                 "type_pass": type_ok, "timing_pass": timing_ok})

    r = run_case(SILENT, "pm")
    type_ok = (r.endpoint_probe == ProbeType.NUDGE and len(r.fired) == 0)
    leading_words = ("metric", "number", "mention", "result", "story",
                     "detail", "outcome")
    timing_ok = type_ok and not any(w in r.endpoint_text.lower()
                                    for w in leading_words)
    rows.append({"case": "Silent", "expected": "NUDGE, non-leading",
                 "got": f"{r.endpoint_probe} text={r.endpoint_text!r}",
                 "type_pass": type_ok, "timing_pass": timing_ok})
    return rows


if __name__ == "__main__":
    passed_type = passed_timing = 0
    for row in evaluate():
        mark = "PASS" if row["type_pass"] and row["timing_pass"] else (
            "TYPE-ONLY" if row["type_pass"] else "FAIL")
        passed_type += row["type_pass"]
        passed_timing += row["type_pass"] and row["timing_pass"]
        print(f"[{mark:9}] {row['case']:9} expected: {row['expected']}")
        print(f"            got: {row['got']}")
    print(f"\ntype: {passed_type}/5 (need 5), type+timing: {passed_timing}/5 (need 4)")
