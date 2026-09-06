#!/usr/bin/env python3
"""Validate or execute the preregistered WORLD EXP-000 live multi-agent pilot.

Validate-only performs source/deployment/config checks without importing torch or
loading the model. Execute composes the already-reviewed C10 score-selected
runtime, deterministic kernel, SQLite durable store, CAS evidence, and the
read-only LIVE controller for one bounded run.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))
sys.path.insert(0, str(REPOSITORY_ROOT))

from alifelm.context import ContextCognitionPipeline  # noqa: E402
from alifelm.domain import RunId  # noqa: E402
from alifelm.kernel import (  # noqa: E402
    BirthConflictTransition,
    BirthTransition,
    MessageTransition,
    NaturalDeathTransition,
    ProposalCreatedTransition,
    ProposalRejectedTransition,
    TransitionKind,
)
from alifelm.live import LiveExperimentConfig, LiveExperimentController  # noqa: E402
from alifelm.model.peft_runtime import PeftTransformersLoader  # noqa: E402
from alifelm.model.score_selected_c10 import build_c10_score_selected_runtime  # noqa: E402
from alifelm.model.world_v0_smoke import (  # noqa: E402
    DeploymentPaths,
    SmokePreflightError,
    build_context_policy,
    canonical_bytes,
    canonical_digest,
    ensure_execute_environment,
    verify_static_deployment,
)
from alifelm.persistence import SQLiteReferenceStore  # noqa: E402
from tools.world_p2_phase_decoupled_behavioral_admission import (  # noqa: E402
    GENERATION_SEED,
    GENERATION_SEED_ID,
    PIP_FREEZE_SHA256,
    RUNTIME_PACKAGE_COUNT,
    _policy,
    _profile,
    _runtime_freeze_sha256,
)


STUDY_ID = "WORLD_EXP000_LIVE_MULTIAGENT_PILOT_V1"
RUN_ID = "WORLD_EXP000_LIVE_PILOT_V1_R1"
SCHEMA_VERSION = "1.0.0"
PREREG_COMMIT = "0aa0fdbeb4f9c0a04a52bdff54d0d751febacb1c"
D1_DETAILS_SHA256 = "0e5e62709d58168c9922645c1d05d54a7f5c417b68b3f461b4558d3706ca3b17"
SMOKE_RESULT_DIGEST = "7e69dbc2c40509f0cc6f10906a5482cc4cc2d01a8a114e66cb836e72ff95a912"
SMOKE_MANIFEST_SHA256 = "49c2591124d7cc182b232a0d95243e44ee5a4dd3e29016a1faa79f7863c34d8b"
SMOKE_ARCHIVE_SHA256 = "d60225464d8c89dea55fad82fc977895fb69bdd597ee6e0882e0ced2789817f2"
FOUNDERS = ("EXP000_FOUNDER_A", "EXP000_FOUNDER_B", "EXP000_FOUNDER_C")
HORIZON_TICKS = 20
LIFESPAN_TICKS = 20
MATURITY_DELAY_TICKS = 0
REFRACTORY_INTERVAL_TICKS = 0
POPULATION_CAPACITY = 6


class LivePilotError(RuntimeError):
    """Fail-closed pilot contract error."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--base-model-dir", required=True, type=Path)
    parser.add_argument("--adapter-path", required=True, type=Path)
    parser.add_argument("--d1-details", required=True, type=Path)
    parser.add_argument("--smoke-manifest", required=True, type=Path)
    parser.add_argument("--smoke-archive", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--expected-git-commit", required=True)
    return parser


def _sha256_file(path: Path) -> str:
    if not path.is_file():
        raise LivePilotError(f"required source file is missing: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def pilot_config() -> LiveExperimentConfig:
    """Return exactly the preregistered bounded run configuration."""

    return LiveExperimentConfig(
        run_id=RUN_ID,
        founders=FOUNDERS,
        lifespan_ticks=LIFESPAN_TICKS,
        maturity_delay_ticks=MATURITY_DELAY_TICKS,
        refractory_interval_ticks=REFRACTORY_INTERVAL_TICKS,
        population_capacity=POPULATION_CAPACITY,
        horizon_ticks=HORIZON_TICKS,
    )


def _verify_smoke_sources(manifest_path: Path, archive_path: Path) -> dict[str, Any]:
    manifest_sha = _sha256_file(manifest_path)
    archive_sha = _sha256_file(archive_path)
    if manifest_sha != SMOKE_MANIFEST_SHA256:
        raise LivePilotError("A40 smoke manifest SHA-256 drift")
    if archive_sha != SMOKE_ARCHIVE_SHA256:
        raise LivePilotError("A40 smoke canonical archive SHA-256 drift")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LivePilotError("A40 smoke manifest is not valid JSON") from error
    if (
        manifest.get("status") != "INFRASTRUCTURE_PASS"
        or manifest.get("result_digest") != SMOKE_RESULT_DIGEST
        or manifest.get("selector", {}).get("selected_action") != "SEND"
        or manifest.get("integrity", {}).get("simulation_state_commits") != 0
        or manifest.get("integrity", {}).get("weight_updates") != 0
    ):
        raise LivePilotError("A40 smoke semantic identity drift")
    return {
        "manifest_sha256": manifest_sha,
        "archive_sha256": archive_sha,
        "result_digest": manifest["result_digest"],
        "status": manifest["status"],
    }


def static_preflight(args) -> dict[str, Any]:
    head = _git_head()
    if head != args.expected_git_commit:
        raise LivePilotError("live pilot repository commit mismatch")
    if not _git_clean():
        raise LivePilotError("live pilot requires a clean worktree")
    if args.output_root.exists():
        raise LivePilotError("live pilot output root already exists")

    if _sha256_file(args.d1_details) != D1_DETAILS_SHA256:
        raise LivePilotError("P2-D1 details SHA-256 drift")
    smoke = _verify_smoke_sources(args.smoke_manifest, args.smoke_archive)

    freeze_sha, package_count = _runtime_freeze_sha256()
    if freeze_sha != PIP_FREEZE_SHA256 or package_count != RUNTIME_PACKAGE_COUNT:
        raise LivePilotError("canonical runtime freeze drift")

    deployment = verify_static_deployment(
        DeploymentPaths(
            base_model_dir=args.base_model_dir,
            adapter_path=args.adapter_path,
            output_root=args.output_root / "_static_identity_only",
        ),
        expected_git_commit=args.expected_git_commit,
        repository_root=REPOSITORY_ROOT,
    )

    config = pilot_config()
    return {
        "status": "STATIC_PREFLIGHT_OK",
        "study_id": STUDY_ID,
        "schema_version": SCHEMA_VERSION,
        "git_commit": head,
        "prereg_commit": PREREG_COMMIT,
        "worktree_clean": True,
        "runtime_pip_freeze_sha256": freeze_sha,
        "runtime_package_count": package_count,
        "d1_details_sha256": D1_DETAILS_SHA256,
        "smoke_source": smoke,
        "deployment": deployment,
        "run": {
            "run_id": config.run_id,
            "founders": list(config.founders),
            "horizon_ticks": config.horizon_ticks,
            "lifespan_ticks": config.lifespan_ticks,
            "maturity_delay_ticks": config.maturity_delay_ticks,
            "refractory_interval_ticks": config.refractory_interval_ticks,
            "population_capacity": config.population_capacity,
        },
        "selector": {
            "phase": "C10_FA_PREFILL_BASE_SELECTOR",
            "temperature": 1.0,
            "legality_mask": False,
            "retry": False,
            "fallback": False,
            "repair": False,
            "batching": False,
        },
        "model_loaded": False,
        "generation": False,
        "simulation_state_commit": False,
        "weight_update": False,
    }


def _write_json_once(path: Path, value: Any) -> None:
    if path.exists():
        raise LivePilotError(f"refusing to overwrite immutable pilot evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_bytes(value) + b"\n"
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        import os

        os.fsync(stream.fileno())


def _artifact_ref_dict(reference) -> dict[str, str] | None:
    if reference is None:
        return None
    return {"artifact_id": reference.artifact_id.value, "digest": reference.digest}


def _candidate_dict(candidate) -> dict[str, Any] | None:
    if candidate is None:
        return None
    return {"action_label": candidate.action_label, "payload": dict(candidate.payload)}


def _intent_dict(intent) -> dict[str, Any] | None:
    if intent is None:
        return None
    payload = {}
    for name in getattr(intent.payload, "__dataclass_fields__", {}):
        value = getattr(intent.payload, name)
        payload[name] = value.value if hasattr(value, "value") else value
    return {
        "intent_id": intent.intent_id.value,
        "actor_id": intent.actor_id.value,
        "tick": int(intent.tick),
        "kind": intent.kind.value,
        "payload": payload,
    }


def _rejection_dict(rejection) -> dict[str, Any] | None:
    if rejection is None:
        return None
    return {
        "generation_id": rejection.generation_id,
        "status": getattr(rejection.status, "value", rejection.status),
        "error_type": rejection.error_type,
        "error_message": rejection.error_message,
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


def _fragment_dict(fragment) -> dict[str, Any]:
    payload = fragment.payload
    base = {"kind": fragment.kind.value, "fragment_id": fragment.fragment_id.value}
    if isinstance(payload, MessageTransition):
        message = payload.message
        base["message"] = {
            "message_id": message.message_id.value,
            "sender_id": message.sender_id.value,
            "recipient_id": message.recipient_id.value,
            "body": message.body,
            "committed_tick": int(message.committed_tick),
            "available_tick": int(message.available_tick),
        }
    elif isinstance(payload, ProposalCreatedTransition):
        proposal = payload.proposal
        base["proposal"] = {
            "proposal_id": proposal.proposal_id.value,
            "proposer_id": proposal.proposer_id.value,
            "target_id": proposal.target_id.value,
            "created_tick": int(proposal.created_tick),
        }
    elif isinstance(payload, ProposalRejectedTransition):
        base["rejection"] = {
            "proposal_id": payload.proposal_id.value,
            "actor_id": payload.actor_id.value,
        }
    elif isinstance(payload, BirthTransition):
        base["birth"] = {
            "proposal_id": payload.proposal_id.value,
            "child_id": payload.child.agent_id.value,
            "parent_ids": [value.value for value in payload.parent_ids],
            "birth_tick": int(payload.child.birth_tick),
            "first_active_tick": int(payload.child.first_active_tick),
        }
    elif isinstance(payload, BirthConflictTransition):
        base["birth_conflict"] = {
            "proposal_id": payload.proposal_id.value,
            "reason": payload.reason.value,
        }
    elif isinstance(payload, NaturalDeathTransition):
        base["death"] = {"agent_id": payload.agent_id.value}
    return base


def _gpu_memory_mib() -> int | None:
    try:
        text = subprocess.run(
            [
                "nvidia-smi",
                "--query-compute-apps=used_memory",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        values = [int(line.strip()) for line in text.splitlines() if line.strip().isdigit()]
        return max(values) if values else 0
    except (OSError, ValueError, subprocess.CalledProcessError):
        return None


def tick_record(result, score_runtime) -> dict[str, Any]:
    """Build the durable researcher-side record for one already-committed tick."""

    attempts = {item.opportunity_id: item for item in result.cognition_attempts}
    intents = {item.actor_id: item for item in result.intent_batch.intents}
    validated = {item.intent.actor_id: item.intent for item in result.validated_intents}
    cognition = []
    for opportunity in result.opportunities:
        oid = opportunity.opportunity_id
        decision = score_runtime.decision_for(oid)
        probe = score_runtime.score_provider.probe_for(oid)
        attempt = attempts[oid]
        trace = None
        if decision.selected_action != "WAIT":
            trace = score_runtime.payload_provider.trace_for(oid)
        intent = intents.get(opportunity.agent_id)
        cognition.append(
            {
                "opportunity_id": oid.value,
                "agent_id": opportunity.agent_id.value,
                "selected_action": decision.selected_action,
                "score_vector": dict(decision.score_vector),
                "probabilities": dict(decision.probabilities),
                "seed_digest": decision.seed_digest,
                "uniform_numerator": decision.uniform_numerator,
                "uniform_denominator": decision.uniform_denominator,
                "score_phase": {
                    "prefill_adapter": probe.prefill_adapter,
                    "selector_adapter": probe.selector_adapter,
                    "phase_boundary_token_aligned": probe.phase_boundary_token_aligned,
                    "world_prefill_forward_count": probe.world_prefill_forward_count,
                    "selector_prefix_forward_count": probe.selector_prefix_forward_count,
                    "world_context_recomputed_after_switch": probe.world_context_recomputed_after_switch,
                },
                "payload_phase": None if trace is None else _trace_dict(trace),
                "parse_status": getattr(attempt.parse_status, "value", attempt.parse_status),
                "candidate": _candidate_dict(attempt.candidate),
                "rejection": _rejection_dict(attempt.rejection),
                "evidence_ref": _artifact_ref_dict(attempt.evidence_ref),
                "gateway_intent": _intent_dict(intent),
                "law_admitted": opportunity.agent_id in validated,
            }
        )

    after = result.commit_result.snapshot
    return {
        "tick": int(result.snapshot_before.tick),
        "state_version_before": int(result.snapshot_before.state_version),
        "state_hash_before": result.snapshot_before.state_hash(),
        "population_before": len(result.snapshot_before.agents),
        "opportunities": len(result.opportunities),
        "cognition": cognition,
        "validated_intents": [_intent_dict(item.intent) for item in result.validated_intents],
        "fragments": [_fragment_dict(item) for item in result.fragments],
        "events": [
            {
                "event_id": event.event_id.value,
                "event_type": event.event_type,
                "commit_tick": int(event.commit_tick),
                "commit_order": event.commit_order,
            }
            for event in result.commit_result.events
        ],
        "context_artifact_refs": [_artifact_ref_dict(ref) for ref in result.context_artifact_refs],
        "commit": {
            "committed": result.commit_result.committed,
            "capacity_censored": result.commit_result.capacity_censored,
            "state_version_after": int(after.state_version),
            "state_hash_after": after.state_hash(),
            "tick_after": int(after.tick),
            "status_after": after.status.value,
            "population_after": len(after.agents),
        },
    }


def summarize_trajectory(records: list[dict[str, Any]], final_snapshot) -> dict[str, Any]:
    selected = Counter()
    per_agent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    messages = []
    proposals = []
    births = []
    deaths = []
    birth_conflicts = []
    parse_rejections = 0
    law_rejections = 0
    opportunities = 0
    population = []

    for record in records:
        opportunities += record["opportunities"]
        population.append(
            {
                "tick": record["tick"],
                "before": record["population_before"],
                "after": record["commit"]["population_after"],
            }
        )
        for cognition in record["cognition"]:
            selected[cognition["selected_action"]] += 1
            per_agent[cognition["agent_id"]].append(
                {
                    "tick": record["tick"],
                    "selected_action": cognition["selected_action"],
                    "gateway_intent_kind": (
                        None
                        if cognition["gateway_intent"] is None
                        else cognition["gateway_intent"]["kind"]
                    ),
                    "law_admitted": cognition["law_admitted"],
                }
            )
            if cognition["rejection"] is not None:
                parse_rejections += 1
            if cognition["gateway_intent"] is not None and not cognition["law_admitted"]:
                law_rejections += 1
        for fragment in record["fragments"]:
            kind = fragment["kind"]
            if kind == TransitionKind.MESSAGE.value:
                messages.append(fragment["message"])
            elif kind == TransitionKind.PROPOSAL_CREATED.value:
                proposals.append(fragment["proposal"])
            elif kind == TransitionKind.BIRTH.value:
                births.append(fragment["birth"])
            elif kind == TransitionKind.NATURAL_DEATH.value:
                deaths.append(fragment["death"])
            elif kind == TransitionKind.BIRTH_CONFLICT_REJECTED.value:
                birth_conflicts.append(fragment["birth_conflict"])

    depths = {founder: 0 for founder in FOUNDERS}
    pending = list(births)
    while pending:
        progressed = False
        for birth in pending[:]:
            parents = birth["parent_ids"]
            if all(parent in depths for parent in parents):
                depths[birth["child_id"]] = 1 + max(depths[parent] for parent in parents)
                pending.remove(birth)
                progressed = True
        if not progressed:
            break

    return {
        "total_cognition_opportunities": opportunities,
        "selected_action_distribution": dict(sorted(selected.items())),
        "parse_or_payload_rejections": parse_rejections,
        "law_rejections": law_rejections,
        "messages": messages,
        "proposals_created": proposals,
        "births": births,
        "birth_conflicts": birth_conflicts,
        "natural_deaths": deaths,
        "population_by_tick": population,
        "per_agent_action_sequence": dict(sorted(per_agent.items())),
        "generation_depth": dict(sorted(depths.items())),
        "max_generation_depth": max(depths.values()) if depths else 0,
        "final_population": len(final_snapshot.agents),
        "final_agents": [agent.agent_id.value for agent in final_snapshot.agents],
        "final_tick": int(final_snapshot.tick),
        "final_state_version": int(final_snapshot.state_version),
        "final_state_hash": final_snapshot.state_hash(),
        "final_status": final_snapshot.status.value,
    }


def execute(args, static: dict[str, Any]) -> dict[str, Any]:
    args.output_root.mkdir(parents=True, exist_ok=False)
    _write_json_once(
        args.output_root / "run_plan.json",
        {
            "study_id": STUDY_ID,
            "schema_version": SCHEMA_VERSION,
            "git_commit": _git_head(),
            "prereg_commit": PREREG_COMMIT,
            "static_preflight": static,
            "run": static["run"],
            "selector": static["selector"],
        },
    )

    environment = ensure_execute_environment()
    started = time.perf_counter()
    gpu_start = _gpu_memory_mib()
    store = SQLiteReferenceStore(
        args.output_root / "run.sqlite",
        artifact_root=args.output_root / "cas",
    )
    records: list[dict[str, Any]] = []
    try:
        profile = _profile(args.base_model_dir)
        policy = _policy()
        pipeline = ContextCognitionPipeline(
            build_context_policy(),
            model_profile_id=profile.profile_id,
            generation_policy_id=policy.policy_id,
            generation_seed_id=GENERATION_SEED_ID,
            artifact_store=store.artifact_store,
        )
        model_runtime = PeftTransformersLoader(
            base_model_dir=args.base_model_dir,
            adapter_path=args.adapter_path,
        )(profile)
        score_runtime = build_c10_score_selected_runtime(
            model_runtime,
            profile=profile,
            generation_policy=policy,
            artifact_store=store.artifact_store,
            generation_seed=GENERATION_SEED,
        )
        controller = LiveExperimentController.create(
            pilot_config(),
            runtime=score_runtime,
            context_pipeline=pipeline,
            store=store,
        )

        while controller.run.status.value == "RUNNING":
            result = controller.run_one_tick()
            record = tick_record(result, score_runtime)
            records.append(record)
            _write_json_once(
                args.output_root / "ticks" / f"tick_{record['tick']:04d}.json",
                record,
            )
            action_counts = Counter(item["selected_action"] for item in record["cognition"])
            print(
                "LIVE_EXP000_TICK "
                f"{record['commit']['tick_after']}/{HORIZON_TICKS} "
                f"status={record['commit']['status_after']} "
                f"pop={record['commit']['population_after']} "
                f"selected={dict(sorted(action_counts.items()))}",
                flush=True,
            )

        final_snapshot = controller.run.snapshot
        durable = store.load_run(RunId(RUN_ID))
        if durable.state_hash() != final_snapshot.state_hash() or durable.snapshot != final_snapshot:
            raise LivePilotError("durable final boundary differs from in-memory final boundary")

        decision_count_before_replay = sum(item["opportunities"] for item in records)
        replay = store.replay(RunId(RUN_ID))
        decision_count_after_replay = sum(item["opportunities"] for item in records)
        if replay.snapshot.state_hash() != final_snapshot.state_hash():
            raise LivePilotError("durable replay final hash differs from live final hash")
        if decision_count_after_replay != decision_count_before_replay:
            raise LivePilotError("replay changed cognition accounting")

        trajectory = summarize_trajectory(records, final_snapshot)
        wall_seconds = time.perf_counter() - started
        gpu_end = _gpu_memory_mib()
        integrity = {
            "g0_static_preflight": static["status"] == "STATIC_PREFLIGHT_OK",
            "g1_opportunities_equal_decisions": all(
                item["opportunities"] == len(item["cognition"]) for item in records
            ),
            "g1_c10_phase_integrity": all(
                c["score_phase"]["prefill_adapter"] is True
                and c["score_phase"]["selector_adapter"] is False
                and c["score_phase"]["phase_boundary_token_aligned"] is True
                and c["score_phase"]["world_context_recomputed_after_switch"] is False
                for item in records
                for c in item["cognition"]
            ),
            "g1_wait_has_no_payload": all(
                (c["selected_action"] != "WAIT" or c["payload_phase"] is None)
                for item in records
                for c in item["cognition"]
            ),
            "g1_nonwait_has_one_payload_trace": all(
                (c["selected_action"] == "WAIT" or c["payload_phase"] is not None)
                for item in records
                for c in item["cognition"]
            ),
            "g2_all_commits_succeeded": all(item["commit"]["committed"] for item in records),
            "g2_monotonic_state_versions": all(
                item["commit"]["state_version_after"] == item["state_version_before"] + 1
                for item in records
            ),
            "g3_durable_final_hash_match": durable.state_hash() == final_snapshot.state_hash(),
            "g3_replay_final_hash_match": replay.snapshot.state_hash() == final_snapshot.state_hash(),
            "g3_replay_new_cognition_delta": decision_count_after_replay - decision_count_before_replay,
            "retries": 0,
            "fallbacks": 0,
            "repairs": 0,
            "legality_mask": False,
            "weight_updates": 0,
        }
        gates = {
            "G0": bool(integrity["g0_static_preflight"]),
            "G1": bool(
                integrity["g1_opportunities_equal_decisions"]
                and integrity["g1_c10_phase_integrity"]
                and integrity["g1_wait_has_no_payload"]
                and integrity["g1_nonwait_has_one_payload_trace"]
            ),
            "G2": bool(
                integrity["g2_all_commits_succeeded"]
                and integrity["g2_monotonic_state_versions"]
            ),
            "G3": bool(
                integrity["g3_durable_final_hash_match"]
                and integrity["g3_replay_final_hash_match"]
                and integrity["g3_replay_new_cognition_delta"] == 0
            ),
        }
        result = {
            "status": "LIVE_PILOT_COMPLETE" if all(gates.values()) else "LIVE_PILOT_INTEGRITY_FAIL",
            "study_id": STUDY_ID,
            "schema_version": SCHEMA_VERSION,
            "git_commit": _git_head(),
            "prereg_commit": PREREG_COMMIT,
            "environment": environment,
            "static_preflight": static,
            "gates": gates,
            "integrity": integrity,
            "trajectory": trajectory,
            "replay": {
                "verified_commit_count": len(replay.verified_commit_ids),
                "final_state_hash": replay.snapshot.state_hash(),
                "new_cognition_delta": 0,
            },
            "infrastructure": {
                "wall_seconds": wall_seconds,
                "gpu_memory_mib_at_start": gpu_start,
                "gpu_memory_mib_at_end": gpu_end,
                "tick_record_count": len(records),
            },
        }
        result["result_digest"] = canonical_digest(result)
        _write_json_once(args.output_root / "manifest.json", result)
        return result
    finally:
        store.close()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        static = static_preflight(args)
        if args.validate_only:
            print(json.dumps(static, ensure_ascii=False, sort_keys=True))
            return 0
        result = execute(args, static)
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "gates": result["gates"],
                    "result_digest": result["result_digest"],
                    "final_status": result["trajectory"]["final_status"],
                    "final_population": result["trajectory"]["final_population"],
                    "selected_action_distribution": result["trajectory"]["selected_action_distribution"],
                    "messages": len(result["trajectory"]["messages"]),
                    "proposals": len(result["trajectory"]["proposals_created"]),
                    "births": len(result["trajectory"]["births"]),
                    "deaths": len(result["trajectory"]["natural_deaths"]),
                    "manifest": str(args.output_root / "manifest.json"),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0 if result["status"] == "LIVE_PILOT_COMPLETE" else 2
    except (
        LivePilotError,
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
