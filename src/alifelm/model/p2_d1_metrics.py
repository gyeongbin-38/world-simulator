"""Pure descriptive metrics for WORLD P2-D1.

No metric in this module changes the frozen P2 admission decision. Numerical
values are descriptive; no post-hoc sensitivity threshold is introduced.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any, Iterable

from .p2_d1_boundary import D1_ACTION_ORDER


D1_CONTEXT_CLASSES = (
    "QUIET",
    "MESSAGE_RECEIVED",
    "PROPOSAL_RECEIVED",
    "OWN_PROPOSAL_PENDING",
    "RECENT_INTERACTION",
)


def _summary(values: Iterable[float]) -> dict[str, float | int]:
    data = list(values)
    if not data:
        return {"count": 0, "min": 0.0, "median": 0.0, "max": 0.0, "max_abs": 0.0}
    return {
        "count": len(data),
        "min": min(data),
        "median": median(data),
        "max": max(data),
        "max_abs": max(abs(value) for value in data),
    }


def _index(records: list[dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
    result = {(row["context_class"], row["case_index"]): row for row in records}
    if len(result) != len(records):
        raise ValueError("duplicate P2-D1 context/case record")
    return result


def matched_nonquiet_vs_quiet(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Describe paired C10 context movement without inventing a gate."""

    rows = _index(records)
    case_indices = sorted(index for context, index in rows if context == "QUIET")
    result: dict[str, Any] = {}
    for context in D1_CONTEXT_CLASSES[1:]:
        per_case = []
        total_deltas = defaultdict(list)
        mean_deltas = defaultdict(list)
        margin_deltas: list[float] = []
        max_vector_deltas: list[float] = []
        total_rank_change = 0
        total_rank1_change = 0
        for case_index in case_indices:
            quiet = rows[("QUIET", case_index)]
            other = rows[(context, case_index)]
            branch_total = {
                action: other["total_scores"][action] - quiet["total_scores"][action]
                for action in D1_ACTION_ORDER
            }
            branch_mean = {
                action: other["mean_scores"][action] - quiet["mean_scores"][action]
                for action in D1_ACTION_ORDER
            }
            for action in D1_ACTION_ORDER:
                total_deltas[action].append(branch_total[action])
                mean_deltas[action].append(branch_mean[action])
            margin_delta = other["nda_total_margin"] - quiet["nda_total_margin"]
            vector_max = max(abs(value) for value in branch_total.values())
            rank_changed = any(
                other["total_ranks"][action] != quiet["total_ranks"][action]
                for action in D1_ACTION_ORDER
            )
            rank1_changed = other["total_rank1"] != quiet["total_rank1"]
            total_rank_change += int(rank_changed)
            total_rank1_change += int(rank1_changed)
            margin_deltas.append(margin_delta)
            max_vector_deltas.append(vector_max)
            per_case.append(
                {
                    "case_index": case_index,
                    "total_score_delta": branch_total,
                    "mean_score_delta": branch_mean,
                    "max_abs_total_score_vector_delta": vector_max,
                    "nda_margin_delta": margin_delta,
                    "any_total_rank_change": rank_changed,
                    "total_rank1_change": rank1_changed,
                }
            )
        result[context] = {
            "cases": per_case,
            "total_score_delta_summary": {
                action: _summary(total_deltas[action]) for action in D1_ACTION_ORDER
            },
            "mean_score_delta_summary": {
                action: _summary(mean_deltas[action]) for action in D1_ACTION_ORDER
            },
            "max_abs_total_score_vector_delta_summary": _summary(max_vector_deltas),
            "nda_margin_delta_summary": _summary(margin_deltas),
            "any_total_rank_change_count": total_rank_change,
            "total_rank1_change_count": total_rank1_change,
        }
    return result


def paired_condition_shift(
    c10_records: list[dict[str, Any]], c00_records: list[dict[str, Any]]
) -> dict[str, Any]:
    """Describe FA-prefill shift while BASE selector is held fixed."""

    c10 = _index(c10_records)
    c00 = _index(c00_records)
    if set(c10) != set(c00):
        raise ValueError("C10/C00 P2-D1 record keys differ")
    per_context: dict[str, Any] = {}
    for context in D1_CONTEXT_CLASSES:
        selected = sorted(index for name, index in c10 if name == context)
        totals = defaultdict(list)
        margins: list[float] = []
        rank1_change = 0
        for case_index in selected:
            left = c10[(context, case_index)]
            right = c00[(context, case_index)]
            for action in D1_ACTION_ORDER:
                totals[action].append(left["total_scores"][action] - right["total_scores"][action])
            margins.append(left["nda_total_margin"] - right["nda_total_margin"])
            rank1_change += int(left["total_rank1"] != right["total_rank1"])
        per_context[context] = {
            "total_score_shift_summary": {action: _summary(totals[action]) for action in D1_ACTION_ORDER},
            "nda_margin_shift_summary": _summary(margins),
            "total_rank1_change_count": rank1_change,
        }
    return per_context


def exact_repeat_deltas(
    first: list[dict[str, Any]], repeat: list[dict[str, Any]]
) -> dict[str, Any]:
    """Report exact-repeat numerical and structural deltas."""

    a = _index(first)
    b = _index(repeat)
    if set(a) != set(b):
        raise ValueError("P2-D1 repeat record keys differ")
    total_deltas: list[float] = []
    mean_deltas: list[float] = []
    structural_mismatch_count = 0
    for key in sorted(a):
        left, right = a[key], b[key]
        structural_fields = (
            "context_token_ids",
            "prefix_token_ids",
            "combined_token_ids",
            "common_prefix_token_ids",
            "divergence_step",
            "total_ranks",
            "mean_ranks",
            "total_rank1",
            "mean_rank1",
        )
        structural_mismatch_count += int(any(left[field] != right[field] for field in structural_fields))
        for action in D1_ACTION_ORDER:
            total_deltas.append(right["total_scores"][action] - left["total_scores"][action])
            mean_deltas.append(right["mean_scores"][action] - left["mean_scores"][action])
    return {
        "structural_mismatch_count": structural_mismatch_count,
        "total_score_delta": _summary(total_deltas),
        "mean_score_delta": _summary(mean_deltas),
        "serialized_equal": first == repeat,
    }


def localization_tag(
    c10_records: list[dict[str, Any]],
    matched: dict[str, Any],
    repeat: dict[str, Any],
) -> str:
    """Apply preregistered descriptive tags using exact-repeat noise only."""

    rank1_values = {row["total_rank1"] for row in c10_records}
    any_rank_change = any(
        payload["any_total_rank_change_count"] > 0 for payload in matched.values()
    )
    if any_rank_change or len(rank1_values) > 1:
        return "RANK_CONTEXT_SENSITIVE"

    repeat_noise = float(repeat["total_score_delta"]["max_abs"])
    context_effect = max(
        float(payload["max_abs_total_score_vector_delta_summary"]["max_abs"])
        for payload in matched.values()
    )
    if rank1_values == {"WAIT"} and context_effect > repeat_noise:
        return "RANK_STABLE_SCORE_SENSITIVE_NDA_DOMINANCE"
    if context_effect <= repeat_noise:
        return "ACTION_SCORE_CONTEXT_INSENSITIVE"
    return "MIXED_OR_UNRESOLVED"


__all__ = [
    "D1_CONTEXT_CLASSES",
    "matched_nonquiet_vs_quiet",
    "paired_condition_shift",
    "exact_repeat_deltas",
    "localization_tag",
]
