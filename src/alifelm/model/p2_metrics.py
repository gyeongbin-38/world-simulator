"""Pure preregistered measurements for WORLD P2 behavioral admission.

No model loading, generation, state mutation, calibration, or action selection
occurs here.  These functions only evaluate frozen P2 measurements.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import statistics
from typing import Mapping, Sequence

from .p1b_metrics import (
    P1B_G5_MATCHED_SENSITIVITY_RATE_MIN,
    P1B_G5_NONQUIET_TVD_CLASSES_MIN,
    P1B_G5_TVD_MIN,
    total_variation_distance,
)


P2_STUDY_ID = "WORLD_P2_PHASE_DECOUPLED_BEHAVIORAL_ADMISSION_V1"
P2_CONTEXT_CLASSES = (
    "QUIET",
    "MESSAGE_RECEIVED",
    "PROPOSAL_RECEIVED",
    "OWN_PROPOSAL_PENDING",
    "RECENT_INTERACTION",
)
P2_CONTROL_CONTEXT = "QUIET"
P2_MATCHED_CASES = 32
P2_INVALID_LABEL = "INVALID"
P2_WAIT_LABEL = "NO_DIRECTED_ACTION"


@dataclass(frozen=True, slots=True)
class GeneratedSensitivityMetrics:
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
            "matched_sensitivity_rate_min": P1B_G5_MATCHED_SENSITIVITY_RATE_MIN,
            "matched_case_requires_all_five_domain_valid": True,
            "tvd_from_quiet": dict(self.tvd_from_quiet),
            "tvd_min": P1B_G5_TVD_MIN,
            "tvd_passing_class_count": self.tvd_passing_class_count,
            "tvd_passing_classes_min": P1B_G5_NONQUIET_TVD_CLASSES_MIN,
            "domain_invalid_distribution_label": P2_INVALID_LABEL,
            "pass": self.passed,
        }


def generated_context_sensitivity(
    labels_by_context: Mapping[str, Sequence[str | None]],
    domain_valid_by_context: Mapping[str, Sequence[bool]],
) -> GeneratedSensitivityMetrics:
    """Evaluate complete generated actions under the frozen P2 G2 rule."""

    if set(labels_by_context) != set(P2_CONTEXT_CLASSES):
        raise ValueError("labels must contain exactly the five P2 context classes")
    if set(domain_valid_by_context) != set(P2_CONTEXT_CLASSES):
        raise ValueError("validity must contain exactly the five P2 context classes")
    lengths = {len(labels_by_context[name]) for name in P2_CONTEXT_CLASSES}
    valid_lengths = {len(domain_valid_by_context[name]) for name in P2_CONTEXT_CLASSES}
    if lengths != {P2_MATCHED_CASES} or valid_lengths != {P2_MATCHED_CASES}:
        raise ValueError("P2 sensitivity requires 32 aligned cases per context class")

    sensitive = 0
    for index in range(P2_MATCHED_CASES):
        all_valid = all(bool(domain_valid_by_context[name][index]) for name in P2_CONTEXT_CLASSES)
        labels = [labels_by_context[name][index] for name in P2_CONTEXT_CLASSES]
        if all_valid:
            if any(label is None for label in labels):
                raise ValueError("domain-valid P2 output must have a generated action label")
            if len(set(labels)) >= 2:
                sensitive += 1

    distributions: dict[str, tuple[str, ...]] = {}
    for name in P2_CONTEXT_CLASSES:
        values = []
        for label, valid in zip(
            labels_by_context[name], domain_valid_by_context[name], strict=True
        ):
            values.append(str(label) if valid and label is not None else P2_INVALID_LABEL)
        distributions[name] = tuple(values)

    quiet = distributions[P2_CONTROL_CONTEXT]
    tvds = []
    for name in P2_CONTEXT_CLASSES:
        if name == P2_CONTROL_CONTEXT:
            continue
        tvds.append((name, total_variation_distance(quiet, distributions[name])))
    passing = sum(value >= P1B_G5_TVD_MIN for _, value in tvds)
    rate = sensitive / P2_MATCHED_CASES
    passed = (
        rate >= P1B_G5_MATCHED_SENSITIVITY_RATE_MIN
        and passing >= P1B_G5_NONQUIET_TVD_CLASSES_MIN
    )
    return GeneratedSensitivityMetrics(
        matched_sensitive_count=sensitive,
        matched_total=P2_MATCHED_CASES,
        matched_sensitivity_rate=rate,
        tvd_from_quiet=tuple(tvds),
        tvd_passing_class_count=passing,
        passed=passed,
    )


def action_distribution_by_context(
    labels_by_context: Mapping[str, Sequence[str | None]],
    domain_valid_by_context: Mapping[str, Sequence[bool]],
) -> dict[str, dict[str, int]]:
    result = {}
    for name in P2_CONTEXT_CLASSES:
        counter: Counter[str] = Counter()
        for label, valid in zip(
            labels_by_context[name], domain_valid_by_context[name], strict=True
        ):
            counter[str(label) if valid and label is not None else P2_INVALID_LABEL] += 1
        result[name] = dict(sorted(counter.items()))
    return result


def wait_rates_by_context(
    labels_by_context: Mapping[str, Sequence[str | None]],
) -> dict[str, dict[str, float | int]]:
    result: dict[str, dict[str, float | int]] = {}
    for name in P2_CONTEXT_CLASSES:
        values = tuple(labels_by_context[name])
        if len(values) != P2_MATCHED_CASES:
            raise ValueError("WAIT-rate diagnostics require 32 cases per context")
        count = sum(value == P2_WAIT_LABEL for value in values)
        result[name] = {"wait_count": count, "total": len(values), "wait_rate": count / len(values)}
    return result


def paired_label_agreement(
    left: Sequence[str | None], right: Sequence[str | None]
) -> dict[str, float | int]:
    if len(left) != len(right) or not left:
        raise ValueError("paired label agreement requires matched non-empty sequences")
    agreeing = sum(a == b for a, b in zip(left, right, strict=True))
    return {"agreeing": agreeing, "total": len(left), "rate": agreeing / len(left)}


def wait_escape_reversal(
    c11: Sequence[str | None], c10: Sequence[str | None]
) -> dict[str, int]:
    if len(c11) != len(c10) or not c11:
        raise ValueError("WAIT escape diagnostics require matched non-empty sequences")
    escape = 0
    reversal = 0
    both_wait = 0
    both_nonwait = 0
    for full_fa, decoupled in zip(c11, c10, strict=True):
        if full_fa == P2_WAIT_LABEL and decoupled != P2_WAIT_LABEL:
            escape += 1
        elif full_fa != P2_WAIT_LABEL and decoupled == P2_WAIT_LABEL:
            reversal += 1
        elif full_fa == P2_WAIT_LABEL and decoupled == P2_WAIT_LABEL:
            both_wait += 1
        else:
            both_nonwait += 1
    return {
        "c11_wait_to_c10_nonwait": escape,
        "c11_nonwait_to_c10_wait": reversal,
        "both_wait": both_wait,
        "both_nonwait": both_nonwait,
        "total": len(c11),
    }


def token_count_summary(values: Sequence[int]) -> dict[str, float | int]:
    normalized = tuple(int(value) for value in values)
    if not normalized or any(value < 0 for value in normalized):
        raise ValueError("token counts must be non-negative and non-empty")
    return {
        "count": len(normalized),
        "min": min(normalized),
        "max": max(normalized),
        "median": float(statistics.median(normalized)),
        "mean": float(statistics.fmean(normalized)),
    }


__all__ = [
    "P2_STUDY_ID",
    "P2_CONTEXT_CLASSES",
    "P2_CONTROL_CONTEXT",
    "P2_MATCHED_CASES",
    "P2_INVALID_LABEL",
    "P2_WAIT_LABEL",
    "GeneratedSensitivityMetrics",
    "generated_context_sensitivity",
    "action_distribution_by_context",
    "wait_rates_by_context",
    "paired_label_agreement",
    "wait_escape_reversal",
    "token_count_summary",
]
