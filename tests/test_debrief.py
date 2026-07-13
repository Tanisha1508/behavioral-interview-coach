"""Simulation debrief rendering (spec 2.2): cross-answer patterns are
exact counts computed in code, missed ammo deduplicates across the set,
and ungraded answers are named, never dropped silently."""

from src.grading.ammo import AmmoItem
from src.grading.grader import DIMENSIONS, DimensionScore, RubricScores
from src.grading.report import (RepResult, combined_ammo, debrief_patterns,
                                render_debrief, spoken_debrief)


def make_scores(weak: tuple[str, ...] = ()) -> RubricScores:
    return RubricScores(
        dimensions={d: DimensionScore(level="Gap" if d in weak else "Solid")
                    for d in DIMENSIONS},
        spoken_summary=["One fix."])


def rep(weak=(), question="Q?", ammo=None, graded=True) -> RepResult:
    return RepResult(question=question, duration_s=90,
                     scores=make_scores(weak) if graded else None,
                     ammo=ammo or [])


def test_pattern_needs_two_weak_answers_and_half_the_set():
    reps = [rep(weak=("i_vs_we",)), rep(weak=("i_vs_we",)),
            rep(), rep(weak=("structure",))]
    patterns = debrief_patterns(reps)
    assert "we-heavy in 2 of 4 answers" in patterns
    # structure was weak once: not a pattern.
    assert not any("hard to follow" in p for p in patterns)


def test_single_answer_yields_no_patterns():
    assert debrief_patterns([rep(weak=("i_vs_we",))]) == []


def test_ungraded_reps_do_not_dilute_pattern_counts():
    reps = [rep(weak=("quantification",)), rep(weak=("quantification",)),
            rep(graded=False), rep(graded=False)]
    assert debrief_patterns(reps) == ["missing numbers in 2 of 2 answers"]


def test_combined_ammo_dedupes_on_fact():
    a1 = AmmoItem(fact="Cut latency 40%", doc_source="resume", relevance="r")
    a2 = AmmoItem(fact="cut latency 40%", doc_source="resume", relevance="r")
    a3 = AmmoItem(fact="Led a team of 8", doc_source="stories", relevance="r")
    out = combined_ammo([rep(ammo=[a1]), rep(ammo=[a2, a3])])
    assert [a.fact for a in out] == ["Cut latency 40%", "Led a team of 8"]


def test_spoken_debrief_names_dropped_ungraded_and_first_pattern():
    reps = [rep(weak=("i_vs_we",)), rep(weak=("i_vs_we",)),
            rep(graded=False)]
    script = spoken_debrief(reps, debrief_patterns(reps),
                            combined_ammo(reps), dropped=2)
    assert "3 questions" in script
    assert "dropped 2" in script
    assert "could not score 1" in script
    assert "we-heavy" in script
    assert "say end" in script


def test_render_debrief_marks_unscored_answers():
    card = render_debrief([rep(), rep(graded=False)], [], [], dropped=1)
    assert "not scored" in card
    assert "1 planned question dropped" in card
