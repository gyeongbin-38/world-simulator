"""Pure measurement rules for WORLD P1B adapter-selector decomposition.

This module performs no model loading, generation, state mutation, or model
selection. It only evaluates measurements defined by the frozen P1B
preregistration.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import statistics
from typing import Mapping, Sequence


P1B_STUDY_ID = "WORLD_P1B_ADAPTER_SELECTOR_DECOMPOSITION_V1"
P1B_SCHEMA_VERSION = "1.0.0"
P1B_CONTEXT_CLASSES = (
    "QUIET",
    "MESSAGE_RECEIVED",
    "PROPOSAL_RECEIVED",
    "OWN_PROPOSAL_PENDING",
    "RECENT_INTERACTION",
)
P1B_CONTROL_CONTEXT = "QUIET"
P1B_HELDOUT_CASES = 32
P1B_PAIRED_CASES = 16
WAIT_LABEL = "NO_DIRECTED_ACTION"
DIRECTED_LABELS = (
    "DIRECT_TEXT",
    "OPEN_BILATERAL_REQUEST",
    "CONFIRM_BILATERAL_REQUEST",
    "DECLINE_BILATERAL_REQUEST",
)
ACTION_LABELS = (WAIT_LABEL, *DIRECTED_LABELS)
RESPONSE_FAMILY = (
    "CONFIRM_BILATERAL_REQUEST",
    "DECLINE_BILATERAL_REQUEST",
)
OTHER_DIRECTED_FAMILY = (
    "DIRECT_TEXT",
    "OPEN_BILATERAL_REQUEST",
)
POSITIVE_FRACTION_MIN = 0.75
P1B_G1_OVERALL_WAIT_RATE_MIN = 0.95
P1B_G1_PER_CONTEXT_WAIT_RATE_MIN = 0.90
P1B_G3_CONTRASTS_REQUIRED = 2
P1B_G4_CONTRASTS_REQUIRED = 2
P1B_G5_MATCHED_SENSITIVITY_RATE_MIN = 0.25
P1B_G5_TVD_MIN = 0.25
P1B_G5_NONQUIET_TVD_CLASSES_MIN = 2


def _validate_score_map(scores: Mapping[str, float]) -> dict[str, float]:
    if set(scores) != set(ACTION_LABELS):
        raise ValueError("scores must contain exactly the five frozen action labels")
    normalized = {label: float(scores[label]) for label in ACTION_LABELS}
    return normalized


def total_variation_distance(left: Sequence[str], right: Sequence[str]) -> float:
    if not left or not right:
        raise ValueError("TVD samples must be non-empty")
    lc = Counter(left)
    rc = Counter(right)
    labels = set(lc) | set(rc)
    return 0.5 * sum(
        abs(lc[label] / len(left) - rc[label] / len(right)) for label in labels
    )


@dataclass(frozen=True, slots=True)
class ScoreStructure:
    wait_margin: float
    relative_to_wait: tuple[tuple[str, float], ...]
    centered_directed: tuple[tuple[str, float], ...]

    def relative_dict(self) -> dict[str, float]:
        return dict(self.relative_to_wait)

    def centered_dict(self) -> dict[str, float]:
        return dict(self.centered_directed)


@dataclass(frozen=True, slots=True)
class PositiveRuleResult:
    count: int
    positive_count: int
    positive_fraction: float
    median: float
    passed: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "count": self.count,
            "positive_count": self.positive_count,
            "positive_fraction": self.positive_fraction,
            "positive_fraction_min": POSITIVE_FRACTION_MIN,
            "median": self.median,
            "median_strictly_positive": self.median > 0.0,
            "pass": self.passed,
        }


@dataclass(frozen=True, slots=True)
class LabelSensitivityMetrics:
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
            "tvd_from_quiet": dict(self.tvd_from_quiet),
            "tvd_min": P1B_G5_TVD_MIN,
            "tvd_passing_class_count": self.tvd_passing_class_count,
            "tvd_passing_classes_min": P1B_G5_NONQUIET_TVD_CLASSES_MIN,
            "pass": self.passed,
        }


@dataclass(frozen=True, slots=True)
class WaitDominanceMetrics:
    overall_wait_count: int
    overall_total: int
    overall_wait_rate: float
    per_context: tuple[tuple[str, int, int, float], ...]
    passed: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "overall_wait_count": self.overall_wait_count,
            "overall_total": self.overall_total,
            "overall_wait_rate": self.overall_wait_rate,
            "overall_wait_rate_min": P1B_G1_OVERALL_WAIT_RATE_MIN,
            "per_context": {
                name: {"wait_count": wait, "total": total, "wait_rate": rate}
                for name, wait, total, rate in self.per_context
            },
            "per_context_wait_rate_min": P1B_G1_PER_CONTEXT_WAIT_RATE_MIN,
            "pass": self.passed,
        }


def score_structure(scores: Mapping[str, float]) -> ScoreStructure:
    """Compute preregistered r, M, and q from one five-label score set."""

    values = _validate_score_map(scores)
    wait = values[WAIT_LABEL]
    relative = {label: values[label] - wait for label in DIRECTED_LABELS}
    mean_relative = statistics.fmean(relative.values())
    centered = {label: relative[label] - mean_relative for label in DIRECTED_LABELS}
    margin = wait - max(values[label] for label in DIRECTED_LABELS)
    return ScoreStructure(
        wait_margin=margin,
        relative_to_wait=tuple((label, relative[label]) for label in DIRECTED_LABELS),
        centered_directed=tuple((label, centered[label]) for label in DIRECTED_LABELS),
    )


def response_family_separation(scores: Mapping[str, float]) -> float:
    q = score_structure(scores).centered_dict()
    response = statistics.fmean(q[label] for label in RESPONSE_FAMILY)
    other = statistics.fmean(q[label] for label in OTHER_DIRECTED_FAMILY)
    return response - other


def structural_contrasts(
    scores_by_context: Mapping[str, Mapping[str, float]],
) -> dict[str, float]:
    """Compute S_msg, S_prop, and S_owner for one matched case index."""

    if set(scores_by_context) != set(P1B_CONTEXT_CLASSES):
        raise ValueError("one matched case must contain exactly the five context classes")
    structures = {
        name: score_structure(scores_by_context[name]) for name in P1B_CONTEXT_CLASSES
    }
    quiet_q = structures["QUIET"].centered_dict()
    message_q = structures["MESSAGE_RECEIVED"].centered_dict()
    family = {
        name: response_family_separation(scores_by_context[name])
        for name in P1B_CONTEXT_CLASSES
    }
    return {
        "S_msg": message_q["DIRECT_TEXT"] - quiet_q["DIRECT_TEXT"],
        "S_prop": family["PROPOSAL_RECEIVED"] - family["QUIET"],
        "S_owner": family["PROPOSAL_RECEIVED"] - family["OWN_PROPOSAL_PENDING"],
    }


def evaluate_positive_rule(values: Sequence[float]) -> PositiveRuleResult:
    normalized = tuple(float(value) for value in values)
    if not normalized:
        raise ValueError("positive-rule values must be non-empty")
    positive = sum(value > 0.0 for value in normalized)
    fraction = positive / len(normalized)
    median = float(statistics.median(normalized))
    return PositiveRuleResult(
        count=len(normalized),
        positive_count=positive,
        positive_fraction=fraction,
        median=median,
        passed=(median > 0.0 and fraction >= POSITIVE_FRACTION_MIN),
    )


def evaluate_wait_amplification(
    base_margins: Sequence[float], fa_margins: Sequence[float]
) -> tuple[PositiveRuleResult, tuple[float, ...]]:
    if len(base_margins) != len(fa_margins) or not base_margins:
        raise ValueError("base and FA wait-margin sequences must be non-empty and matched")
    effects = tuple(float(fa) - float(base) for base, fa in zip(base_margins, fa_margins, strict=True))
    return evaluate_positive_rule(effects), effects


def evaluate_structural_presence(
    contrast_values: Mapping[str, Sequence[float]],
) -> tuple[dict[str, PositiveRuleResult], bool]:
    required = {"S_msg", "S_prop", "S_owner"}
    if set(contrast_values) != required:
        raise ValueError("structural contrast map must contain S_msg, S_prop, and S_owner")
    results = {name: evaluate_positive_rule(contrast_values[name]) for name in sorted(required)}
    passed = sum(result.passed for result in results.values()) >= P1B_G3_CONTRASTS_REQUIRED
    return results, passed


def evaluate_adapter_structural_gain(
    base_contrasts: Mapping[str, Sequence[float]],
    fa_contrasts: Mapping[str, Sequence[float]],
) -> tuple[dict[str, PositiveRuleResult], dict[str, tuple[float, ...]], bool]:
    required = {"S_msg", "S_prop", "S_owner"}
    if set(base_contrasts) != required or set(fa_contrasts) != required:
        raise ValueError("adapter-gain inputs must contain the three frozen contrasts")
    gains: dict[str, tuple[float, ...]] = {}
    results: dict[str, PositiveRuleResult] = {}
    for name in sorted(required):
        base = tuple(float(value) for value in base_contrasts[name])
        fa = tuple(float(value) for value in fa_contrasts[name])
        if len(base) != len(fa) or not base:
            raise ValueError("adapter-gain contrast values must be non-empty and matched")
        values = tuple(fa_value - base_value for base_value, fa_value in zip(base, fa, strict=True))
        gains[name] = values
        results[name] = evaluate_positive_rule(values)
    passed = sum(result.passed for result in results.values()) >= P1B_G4_CONTRASTS_REQUIRED
    return results, gains, passed


def _validated_label_samples(
    labels_by_context: Mapping[str, Sequence[str]], *, cases_per_context: int
) -> dict[str, tuple[str, ...]]:
    if set(labels_by_context) != set(P1B_CONTEXT_CLASSES):
        raise ValueError("label samples must contain exactly the five frozen context classes")
    normalized: dict[str, tuple[str, ...]] = {}
    for name in P1B_CONTEXT_CLASSES:
        values = tuple(labels_by_context[name])
        if len(values) != cases_per_context:
            raise ValueError("label sample count does not match the frozen cohort size")
        if any(value not in ACTION_LABELS for value in values):
            raise ValueError("label samples contain an unknown action label")
        normalized[name] = values
    return normalized


def evaluate_label_sensitivity(
    labels_by_context: Mapping[str, Sequence[str]], *, cases_per_context: int = P1B_HELDOUT_CASES
) -> LabelSensitivityMetrics:
    samples = _validated_label_samples(labels_by_context, cases_per_context=cases_per_context)
    matched_sensitive = sum(
        len({samples[name][index] for name in P1B_CONTEXT_CLASSES}) > 1
        for index in range(cases_per_context)
    )
    matched_rate = matched_sensitive / cases_per_context
    quiet = samples[P1B_CONTROL_CONTEXT]
    tvds = tuple(
        (name, total_variation_distance(quiet, samples[name]))
        for name in P1B_CONTEXT_CLASSES
        if name != P1B_CONTROL_CONTEXT
    )
    passing = sum(value >= P1B_G5_TVD_MIN for _, value in tvds)
    passed = (
        matched_rate >= P1B_G5_MATCHED_SENSITIVITY_RATE_MIN
        and passing >= P1B_G5_NONQUIET_TVD_CLASSES_MIN
    )
    return LabelSensitivityMetrics(
        matched_sensitive_count=matched_sensitive,
        matched_total=cases_per_context,
        matched_sensitivity_rate=matched_rate,
        tvd_from_quiet=tvds,
        tvd_passing_class_count=passing,
        passed=passed,
    )


def evaluate_wait_dominance(
    labels_by_context: Mapping[str, Sequence[str]], *, cases_per_context: int = P1B_PAIRED_CASES
) -> WaitDominanceMetrics:
    samples = _validated_label_samples(labels_by_context, cases_per_context=cases_per_context)
    rows = []
    total_wait = 0
    total = 0
    per_context_pass = True
    for name in P1B_CONTEXT_CLASSES:
        values = samples[name]
        wait = sum(value == WAIT_LABEL for value in values)
        rate = wait / len(values)
        rows.append((name, wait, len(values), rate))
        total_wait += wait
        total += len(values)
        per_context_pass = per_context_pass and rate >= P1B_G1_PER_CONTEXT_WAIT_RATE_MIN
    overall = total_wait / total
    return WaitDominanceMetrics(
        overall_wait_count=total_wait,
        overall_total=total,
        overall_wait_rate=overall,
        per_context=tuple(rows),
        passed=(overall >= P1B_G1_OVERALL_WAIT_RATE_MIN and per_context_pass),
    )


__all__ = [
    "P1B_STUDY_ID",
    "P1B_SCHEMA_VERSION",
    "P1B_CONTEXT_CLASSES",
    "P1B_CONTROL_CONTEXT",
    "P1B_HELDOUT_CASES",
    "P1B_PAIRED_CASES",
    "WAIT_LABEL",
    "DIRECTED_LABELS",
    "ACTION_LABELS",
    "ScoreStructure",
    "PositiveRuleResult",
    "LabelSensitivityMetrics",
    "WaitDominanceMetrics",
    "score_structure",
    "response_family_separation",
    "structural_contrasts",
    "evaluate_positive_rule",
    "evaluate_wait_amplification",
    "evaluate_structural_presence",
    "evaluate_adapter_structural_gain",
    "total_variation_distance",
    "evaluate_label_sensitivity",
    "evaluate_wait_dominance",
]
