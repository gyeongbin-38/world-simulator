"""Pure measurement rules for WORLD P1 context-sensitive policy study.

This module performs no model loading, generation, state mutation, or action
selection. It only evaluates frozen P1 measurements collected elsewhere.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Mapping, Sequence


P1_STUDY_ID = "WORLD_P1_CONTEXT_SENSITIVE_POLICY_V1"
P1_SCHEMA_VERSION = "1.0.0"
P1_CASES_PER_CONTEXT = 16
P1_CONTEXT_CLASSES = (
    "QUIET",
    "MESSAGE_RECEIVED",
    "PROPOSAL_RECEIVED",
    "OWN_PROPOSAL_PENDING",
    "RECENT_INTERACTION",
)
P1_CONTROL_CONTEXT = "QUIET"
P1_MATCHED_SENSITIVITY_RATE_MIN = 0.25
P1_TVD_MIN = 0.25
P1_NONCONTROL_TVD_CLASSES_MIN = 2


def total_variation_distance(left: Sequence[str], right: Sequence[str]) -> float:
    """Return empirical TVD between equally interpreted categorical samples."""

    if not left or not right:
        raise ValueError("TVD samples must be non-empty")
    left_counts = Counter(left)
    right_counts = Counter(right)
    labels = set(left_counts) | set(right_counts)
    left_n = len(left)
    right_n = len(right)
    return 0.5 * sum(
        abs(left_counts[label] / left_n - right_counts[label] / right_n)
        for label in labels
    )


@dataclass(frozen=True, slots=True)
class P1SensitivityMetrics:
    matched_sensitive_count: int
    matched_total: int
    matched_sensitivity_rate: float
    tvd_from_quiet: tuple[tuple[str, float], ...]
    tvd_passing_class_count: int
    passed: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "matched_sensitive_count": self.matched_sensitive_count,
            "matched_total": self.matched_total,
            "matched_sensitivity_rate": self.matched_sensitivity_rate,
            "matched_sensitivity_rate_min": P1_MATCHED_SENSITIVITY_RATE_MIN,
            "tvd_from_quiet": {
                context_class: value for context_class, value in self.tvd_from_quiet
            },
            "tvd_min": P1_TVD_MIN,
            "tvd_passing_class_count": self.tvd_passing_class_count,
            "tvd_passing_classes_min": P1_NONCONTROL_TVD_CLASSES_MIN,
            "pass": self.passed,
        }


def _validated_samples(
    labels_by_context: Mapping[str, Sequence[str]],
) -> dict[str, tuple[str, ...]]:
    if set(labels_by_context) != set(P1_CONTEXT_CLASSES):
        raise ValueError("P1 labels must contain exactly the frozen context classes")
    normalized: dict[str, tuple[str, ...]] = {}
    for context_class in P1_CONTEXT_CLASSES:
        values = tuple(labels_by_context[context_class])
        if len(values) != P1_CASES_PER_CONTEXT:
            raise ValueError("each P1 context class must contain exactly 16 labels")
        if any(not isinstance(value, str) or not value for value in values):
            raise ValueError("P1 action labels must be non-empty strings")
        normalized[context_class] = values
    return normalized


def evaluate_context_sensitivity(
    labels_by_context: Mapping[str, Sequence[str]],
) -> P1SensitivityMetrics:
    """Evaluate the preregistered non-normative P1 sensitivity gate."""

    samples = _validated_samples(labels_by_context)
    matched_sensitive = 0
    for index in range(P1_CASES_PER_CONTEXT):
        if len({samples[name][index] for name in P1_CONTEXT_CLASSES}) > 1:
            matched_sensitive += 1
    matched_rate = matched_sensitive / P1_CASES_PER_CONTEXT

    quiet = samples[P1_CONTROL_CONTEXT]
    tvds = tuple(
        (
            context_class,
            total_variation_distance(quiet, samples[context_class]),
        )
        for context_class in P1_CONTEXT_CLASSES
        if context_class != P1_CONTROL_CONTEXT
    )
    passing_classes = sum(value >= P1_TVD_MIN for _, value in tvds)
    passed = (
        matched_rate >= P1_MATCHED_SENSITIVITY_RATE_MIN
        and passing_classes >= P1_NONCONTROL_TVD_CLASSES_MIN
    )
    return P1SensitivityMetrics(
        matched_sensitive_count=matched_sensitive,
        matched_total=P1_CASES_PER_CONTEXT,
        matched_sensitivity_rate=matched_rate,
        tvd_from_quiet=tvds,
        tvd_passing_class_count=passing_classes,
        passed=passed,
    )


def classify_p1(
    *, integrity_pass: bool, generated_pass: bool, latent_pass: bool
) -> str:
    """Apply the frozen interpretation matrix from the P1 preregistration."""

    if not integrity_pass:
        return "NOT_EVALUABLE"
    if generated_pass and latent_pass:
        return "GENERATED_AND_LATENT_CONTEXT_SENSITIVITY"
    if generated_pass:
        return "GENERATED_CONTEXT_SENSITIVITY_ONLY"
    if latent_pass:
        return "LATENT_CONTEXT_SENSITIVITY_ONLY"
    return "NO_CONTEXT_SENSITIVE_POLICY_EVIDENCE"


__all__ = [
    "P1_STUDY_ID",
    "P1_SCHEMA_VERSION",
    "P1_CASES_PER_CONTEXT",
    "P1_CONTEXT_CLASSES",
    "P1_CONTROL_CONTEXT",
    "P1_MATCHED_SENSITIVITY_RATE_MIN",
    "P1_TVD_MIN",
    "P1_NONCONTROL_TVD_CLASSES_MIN",
    "P1SensitivityMetrics",
    "total_variation_distance",
    "evaluate_context_sensitivity",
    "classify_p1",
]
