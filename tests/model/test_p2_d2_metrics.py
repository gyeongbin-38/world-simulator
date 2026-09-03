import pytest

from alifelm.model.p2_d2_metrics import (
    mediator_values,
    median_symmetric_score,
    select_top_blocks,
    select_top_layers,
    union_localization_label,
)


def test_mediator_values_preserve_overshoot_and_direction():
    row = mediator_values(g_base=-1.0, g_fa=1.0, g_rescue=-1.5, g_induction=1.5)
    assert row["denominator"] == 2.0
    assert row["normalized_rescue"] == 1.25
    assert row["normalized_induction"] == 1.25
    assert row["symmetric_score"] == 1.25


def test_mediator_values_fail_if_frozen_d1_gap_direction_is_lost():
    with pytest.raises(ValueError):
        mediator_values(g_base=1.0, g_fa=1.0, g_rescue=0.0, g_induction=0.0)
    with pytest.raises(ValueError):
        mediator_values(g_base=2.0, g_fa=1.0, g_rescue=0.0, g_induction=0.0)


def test_block_selection_is_rank_based_with_lower_index_tie_break():
    selected = select_top_blocks({"Q0": 0.1, "Q1": 0.8, "Q2": 0.8, "Q3": -1.0})
    assert selected == ("Q1", "Q2")


def test_layer_selection_is_rank_based_with_lower_index_tie_break():
    selected = select_top_layers({4: 0.3, 5: 0.9, 6: 0.9, 7: 0.1})
    assert selected == (5, 6)


def test_median_symmetric_score():
    assert median_symmetric_score([
        {"symmetric_score": -1.0},
        {"symmetric_score": 0.5},
        {"symmetric_score": 2.0},
    ]) == 0.5


def test_union_labels_are_exact_count_descriptors():
    assert union_localization_label([-1.0] * 160, [1.0] * 160) == "UNION_BIDIRECTIONAL_UNIVERSAL_FLIP"
    assert union_localization_label([-1.0] + [1.0] * 159, [1.0] + [-1.0] * 159) == "UNION_BIDIRECTIONAL_NONUNIVERSAL"
    assert union_localization_label([-1.0] + [1.0] * 159, [-1.0] * 160) == "UNION_ONE_DIRECTION_ONLY"
    assert union_localization_label([1.0] * 160, [-1.0] * 160) == "NO_SIGN_FLIP_MEDIATION"


def test_union_label_requires_full_160_case_confirmation():
    with pytest.raises(ValueError):
        union_localization_label([-1.0] * 20, [1.0] * 20)
