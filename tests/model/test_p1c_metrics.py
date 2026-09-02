from alifelm.model.p1b_metrics import WAIT_LABEL
from alifelm.model.p1c_metrics import (
    P1C_CONTEXT_CLASSES,
    evaluate_base_wrapper_equivalence,
    evaluate_decoupling_candidate,
    matched_phase_effect,
    rank1_sensitivity,
    structural_gain,
)


def test_matched_phase_effect_uses_treatment_minus_reference():
    result = matched_phase_effect([1.0] * 32, [2.0] * 32)
    assert result.effects == (1.0,) * 32
    assert result.passed


def test_matched_phase_effect_requires_frozen_positive_fraction():
    result = matched_phase_effect([0.0] * 32, [1.0] * 23 + [-1.0] * 9)
    assert result.rule.median > 0.0
    assert result.rule.positive_fraction == 23 / 32
    assert not result.passed


def test_structural_gain_requires_two_of_three():
    reference = {name: [0.0] * 32 for name in ("S_msg", "S_prop", "S_owner")}
    treatment = {
        "S_msg": [1.0] * 32,
        "S_prop": [1.0] * 32,
        "S_owner": [-1.0] * 32,
    }
    result = structural_gain(reference, treatment)
    assert result.passed
    rows = dict(result.contrasts)
    assert rows["S_msg"].passed
    assert rows["S_prop"].passed
    assert not rows["S_owner"].passed


def test_decoupling_candidate_requires_structural_carryover_and_wait_reduction():
    reduction, passed = evaluate_decoupling_candidate(
        structural_carryover_pass=True,
        c11_margins=[4.0] * 160,
        c10_margins=[1.0] * 160,
    )
    assert reduction.passed
    assert passed

    _, passed = evaluate_decoupling_candidate(
        structural_carryover_pass=False,
        c11_margins=[4.0] * 160,
        c10_margins=[1.0] * 160,
    )
    assert not passed


def test_base_wrapper_equivalence_is_inclusive_at_frozen_tolerance():
    result = evaluate_base_wrapper_equivalence(
        token_ids_equal=[True] * 800,
        total_abs_differences=[1e-5] * 800,
        mean_abs_differences=[1e-5] * 800,
    )
    assert result.passed
    assert result.comparisons == 800


def test_base_wrapper_equivalence_fails_token_or_numeric_drift():
    result = evaluate_base_wrapper_equivalence(
        token_ids_equal=[True, False],
        total_abs_differences=[0.0, 0.0],
        mean_abs_differences=[0.0, 0.0],
    )
    assert not result.passed

    result = evaluate_base_wrapper_equivalence(
        token_ids_equal=[True, True],
        total_abs_differences=[0.0, 1.00001e-5],
        mean_abs_differences=[0.0, 0.0],
    )
    assert not result.passed


def test_rank1_sensitivity_reuses_p1b_thresholds():
    labels = {name: [WAIT_LABEL] * 32 for name in P1C_CONTEXT_CLASSES}
    labels["MESSAGE_RECEIVED"] = ["DIRECT_TEXT"] * 8 + [WAIT_LABEL] * 24
    labels["PROPOSAL_RECEIVED"] = ["CONFIRM_BILATERAL_REQUEST"] * 8 + [WAIT_LABEL] * 24
    result = rank1_sensitivity(labels)
    assert result.matched_sensitivity_rate == 0.25
    assert result.tvd_passing_class_count == 2
    assert result.passed
