"""Round profile and bank config validation (scope item 2)."""

from pathlib import Path

import pytest

from src.engine.state import (
    BUNDLED_PROFILE_IDS,
    DepthStyle,
    load_bank,
    load_round_profile,
)

ROOT = Path(__file__).resolve().parents[1]
ROUNDS = ROOT / "config" / "rounds"
BANKS = ROOT / "config" / "banks"


def test_exactly_five_bundled_profiles():
    names = {p.stem for p in ROUNDS.glob("*.yaml")}
    assert names == BUNDLED_PROFILE_IDS


@pytest.mark.parametrize("name", sorted(BUNDLED_PROFILE_IDS))
def test_round_profile_loads_and_validates(name):
    profile = load_round_profile(ROUNDS / f"{name}.yaml")
    assert profile.profile_id == name


def test_pm_values_match_spec():
    p = load_round_profile(ROUNDS / "pm.yaml")
    assert p.time_budget_s == 150
    assert p.we_ratio_threshold == 0.6
    assert p.emotional_probe_weight == 0.0
    assert p.patience_ms == 600
    assert p.length_band_s == (90, 150)
    assert p.depth_style == DepthStyle.BREADTH


def test_consulting_values_match_spec():
    p = load_round_profile(ROUNDS / "consulting.yaml")
    assert p.time_budget_s == 210
    assert p.we_ratio_threshold == 0.45
    assert p.emotional_probe_weight == 0.5
    assert p.patience_ms == 900
    assert p.depth_style == DepthStyle.ONE_STORY_DEEP


@pytest.mark.parametrize("name", sorted(BUNDLED_PROFILE_IDS))
def test_bank_loads_with_valid_questions(name):
    questions = load_bank(BANKS / f"{name}.yaml")
    assert len(questions) >= 2
    ids = [q.id for q in questions]
    assert len(ids) == len(set(ids)), "duplicate question ids"
    for q in questions:
        assert q.text.strip()
        assert q.expected_buckets


def test_full_banks_have_volume():
    assert len(load_bank(BANKS / "pm.yaml")) >= 12
    assert len(load_bank(BANKS / "consulting.yaml")) >= 10


def test_rubric_yaml_parses_and_is_complete():
    """The grader loads rubric.yaml on every rep; a YAML syntax error here
    (e.g. an unquoted colon mid-sentence) crashes grading live. Regression
    for the 2026-07-12 mid-test wedge."""
    from src.grading.grader import DIMENSIONS, load_rubric
    rubric = load_rubric()
    for dim in DIMENSIONS:
        entry = rubric["dimensions"][dim]
        assert entry["question"].strip()
        assert set(entry["levels"]) == {"Solid", "NeedsWork", "Gap"}
    assert rubric["spoken_summary"]["lines"] == 1
