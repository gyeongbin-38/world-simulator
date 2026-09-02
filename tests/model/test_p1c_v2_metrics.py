from alifelm.model.p1c_v2_metrics import (
    P1C_V2_STRUCTURAL_CONTRASTS,
    evaluate_decoupling_candidate_v2,
    evaluate_structural_replication_carryover,
    factorial_interaction,
    interaction_summary,
    matched_phase_effect,
)


def _structural(value_by_name):
    return {
        name: tuple(float(value_by_name.get(name, 0.0)) for _ in range(32))
        for name in P1C_V2_STRUCTURAL_CONTRASTS
    }


def test_matched_phase_effect_uses_frozen_positive_rule():
    result = matched_phase_effect([0.0] * 8, [1.0] * 6 + [0.0] * 2)
    assert result.passed is True
    assert result.rule.positive_fraction == 0.75
    assert result.rule.median > 0.0


def test_structural_g3_requires_same_contrast_to_pass_full_and_prefill():
    c00 = _structural({})
    c11 = _structural({"S_msg": 1.0, "S_prop": 1.0, "S_owner": -1.0})
    c10 = _structural({"S_msg": 1.0, "S_prop": -1.0, "S_owner": 1.0})
    result = evaluate_structural_replication_carryover(c00=c00, c11=c11, c10=c10)
    assert dict(result.replicated_carryover) == {
        "S_msg": True,
        "S_prop": False,
        "S_owner": False,
    }
    assert result.passed is False


def test_structural_g3_passes_two_replicated_carryovers():
    c00 = _structural({})
    c11 = _structural({"S_msg": 1.0, "S_prop": 1.0, "S_owner": -1.0})
    c10 = _structural({"S_msg": 0.5, "S_prop": 0.5, "S_owner": 1.0})
    result = evaluate_structural_replication_carryover(c00=c00, c11=c11, c10=c10)
    assert dict(result.replicated_carryover) == {
        "S_msg": True,
        "S_prop": True,
        "S_owner": False,
    }
    assert result.passed is True


def test_decoupling_requires_g3_even_when_wait_rule_passes():
    reduction, passed = evaluate_decoupling_candidate_v2(
        structural_replication_carryover_pass=False,
        c10_margins=[0.0] * 8,
        c11_margins=[1.0] * 8,
    )
    assert reduction.passed is True
    assert passed is False


def test_decoupling_passes_with_g3_and_positive_wait_effect():
    reduction, passed = evaluate_decoupling_candidate_v2(
        structural_replication_carryover_pass=True,
        c10_margins=[0.0] * 8,
        c11_margins=[1.0] * 8,
    )
    assert reduction.passed is True
    assert passed is True


def test_factorial_interaction_is_c11_minus_c10_minus_c01_plus_c00():
    values, summary = factorial_interaction(
        c00=[1.0, 1.0],
        c10=[2.0, 2.0],
        c01=[3.0, 3.0],
        c11=[5.0, 4.0],
    )
    assert values == (1.0, 0.0)
    assert summary.count == 2
    assert summary.positive_fraction == 0.5
    assert summary.zero_fraction == 0.5


def test_interaction_summary_reports_sign_fractions_without_gate():
    result = interaction_summary([-2.0, 0.0, 1.0, 3.0])
    assert result.count == 4
    assert result.positive_fraction == 0.5
    assert result.negative_fraction == 0.25
    assert result.zero_fraction == 0.25
    assert result.median == 0.5


def test_factorial_interaction_rejects_mismatched_lengths():
    try:
        factorial_interaction(c00=[0.0], c10=[0.0, 1.0], c01=[0.0], c11=[0.0])
    except ValueError as error:
        assert "matched" in str(error)
    else:
        raise AssertionError("mismatched factorial inputs must fail closed")
