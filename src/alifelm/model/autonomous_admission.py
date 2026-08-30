"""Deterministic admission rules for the A0 autonomous-interface study.

This module contains only preregistered cohort/treatment identities and pure
admission arithmetic.  It does not load a model, generate text, mutate WORLD
state, or choose an action for an agent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .r3_fixtures import R3ContextClass


A0_ADMISSION_ID = "A0_AUTONOMOUS_INTERFACE_ADMISSION_V1"
A0_SCHEMA_VERSION = "1.0.0"
A0_CASES_PER_CONTEXT_CLASS = 16
A0_CONTEXT_CLASSES = tuple(R3ContextClass)
A0_TREATMENT_ORDER = ("I0", "I1", "I2", "I3")
A0_ATTEMPTS_PER_TREATMENT = len(A0_CONTEXT_CLASSES) * A0_CASES_PER_CONTEXT_CLASS

# Interface-capability gates only.  There is deliberately no required action
# distribution, SEND/PROPOSE frequency, social score, or behavioral target.
A0_CODEC_VALID_RATE_MIN = 0.99
A0_DOMAIN_VALID_RATE_MIN = 0.95
A0_CONTEXT_CLASS_DOMAIN_VALID_RATE_MIN = 0.90
A0_FIRST_TOKEN_EOS_RATE_MAX = 0.01
A0_EVIDENCE_COMPLETE_RATE_REQUIRED = 1.0
A0_I3_BRANCH_CANDIDATE_AGREEMENT_MIN = 0.95
A0_I3_BRANCH_DOMAIN_RATE_SPREAD_MAX = 0.05


@dataclass(frozen=True, slots=True)
class A0TreatmentMetrics:
    treatment: str
    attempts: int
    codec_valid: int
    domain_valid: int
    first_token_eos: int
    evidence_complete: int
    infrastructure_failures: int
    exact_repeat_equal: bool
    context_class_domain_valid: tuple[tuple[str, int, int], ...]

    def __post_init__(self) -> None:
        if self.treatment not in A0_TREATMENT_ORDER and not self.treatment.startswith("I3_ORDER_"):
            raise ValueError("unknown A0 treatment")
        if self.attempts <= 0:
            raise ValueError("attempts must be positive")
        for value, name in (
            (self.codec_valid, "codec_valid"),
            (self.domain_valid, "domain_valid"),
            (self.first_token_eos, "first_token_eos"),
            (self.evidence_complete, "evidence_complete"),
            (self.infrastructure_failures, "infrastructure_failures"),
        ):
            if value < 0 or value > self.attempts:
                raise ValueError(f"{name} must be within the attempt count")
        total = sum(count for _, count, _ in self.context_class_domain_valid)
        denominator = sum(count_total for _, _, count_total in self.context_class_domain_valid)
        if total != self.domain_valid or denominator != self.attempts:
            raise ValueError("context-class domain counts must partition the treatment attempts")

    @property
    def codec_valid_rate(self) -> float:
        return self.codec_valid / self.attempts

    @property
    def domain_valid_rate(self) -> float:
        return self.domain_valid / self.attempts

    @property
    def first_token_eos_rate(self) -> float:
        return self.first_token_eos / self.attempts

    @property
    def evidence_complete_rate(self) -> float:
        return self.evidence_complete / self.attempts

    @property
    def minimum_context_class_domain_valid_rate(self) -> float:
        return min(valid / total for _, valid, total in self.context_class_domain_valid)

    def as_dict(self) -> dict[str, object]:
        return {
            "treatment": self.treatment,
            "attempts": self.attempts,
            "codec_valid": self.codec_valid,
            "codec_valid_rate": self.codec_valid_rate,
            "domain_valid": self.domain_valid,
            "domain_valid_rate": self.domain_valid_rate,
            "first_token_eos": self.first_token_eos,
            "first_token_eos_rate": self.first_token_eos_rate,
            "evidence_complete": self.evidence_complete,
            "evidence_complete_rate": self.evidence_complete_rate,
            "infrastructure_failures": self.infrastructure_failures,
            "exact_repeat_equal": self.exact_repeat_equal,
            "minimum_context_class_domain_valid_rate": self.minimum_context_class_domain_valid_rate,
            "context_class_domain_valid": [
                {"context_class": name, "valid": valid, "total": total, "rate": valid / total}
                for name, valid, total in self.context_class_domain_valid
            ],
        }


def evaluate_treatment(metrics: A0TreatmentMetrics) -> dict[str, object]:
    """Evaluate interface competence without imposing an action preference."""

    motor_pass = (
        metrics.infrastructure_failures == 0
        and metrics.codec_valid_rate >= A0_CODEC_VALID_RATE_MIN
        and metrics.first_token_eos_rate <= A0_FIRST_TOKEN_EOS_RATE_MAX
        and metrics.evidence_complete_rate == A0_EVIDENCE_COMPLETE_RATE_REQUIRED
        and metrics.exact_repeat_equal
    )
    autonomous_pass = (
        motor_pass
        and metrics.domain_valid_rate >= A0_DOMAIN_VALID_RATE_MIN
        and metrics.minimum_context_class_domain_valid_rate
        >= A0_CONTEXT_CLASS_DOMAIN_VALID_RATE_MIN
    )
    return {
        "motor_pass": motor_pass,
        "autonomous_pass": autonomous_pass,
        "thresholds": {
            "codec_valid_rate_min": A0_CODEC_VALID_RATE_MIN,
            "domain_valid_rate_min": A0_DOMAIN_VALID_RATE_MIN,
            "context_class_domain_valid_rate_min": A0_CONTEXT_CLASS_DOMAIN_VALID_RATE_MIN,
            "first_token_eos_rate_max": A0_FIRST_TOKEN_EOS_RATE_MAX,
            "evidence_complete_rate_required": A0_EVIDENCE_COMPLETE_RATE_REQUIRED,
            "infrastructure_failures_required": 0,
            "exact_repeat_equal_required": True,
            "action_frequency_target": None,
        },
    }


def choose_minimal_treatment(
    metrics_by_treatment: Mapping[str, A0TreatmentMetrics],
) -> str | None:
    """Select the least-intervening treatment that passes both gates.

    I3 is returned provisionally; its final admission additionally requires the
    preregistered branch-order audit.
    """

    for treatment in A0_TREATMENT_ORDER:
        metrics = metrics_by_treatment.get(treatment)
        if metrics is None:
            raise ValueError(f"missing preregistered treatment {treatment}")
        if bool(evaluate_treatment(metrics)["autonomous_pass"]):
            return treatment
    return None


def evaluate_i3_branch_order_audit(
    summaries: Sequence[A0TreatmentMetrics],
    candidate_labels_by_order: Sequence[Sequence[str | None]],
) -> dict[str, object]:
    """Check that typed-schema branch ordering is not driving action choice."""

    if len(summaries) != 4 or len(candidate_labels_by_order) != 4:
        raise ValueError("the I3 branch audit requires exactly four preregistered orders")
    if any(len(values) != A0_ATTEMPTS_PER_TREATMENT for values in candidate_labels_by_order):
        raise ValueError("each I3 branch order must cover the complete A0 cohort")
    all_core_pass = all(bool(evaluate_treatment(summary)["autonomous_pass"]) for summary in summaries)
    agreeing = 0
    for index in range(A0_ATTEMPTS_PER_TREATMENT):
        values = {order[index] for order in candidate_labels_by_order}
        if len(values) == 1:
            agreeing += 1
    agreement_rate = agreeing / A0_ATTEMPTS_PER_TREATMENT
    domain_rates = [summary.domain_valid_rate for summary in summaries]
    domain_rate_spread = max(domain_rates) - min(domain_rates)
    passed = (
        all_core_pass
        and agreement_rate >= A0_I3_BRANCH_CANDIDATE_AGREEMENT_MIN
        and domain_rate_spread <= A0_I3_BRANCH_DOMAIN_RATE_SPREAD_MAX
    )
    return {
        "pass": passed,
        "all_orders_core_pass": all_core_pass,
        "candidate_agreement_count": agreeing,
        "candidate_agreement_rate": agreement_rate,
        "candidate_agreement_min": A0_I3_BRANCH_CANDIDATE_AGREEMENT_MIN,
        "domain_valid_rate_spread": domain_rate_spread,
        "domain_valid_rate_spread_max": A0_I3_BRANCH_DOMAIN_RATE_SPREAD_MAX,
    }


__all__ = [
    "A0_ADMISSION_ID",
    "A0_SCHEMA_VERSION",
    "A0_CASES_PER_CONTEXT_CLASS",
    "A0_CONTEXT_CLASSES",
    "A0_TREATMENT_ORDER",
    "A0_ATTEMPTS_PER_TREATMENT",
    "A0TreatmentMetrics",
    "choose_minimal_treatment",
    "evaluate_i3_branch_order_audit",
    "evaluate_treatment",
]
