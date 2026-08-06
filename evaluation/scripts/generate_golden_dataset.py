"""Builds the 100-item golden dataset (8 categories) used by this evaluation
suite. Extends evals/golden/dataset.py's 50-item set (excellent/weak/average/
off_topic, reused unchanged) with 50 new items across 4 new categories:

  star_explicit  -- canonical S-T-A-R order, explicit transition labels
  non_star       -- the SAME facts as star_explicit, reordered result-first,
                     to isolate whether the grader penalizes order (it
                     should not: rubric.yaml says "never penalize an answer
                     for deviating from the canonical sequence", and
                     DECISIONS.md 2026-07-11 states structure is graded on
                     followability, not canonical order)
  incomplete     -- situation/complication given, then cuts off before
                     action/resolution/reflection
  fabricated     -- internally inconsistent numeric/factual claims, to test
                     whether anything in the pipeline catches self-
                     contradiction (nothing does today -- see the report)

All labels are author intent at authoring time, not independent human
ratings. Deterministic and reusable: re-running this script produces the
same 100 items every time (no randomness, no LLM calls).
"""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from evals.golden.dataset import (  # noqa: E402
    EXCELLENT_PARAMS, _finalize, build_golden_set,
)

OUT_DIR = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# star_explicit: same facts as EXCELLENT_PARAMS, explicit S/T/A/R labels,
# strict canonical order.
# ---------------------------------------------------------------------------

T_STAR_EXPLICIT = (
    "Situation: I was the {role} on {product} at {company}, which had "
    "{scale} at the time. Task: the problem was {problem}, and it had been "
    "getting worse for {duration_phrase}, so my task was to fix it before "
    "it did more damage. I had already tried a couple of quick fixes myself "
    "before this, and neither one moved the number, so I knew it needed a "
    "real investigation. Action: what I did was pull {evidence} and I found "
    "{finding}. I built a proposal and I went to {colleague}, our "
    "{colleague_role}, with {num_options} specific options, and I walked "
    "{colleague} through how each option would land for our highest-value "
    "customers specifically, since that was what leadership cared about "
    "most. I decided to {decision}, writing the rollout plan myself with "
    "{safeguard}, and I checked in with {colleague} twice a week during the "
    "rollout so we could react fast if anything looked off. Result: "
    "{metric_before} improved to {metric_after} within {outcome_timeframe}, "
    "verified across {verify_scope}. What I learned is {learning}, and I "
    "have used that rule {reuse_count} times since."
)

# ---------------------------------------------------------------------------
# non_star: the SAME facts, told result-first / achievement-first, with no
# canonical-order transition words -- deliberately out of S-T-A-R sequence.
# ---------------------------------------------------------------------------

T_NON_STAR = (
    "the headline is {metric_before} went from a problem to {metric_after} "
    "within {outcome_timeframe}, and we verified that across {verify_scope}. "
    "that came out of my time as {role} on {product} at {company} -- "
    "{scale} was riding on it. what actually got us there was {decision}, "
    "which I decided on after I went to {colleague}, our {colleague_role}, "
    "with {num_options} specific options I had built from {evidence}; "
    "{finding} is what that digging turned up. I also walked {colleague} "
    "through how each option would land for our highest-value customers "
    "specifically, since that was what leadership cared about most, and I "
    "wrote the rollout plan myself with {safeguard}, checking in with "
    "{colleague} twice a week during the rollout so we could react fast if "
    "anything looked off. the backstory is the problem had been {problem} "
    "for {duration_phrase} before I got pulled in, and I'd already tried a "
    "couple of quick fixes myself that hadn't worked. {learning} is the "
    "lesson I keep coming back to, {reuse_count} times since."
)

# ---------------------------------------------------------------------------
# incomplete: situation + complication only, then trails off before action,
# resolution, or reflection.
# ---------------------------------------------------------------------------

INCOMPLETE_SCENARIOS = [
    "the situation was I was leading the vendor migration at a logistics "
    "startup, and about 40 warehouses depended on the old system. the "
    "problem was the new vendor's API kept failing intermittently during "
    "peak hours, and honestly the whole thing was pretty stressful because "
    "leadership was watching closely. so what I did was, um, I started "
    "looking into the failure logs and, sorry, I'm blanking on exactly "
    "what came next.",

    "at the time I was the PM for the referral program at a consumer app, "
    "and signups had been declining for a few months. the problem was we "
    "didn't really know why, there were a few theories floating around "
    "about the incentive structure. I pulled some data and, honestly, I'm "
    "not totally sure how to summarize what happened after that.",

    "the situation was our onboarding flow at a fintech company had a big "
    "drop-off at the identity verification step, something like a third of "
    "users never finished it. the problem was compliance required that "
    "step, so we couldn't just remove it, and the vendor doing the "
    "verification was slow to respond to our questions.",

    "I was working on the search ranking team at a marketplace, and click-"
    "through rate had dropped after a recent change. the problem was it "
    "wasn't obvious right away why, since a few things shipped around the "
    "same time. I remember pulling logs but I don't really remember the "
    "rest clearly.",

    "at the time I was managing the support queue at a SaaS company, and "
    "response times had crept up over a quarter. the problem was we'd lost "
    "two support reps and hadn't backfilled yet, so the remaining team was "
    "stretched pretty thin.",

    "the situation was I was on the growth team at a media app, and paid "
    "acquisition costs had climbed a lot faster than revenue per user. the "
    "problem was finance wanted an answer within the week, which wasn't a "
    "lot of time to actually dig into it properly.",

    "I was the PM for billing at an enterprise software company, and a "
    "chunk of invoices were going out with the wrong tax calculation. the "
    "problem was it had apparently been happening for a couple months "
    "before anyone noticed, so there was already a backlog of bad "
    "invoices.",

    "at the time our team owned the internal deployment pipeline, and "
    "deploys had started failing randomly, maybe one in five. the problem "
    "was it wasn't consistent, so it was hard to even reproduce reliably "
    "enough to debug.",

    "the situation was I was working on notifications at a fitness app, "
    "and users were complaining about getting too many reminders. the "
    "problem was different teams owned different notification types, so "
    "no one had the full picture of what a user was actually receiving.",

    "I was PM for the checkout experience at a retailer, and there was a "
    "spike in payment failures right before a big sale weekend. the "
    "problem was our payment processor's status page said everything was "
    "fine, which made it confusing to even know where to start.",

    "at the time I owned the data pipeline for our reporting dashboards at "
    "a logistics company, and numbers had started looking inconsistent "
    "between two different reports that should have matched. the problem "
    "was both reports pulled from different systems that were supposed to "
    "sync nightly.",

    "the situation was our hiring team at a mid-size company had a "
    "candidate experience survey come back much worse than usual, and "
    "leadership wanted to know why. the problem was the survey itself "
    "didn't break down by stage, so it wasn't clear where things had gone "
    "wrong.",

    "I was working on the mobile app's crash rate at a media company, and "
    "crashes had ticked up noticeably after a release. the problem was the "
    "crash reports weren't grouping cleanly, so it looked like dozens of "
    "small issues instead of possibly one root cause.",
]

# ---------------------------------------------------------------------------
# fabricated: internally inconsistent claims (contradicting numbers or
# implausible scale shifts within the same answer). No component in this
# codebase fact-checks claims -- this category exists to test that directly.
# ---------------------------------------------------------------------------

FABRICATED_SCENARIOS = [
    "the situation was I was the sole PM on a 3-person startup team, and "
    "we had no budget at all for this project. the problem was our biggest "
    "competitor was outspending us. so what I did was I personally led a "
    "200-person cross-functional task force to redesign the entire "
    "platform in a week. as a result, revenue grew from 2 million to 2 "
    "billion dollars in that single week. what I learned is that speed "
    "matters more than anything.",

    "the situation was I was a junior PM, six months into my first job, "
    "at the time. the problem was our onboarding conversion was stuck at "
    "12 percent. so what I did was I single-handedly rebuilt our entire "
    "backend infrastructure over a weekend with no help from engineering. "
    "as a result, conversion jumped to 340 percent, and the CEO gave me "
    "his job. what I learned is that anything is possible if you just try "
    "hard enough.",

    "the situation was I was managing a small feature team of 4 people at "
    "a startup with about 10,000 users. the problem was our server costs "
    "were too high for our size. so what I did was I negotiated directly "
    "with the CEO of AWS to cut our bill by 99 percent overnight, saving "
    "us 50 million dollars a year even though our total revenue was under "
    "1 million dollars. as a result, we became profitable instantly. what "
    "I learned is that you should always ask for what you want.",

    "the situation was I was an intern at the time, three weeks into the "
    "internship. the problem was the company's flagship product had a "
    "critical bug in production. so what I did was I fixed it myself in "
    "five minutes without looking at any code, and I also rewrote the "
    "entire codebase from scratch that same afternoon. as a result, the "
    "company's valuation tripled the next day because of my fix. what I "
    "learned is that experience doesn't matter as much as people think.",

    "the situation was I was a product manager for a 2-person weekend "
    "hobby project with zero users. the problem was we needed more "
    "traction. so what I did was I ran a marketing campaign that reached "
    "every person on earth simultaneously through a channel I invented "
    "myself. as a result, we had 12 billion signups in one day, which is "
    "more people than exist. what I learned is that ambition has no "
    "limits.",

    "the situation was I joined a team of 5 people building an internal "
    "tool nobody outside the company used. the problem was leadership "
    "wanted more visibility into usage. so what I did was I personally "
    "flew to every one of our 400,000 enterprise customers' offices in a "
    "single afternoon to interview them face to face. as a result, I "
    "collected feedback that increased our stock price by 800 percent, "
    "even though we were a private company with no stock. what I learned "
    "is that direct customer contact is invaluable.",

    "the situation was I was working part-time, 10 hours a week, on a "
    "student project with a team of 2 classmates. the problem was we had "
    "no engineering resources and a deadline in 3 days. so what I did was "
    "I wrote 500,000 lines of production code by myself in that time. as "
    "a result, our project won a Nobel Prize, and we signed a deal worth "
    "more than the GDP of a mid-size country. what I learned is that "
    "constraints breed creativity.",

    "the situation was I managed a support queue with 2 other agents "
    "handling maybe 30 tickets a day total. the problem was response "
    "times were slow. so what I did was I personally answered 4 million "
    "tickets in one afternoon without using any tools or automation. as a "
    "result, our customer satisfaction score went from 60 percent to 600 "
    "percent, which is not a possible percentage. what I learned is that "
    "hard work always pays off.",

    "the situation was I was one of three founders at a pre-seed startup "
    "that had raised no outside funding yet. the problem was we needed "
    "capital fast. so what I did was I convinced every venture capital "
    "firm in the world to invest on the same day, raising 900 trillion "
    "dollars, more money than exists in the global economy. as a result, "
    "we were instantly the most valuable company ever. what I learned is "
    "that confidence opens doors.",

    "the situation was I was a new hire, two weeks into the job, on a "
    "team of 6. the problem was our product had a 2-star app rating. so "
    "what I did was I personally called and apologized to every single "
    "one of our 8 million users individually within one business day. as "
    "a result, our rating went to 12 stars, which does not exist on a "
    "5-star scale. what I learned is that personal attention scales "
    "infinitely.",

    "the situation was I ran a small internal pilot with 15 test users at "
    "an enterprise software company. the problem was the pilot metrics "
    "were mixed. so what I did was I unilaterally rewrote our entire "
    "sales contract with all 50,000 of our enterprise customers overnight "
    "without legal review. as a result, every single customer signed a "
    "10-year renewal the next morning, and our churn dropped to negative "
    "40 percent, which is not mathematically possible. what I learned is "
    "that boldness beats process.",

    "the situation was I was a product analyst, not a decision-maker, on "
    "a team where I had no direct reports. the problem was our roadmap "
    "was unclear. so what I did was I fired our entire executive team and "
    "became CEO on the spot without any authority to do so. as a result, "
    "the company's headcount grew from 40 to 4 million employees in a "
    "single quarter. what I learned is that leadership is about taking "
    "initiative.",
]


def build_extra_items(params, template, category, prefix):
    return [
        _finalize(f"{prefix}_{i:02d}", category, template.format(**p))
        for i, p in enumerate(params, start=1)
    ]


def build_text_items(texts, category, prefix):
    return [
        _finalize(f"{prefix}_{i:02d}", category, text)
        for i, text in enumerate(texts, start=1)
    ]


def build_full_dataset():
    items = build_golden_set()  # 50: excellent/weak/average/off_topic (reused, unchanged)
    items += build_extra_items(EXCELLENT_PARAMS, T_STAR_EXPLICIT, "star_explicit", "star_explicit")
    items += build_extra_items(EXCELLENT_PARAMS, T_NON_STAR, "non_star", "non_star")
    items += build_text_items(INCOMPLETE_SCENARIOS, "incomplete", "incomplete")
    items += build_text_items(FABRICATED_SCENARIOS, "fabricated", "fabricated")
    return items


def main():
    items = build_full_dataset()
    by_cat = {}
    for it in items:
        by_cat.setdefault(it.category, 0)
        by_cat[it.category] += 1
    print(f"total items: {len(items)}")
    for cat, n in sorted(by_cat.items()):
        print(f"  {cat:16s} {n}")

    records = [asdict(it) for it in items]
    (OUT_DIR / "GOLDEN_DATASET.json").write_text(json.dumps(records, indent=2))

    with open(OUT_DIR / "GOLDEN_DATASET.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "category", "question", "word_count", "duration_s", "text"])
        for it in items:
            w.writerow([it.id, it.category, it.question, it.word_count,
                       it.duration_s, it.text])

    print(f"\nwrote {OUT_DIR / 'GOLDEN_DATASET.json'}")
    print(f"wrote {OUT_DIR / 'GOLDEN_DATASET.csv'}")


if __name__ == "__main__":
    main()
