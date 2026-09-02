"""Protocol-neutral implementation hardening for WORLD P2.

This module does not load a model, generate text, mutate WORLD state, alter
preregistered thresholds, or choose actions.  It closes pre-inference
implementation/provenance gaps while preserving the frozen P2 scientific
contract.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Sequence

from .autonomous_admission import (
    A0TreatmentMetrics,
    A0_I3_BRANCH_CANDIDATE_AGREEMENT_MIN,
    A0_I3_BRANCH_DOMAIN_RATE_SPREAD_MAX,
    evaluate_treatment,
)


P2_BRANCH_AUDIT_ATTEMPTS = 160
P2_PHASE_EXECUTION_EVIDENCE_CONTRACT = "world-p2-phase-execution-1.0.0"
P2_PHASE_EXECUTION_DOMAIN = "WORLD_P2_PHASE_EXECUTION_V1"
P2_PHASE_CONDITIONS = {
    "C00": (False, False),
    "C01": (False, True),
    "C10": (True, False),
    "C11": (True, True),
}


def evaluate_p2_i3_branch_order_audit(
    summaries: Sequence[A0TreatmentMetrics],
    candidate_labels_by_order: Sequence[Sequence[str | None]],
) -> dict[str, object]:
    """Evaluate the frozen P2 160-context I3 branch-order audit.

    Thresholds are exactly the previously frozen A0 thresholds; only the
    preregistered P2 cohort cardinality differs from A0.
    """

    if len(summaries) != 4 or len(candidate_labels_by_order) != 4:
        raise ValueError("P2 G3 requires exactly four frozen I3 branch orders")
    if any(summary.attempts != P2_BRANCH_AUDIT_ATTEMPTS for summary in summaries):
        raise ValueError("each P2 G3 summary must cover exactly 160 attempts")
    if any(
        len(values) != P2_BRANCH_AUDIT_ATTEMPTS
        for values in candidate_labels_by_order
    ):
        raise ValueError("each P2 G3 branch order must cover exactly 160 labels")

    all_core_pass = all(
        bool(evaluate_treatment(summary)["autonomous_pass"])
        for summary in summaries
    )
    agreeing = 0
    for index in range(P2_BRANCH_AUDIT_ATTEMPTS):
        if len({order[index] for order in candidate_labels_by_order}) == 1:
            agreeing += 1
    agreement_rate = agreeing / P2_BRANCH_AUDIT_ATTEMPTS
    domain_rates = [summary.domain_valid_rate for summary in summaries]
    domain_rate_spread = max(domain_rates) - min(domain_rates)
    passed = (
        all_core_pass
        and agreement_rate >= A0_I3_BRANCH_CANDIDATE_AGREEMENT_MIN
        and domain_rate_spread <= A0_I3_BRANCH_DOMAIN_RATE_SPREAD_MAX
    )
    return {
        "pass": passed,
        "all_orders_core_pass": all_core_pass,
        "candidate_agreement_count": agreeing,
        "candidate_agreement_total": P2_BRANCH_AUDIT_ATTEMPTS,
        "candidate_agreement_rate": agreement_rate,
        "candidate_agreement_min": A0_I3_BRANCH_CANDIDATE_AGREEMENT_MIN,
        "domain_valid_rate_spread": domain_rate_spread,
        "domain_valid_rate_spread_max": A0_I3_BRANCH_DOMAIN_RATE_SPREAD_MAX,
    }


def canonical_allowed_tokens(allowed_tokens: Sequence[int]) -> tuple[int, ...]:
    """Return a process-stable allowed-token order for constrained greedy decode."""

    values = tuple(allowed_tokens)
    if not values:
        raise ValueError("I3 constraint returned no allowed tokens")
    if any(type(token_id) is not int or token_id < 0 for token_id in values):
        raise ValueError("I3 constraint returned invalid token IDs")
    if len(set(values)) != len(values):
        raise ValueError("I3 constraint returned duplicate token IDs")
    return tuple(sorted(values))


def stable_allowed_argmax(torch_module: Any, logits: Any, allowed_tokens: list[int]) -> int:
    """Greedy constrained argmax with a canonical lowest-token-ID tie break."""

    try:
        canonical = canonical_allowed_tokens(allowed_tokens)
    except ValueError as error:
        from .transformers_backend import GenerationError

        raise GenerationError(str(error)) from error
    indices = torch_module.tensor(canonical, dtype=torch_module.long, device=logits.device)
    selected = int(torch_module.argmax(logits.index_select(0, indices)).item())
    return int(canonical[selected])


def phase_execution_evidence_bytes(
    *,
    study_id: str,
    protocol_commit: str,
    config_sha256: str,
    condition: str,
    prefill_adapter: bool,
    selector_adapter: bool,
    audit_index: int | None,
    branch_order: Sequence[str] | None,
    context_class: str,
    case_index: int,
    generation_id: str,
    rendered_context_sha256: str,
    raw_generation_ref: str,
) -> bytes:
    """Bind a non-model-facing causal phase condition to immutable evidence."""

    expected = P2_PHASE_CONDITIONS.get(condition)
    if expected is None:
        raise ValueError("unknown P2 phase condition")
    if expected != (prefill_adapter, selector_adapter):
        raise ValueError("P2 phase condition flags do not match frozen condition")
    if audit_index is not None and condition != "C10":
        raise ValueError("P2 branch-order audits are C10-only")
    value = {
        "domain": P2_PHASE_EXECUTION_DOMAIN,
        "study_id": study_id,
        "protocol_commit": protocol_commit,
        "config_sha256": config_sha256,
        "condition": condition,
        "prefill_adapter": prefill_adapter,
        "selector_adapter": selector_adapter,
        "audit_index": audit_index,
        "branch_order": list(branch_order) if branch_order is not None else None,
        "context_class": context_class,
        "case_index": case_index,
        "generation_id": generation_id,
        "rendered_context_sha256": rendered_context_sha256,
        "raw_generation_ref": raw_generation_ref,
        "phase_boundary": "WORLD_CONTEXT_ONCE_THEN_I3_SUFFIX_AND_CONTINUATION",
    }
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def phase_execution_identity(**kwargs: Any) -> str:
    """SHA-256 identity of :func:`phase_execution_evidence_bytes`."""

    return hashlib.sha256(phase_execution_evidence_bytes(**kwargs)).hexdigest()


def require_clean_git_status(status_porcelain: str) -> None:
    """Fail closed if tracked or untracked worktree state is present."""

    if not isinstance(status_porcelain, str):
        raise TypeError("git status output must be text")
    if status_porcelain.strip():
        raise RuntimeError("P2 execution requires a clean git worktree")


__all__ = [
    "P2_BRANCH_AUDIT_ATTEMPTS",
    "P2_PHASE_EXECUTION_EVIDENCE_CONTRACT",
    "P2_PHASE_EXECUTION_DOMAIN",
    "P2_PHASE_CONDITIONS",
    "evaluate_p2_i3_branch_order_audit",
    "canonical_allowed_tokens",
    "stable_allowed_argmax",
    "phase_execution_evidence_bytes",
    "phase_execution_identity",
    "require_clean_git_status",
]
