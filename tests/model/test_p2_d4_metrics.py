import pytest

from alifelm.model.p2_d4_metrics import D4_CANDIDATE_ORDER, select_component_candidate


def test_d4_candidate_order_is_frozen():
    assert D4_CANDIDATE_ORDER == (
        "L9_K",
        "L9_V",
        "L10_K",
        "L10_V",
        "L9_L10_K",
        "L9_L10_V",
    )


def test_d4_selects_highest_mediator_score():
    scores = {name: 0.0 for name in D4_CANDIDATE_ORDER}
    scores["L10_V"] = 2.0
    assert select_component_candidate(scores) == "L10_V"


def test_d4_tie_break_uses_frozen_candidate_order():
    scores = {name: 1.0 for name in D4_CANDIDATE_ORDER}
    assert select_component_candidate(scores) == "L9_K"


def test_d4_rejects_missing_or_reordered_candidate_map():
    scores = {name: 0.0 for name in reversed(D4_CANDIDATE_ORDER)}
    with pytest.raises(ValueError):
        select_component_candidate(scores)
