"""Pure measurement rules for WORLD P1C foundation-policy phase ablation.

This module performs no model loading, forward passes, cache mutation, state
commit, or action execution.  It evaluates only measurements frozen by the
P1C preregistration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .p1b_metrics import (
    ACTION_LABELS,
    P1B_CONTEXT_CLASSES,
    P1B_HELDOUT_CASES,
    PositiveRuleResult,
    evaluate_label_sensitivity,
    evaluate_positive_rule,
)


P1C_STUDY_ID = "WORLD_P1C_FOUNDATION_POLICY_PHASE_ABLATION_V1"
P1C_SCHEMA_VERSION = "1.0.0"
P1C_CONTEXT_CLASSES = P1B_CONTEXT_CLASSES
P1C_CASES_PER_CONTEXT = P1B_HELDOUT_CASES
P1C_CONDITIONS = ("C00", "C11", "C10", "C01")
P1C_STRUCTURAL_CONTRASTS = ("S_msg", "S_prop", "S_owner")
P1C_STRUCTURAL_CONTRASTS_REQUIRED = 2
P1C_EQUIVALENCE_TOLERANCE = 1e-5


@dataclass(frozen=True, slots=True)
class PhaseEffectResult:
    """One preregistered matched phase contrast and its positive-rule gate."""

    effects: tuple[float, ...]
    rule: PositiveRuleResult

    @property
    def passed(self) -> bool:
        return self.rule.passed

    def as_dict(self) -> dict[str, object]:
        value = self.rule.as_dict()
        value["effects"] = list(self.effects)
        return value


@dataclass(frozen=True, slots=True)
class StructuralGainResult:
    """Three frozen structural contrasts plus the two-of-three summary gate."""

    contrasts: tuple[tuple[str, PositiveRuleResult], ...]
    values: tuple[tuple[str, tuple[float, ...]], ...]
    passed: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "contrasts": {name: result.as_dict() for name, result in self.contrasts},
            "values": {name: list(values) for name, values in self.values},
            "pass": self.passed,
        }


@dataclass(frozen=True, slots=True)
class EquivalenceResult:
    """Base-wrapper equivalence summary frozen by P1C section 8."""

    comparisons: int
    token_ids_exact: bool
    max_total_abs_difference: float
    max_mean_abs_difference: float
    tolerance: float
    passed: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "comparisons": self.comparisons,
            "token_ids_exact": self.token_ids_exact,
            "max_total_abs_difference": self.max_total_abs_difference,
            "max_mean_abs_difference": self.max_mean_abs_difference,
            "tolerance": self.tolerance,
            "pass": self.passed,
        }


def matched_phase_effect(
    reference: Sequence[float], treatment: Sequence[float]
) -> PhaseEffectResult:
    """Evaluate treatment-reference under the frozen median/fraction rule."""

    left = tuple(float(value) for value in reference)
    right = tuple(float(value) for value in treatment)
    if not left or len(left) != len(right):
        raise ValueError("phase-effect sequences must be non-empty and matched")
    effects = tuple(
        treatment_value - reference_value
        for reference_value, treatment_value in zip(left, right, strict=True)
    )
    return PhaseEffectResult(effects=effects, rule=evaluate_positive_rule(effects))


def structural_gain(
    reference: Mapping[str, Sequence[float]],
    treatment: Mapping[str, Sequence[float]],
) -> StructuralGainResult:
    """Evaluate preregistered structural carryover/gain for three contrasts."""

    required = set(P1C_STRUCTURAL_CONTRASTS)
    if set(reference) != required or set(treatment) != required:
        raise ValueError("structural inputs must contain S_msg, S_prop, and S_owner")
    results: list[tuple[str, PositiveRuleResult]] = []
    values_out: list[tuple[str, tuple[float, ...]]] = []
    for name in P1C_STRUCTURAL_CONTRASTS:
        base = tuple(float(value) for value in reference[name])
        changed = tuple(float(value) for value in treatment[name])
        if not base or len(base) != len(changed):
            raise ValueError("structural contrast values must be non-empty and matched")
        values = tuple(
            changed_value - base_value
            for base_value, changed_value in zip(base, changed, strict=True)
        )
        values_out.append((name, values))
        results.append((name, evaluate_positive_rule(values)))
    passed = sum(result.passed for _, result in results) >= P1C_STRUCTURAL_CONTRASTS_REQUIRED
    return StructuralGainResult(tuple(results), tuple(values_out), passed)


def evaluate_decoupling_candidate(
    *, structural_carryover_pass: bool, c11_margins: Sequence[float], c10_margins: Sequence[float]
) -> tuple[PhaseEffectResult, bool]:
    """Evaluate P1C-G4: C11-C10 WAIT reduction plus mandatory G3 dependency."""

    reduction = matched_phase_effect(c10_margins, c11_margins)
    return reduction, bool(structural_carryover_pass and reduction.passed)


def evaluate_base_wrapper_equivalence(
    *,
    token_ids_equal: Sequence[bool],
    total_abs_differences: Sequence[float],
    mean_abs_differences: Sequence[float],
    tolerance: float = P1C_EQUIVALENCE_TOLERANCE,
) -> EquivalenceResult:
    """Apply the frozen <=1e-5 C00 versus separate-base equivalence rule."""

    token_equal = tuple(bool(value) for value in token_ids_equal)
    total = tuple(float(value) for value in total_abs_differences)
    mean = tuple(float(value) for value in mean_abs_differences)
    if not token_equal or len(token_equal) != len(total) or len(total) != len(mean):
        raise ValueError("equivalence sequences must be non-empty and matched")
    if tolerance < 0.0:
        raise ValueError("equivalence tolerance must be non-negative")
    max_total = max(total)
    max_mean = max(mean)
    tokens_ok = all(token_equal)
    passed = tokens_ok and max_total <= tolerance and max_mean <= tolerance
    return EquivalenceResult(
        comparisons=len(total),
        token_ids_exact=tokens_ok,
        max_total_abs_difference=max_total,
        max_mean_abs_difference=max_mean,
        tolerance=tolerance,
        passed=passed,
    )


def rank1_sensitivity(labels_by_context: Mapping[str, Sequence[str]]):
    """Reuse the exact P1/P1B matched rank-1 sensitivity rule for P1C-G5."""

    return evaluate_label_sensitivity(
        labels_by_context, cases_per_context=P1C_CASES_PER_CONTEXT
    )


__all__ = [
    "ACTION_LABELS",
    "P1C_STUDY_ID",
    "P1C_SCHEMA_VERSION",
    "P1C_CONTEXT_CLASSES",
    "P1C_CASES_PER_CONTEXT",
    "P1C_CONDITIONS",
    "P1C_STRUCTURAL_CONTRASTS",
    "P1C_STRUCTURAL_CONTRASTS_REQUIRED",
    "P1C_EQUIVALENCE_TOLERANCE",
    "PhaseEffectResult",
    "StructuralGainResult",
    "EquivalenceResult",
    "matched_phase_effect",
    "structural_gain",
    "evaluate_decoupling_candidate",
    "evaluate_base_wrapper_equivalence",
    "rank1_sensitivity",
]
