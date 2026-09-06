"""Frozen candidate selection helpers for WORLD P2-D4."""

from __future__ import annotations

from typing import Mapping


D4_CANDIDATE_ORDER = (
    "L9_K",
    "L9_V",
    "L10_K",
    "L10_V",
    "L9_L10_K",
    "L9_L10_V",
)


def select_component_candidate(scores: Mapping[str, float]) -> str:
    """Select the highest mediator-score candidate with frozen tie order."""

    if tuple(scores) != D4_CANDIDATE_ORDER:
        raise ValueError("P2-D4 candidate scores must use frozen candidate order")
    ordered = sorted(
        D4_CANDIDATE_ORDER,
        key=lambda candidate: (
            -float(scores[candidate]),
            D4_CANDIDATE_ORDER.index(candidate),
        ),
    )
    return ordered[0]


__all__ = ["D4_CANDIDATE_ORDER", "select_component_candidate"]
