#!/usr/bin/env python3
"""R2 runtime-compatibility wrapper for WORLD P2-D3.

The preregistered intervention and selection protocol are unchanged. R1 reached
real model inference but failed while serializing a D1BoundaryProbeResult with
the D2 cache-score serializer. This wrapper replaces only the D3 record
serializer with one matching the D1 boundary probe result type, then delegates
to the frozen D3 runner.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))
sys.path.insert(0, str(REPOSITORY_ROOT))

from alifelm.model.p2_d1_boundary import D1_ACTION_ORDER  # noqa: E402
from tools import world_p2_d3_targeted_adapter_scaling as base  # noqa: E402


def _score_record_from_d1(score: Any, *, condition: str, layers: tuple[int, ...]) -> dict[str, Any]:
    """Serialize D1BoundaryProbeResult without assuming D2-only attributes."""

    branch = [
        {
            "internal_action": item.internal_action,
            "model_label": item.model_label,
            "token_ids": list(item.token_ids),
            "token_count": len(item.token_ids),
            "total_log_probability": item.total_log_probability,
            "mean_log_probability": item.mean_log_probability,
            "total_rank": item.total_rank,
            "mean_rank": item.mean_rank,
        }
        for item in score.branch_scores
    ]
    totals = score.total_scores()
    means = score.mean_scores()
    return {
        "condition": condition,
        "patch_layers": list(layers),
        "actions_scored": list(D1_ACTION_ORDER),
        "common_prefix_token_ids": list(score.common_prefix_token_ids),
        "divergence_step": score.divergence_step,
        "selector_prefix_forward_count": score.selector_prefix_forward_count,
        "common_prefix_forward_count": score.common_prefix_forward_count,
        "branch_continuation_forward_count": score.branch_continuation_forward_count,
        "branch_scores": branch,
        "total_scores": totals,
        "mean_scores": means,
        "wait_send_total_gap": totals["WAIT"] - totals["SEND"],
        "wait_send_mean_gap": means["WAIT"] - means["SEND"],
        "total_rank1": min(branch, key=lambda row: row["total_rank"])["internal_action"],
        "mean_rank1": min(branch, key=lambda row: row["mean_rank"])["internal_action"],
    }


def _record(score: Any, *, context: str, case: int, scale: float, applied: Any) -> dict[str, Any]:
    payload = _score_record_from_d1(
        score,
        condition=f"L9_L10_SCALE_{scale:.2f}",
        layers=base.TARGET_LAYERS,
    )
    payload.update(
        {
            "context_class": context,
            "case_index": case,
            "scale": scale,
            "matched_modules_by_layer": [list(item) for item in applied.matched_modules_by_layer],
            "matched_module_names": list(applied.matched_module_names),
        }
    )
    return payload


def main() -> int:
    base._record = _record
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
