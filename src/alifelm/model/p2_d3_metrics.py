"""Pure preregistered selection and descriptive metrics for WORLD P2-D3."""

from __future__ import annotations

from collections import Counter
from statistics import median
from typing import Iterable, Mapping, Sequence

from .p1b_metrics import total_variation_distance


CONTEXTS = (
    "QUIET",
    "MESSAGE_RECEIVED",
    "PROPOSAL_RECEIVED",
    "OWN_PROPOSAL_PENDING",
    "RECENT_INTERACTION",
)


def matched_rank1_sensitivity(records: Sequence[Mapping[str, object]]) -> int:
    """Count matched case indices whose five contexts do not share one rank-1 action."""

    by_case: dict[int, dict[str, str]] = {}
    for row in records:
        case = int(row["case_index"])
        context = str(row["context_class"])
        action = str(row["total_rank1"])
        by_case.setdefault(case, {})[context] = action
    count = 0
    for case, values in by_case.items():
        if set(values) != set(CONTEXTS):
            raise ValueError(f"P2-D3 case {case} does not contain exactly five contexts")
        if len(set(values.values())) >= 2:
            count += 1
    return count


def summarize_scale(records: Sequence[Mapping[str, object]], scale: float) -> dict[str, object]:
    if not records:
        raise ValueError("P2-D3 cannot summarize an empty scale condition")
    gaps = [float(row["wait_send_total_gap"]) for row in records]
    actions = [str(row["total_rank1"]) for row in records]
    return {
        "scale": float(scale),
        "matched_sensitive_count": matched_rank1_sensitivity(records),
        "distinct_rank1_action_count": len(set(actions)),
        "rank1_distribution": dict(sorted(Counter(actions).items())),
        "median_wait_send_gap": float(median(gaps)),
        "abs_median_wait_send_gap": abs(float(median(gaps))),
        "strict_wait_gap_count": sum(value > 0 for value in gaps),
        "strict_send_gap_count": sum(value < 0 for value in gaps),
        "tie_gap_count": sum(value == 0 for value in gaps),
    }


def select_scale(summaries: Mapping[float, Mapping[str, object]]) -> float:
    """Apply the frozen lexicographic D3 selection rule."""

    expected = (0.0, 0.25, 0.5, 0.75, 1.0)
    if tuple(sorted(float(value) for value in summaries)) != expected:
        raise ValueError("P2-D3 scale summaries do not match the frozen candidate grid")
    ordered = sorted(
        expected,
        key=lambda scale: (
            -int(summaries[scale]["matched_sensitive_count"]),
            -int(summaries[scale]["distinct_rank1_action_count"]),
            float(summaries[scale]["abs_median_wait_send_gap"]),
            -scale,
        ),
    )
    return float(ordered[0])


def full_cohort_summary(records: Sequence[Mapping[str, object]]) -> dict[str, object]:
    if len(records) != 160:
        raise ValueError("P2-D3 full-cohort summary requires 160 records")
    by_context: dict[str, list[Mapping[str, object]]] = {name: [] for name in CONTEXTS}
    for row in records:
        context = str(row["context_class"])
        if context not in by_context:
            raise ValueError("P2-D3 observed an unknown context class")
        by_context[context].append(row)
    if any(len(values) != 32 for values in by_context.values()):
        raise ValueError("P2-D3 requires 32 records per context class")

    actions_by_context = {
        name: [str(row["total_rank1"]) for row in sorted(values, key=lambda item: int(item["case_index"]))]
        for name, values in by_context.items()
    }
    quiet = actions_by_context["QUIET"]
    tvd = {
        name: total_variation_distance(quiet, actions_by_context[name])
        for name in CONTEXTS
        if name != "QUIET"
    }
    gaps = [float(row["wait_send_total_gap"]) for row in records]
    actions = [str(row["total_rank1"]) for row in records]
    per_context = {}
    for name, values in by_context.items():
        context_gaps = [float(row["wait_send_total_gap"]) for row in values]
        context_actions = [str(row["total_rank1"]) for row in values]
        per_context[name] = {
            "rank1_distribution": dict(sorted(Counter(context_actions).items())),
            "median_wait_send_gap": float(median(context_gaps)),
            "min_wait_send_gap": min(context_gaps),
            "max_wait_send_gap": max(context_gaps),
        }
    return {
        "matched_sensitive_count": matched_rank1_sensitivity(records),
        "matched_total": 32,
        "matched_sensitivity_rate": matched_rank1_sensitivity(records) / 32.0,
        "distinct_rank1_action_count": len(set(actions)),
        "rank1_distribution": dict(sorted(Counter(actions).items())),
        "tvd_from_quiet": tvd,
        "tvd_passing_class_count_at_0_25": sum(value >= 0.25 for value in tvd.values()),
        "median_wait_send_gap": float(median(gaps)),
        "min_wait_send_gap": min(gaps),
        "max_wait_send_gap": max(gaps),
        "strict_wait_gap_count": sum(value > 0 for value in gaps),
        "strict_send_gap_count": sum(value < 0 for value in gaps),
        "tie_gap_count": sum(value == 0 for value in gaps),
        "by_context": per_context,
        "score_proxy_g5_shape_pass": (
            matched_rank1_sensitivity(records) / 32.0 >= 0.25
            and sum(value >= 0.25 for value in tvd.values()) >= 2
        ),
    }


__all__ = [
    "CONTEXTS",
    "full_cohort_summary",
    "matched_rank1_sensitivity",
    "select_scale",
    "summarize_scale",
]
