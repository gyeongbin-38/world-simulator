"""Pure descriptive and selection metrics for WORLD P2-D2."""

from __future__ import annotations

from statistics import median
from typing import Iterable


def mediator_values(g_base: float, g_fa: float, g_rescue: float, g_induction: float) -> dict[str, float]:
    denominator = g_fa - g_base
    if denominator <= 0:
        raise ValueError("P2-D2 requires a positive C10-minus-C00 WAIT-SEND gap")
    nr = (g_fa - g_rescue) / denominator
    ni = (g_induction - g_base) / denominator
    return {
        "denominator": denominator,
        "normalized_rescue": nr,
        "normalized_induction": ni,
        "symmetric_score": (nr + ni) / 2.0,
    }


def median_symmetric_score(rows: Iterable[dict[str, float]]) -> float:
    values = [float(row["symmetric_score"]) for row in rows]
    if not values:
        raise ValueError("P2-D2 cannot summarize an empty mediator set")
    return float(median(values))


def select_top_blocks(scores: dict[str, float]) -> tuple[str, str]:
    expected = ("Q0", "Q1", "Q2", "Q3")
    if tuple(scores) != expected:
        raise ValueError("P2-D2 coarse block scores must use frozen block order")
    ordered = sorted(expected, key=lambda name: (-float(scores[name]), int(name[1:])))
    return ordered[0], ordered[1]


def select_top_layers(scores: dict[int, float]) -> tuple[int, int]:
    if not scores or any(type(layer) is not int or layer < 0 or layer > 15 for layer in scores):
        raise ValueError("P2-D2 layer scores must use frozen layer IDs 0..15")
    ordered = sorted(scores, key=lambda layer: (-float(scores[layer]), layer))
    if len(ordered) < 2:
        raise ValueError("P2-D2 requires at least two candidate layers")
    return ordered[0], ordered[1]


def union_localization_label(rescue_gaps: Iterable[float], induction_gaps: Iterable[float]) -> str:
    rescue = list(rescue_gaps)
    induction = list(induction_gaps)
    if len(rescue) != 160 or len(induction) != 160:
        raise ValueError("P2-D2 Stage-C union label requires 160 paired gaps")
    rescue_flips = sum(value < 0 for value in rescue)
    induction_flips = sum(value > 0 for value in induction)
    if rescue_flips == 160 and induction_flips == 160:
        return "UNION_BIDIRECTIONAL_UNIVERSAL_FLIP"
    if rescue_flips > 0 and induction_flips > 0:
        return "UNION_BIDIRECTIONAL_NONUNIVERSAL"
    if (rescue_flips > 0) != (induction_flips > 0):
        return "UNION_ONE_DIRECTION_ONLY"
    return "NO_SIGN_FLIP_MEDIATION"


__all__ = [
    "mediator_values",
    "median_symmetric_score",
    "select_top_blocks",
    "select_top_layers",
    "union_localization_label",
]
