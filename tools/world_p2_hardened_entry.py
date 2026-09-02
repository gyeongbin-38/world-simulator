#!/usr/bin/env python3
"""Canonical hardened entrypoint for frozen WORLD P2.

This wrapper preserves the preregistered P2 runner and scientific contract,
while installing protocol-neutral pre-inference hardening discovered by the
final independent audit.  It never changes model-facing text, thresholds,
cohort membership, action semantics, or generation policy.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

import alifelm.model.phase_generation as phase_generation  # noqa: E402
from alifelm.model.p2_hardening import (  # noqa: E402
    P2_PHASE_EXECUTION_EVIDENCE_CONTRACT,
    evaluate_p2_i3_branch_order_audit,
    phase_execution_evidence_bytes,
    require_clean_git_status,
    stable_allowed_argmax,
)

BASE_RUNNER_PATH = REPOSITORY_ROOT / "tools" / "world_p2_phase_decoupled_behavioral_admission.py"
HARDENING_VERSION = "1.0.0"


def _load_base_runner():
    spec = importlib.util.spec_from_file_location("world_p2_frozen_base_runner", BASE_RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen P2 base runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git_status_porcelain() -> str:
    completed = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


class AuditedPhaseSwitchedGenerationRuntime(phase_generation.PhaseSwitchedGenerationRuntime):
    """Fail closed unless observed forward-call topology matches frozen P2."""

    def generate(self, request):
        original_forward = phase_generation._forward
        counts = {"without_past": 0, "with_past": 0, "total": 0}

        def counted_forward(model, *, input_ids, attention_mask, past_key_values=None):
            counts["total"] += 1
            if past_key_values is None:
                counts["without_past"] += 1
            else:
                counts["with_past"] += 1
            return original_forward(
                model,
                input_ids=input_ids,
                attention_mask=attention_mask,
                past_key_values=past_key_values,
            )

        phase_generation._forward = counted_forward
        try:
            result = super().generate(request)
        finally:
            phase_generation._forward = original_forward

        trace = self.last_trace
        if trace is None:
            raise RuntimeError("P2 audited runtime did not emit a phase trace")
        expected_total = 2 + trace.selector_continuation_forward_count
        if counts["without_past"] != 1:
            raise RuntimeError("P2 observed WORLD-context prefill count is not exactly one")
        if counts["with_past"] != 1 + trace.selector_continuation_forward_count:
            raise RuntimeError("P2 observed cached Phase-B forward count drift")
        if counts["total"] != expected_total:
            raise RuntimeError("P2 observed total forward count drift")
        if trace.world_prefill_forward_count != counts["without_past"]:
            raise RuntimeError("P2 phase trace prefill count is not runtime-observed")
        if trace.selector_prefix_forward_count != 1:
            raise RuntimeError("P2 selector-prefix trace count drift")
        if trace.world_context_recomputed_after_switch:
            raise RuntimeError("P2 trace reports forbidden WORLD-context recomputation")
        self.last_observed_forward_counts = dict(counts)
        return result


def _install_phase_evidence_wrapper(base: Any) -> None:
    original = base._run_condition

    def hardened_run_condition(**kwargs):
        result = original(**kwargs)
        condition = kwargs["condition"]
        prefill_adapter = bool(kwargs["prefill_adapter"])
        selector_adapter = bool(kwargs["selector_adapter"])
        audit_index = kwargs.get("audit_index")
        branch_order = kwargs.get("branch_order")
        store = kwargs["store"]

        for row in result["records"]:
            phase_bytes = phase_execution_evidence_bytes(
                study_id=base.P2_STUDY_ID,
                protocol_commit=base.PROTOCOL_COMMIT,
                config_sha256=base.CONFIG_SHA256,
                condition=condition,
                prefill_adapter=prefill_adapter,
                selector_adapter=selector_adapter,
                audit_index=audit_index,
                branch_order=branch_order,
                context_class=row["context_class"],
                case_index=row["case_index"],
                generation_id=row["generation_id"],
                rendered_context_sha256=row["rendered_context_sha256"],
                raw_generation_ref=row["raw_generation_ref"],
            )
            phase_ref = store.put_bytes(
                phase_bytes,
                media_type="application/json",
                contract_id=P2_PHASE_EXECUTION_EVIDENCE_CONTRACT,
            )
            row["phase_execution_id"] = phase_ref.digest
            row["phase_execution_ref"] = phase_ref.digest
            row["phase_execution_condition"] = condition
            row["phase_execution_prefill_adapter"] = prefill_adapter
            row["phase_execution_selector_adapter"] = selector_adapter
            row["phase_execution_audit_index"] = audit_index
            row["constrained_greedy_tie_policy"] = "LOWEST_ALLOWED_TOKEN_ID"
            row["runtime_forward_topology_asserted"] = True

        first = result["records"][0]
        repeat_bytes = phase_execution_evidence_bytes(
            study_id=base.P2_STUDY_ID,
            protocol_commit=base.PROTOCOL_COMMIT,
            config_sha256=base.CONFIG_SHA256,
            condition=condition,
            prefill_adapter=prefill_adapter,
            selector_adapter=selector_adapter,
            audit_index=audit_index,
            branch_order=branch_order,
            context_class=first["context_class"],
            case_index=first["case_index"],
            generation_id=first["generation_id"],
            rendered_context_sha256=first["rendered_context_sha256"],
            raw_generation_ref=result["repeat_raw_generation_ref"],
        )
        repeat_ref = store.put_bytes(
            repeat_bytes,
            media_type="application/json",
            contract_id=P2_PHASE_EXECUTION_EVIDENCE_CONTRACT,
        )
        phase_repeat_equal = repeat_ref.digest == first["phase_execution_id"]
        result["phase_execution_repeat_equal"] = phase_repeat_equal
        result["repeat_phase_execution_ref"] = repeat_ref.digest
        result["exact_repeat"] = bool(result["exact_repeat"] and phase_repeat_equal)
        return result

    base._run_condition = hardened_run_condition


def main() -> int:
    require_clean_git_status(_git_status_porcelain())
    base = _load_base_runner()

    # Protocol-neutral hardening only: same frozen thresholds and model-facing
    # behavior, but P2 cohort cardinality, deterministic tie ordering, observed
    # forward topology, and immutable phase provenance are fail-closed.
    base.evaluate_i3_branch_order_audit = evaluate_p2_i3_branch_order_audit
    phase_generation._allowed_argmax = stable_allowed_argmax
    base.PhaseSwitchedGenerationRuntime = AuditedPhaseSwitchedGenerationRuntime
    _install_phase_evidence_wrapper(base)
    return int(base.main())


if __name__ == "__main__":
    raise SystemExit(main())
