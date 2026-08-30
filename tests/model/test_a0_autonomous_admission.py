from __future__ import annotations

from alifelm.model.autonomous_admission import (
    A0_ATTEMPTS_PER_TREATMENT,
    A0_CASES_PER_CONTEXT_CLASS,
    A0_CONTEXT_CLASSES,
    A0TreatmentMetrics,
    choose_minimal_treatment,
    evaluate_i3_branch_order_audit,
    evaluate_treatment,
)


def _class_counts(*, one_per_class_failure: bool = False):
    values = []
    for index, context_class in enumerate(A0_CONTEXT_CLASSES):
        valid = A0_CASES_PER_CONTEXT_CLASS
        if one_per_class_failure and index < 4:
            valid -= 1
        values.append((context_class.value, valid, A0_CASES_PER_CONTEXT_CLASS))
    return tuple(values)


def _passing(name: str) -> A0TreatmentMetrics:
    counts = _class_counts(one_per_class_failure=True)
    return A0TreatmentMetrics(
        treatment=name,
        attempts=A0_ATTEMPTS_PER_TREATMENT,
        codec_valid=A0_ATTEMPTS_PER_TREATMENT,
        domain_valid=sum(value for _, value, _ in counts),
        first_token_eos=0,
        evidence_complete=A0_ATTEMPTS_PER_TREATMENT,
        infrastructure_failures=0,
        exact_repeat_equal=True,
        context_class_domain_valid=counts,
    )


def _failing_i0() -> A0TreatmentMetrics:
    counts = tuple(
        (context_class.value, 0, A0_CASES_PER_CONTEXT_CLASS)
        for context_class in A0_CONTEXT_CLASSES
    )
    return A0TreatmentMetrics(
        treatment="I0",
        attempts=A0_ATTEMPTS_PER_TREATMENT,
        codec_valid=0,
        domain_valid=0,
        first_token_eos=A0_ATTEMPTS_PER_TREATMENT,
        evidence_complete=A0_ATTEMPTS_PER_TREATMENT,
        infrastructure_failures=0,
        exact_repeat_equal=True,
        context_class_domain_valid=counts,
    )


def test_a0_cohort_is_five_by_sixteen() -> None:
    assert len(A0_CONTEXT_CLASSES) == 5
    assert A0_CASES_PER_CONTEXT_CLASS == 16
    assert A0_ATTEMPTS_PER_TREATMENT == 80


def test_a0_passes_validity_without_action_frequency_requirement() -> None:
    metrics = _passing("I1")
    evaluation = evaluate_treatment(metrics)
    assert evaluation["motor_pass"] is True
    assert evaluation["autonomous_pass"] is True
    assert evaluation["thresholds"]["action_frequency_target"] is None
    assert metrics.domain_valid == 76
    assert metrics.minimum_context_class_domain_valid_rate == 15 / 16


def test_first_token_eos_fails_motor_and_autonomous() -> None:
    evaluation = evaluate_treatment(_failing_i0())
    assert evaluation["motor_pass"] is False
    assert evaluation["autonomous_pass"] is False


def test_minimal_passing_treatment_is_selected() -> None:
    values = {
        "I0": _failing_i0(),
        "I1": _passing("I1"),
        "I2": _passing("I2"),
        "I3": _passing("I3"),
    }
    assert choose_minimal_treatment(values) == "I1"


def test_i3_branch_audit_requires_order_invariance() -> None:
    summaries = tuple(_passing(f"I3_ORDER_{index}") for index in range(4))
    same = tuple(
        tuple("NO_DIRECTED_ACTION" for _ in range(A0_ATTEMPTS_PER_TREATMENT))
        for _ in range(4)
    )
    passed = evaluate_i3_branch_order_audit(summaries, same)
    assert passed["pass"] is True
    assert passed["candidate_agreement_rate"] == 1.0

    changed = [list(values) for values in same]
    for index in range(5):
        changed[3][index] = "DIRECT_TEXT"
    failed = evaluate_i3_branch_order_audit(summaries, tuple(tuple(v) for v in changed))
    assert failed["pass"] is False
    assert failed["candidate_agreement_rate"] == 75 / 80
