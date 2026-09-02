"""Pure measurement rules for WORLD P1C-v2 common-topology phase ablation.

No model loading, forward pass, cache mutation, generation, state commit, or
weight update occurs in this module.  It evaluates only measurements frozen by
the P1C-v2 preregistration.
"""

from __future__ import annotations

from dataclasses import dataclass
import statistics
from typing import Mapping, Sequence

from .p1b_metrics import ACTION_LABELS, PositiveRuleResult, evaluate_positive_rule
from .p1c_metrics import matched_phase_effect, rank1_sensitivity


P1C_V2_STUDY_ID = "WORLD_P1C_V2_COMMON_TOPOLOGY_PHASE_ABLATION_V1"
P1C_V2_SCHEMA_VERSION = "1.0.0"
P1C_V2_CONTEXT_CLASSES = (
    "QUIET",
    "MESSAGE_RECEIVED",
    "PROPOSAL_RECEIVED",
    "OWN_PROPOSAL_PENDING",
    "RECENT_INTERACTION",
)
P1C_V2_CASES_PER_CONTEXT = 32
P1C_V2_CONDITIONS = ("C00", "C11", "C10", "C01")
P1C_V2_STRUCTURAL_CONTRASTS = ("S_msg", "S_prop", "S_owner")
P1C_V2_STRUCTURAL_REQUIRED = 2


@dataclass(frozen=True, slots=True)
class StructuralReplicationCarryoverResult:
    """Full-adapter replication and prefill-only carryover on the same contrasts."""

    full_gain_rules: tuple[tuple[str, PositiveRuleResult], ...]
    prefill_carryover_rules: tuple[tuple[str, PositiveRuleResult], ...]
    full_gain_values: tuple[tuple[str, tuple[float, ...]], ...]
    prefill_carryover_values: tuple[tuple[str, tuple[float, ...]], ...]
    replicated_carryover: tuple[tuple[str, bool], ...]
    passed: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "full_gain": {
                name: rule.as_dict() for name, rule in self.full_gain_rules
            },
            "prefill_carryover": {
                name: rule.as_dict() for name, rule in self.prefill_carryover_rules
            },
            "full_gain_values": {
                name: list(values) for name, values in self.full_gain_values
            },
            "prefill_carryover_values": {
                name: list(values) for name, values in self.prefill_carryover_values
            },
            "replicated_carryover": dict(self.replicated_carryover),
            "required_same_contrasts": P1C_V2_STRUCTURAL_REQUIRED,
            "pass": self.passed,
        }


@dataclass(frozen=True, slots=True)
class InteractionSummary:
    count: int
    median: float
    mean: float
    positive_fraction: float
    negative_fraction: float
    zero_fraction: float

    def as_dict(self) -> dict[str, float | int]:
        return {
            "count": self.count,
            "median": self.median,
            "mean": self.mean,
            "positive_fraction": self.positive_fraction,
            "negative_fraction": self.negative_fraction,
            "zero_fraction": self.zero_fraction,
        }


def _matched_values(reference: Sequence[float], treatment: Sequence[float]) -> tuple[float, ...]:
    left = tuple(float(value) for value in reference)
    right = tuple(float(value) for value in treatment)
    if not left or len(left) != len(right):
        raise ValueError("matched sequences must be non-empty and equal length")
    return tuple(
        treatment_value - reference_value
        for reference_value, treatment_value in zip(left, right, strict=True)
    )


def evaluate_structural_replication_carryover(
    *,
    c00: Mapping[str, Sequence[float]],
    c11: Mapping[str, Sequence[float]],
    c10: Mapping[str, Sequence[float]],
) -> StructuralReplicationCarryoverResult:
    """Evaluate P1C-v2 G3 exactly as preregistered.

    A contrast counts only when the full-adapter gain C11-C00 and the
    prefill-only carryover C10-C00 both pass the frozen positive rule on that
    same structural contrast.
    """

    required = set(P1C_V2_STRUCTURAL_CONTRASTS)
    if set(c00) != required or set(c11) != required or set(c10) != required:
        raise ValueError("G3 inputs must contain exactly S_msg, S_prop, and S_owner")

    full_rules: list[tuple[str, PositiveRuleResult]] = []
    prefill_rules: list[tuple[str, PositiveRuleResult]] = []
    full_values: list[tuple[str, tuple[float, ...]]] = []
    prefill_values: list[tuple[str, tuple[float, ...]]] = []
    replicated: list[tuple[str, bool]] = []

    for name in P1C_V2_STRUCTURAL_CONTRASTS:
        full = _matched_values(c00[name], c11[name])
        prefill = _matched_values(c00[name], c10[name])
        full_rule = evaluate_positive_rule(full)
        prefill_rule = evaluate_positive_rule(prefill)
        full_rules.append((name, full_rule))
        prefill_rules.append((name, prefill_rule))
        full_values.append((name, full))
        prefill_values.append((name, prefill))
        replicated.append((name, bool(full_rule.passed and prefill_rule.passed)))

    passed = sum(value for _, value in replicated) >= P1C_V2_STRUCTURAL_REQUIRED
    return StructuralReplicationCarryoverResult(
        full_gain_rules=tuple(full_rules),
        prefill_carryover_rules=tuple(prefill_rules),
        full_gain_values=tuple(full_values),
        prefill_carryover_values=tuple(prefill_values),
        replicated_carryover=tuple(replicated),
        passed=passed,
    )


def evaluate_decoupling_candidate_v2(
    *,
    structural_replication_carryover_pass: bool,
    c10_margins: Sequence[float],
    c11_margins: Sequence[float],
):
    """Evaluate P1C-v2 G4: C11-C10 WAIT effect plus mandatory G3 dependency."""

    reduction = matched_phase_effect(c10_margins, c11_margins)
    return reduction, bool(structural_replication_carryover_pass and reduction.passed)


def interaction_summary(values: Sequence[float]) -> InteractionSummary:
    normalized = tuple(float(value) for value in values)
    if not normalized:
        raise ValueError("interaction values must be non-empty")
    positive = sum(value > 0.0 for value in normalized)
    negative = sum(value < 0.0 for value in normalized)
    zero = len(normalized) - positive - negative
    return InteractionSummary(
        count=len(normalized),
        median=float(statistics.median(normalized)),
        mean=float(statistics.fmean(normalized)),
        positive_fraction=positive / len(normalized),
        negative_fraction=negative / len(normalized),
        zero_fraction=zero / len(normalized),
    )


def factorial_interaction(
    *,
    c00: Sequence[float],
    c10: Sequence[float],
    c01: Sequence[float],
    c11: Sequence[float],
) -> tuple[tuple[float, ...], InteractionSummary]:
    """Return C11-C10-C01+C00 for one matched 2x2 factorial measurement."""

    values = tuple(tuple(float(value) for value in seq) for seq in (c00, c10, c01, c11))
    lengths = {len(seq) for seq in values}
    if lengths != {next(iter(lengths))} or not values[0]:
        raise ValueError("factorial sequences must be non-empty and matched")
    interaction = tuple(
        v11 - v10 - v01 + v00
        for v00, v10, v01, v11 in zip(*values, strict=True)
    )
    return interaction, interaction_summary(interaction)


__all__ = [
    "ACTION_LABELS",
    "P1C_V2_STUDY_ID",
    "P1C_V2_SCHEMA_VERSION",
    "P1C_V2_CONTEXT_CLASSES",
    "P1C_V2_CASES_PER_CONTEXT",
    "P1C_V2_CONDITIONS",
    "P1C_V2_STRUCTURAL_CONTRASTS",
    "P1C_V2_STRUCTURAL_REQUIRED",
    "StructuralReplicationCarryoverResult",
    "InteractionSummary",
    "evaluate_structural_replication_carryover",
    "evaluate_decoupling_candidate_v2",
    "interaction_summary",
    "factorial_interaction",
    "matched_phase_effect",
    "rank1_sensitivity",
]
