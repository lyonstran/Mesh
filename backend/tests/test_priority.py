"""Priority formula (PLAN.md §9.4). Pure functions, no database."""

from datetime import UTC, datetime, timedelta

import pytest

from app.db import DEFAULT_WEIGHTS
from app.services.priority import FACTORS, compute, normalize_weights

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


def _compute(urgency=3, hazard_level=0, eji_rank=0.5, minutes=0.0, is_open=True, weights=None):
    return compute(
        urgency=urgency,
        hazard_level=hazard_level,
        eji_rank=eji_rank,
        created_at=NOW - timedelta(minutes=minutes),
        now=NOW,
        is_open=is_open,
        weights=weights or normalize_weights(DEFAULT_WEIGHTS),
    )


def test_formula_matches_plan_defaults():
    score, _ = _compute(urgency=5, hazard_level=3, eji_rank=0.8, minutes=30)
    expected = 0.45 * 1.0 + 0.20 * 1.0 + 0.20 * 0.8 + 0.15 * 0.5
    assert score == pytest.approx(expected, abs=1e-4)


def test_bounds_are_zero_and_one():
    assert _compute(urgency=1, hazard_level=0, eji_rank=0.0, minutes=0)[0] == 0
    assert _compute(urgency=5, hazard_level=3, eji_rank=1.0, minutes=600)[0] == pytest.approx(1.0)


def test_breakdown_contributions_sum_to_priority():
    score, breakdown = _compute(urgency=4, hazard_level=2, eji_rank=0.63, minutes=12)
    assert sum(breakdown[k]["contribution"] for k in FACTORS) == pytest.approx(score, abs=1e-3)
    for k in FACTORS:
        assert set(breakdown[k]) == {"raw", "value", "weight", "contribution", "source"}
    assert breakdown["note"] == "Weights are designed defaults, not fitted."


def test_missing_eji_is_neutral_and_flagged():
    _, breakdown = _compute(eji_rank=None)
    assert breakdown["eji"]["value"] == 0.5 and breakdown["eji_missing"] is True
    assert _compute(eji_rank=0.2)[1]["eji_missing"] is False


def test_wait_caps_at_an_hour_and_stops_once_not_open():
    assert _compute(minutes=30)[1]["wait"]["value"] == 0.5
    assert _compute(minutes=240)[1]["wait"]["value"] == 1.0
    assert _compute(minutes=240, is_open=False)[1]["wait"]["value"] == 0.0


def test_out_of_range_inputs_are_clamped():
    _, b = _compute(urgency=9, hazard_level=7, eji_rank=1.4)
    assert (b["urgency"]["value"], b["hazard"]["value"], b["eji"]["value"]) == (1.0, 1.0, 1.0)


def test_weights_normalize_to_one_and_reject_negatives():
    w = normalize_weights({"urgency": 2, "hazard": 1, "eji": 1, "wait": -5})
    assert sum(w.values()) == pytest.approx(1.0)
    assert w["wait"] == 0 and w["urgency"] == pytest.approx(0.5)


def test_all_zero_weights_fall_back_to_defaults():
    assert normalize_weights({"urgency": 0, "hazard": 0, "eji": 0, "wait": 0}) == DEFAULT_WEIGHTS


def test_higher_urgency_always_ranks_higher_all_else_equal():
    scores = [_compute(urgency=u, hazard_level=1, eji_rank=0.4)[0] for u in range(1, 6)]
    assert scores == sorted(scores) and len(set(scores)) == 5
