#!/usr/bin/env python3
"""Execute the preregistered WORLD P0 end-to-end multi-agent pilot.

P0 is an infrastructure and causal-integrity pilot. A WAIT-only trajectory may
pass. The runner uses the exact accepted FA-v1 deployment, I3 conditional typed
codec, independent durable stores for FWD/REV replicas, one model call per
opportunity, and no retry/fallback/repair path.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import fields, is_dataclass
from enum import Enum
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import sys
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from alifelm.context import ContextCognitionPipeline
from alifelm.context.render import render_model_input_bytes
from alifelm.context.serialization import model_input_to_dict, serialize_context_pack
from alifelm.context.visibility import project_visibility
from alifelm.domain import (
    AgentId,
    ArtifactId,
    ArtifactRef,
    Duration,
    RunId,
    Tick,
    is_active,
)
from alifelm.kernel import DeterministicKernel, SimulationRun
from alifelm.model import (
    GenerationPolicy,
    I3_CONDITIONAL_TYPED_CODEC,
    LiveCandidateRuntime,
    ModelProfile,
    PeftTransformersLoader,
    WORLD_V0_FA_V1_IDENTITY,
    build_transformers_constraint,
    typed_action_codec_json_schema,
    validate_live_runtime_identity,
)
from alifelm.model.world_v0_smoke import (
    DeploymentPaths,
    build_context_policy,
    ensure_execute_environment,
    verify_static_deployment,
)
from alifelm.persistence import SQLiteReferenceStore
from alifelm.persistence.serialization import event_to_dict, fragment_to_dict


PROTOCOL_ID = "WORLD_P0_END_TO_END_PILOT_V1"
RUN_ID = "WORLD_P0_END_TO_END_PILOT_V1"
RUNNER_VERSION = "1.0.0"
EXPECTED_CONFIG_SHA256 = (
    "2e5561690462bcc14ebde2d8a82d4f670c5cc1a438447c41fd662ff191b05ed2"
)
EXPECTED_RUNTIME_FREEZE_SHA256 = (
    "a98b9c11baf90a5e7717b1f108029838e9c917d46d1f499bf93e9adffad087bf"
)
MODEL_INPUT_KEYS = {
    "stable_prefix",
    "current_self",
    "peer_directory",
    "newly_delivered",
    "visible_protocol_state",
    "prior_history",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_head() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise RuntimeError("cannot resolve repository commit") from error


def _write_json(path: Path, value: Any) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite immutable result: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _load_config(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    digest = _sha256(raw)
    if digest != EXPECTED_CONFIG_SHA256:
        raise RuntimeError(
            f"P0 config SHA mismatch: expected {EXPECTED_CONFIG_SHA256}, got {digest}"
        )
    value = json.loads(raw)
    if value.get("protocol_id") != PROTOCOL_ID:
        raise RuntimeError("P0 protocol identity mismatch")
    return value, digest


def _validate_config(config: dict[str, Any]) -> None:
    interface = config["interface"]
    treatment = I3_CONDITIONAL_TYPED_CODEC
    expected_interface = {
        "treatment_id": treatment.treatment_id,
        "version": treatment.version,
        "completion_suffix": treatment.completion_suffix,
        "constraint_policy_id": treatment.constraint_policy_id,
    }
    if interface != expected_interface:
        raise RuntimeError("P0 I3 interface configuration mismatch")

    generation = config["generation"]
    expected_generation = {
        "max_new_tokens": 128,
        "do_sample": False,
        "temperature": None,
        "top_p": None,
        "top_k": None,
        "repetition_penalty": 1.0,
        "seed": 35020260831,
    }
    for key, expected in expected_generation.items():
        if generation[key] != expected:
            raise RuntimeError(f"P0 generation configuration mismatch: {key}")

    world = config["world"]
    if (
        world["founders"] != ["A", "B", "C"]
        or world["initial_tick"] != 0
        or world["initial_state_version"] != 0
        or world["committed_ticks"] != 12
        or world["population_capacity"] is not None
    ):
        raise RuntimeError("P0 world configuration mismatch")

    replica = config["replica_execution"]
    if replica != {
        "completion_order_domain": "ACTIVE_AGENTS_AT_BOUND_TICK",
        "P0-FWD": "LEXICAL_ASCENDING_AGENT_ID",
        "P0-REV": "LEXICAL_DESCENDING_AGENT_ID",
        "completion_order_is_model_visible": False,
    }:
        raise RuntimeError("P0 completion-order rule mismatch")

    if not all(config["forbidden"].values()):
        raise RuntimeError("a P0 forbidden workaround was not frozen as forbidden")


def _runtime_freeze_sha256() -> tuple[str, int]:
    completed = subprocess.run(
        [sys.executable, "-m", "pip", "freeze", "--all"],
        check=True,
        capture_output=True,
        text=True,
    )
    lines = sorted(line for line in completed.stdout.splitlines() if line)
    return _sha256(("\n".join(lines) + "\n").encode("utf-8")), len(lines)


def _environment(config: dict[str, Any]) -> dict[str, Any]:
    import torch

    base = ensure_execute_environment(torch_module=torch)
    freeze_sha, package_count = _runtime_freeze_sha256()
    capability = tuple(torch.cuda.get_device_capability(0))
    checks = {
        "python": platform.python_version() == "3.12.3",
        "torch": torch.__version__ == "2.7.1+cu118",
        "torch_cuda": torch.version.cuda == "11.8",
        "cudnn": torch.backends.cudnn.version() == 90100,
        "gpu": torch.cuda.get_device_name(0) == "NVIDIA A40",
        "compute_capability": capability == (8, 6),
        "package_count": package_count == 60,
        "pip_freeze_sha256": freeze_sha == EXPECTED_RUNTIME_FREEZE_SHA256,
        "config_freeze_sha256": (
            config["deployment_identity"]["runtime_pip_freeze_sha256"]
            == EXPECTED_RUNTIME_FREEZE_SHA256
        ),
    }
    if not all(checks.values()):
        raise RuntimeError(f"canonical runtime environment mismatch: {checks}")
    return {
        **base,
        "compute_capability": list(capability),
        "cudnn": torch.backends.cudnn.version(),
        "package_count": package_count,
        "pip_freeze_sha256": freeze_sha,
        "checks": checks,
    }


def _profile(config: dict[str, Any], base_model_dir: Path) -> ModelProfile:
    generation = config["generation"]
    identity = WORLD_V0_FA_V1_IDENTITY
    return ModelProfile(
        profile_id=generation["profile_id"],
        profile_version=generation["profile_version"],
        model_identifier=str(base_model_dir),
        model_revision=identity.base_model_revision,
        model_digest=identity.base_checkpoint_sha256,
        tokenizer_identifier=str(base_model_dir),
        tokenizer_revision=identity.tokenizer_revision,
        tokenizer_digest=identity.tokenizer_digest,
        model_class="AUTO_CAUSAL_LM",
        generation_policy_id=generation["policy_id"],
        device=config["deployment_identity"]["device"],
        dtype=config["deployment_identity"]["dtype"],
        adapter_ref=ArtifactRef(
            ArtifactId("F0_FA_V1_FORMAL"), identity.adapter_sha256
        ),
        trust_remote_code=False,
        add_special_tokens=True,
    )


def _generation_policy(config: dict[str, Any]) -> GenerationPolicy:
    value = config["generation"]
    return GenerationPolicy(
        policy_id=value["policy_id"],
        version=value["policy_version"],
        max_new_tokens=value["max_new_tokens"],
        do_sample=value["do_sample"],
        temperature=value["temperature"],
        top_p=value["top_p"],
        top_k=value["top_k"],
        repetition_penalty=value["repetition_penalty"],
        seed_id=value["seed_id"],
        stop_policy_id=value["stop_policy_id"],
    )


def _artifact_ref(value: dict[str, str]) -> ArtifactRef:
    return ArtifactRef(ArtifactId(value["artifact_id"]), value["digest"])


def _primitive(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {field.name: _primitive(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple):
        return [_primitive(item) for item in value]
    if isinstance(value, list):
        return [_primitive(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _primitive(item) for key, item in value.items()}
    primitive = getattr(value, "value", None)
    if isinstance(primitive, (str, int, float, bool)):
        return primitive
    return value


def _intent_projection(validated) -> dict[str, Any]:
    intent = validated.intent
    return {
        "validated_state_version": int(validated.validated_state_version),
        "intent_id": intent.intent_id.value,
        "actor_id": intent.actor_id.value,
        "tick": int(intent.tick),
        "kind": intent.kind.value,
        "payload": _primitive(intent.payload),
    }


def _completion_order(snapshot, *, reverse: bool) -> tuple[AgentId, ...]:
    active = [
        agent.agent_id
        for agent in snapshot.agents
        if is_active(agent, snapshot.tick)
    ]
    return tuple(
        sorted(active, key=lambda agent_id: agent_id.value, reverse=reverse)
    )


def _privacy_pass(pack, snapshot, rendered: bytes, context_policy) -> bool:
    evidence = pack.evidence
    if (
        evidence.bound_tick != int(snapshot.tick)
        or evidence.bound_state_version != int(snapshot.state_version)
        or evidence.bound_state_hash != snapshot.state_hash()
    ):
        return False

    model_dict = model_input_to_dict(pack.model_input)
    if set(model_dict) != MODEL_INPUT_KEYS:
        return False

    base_rendered = render_model_input_bytes(pack.model_input)
    if rendered != I3_CONDITIONAL_TYPED_CODEC.render(base_rendered):
        return False

    actor = pack.model_input.current_self.agent_id
    projection = project_visibility(snapshot, actor, context_policy)
    if pack.model_input.current_self.age != projection.age:
        return False

    actual_peers = {item.agent_id.value for item in pack.model_input.peer_directory}
    expected_peers = {item.model_value.agent_id.value for item in projection.active_peers}
    if actual_peers != expected_peers or actor.value in actual_peers:
        return False

    if pack.model_input.prior_history:
        return False

    for provenance in evidence.provenance:
        if provenance.commit_tick is not None and provenance.commit_tick >= int(snapshot.tick):
            return False

    return True


def _collect_attempts(result, store, snapshot_before, context_policy):
    packs = {
        pack.evidence.opportunity_id.value: pack
        for pack in result.context_packs
    }
    attempts = {
        attempt.opportunity_id.value: attempt
        for attempt in result.cognition_attempts
    }
    if packs.keys() != attempts.keys():
        raise RuntimeError("ContextPack and cognition-attempt sets disagree")

    details: dict[str, Any] = {}
    comparison: dict[str, Any] = {}
    all_evidence = True
    all_privacy = True

    for opportunity_id in sorted(packs):
        pack = packs[opportunity_id]
        attempt = attempts[opportunity_id]
        if attempt.evidence_ref is None:
            raise RuntimeError("final cognition evidence reference is missing")

        final_bytes = store.artifact_store.resolve(attempt.evidence_ref)
        evidence = json.loads(final_bytes)
        nested = {
            key: _artifact_ref(evidence[key])
            for key in (
                "context_pack_ref",
                "rendered_input_ref",
                "raw_text_ref",
                "raw_generation_ref",
            )
        }
        resolved = {
            key: store.artifact_store.resolve(reference)
            for key, reference in nested.items()
        }
        raw_generation = json.loads(resolved["raw_generation_ref"])
        raw_text = resolved["raw_text_ref"].decode("utf-8")
        rendered = resolved["rendered_input_ref"]

        evidence_ok = (
            resolved["context_pack_ref"] == serialize_context_pack(pack)
            and raw_generation["raw_text"] == raw_text
            and raw_generation["generation_id"] == evidence["generation_id"]
            and raw_generation["context_pack_id"] == pack.context_pack_id
            and raw_generation["context_hash"] == pack.context_hash
            and _sha256(rendered) == raw_generation["rendered_input_hash"]
            and raw_generation["interface_treatment_id"]
            == I3_CONDITIONAL_TYPED_CODEC.treatment_id
            and raw_generation["interface_treatment_version"]
            == I3_CONDITIONAL_TYPED_CODEC.version
            and raw_generation["constraint_policy_id"]
            == I3_CONDITIONAL_TYPED_CODEC.constraint_policy_id
            and attempt.generation_id == evidence["generation_id"]
            and getattr(attempt.parse_status, "value", attempt.parse_status)
            == evidence["parse_status"]
        )
        privacy_ok = _privacy_pass(
            pack, snapshot_before, rendered, context_policy
        )
        all_evidence = all_evidence and evidence_ok
        all_privacy = all_privacy and privacy_ok

        actor = pack.evidence.agent_id.value
        details[actor] = {
            "opportunity_id": opportunity_id,
            "context_pack_id": pack.context_pack_id,
            "context_hash": pack.context_hash,
            "context_pack_ref_digest": nested["context_pack_ref"].digest,
            "rendered_input_digest": nested["rendered_input_ref"].digest,
            "evidence_ref_digest": attempt.evidence_ref.digest,
            "raw_text_digest": nested["raw_text_ref"].digest,
            "raw_generation_digest": nested["raw_generation_ref"].digest,
            "generation_id": raw_generation["generation_id"],
            "token_ids": raw_generation["token_ids"],
            "finish_reason": raw_generation["finish_reason"],
            "parse_status": evidence["parse_status"],
            "candidate": evidence["candidate"],
            "action_intent": evidence["action_intent"],
            "rejection": evidence["rejection"],
            "evidence_complete": evidence_ok,
            "privacy_structural_pass": privacy_ok,
        }
        comparison[actor] = {
            "context_pack_id": pack.context_pack_id,
            "context_hash": pack.context_hash,
            "context_pack_ref_digest": nested["context_pack_ref"].digest,
            "rendered_input_digest": nested["rendered_input_ref"].digest,
            "generation_id": raw_generation["generation_id"],
            "raw_text_digest": nested["raw_text_ref"].digest,
            "token_ids": tuple(raw_generation["token_ids"] or ()),
            "finish_reason": raw_generation["finish_reason"],
            "raw_generation_digest": nested["raw_generation_ref"].digest,
        }

    return details, comparison, all_evidence, all_privacy


class CountingRuntime:
    def __init__(self, runtime) -> None:
        self.runtime = runtime
        self.calls = 0

    def infer(self, compiled):
        self.calls += 1
        return self.runtime.infer(compiled)


def _chain_pass(commits, initial_hash: str) -> bool:
    previous_hash = initial_hash
    previous_events = ()
    for index, record in enumerate(commits, start=1):
        if (
            record.commit_seq != index
            or int(record.tick) != index - 1
            or int(record.state_version_before) != index - 1
            or int(record.state_version_after) != index
            or record.previous_state_hash != previous_hash
            or record.snapshot.state_hash() != record.resulting_state_hash
        ):
            return False
        if record.snapshot.events[: len(previous_events)] != previous_events:
            return False
        if record.snapshot.events[len(previous_events) :] != record.events:
            return False
        previous_hash = record.resulting_state_hash
        previous_events = record.snapshot.events
    return True


def _run_replica(
    *,
    name: str,
    reverse: bool,
    output_root: Path,
    config: dict[str, Any],
    backend,
    profile: ModelProfile,
    generation_policy: GenerationPolicy,
):
    replica_root = output_root / name
    replica_root.mkdir(parents=True, exist_ok=False)
    store = SQLiteReferenceStore(
        replica_root / "run.sqlite",
        artifact_root=replica_root / "cas",
    )

    world = config["world"]
    run = SimulationRun.bootstrap(
        RunId(RUN_ID),
        lifespan_ticks=Duration(world["lifespan_ticks"]),
        maturity_delay_ticks=Duration(world["maturity_delay_ticks"]),
        refractory_interval_ticks=Duration(world["refractory_interval_ticks"]),
        founder_ids=tuple(AgentId(value) for value in world["founders"]),
        population_capacity=world["population_capacity"],
        horizon=Tick(world["committed_ticks"]),
    )
    initial_hash = run.snapshot.state_hash()
    store.create_run(run)

    context_policy = build_context_policy()
    pipeline = ContextCognitionPipeline(
        context_policy,
        model_profile_id=profile.profile_id,
        generation_policy_id=generation_policy.policy_id,
        generation_seed_id=config["generation"]["seed_id"],
        artifact_store=store.artifact_store,
    )
    constraint = build_transformers_constraint(
        backend.tokenizer,
        schema=typed_action_codec_json_schema(),
    )
    live = LiveCandidateRuntime(
        backend,
        profile=profile,
        generation_policy=generation_policy,
        artifact_store=store.artifact_store,
        identity=WORLD_V0_FA_V1_IDENTITY,
        generation_seed=config["generation"]["seed"],
        interface_treatment=I3_CONDITIONAL_TYPED_CODEC,
        prefix_allowed_tokens_fn=constraint,
    )
    counted = CountingRuntime(live)
    kernel = DeterministicKernel(
        run,
        counted,
        context_pipeline=pipeline,
        committer=store.commit_store,
    )

    ticks: list[dict[str, Any]] = []
    comparison_ticks: list[dict[str, Any]] = []
    evidence_pass = True
    privacy_pass = True
    opportunity_total = 0
    action_counts: Counter[str] = Counter()

    try:
        for _ in range(world["committed_ticks"]):
            before = run.snapshot
            order = _completion_order(before, reverse=reverse)
            result = kernel.run_tick(completion_order=order)
            if not result.commit_result.committed:
                raise RuntimeError(
                    f"{name} tick {int(before.tick)} failed durable commit: "
                    f"{result.commit_result.error}"
                )

            opportunity_total += len(result.opportunities)
            attempt_details, attempt_compare, tick_evidence, tick_privacy = (
                _collect_attempts(result, store, before, context_policy)
            )
            evidence_pass = evidence_pass and tick_evidence
            privacy_pass = privacy_pass and tick_privacy

            for detail in attempt_details.values():
                intent = detail["action_intent"]
                if intent is None:
                    action_counts[f"REJECTED:{detail['parse_status']}"] += 1
                else:
                    action_counts[intent["kind"]] += 1

            validated = [
                _intent_projection(item) for item in result.validated_intents
            ]
            fragments = [
                fragment_to_dict(item) for item in result.fragments
            ]
            events_after = [
                event_to_dict(item) for item in result.commit_result.snapshot.events
            ]
            tick_summary = {
                "tick": int(before.tick),
                "state_version_before": int(before.state_version),
                "state_hash_before": before.state_hash(),
                "completion_order": [item.value for item in order],
                "opportunity_count": len(result.opportunities),
                "attempts": attempt_details,
                "validated_intents": validated,
                "fragments": fragments,
                "commit_id": result.commit_result.commit_id,
                "commit_seq": result.commit_result.commit_seq,
                "state_version_after": int(result.commit_result.snapshot.state_version),
                "state_hash_after": result.commit_result.snapshot.state_hash(),
                "events_after": events_after,
            }
            ticks.append(tick_summary)
            comparison_ticks.append(
                {
                    "state_hash_after": tick_summary["state_hash_after"],
                    "events_after": events_after,
                    "validated_intents": validated,
                    "fragments": fragments,
                    "attempts": attempt_compare,
                }
            )
            _write_json(
                replica_root / f"tick_{int(before.tick):02d}.json",
                tick_summary,
            )

        commits = store.commit_store.iter_commits(run.run_id)
        calls_before_replay = counted.calls
        replayed = store.replay(run.run_id)
        calls_after_replay = counted.calls
        loaded = store.load_run(run.run_id)

        g1 = (
            len(commits) == world["committed_ticks"]
            and int(run.snapshot.tick) == world["committed_ticks"]
            and int(run.snapshot.state_version) == world["committed_ticks"]
            and counted.calls == opportunity_total
        )
        g2 = evidence_pass
        g3 = (
            _chain_pass(commits, initial_hash)
            and calls_before_replay == calls_after_replay
            and replayed.state_hash == run.snapshot.state_hash()
            and replayed.snapshot == run.snapshot
            and loaded.snapshot == run.snapshot
            and len(replayed.verified_commit_ids) == len(commits)
        )
        g7 = privacy_pass

        summary = {
            "replica": name,
            "completion_order_rule": (
                "LEXICAL_DESCENDING_AGENT_ID"
                if reverse
                else "LEXICAL_ASCENDING_AGENT_ID"
            ),
            "gates": {
                "P0-G1": g1,
                "P0-G2": g2,
                "P0-G3": g3,
                "P0-G7": g7,
            },
            "model_inference_calls": counted.calls,
            "opportunity_total": opportunity_total,
            "replay_model_call_delta": calls_after_replay - calls_before_replay,
            "action_distribution": dict(sorted(action_counts.items())),
            "final_tick": int(run.snapshot.tick),
            "final_state_version": int(run.snapshot.state_version),
            "final_state_hash": run.snapshot.state_hash(),
            "final_agent_count": len(run.snapshot.agents),
            "final_message_count": len(run.snapshot.messages),
            "final_proposal_count": len(run.snapshot.proposals),
            "final_event_count": len(run.snapshot.events),
            "ticks": ticks,
        }
        _write_json(replica_root / "replica_summary.json", summary)
        return summary, comparison_ticks
    finally:
        store.close()


def _compare_replicas(fwd, rev) -> dict[str, Any]:
    g4 = True
    g5 = True
    g6 = True
    mismatches: list[str] = []
    if len(fwd) != len(rev):
        return {
            "P0-G4": False,
            "P0-G5": False,
            "P0-G6": False,
            "mismatches": ["replica tick counts differ"],
        }

    for tick, (left, right) in enumerate(zip(fwd, rev)):
        for field in (
            "state_hash_after",
            "events_after",
            "validated_intents",
            "fragments",
        ):
            if left[field] != right[field]:
                g4 = False
                mismatches.append(f"tick {tick}: G4 {field}")

        left_attempts = left["attempts"]
        right_attempts = right["attempts"]
        if left_attempts.keys() != right_attempts.keys():
            g5 = False
            g6 = False
            mismatches.append(f"tick {tick}: active agent sets differ")
            continue

        for agent in sorted(left_attempts):
            a = left_attempts[agent]
            b = right_attempts[agent]
            for field in (
                "context_pack_id",
                "context_hash",
                "context_pack_ref_digest",
                "rendered_input_digest",
            ):
                if a[field] != b[field]:
                    g5 = False
                    mismatches.append(f"tick {tick} agent {agent}: G5 {field}")
            for field in (
                "generation_id",
                "raw_text_digest",
                "token_ids",
                "finish_reason",
                "raw_generation_digest",
            ):
                if a[field] != b[field]:
                    g6 = False
                    mismatches.append(f"tick {tick} agent {agent}: G6 {field}")

    return {
        "P0-G4": g4,
        "P0-G5": g5,
        "P0-G6": g6,
        "mismatches": mismatches,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--base-model-dir", type=Path, required=True)
    parser.add_argument("--adapter-path", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--expected-git-commit", required=True)
    args = parser.parse_args()

    config, config_sha = _load_config(args.config)
    _validate_config(config)
    actual_commit = _git_head()
    if actual_commit != args.expected_git_commit:
        raise RuntimeError(
            f"repository commit mismatch: expected {args.expected_git_commit}, got {actual_commit}"
        )

    static = verify_static_deployment(
        DeploymentPaths(
            base_model_dir=args.base_model_dir,
            adapter_path=args.adapter_path,
            output_root=args.output_root / "_static_identity_only",
        ),
        expected_git_commit=args.expected_git_commit,
        repository_root=REPOSITORY_ROOT,
    )
    environment = _environment(config)

    if args.validate_only:
        print(
            json.dumps(
                {
                    "status": "P0_STATIC_PREFLIGHT_OK",
                    "git_commit": actual_commit,
                    "config_sha256": config_sha,
                    "runtime_pip_freeze_sha256": environment["pip_freeze_sha256"],
                    "deployment_status": static["status"],
                    "environment_checks": environment["checks"],
                },
                sort_keys=True,
            )
        )
        return 0

    if args.output_root.exists() and any(args.output_root.iterdir()):
        raise RuntimeError(
            "P0 output root is non-empty; replacement execution is forbidden"
        )
    args.output_root.mkdir(parents=True, exist_ok=True)
    _write_json(
        args.output_root / "planned.json",
        {
            "protocol_id": PROTOCOL_ID,
            "runner_version": RUNNER_VERSION,
            "status": "PRIMARY_EXECUTION_STARTED",
            "git_commit": actual_commit,
            "config_sha256": config_sha,
            "static_preflight": static,
            "environment": environment,
        },
    )

    profile = _profile(config, args.base_model_dir)
    generation_policy = _generation_policy(config)
    validate_live_runtime_identity(profile, WORLD_V0_FA_V1_IDENTITY)
    loader = PeftTransformersLoader(
        base_model_dir=args.base_model_dir,
        adapter_path=args.adapter_path,
    )
    backend = loader(profile)

    try:
        fwd_summary, fwd_compare = _run_replica(
            name="P0-FWD",
            reverse=False,
            output_root=args.output_root,
            config=config,
            backend=backend,
            profile=profile,
            generation_policy=generation_policy,
        )
        rev_summary, rev_compare = _run_replica(
            name="P0-REV",
            reverse=True,
            output_root=args.output_root,
            config=config,
            backend=backend,
            profile=profile,
            generation_policy=generation_policy,
        )
        cross = _compare_replicas(fwd_compare, rev_compare)
        replica_pass = all(fwd_summary["gates"].values()) and all(
            rev_summary["gates"].values()
        )
        cross_pass = all(cross[key] for key in ("P0-G4", "P0-G5", "P0-G6"))
        status = "PASS" if replica_pass and cross_pass else "FAIL"

        summary = {
            "protocol_id": PROTOCOL_ID,
            "runner_version": RUNNER_VERSION,
            "status": status,
            "git_commit": actual_commit,
            "config_sha256": config_sha,
            "replicas": {
                "P0-FWD": fwd_summary,
                "P0-REV": rev_summary,
            },
            "cross_replica": cross,
            "interpretation_boundary": {
                "infrastructure_and_causal_integrity_only": True,
                "nontrivial_policy_competence_established": False,
                "founder_freeze": "NOT_ESTABLISHED",
            },
        }
        _write_json(args.output_root / "summary.json", summary)
        print(
            json.dumps(
                {
                    "status": status,
                    "git_commit": actual_commit,
                    "config_sha256": config_sha,
                    "cross_replica": cross,
                },
                sort_keys=True,
            )
        )
        return 0 if status == "PASS" else 2
    except Exception as error:
        failure_path = args.output_root / "failure.json"
        if not failure_path.exists():
            _write_json(
                failure_path,
                {
                    "status": "INFRASTRUCTURE_ABORT",
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                },
            )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
