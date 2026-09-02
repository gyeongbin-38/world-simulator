from alifelm.model.p1_policy import (
    P1_CONTEXT_CLASSES,
    P1_CASES_PER_CONTEXT,
    classify_p1,
    evaluate_context_sensitivity,
    total_variation_distance,
)


def _all(label: str):
    return {name: [label] * P1_CASES_PER_CONTEXT for name in P1_CONTEXT_CLASSES}


def test_total_variation_distance_extremes():
    assert total_variation_distance(["A"] * 16, ["A"] * 16) == 0.0
    assert total_variation_distance(["A"] * 16, ["B"] * 16) == 1.0


def test_all_wait_fails_context_sensitivity():
    result = evaluate_context_sensitivity(_all("NO_DIRECTED_ACTION"))
    assert result.matched_sensitive_count == 0
    assert result.matched_sensitivity_rate == 0.0
    assert result.tvd_passing_class_count == 0
    assert result.passed is False


def test_two_context_classes_cross_frozen_thresholds():
    samples = _all("NO_DIRECTED_ACTION")
    samples["MESSAGE_RECEIVED"] = ["SEND"] * 4 + ["NO_DIRECTED_ACTION"] * 12
    samples["PROPOSAL_RECEIVED"] = ["ACCEPT"] * 4 + ["NO_DIRECTED_ACTION"] * 12
    result = evaluate_context_sensitivity(samples)
    assert result.matched_sensitive_count == 4
    assert result.matched_sensitivity_rate == 0.25
    assert result.tvd_passing_class_count == 2
    assert result.passed is True


def test_one_shifted_context_is_not_enough():
    samples = _all("NO_DIRECTED_ACTION")
    samples["MESSAGE_RECEIVED"] = ["SEND"] * 16
    result = evaluate_context_sensitivity(samples)
    assert result.matched_sensitivity_rate == 1.0
    assert result.tvd_passing_class_count == 1
    assert result.passed is False


def test_interpretation_matrix():
    assert classify_p1(integrity_pass=False, generated_pass=True, latent_pass=True) == "NOT_EVALUABLE"
    assert classify_p1(integrity_pass=True, generated_pass=True, latent_pass=True) == "GENERATED_AND_LATENT_CONTEXT_SENSITIVITY"
    assert classify_p1(integrity_pass=True, generated_pass=True, latent_pass=False) == "GENERATED_CONTEXT_SENSITIVITY_ONLY"
    assert classify_p1(integrity_pass=True, generated_pass=False, latent_pass=True) == "LATENT_CONTEXT_SENSITIVITY_ONLY"
    assert classify_p1(integrity_pass=True, generated_pass=False, latent_pass=False) == "NO_CONTEXT_SENSITIVE_POLICY_EVIDENCE"
