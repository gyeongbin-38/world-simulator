#!/usr/bin/env python3
"""Validate or execute the preregistered EXP-000 C10 score-selector A40 smoke.

Validate-only is dependency-light: it verifies source/deployment identities and
recompiles the frozen R3 fixture without importing torch or loading the model.
Execute mode performs exactly one frozen fixture score-selection/payload path.
It never commits simulation state.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))
sys.path.insert(0, str(REPOSITORY_ROOT))

from alifelm.context import CognitionGateway  # noqa: E402
from alifelm.domain import Duration, IntentBatch  # noqa: E402
from alifelm.kernel import LawValidator, SimulationRun  # noqa: E402
from alifelm.model.peft_runtime import PeftTransformersLoader  # noqa: E402
from alifelm.model.r3_fixtures import R3ContextClass, compile_r3_fixture  # noqa: E402
from alifelm.model.score_selected_c10 import build_c10_score_selected_runtime  # noqa: E402
from alifelm.model.score_selector_smoke import (  # noqa: E402
    D1_DETAILS_SHA256,
    SMOKE_AGENT_ID,
    SMOKE_CASE_INDEX,
    SMOKE_CONTEXT_CLASS,
    SMOKE_OPPORTUNITY_ID,
    SMOKE_RUN_ID,
    SMOKE_SEED_DIGEST,
    SMOKE_SELECTED_ACTION,
    SMOKE_TICK,
    SMOKE_UNIFORM_DENOMINATOR,
    SMOKE_UNIFORM_NUMERATOR,
    ScoreSelectorSmokeError,
    load_frozen_d1_row,
    verify_compiled_smoke_fixture,
)  # noqa: E402
from alifelm.model.world_v0_smoke import (  # noqa: E402
    DeploymentPaths,
    SmokePreflightError,
    build_context_policy,
    canonical_bytes,
    canonical_digest,
    ensure_execute_environment,
    verify_static_deployment,
)  # noqa: E402
from alifelm.persistence import FileSystemArtifactStore  # noqa: E402
from tools.world_p2_phase_decoupled_behavioral_admission import (  # noqa: E402
    GENERATION_SEED,
    GENERATION_SEED_ID,
    PIP_FREEZE_SHA256,
    RUNTIME_PACKAGE_COUNT,
    _policy,
    _profile,
    _runtime_freeze_sha256,
)  # noqa: E402


SMOKE_ID = "WORLD_EXP000_SCORE_SELECTOR_A40_SMOKE_V1"
SMOKE_SCHEMA_VERSION = "1.0.0"
PREREG_COMMIT = "60c35d785ff9e15f05496ad9a12c7fa8f3885239"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--base-model-dir", required=True, type=Path)
    parser.add_argument("--adapter-path", required=True, type=Path)
    parser.add_argument("--d1-details", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--expected-git-commit", required=True)
    return parser


def _git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _git_clean() -> bool:
    return not subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _compile_fixture(*, store, profile, policy):
    return compile_r3_fixture(
        R3ContextClass.QUIET,
        SMOKE_CASE_INDEX,
        policy=build_context_policy(),
        model_profile_id=profile.profile_id,
        generation_policy_id=policy.policy_id,
        generation_seed_id=GENERATION_SEED_ID,
        artifact_store=store,
    )


def _static_preflight(args) -> tuple[dict[str, Any], dict[str, Any]]:
    head = _git_head()
    if head != args.expected_git_commit:
        raise SmokePreflightError("score-selector smoke repository commit mismatch")
    if not _git_clean():
        raise SmokePreflightError("score-selector smoke requires a clean worktree")

    source_row = load_frozen_d1_row(args.d1_details)
    freeze_sha, package_count = _runtime_freeze_sha256()
    if freeze_sha != PIP_FREEZE_SHA256 or package_count != RUNTIME_PACKAGE_COUNT:
        raise SmokePreflightError("score-selector smoke canonical runtime freeze drift")

    paths = DeploymentPaths(
        base_model_dir=args.base_model_dir,
        adapter_path=args.adapter_path,
        output_root=args.output_root / "_static_identity_only",
    )
    deployment = verify_static_deployment(
        paths,
        expected_git_commit=args.expected_git_commit,
        repository_root=REPOSITORY_ROOT,
    )
    profile = _profile(args.base_model_dir)
    policy = _policy()
    with tempfile.TemporaryDirectory(prefix="exp000-score-smoke-") as tmp:
        store = FileSystemArtifactStore(Path(tmp) / "cas")
        compiled = _compile_fixture(store=store, profile=profile, policy=policy)
        source_decision = verify_compiled_smoke_fixture(compiled, source_row)

    return {
        "status": "STATIC_PREFLIGHT_OK",
        "study_id": SMOKE_ID,
        "schema_version": SMOKE_SCHEMA_VERSION,
        "git_commit": head,
        "prereg_commit": PREREG_COMMIT,
        "worktree_clean": True,
        "runtime_pip_freeze_sha256": freeze_sha,
        "runtime_package_count": package_count,
        "d1_details_sha256": D1_DETAILS_SHA256,
        "deployment": deployment,
        "fixture": {
            "context_class": SMOKE_CONTEXT_CLASS,
            "case_index": SMOKE_CASE_INDEX,
            "run_id": SMOKE_RUN_ID,
            "tick": SMOKE_TICK,
            "agent_id": SMOKE_AGENT_ID,
            "opportunity_id": SMOKE_OPPORTUNITY_ID,
        },
        "source_selector": {
            "selected_action": source_decision.selected_action,
            "seed_digest": source_decision.seed_digest,
            "uniform_numerator": source_decision.uniform_numerator,
            "uniform_denominator": source_decision.uniform_denominator,
            "probabilities": dict(source_decision.probabilities),
            "scores": dict(source_decision.score_vector),
        },
        "model_loaded": False,
        "generation": False,
        "simulation_state_commit": False,
        "weight_update": False,
    }, source_row


def _candidate_dict(candidate) -> dict[str, Any] | None:
    if candidate is None:
        return None
    return {
        "action_label": candidate.action_label,
        "payload": dict(candidate.payload),
    }


def _intent_dict(intent) -> dict[str, Any] | None:
    if intent is None:
        return None
    payload = intent.payload
    values = {}
    for name in getattr(payload, "__dataclass_fields__", {}):
        value = getattr(payload, name)
        values[name] = value.value if hasattr(value, "value") else value
    return {
        "intent_id": intent.intent_id.value,
        "actor_id": intent.actor_id.value,
        "tick": int(intent.tick),
        "kind": intent.kind.value,
        "payload": values,
    }


def _trace_dict(trace) -> dict[str, Any]:
    return {
        "prefill_adapter": trace.prefill_adapter,
        "selector_adapter": trace.selector_adapter,
        "phase_boundary_token_aligned": trace.phase_boundary_token_aligned,
        "world_prefill_forward_count": trace.world_prefill_forward_count,
        "selector_prefix_forward_count": trace.selector_prefix_forward_count,
        "selector_continuation_forward_count": trace.selector_continuation_forward_count,
        "world_context_recomputed_after_switch": trace.world_context_recomputed_after_switch,
        "generated_token_ids": list(trace.generated_token_ids),
        "finish_reason": trace.finish_reason,
    }


def _execute(args, static: dict[str, Any], source_row: dict[str, Any]) -> dict[str, Any]:
    if args.output_root.exists():
        raise SmokePreflightError("score-selector smoke output root already exists; runs are immutable")
    args.output_root.mkdir(parents=True, exist_ok=False)

    environment = ensure_execute_environment()
    profile = _profile(args.base_model_dir)
    policy = _policy()
    store = FileSystemArtifactStore(args.output_root / "cas")
    compiled = _compile_fixture(store=store, profile=profile, policy=policy)
    source_decision = verify_compiled_smoke_fixture(compiled, source_row)

    loader = PeftTransformersLoader(
        base_model_dir=args.base_model_dir,
        adapter_path=args.adapter_path,
    )
    model_runtime = loader(profile)
    score_runtime = build_c10_score_selected_runtime(
        model_runtime,
        profile=profile,
        generation_policy=policy,
        artifact_store=store,
        generation_seed=GENERATION_SEED,
    )

    snapshot_hash_before = compiled.opportunity.snapshot.state_hash()
    attempt = score_runtime.infer(compiled)
    opportunity_id = compiled.opportunity.opportunity_id
    decision = score_runtime.decision_for(opportunity_id)
    probe = score_runtime.score_provider.probe_for(opportunity_id)
    live_scores = probe.mean_scores()

    if live_scores != source_row["mean_scores"]:
        raise SmokePreflightError("live C10 mean branch scores differ from frozen P2-D1 row")
    if (
        decision.selected_action != SMOKE_SELECTED_ACTION
        or decision.seed_digest != SMOKE_SEED_DIGEST
        or decision.uniform_numerator != SMOKE_UNIFORM_NUMERATOR
        or decision.uniform_denominator != SMOKE_UNIFORM_DENOMINATOR
        or decision != source_decision
    ):
        raise SmokePreflightError("live selector decision differs from frozen source decision")
    if attempt.candidate is None:
        raise SmokePreflightError(
            "forced SEND payload did not produce a candidate: "
            + str(getattr(attempt.rejection, "error_message", attempt.parse_status))
        )

    gateway = CognitionGateway()
    try:
        intent = gateway.bind(attempt.candidate, compiled.opportunity)
    except (TypeError, ValueError) as error:
        raise SmokePreflightError("forced SEND payload could not bind through CognitionGateway") from error
    if intent.kind.value != SMOKE_SELECTED_ACTION:
        raise SmokePreflightError("Gateway-bound intent differs from frozen selected SEND")

    finalized = attempt.finalize(intent, None)
    if finalized.evidence_ref is None:
        raise SmokePreflightError("final cognition evidence reference is missing")
    final_evidence_bytes = store.resolve(finalized.evidence_ref)
    if not final_evidence_bytes:
        raise SmokePreflightError("final cognition evidence artifact is empty")

    trace = score_runtime.payload_provider.trace_for(opportunity_id)
    snapshot_hash_after = compiled.opportunity.snapshot.state_hash()
    if snapshot_hash_after != snapshot_hash_before:
        raise SmokePreflightError("score-selector smoke mutated its bound Snapshot")

    snapshot = compiled.opportunity.snapshot
    diagnostic_run = SimulationRun(
        run_id=snapshot.run_id,
        lifespan_ticks=Duration(100),
        maturity_delay_ticks=Duration(0),
        refractory_interval_ticks=Duration(0),
        _snapshot=snapshot,
    )
    validated = LawValidator().validate(
        IntentBatch(tick=snapshot.tick, intents=(intent,)),
        snapshot,
        diagnostic_run,
    )

    result = {
        "status": "INFRASTRUCTURE_PASS",
        "study_id": SMOKE_ID,
        "schema_version": SMOKE_SCHEMA_VERSION,
        "git_commit": _git_head(),
        "prereg_commit": PREREG_COMMIT,
        "environment": environment,
        "static_preflight": static,
        "source": {
            "d1_details_sha256": D1_DETAILS_SHA256,
            "context_class": source_row["context_class"],
            "case_index": source_row["case_index"],
            "mean_scores": source_row["mean_scores"],
        },
        "live_score_probe": {
            "mean_scores": live_scores,
            "exact_source_match": True,
            "prefill_adapter": probe.prefill_adapter,
            "selector_adapter": probe.selector_adapter,
            "phase_boundary_token_aligned": probe.phase_boundary_token_aligned,
            "world_prefill_forward_count": probe.world_prefill_forward_count,
            "selector_prefix_forward_count": probe.selector_prefix_forward_count,
            "world_context_recomputed_after_switch": probe.world_context_recomputed_after_switch,
        },
        "selector": {
            "selected_action": decision.selected_action,
            "score_vector": dict(decision.score_vector),
            "probabilities": dict(decision.probabilities),
            "seed_material": decision.seed_material,
            "seed_digest": decision.seed_digest,
            "uniform_numerator": decision.uniform_numerator,
            "uniform_denominator": decision.uniform_denominator,
        },
        "payload": {
            "parse_status": getattr(attempt.parse_status, "value", attempt.parse_status),
            "candidate": _candidate_dict(attempt.candidate),
            "generation_id": attempt.generation_id,
            "phase_trace": _trace_dict(trace),
        },
        "gateway": {
            "intent": _intent_dict(intent),
            "law_validator_admitted_descriptive": len(validated) == 1,
        },
        "evidence": {
            "final_evidence_ref": {
                "artifact_id": finalized.evidence_ref.artifact_id.value,
                "digest": finalized.evidence_ref.digest,
            },
            "final_evidence_bytes": len(final_evidence_bytes),
        },
        "integrity": {
            "snapshot_hash_before": snapshot_hash_before,
            "snapshot_hash_after": snapshot_hash_after,
            "snapshot_unchanged": snapshot_hash_before == snapshot_hash_after,
            "simulation_state_commits": 0,
            "weight_updates": 0,
            "retries": 0,
            "fallbacks": 0,
            "repairs": 0,
            "legality_mask": False,
        },
    }
    result["result_digest"] = canonical_digest(result)
    manifest_path = args.output_root / "manifest.json"
    manifest_path.write_bytes(canonical_bytes(result) + b"\n")
    return result


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        static, source_row = _static_preflight(args)
        if args.validate_only:
            print(json.dumps(static, ensure_ascii=False, sort_keys=True))
            return 0
        result = _execute(args, static, source_row)
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "selected_action": result["selector"]["selected_action"],
                    "candidate": result["payload"]["candidate"],
                    "law_validator_admitted_descriptive": result["gateway"]["law_validator_admitted_descriptive"],
                    "result_digest": result["result_digest"],
                    "manifest": str(args.output_root / "manifest.json"),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except (
        ScoreSelectorSmokeError,
        SmokePreflightError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        subprocess.CalledProcessError,
    ) as error:
        print(
            json.dumps(
                {"status": "BLOCKED", "error_type": type(error).__name__, "error": str(error)},
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
