"""Run bounded Pythia I-05R3 diagnostics without committing simulation state."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict, replace
import json
from pathlib import Path
import statistics
import time

from alifelm.context import (
    ContextPolicy,
    DEFAULT_ACTION_PRESENTATION,
    OrderingPolicy,
    action_presentation_digest,
)
from alifelm.domain import ArtifactId, ArtifactRef, Duration
from alifelm.kernel import SimulationRun
from alifelm.model import (
    ACTION_SCORE_PREFIX,
    GenerationPolicy,
    I3_BRANCH_ORDERS,
    I3_CONDITIONAL_TYPED_CODEC,
    ModelProfile,
    PeftTransformersLoader,
    R3ContextClass,
    RealCognitionDryRunner,
    TransformersModelRuntime,
    WORLD_V0_FA_V1_IDENTITY,
    action_label_score_bytes,
    build_transformers_constraint,
    compile_r3_fixture,
    evaluate_typed_codec,
    forced_action_codec_json_schema,
    i3_branch_order_treatment,
    i3_forced_branch_treatment,
    score_action_labels,
    typed_action_codec_json_schema,
    typed_codec_evaluation_bytes,
    validate_live_runtime_identity,
)
from alifelm.model.world_v0_smoke import DeploymentPaths, verify_static_deployment
from alifelm.persistence import FileSystemArtifactStore


def _policy() -> ContextPolicy:
    return ContextPolicy.exp000(
        max_prior_visible_records=4,
        ordering=OrderingPolicy(
            policy_version="1.0.0",
            unordered_collection_algorithm="ALIFELM_CONTEXT_ORDER_V1",
            digest_algorithm="sha256",
            ordering_seed_id="i05-probe-order",
            ordering_seed_digest="1" * 64,
            cross_tick_order="COMMITTED_TICK_CHRONOLOGICAL",
            tie_breaker="FULL_STABLE_ITEM_KEY",
        ),
        action_presentation_digest=action_presentation_digest(
            DEFAULT_ACTION_PRESENTATION
        ),
    )


def _profile(base_model_dir: Path) -> ModelProfile:
    identity = WORLD_V0_FA_V1_IDENTITY
    return ModelProfile(
        profile_id="i05r3-world-v0-fa-v1-bf16",
        profile_version="1.0.0",
        model_identifier=str(base_model_dir),
        model_revision=identity.base_model_revision,
        model_digest=identity.base_checkpoint_sha256,
        tokenizer_identifier=str(base_model_dir),
        tokenizer_revision=identity.tokenizer_revision,
        tokenizer_digest=identity.tokenizer_digest,
        model_class="AUTO_CAUSAL_LM",
        generation_policy_id="mode-d",
        device="cuda:0",
        dtype="bfloat16",
        adapter_ref=ArtifactRef(
            ArtifactId("F0_FA_V1_FORMAL"), identity.adapter_sha256
        ),
        trust_remote_code=False,
        add_special_tokens=True,
    )


def _generation_policy(mode: str) -> GenerationPolicy:
    return GenerationPolicy(
        policy_id=f"mode-{mode.lower()}",
        version="1.0.0",
        max_new_tokens=64,
        do_sample=mode == "S",
        temperature=0.8 if mode == "S" else None,
        top_p=0.95 if mode == "S" else None,
        top_k=50 if mode == "S" else None,
        repetition_penalty=1.0,
        seed_id=f"mode-{mode.lower()}-seed" if mode == "S" else None,
        stop_policy_id=None,
    )


def _run_generation(
    *,
    compiled,
    runtime,
    profile,
    policy,
    store,
    treatment,
    schema,
    seed: int | None,
) -> dict:
    constraint = build_transformers_constraint(runtime.tokenizer, schema=schema)
    runner = RealCognitionDryRunner(
        runtime,
        profile,
        policy,
        store,
        generation_seed=seed,
        interface_treatment=treatment,
        prefix_allowed_tokens_fn=constraint,
    )
    before = compiled.opportunity.snapshot.state_hash()
    started = time.perf_counter()
    result = runner.run(compiled)
    latency = time.perf_counter() - started
    diagnostic_run = SimulationRun(
        run_id=compiled.opportunity.snapshot.run_id,
        lifespan_ticks=Duration(100),
        maturity_delay_ticks=Duration(0),
        refractory_interval_ticks=Duration(0),
        _snapshot=compiled.opportunity.snapshot,
    )
    evaluation = evaluate_typed_codec(
        result.raw_generation.raw_text,
        compiled.opportunity,
        diagnostic_run,
    )
    diagnostic_ref = store.put_bytes(
        typed_codec_evaluation_bytes(
            evaluation,
            generation_id=result.evidence.generation_id,
            context_hash=result.evidence.context_hash,
            treatment_id=treatment.treatment_id,
            treatment_version=treatment.version,
        ),
        media_type="application/json",
        contract_id="typed-codec-diagnostic-1.0.0",
    )
    if compiled.opportunity.snapshot.state_hash() != before:
        raise RuntimeError("R3 diagnostic mutated the bound Snapshot")
    refs = (
        result.evidence.context_pack_ref,
        result.evidence.rendered_input_ref,
        result.evidence.raw_text_ref,
        result.evidence.raw_generation_ref,
        result.evidence_ref,
        diagnostic_ref,
    )
    if not all(store.is_durable(ref) for ref in refs):
        raise RuntimeError("R3 generation evidence did not resolve")
    candidate = evaluation.candidate
    payload = candidate.payload_dict() if candidate is not None else {}
    model_input = compiled.context_pack.model_input
    visible_peers = {str(item.agent_id) for item in model_input.peer_directory}
    visible_proposals = {
        item.payload.proposal_id for item in model_input.visible_protocol_state
    }
    return {
        "action_label": candidate.action_label if candidate is not None else None,
        "body_non_empty": bool(payload.get("body")),
        "codec_status": evaluation.codec_status.value,
        "commit_status": evaluation.commit_status.value,
        "cognition_evidence_ref": result.evidence_ref.digest,
        "context_hash": result.evidence.context_hash,
        "context_pack_ref": result.evidence.context_pack_ref.digest,
        "diagnostic_ref": diagnostic_ref.digest,
        "domain_status": evaluation.domain_status.value,
        "generation_id": result.evidence.generation_id,
        "latency_seconds": latency,
        "payload": payload,
        "proposal_visible": payload.get("proposal_id") in visible_proposals,
        "raw_generation_ref": result.evidence.raw_generation_ref.digest,
        "raw_text_ref": result.evidence.raw_text_ref.digest,
        "rendered_input_ref": result.evidence.rendered_input_ref.digest,
        "target_visible": payload.get("target_agent_id") in visible_peers,
        "treatment_digest": treatment.digest,
    }


def _summarize_generations(records: list[dict]) -> dict:
    return {
        "n": len(records),
        "actions": dict(
            Counter(record["action_label"] or "NO_CANDIDATE" for record in records)
        ),
        "codec": dict(Counter(record["codec_status"] for record in records)),
        "domain": dict(Counter(record["domain_status"] for record in records)),
        "commit": dict(Counter(record["commit_status"] for record in records)),
        "target_visible": sum(record["target_visible"] for record in records),
        "proposal_visible": sum(record["proposal_visible"] for record in records),
        "body_non_empty": sum(record["body_non_empty"] for record in records),
        "average_latency_seconds": statistics.mean(
            record["latency_seconds"] for record in records
        ),
        "evidence_complete": len(records),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase", choices=("state", "branch-order", "forced", "mode-s"), required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-model-dir", type=Path, required=True)
    parser.add_argument("--adapter-path", type=Path, required=True)
    parser.add_argument("--expected-git-commit", required=True)
    parser.add_argument("--cases", type=int, default=10)
    parser.add_argument("--seed", type=int, default=1729)
    arguments = parser.parse_args()
    arguments.output.mkdir(parents=True, exist_ok=True)

    deployment_paths = DeploymentPaths(
        base_model_dir=arguments.base_model_dir,
        adapter_path=arguments.adapter_path,
        output_root=arguments.output,
    )
    preflight = verify_static_deployment(
        deployment_paths,
        expected_git_commit=arguments.expected_git_commit,
        repository_root=Path(__file__).resolve().parents[1],
    )

    store = FileSystemArtifactStore(arguments.output / "cas")
    profile = _profile(arguments.base_model_dir)
    mode = "S" if arguments.phase == "mode-s" else "D"
    generation_policy = _generation_policy(mode)
    profile = replace(
        profile,
        generation_policy_id=generation_policy.policy_id,
    )
    validate_live_runtime_identity(profile, WORLD_V0_FA_V1_IDENTITY)
    started = time.perf_counter()
    runtime = PeftTransformersLoader(
        base_model_dir=arguments.base_model_dir,
        adapter_path=arguments.adapter_path,
    )(profile)
    load_seconds = time.perf_counter() - started
    context_policy = _policy()
    summary: dict = {
        "phase": arguments.phase,
        "deployment_preflight": preflight,
        "profile": asdict(profile),
        "generation_policy": asdict(generation_policy),
        "load_seconds": load_seconds,
    }

    if arguments.phase in {"state", "mode-s"}:
        classes = tuple(R3ContextClass)
        generation_by_class: dict[str, list[dict]] = defaultdict(list)
        score_by_class: dict[str, list[dict]] = defaultdict(list)
        for context_class in classes:
            for case_index in range(arguments.cases):
                compiled = compile_r3_fixture(
                    context_class,
                    case_index,
                    policy=context_policy,
                    model_profile_id=profile.profile_id,
                    generation_policy_id=generation_policy.policy_id,
                    generation_seed_id=f"mode-{mode.lower()}-seed",
                    artifact_store=store,
                )
                generation_record = _run_generation(
                    compiled=compiled,
                    runtime=runtime,
                    profile=profile,
                    policy=generation_policy,
                    store=store,
                    treatment=I3_CONDITIONAL_TYPED_CODEC,
                    schema=typed_action_codec_json_schema(),
                    seed=(arguments.seed + case_index if mode == "S" else None),
                )
                generation_by_class[context_class.value].append(generation_record)
                if arguments.phase == "state":
                    score_input_ref = store.put_bytes(
                        compiled.rendered_input + ACTION_SCORE_PREFIX,
                        media_type="text/plain; charset=utf-8",
                        contract_id="action-label-score-input-1.0.0",
                    )
                    score = score_action_labels(
                        runtime,
                        rendered_input=compiled.rendered_input,
                        context_hash=compiled.context_pack.context_hash,
                        context_pack_ref=generation_record["context_pack_ref"],
                        rendered_input_ref=score_input_ref.digest,
                    )
                    score_ref = store.put_bytes(
                        action_label_score_bytes(score),
                        media_type="application/json",
                        contract_id="action-label-score-diagnostic-1.0.0",
                    )
                    score_by_class[context_class.value].append(
                        {
                            "context_hash": score.context_hash,
                            "score_ref": score_ref.digest,
                            "scores": [asdict(item) for item in score.scores],
                            "shared_token_prefixes": score.shared_token_prefixes,
                        }
                    )
        summary["generation"] = {
            key: _summarize_generations(value)
            for key, value in generation_by_class.items()
        }
        summary["generation_records"] = generation_by_class
        if score_by_class:
            summary["score_records"] = score_by_class
            score_summary = {}
            for class_name, records in score_by_class.items():
                totals: dict[str, list[float]] = defaultdict(list)
                means: dict[str, list[float]] = defaultdict(list)
                ranks: dict[str, list[int]] = defaultdict(list)
                for record in records:
                    for score in record["scores"]:
                        totals[score["model_label"]].append(score["total_log_probability"])
                        means[score["model_label"]].append(score["mean_log_probability"])
                        ranks[score["model_label"]].append(score["rank"])
                score_summary[class_name] = {
                    label: {
                        "mean_total_log_probability": statistics.mean(totals[label]),
                        "mean_log_probability_per_token": statistics.mean(means[label]),
                        "mean_rank": statistics.mean(ranks[label]),
                        "rank_1_count": ranks[label].count(1),
                    }
                    for label in totals
                }
            summary["score_summary"] = score_summary

    elif arguments.phase == "branch-order":
        compiled = compile_r3_fixture(
            R3ContextClass.QUIET,
            0,
            policy=context_policy,
            model_profile_id=profile.profile_id,
            generation_policy_id=generation_policy.policy_id,
            generation_seed_id="mode-d-seed",
            artifact_store=store,
        )
        records = []
        for index, order in enumerate(I3_BRANCH_ORDERS):
            records.append(
                {
                    "branch_order": order,
                    **_run_generation(
                        compiled=compiled,
                        runtime=runtime,
                        profile=profile,
                        policy=generation_policy,
                        store=store,
                        treatment=i3_branch_order_treatment(index),
                        schema=typed_action_codec_json_schema(action_order=order),
                        seed=None,
                    ),
                }
            )
        summary["records"] = records
        summary["result"] = _summarize_generations(records)

    else:
        fixture_for_action = {
            "SEND": R3ContextClass.QUIET,
            "PROPOSE": R3ContextClass.QUIET,
            "ACCEPT": R3ContextClass.PROPOSAL_RECEIVED,
            "REJECT": R3ContextClass.PROPOSAL_RECEIVED,
        }
        by_action: dict[str, list[dict]] = defaultdict(list)
        for action, context_class in fixture_for_action.items():
            for case_index in range(arguments.cases):
                compiled = compile_r3_fixture(
                    context_class,
                    case_index,
                    policy=context_policy,
                    model_profile_id=profile.profile_id,
                    generation_policy_id=generation_policy.policy_id,
                    generation_seed_id="mode-d-seed",
                    artifact_store=store,
                )
                by_action[action].append(
                    _run_generation(
                        compiled=compiled,
                        runtime=runtime,
                        profile=profile,
                        policy=generation_policy,
                        store=store,
                        treatment=i3_forced_branch_treatment(action),
                        schema=forced_action_codec_json_schema(action),
                        seed=None,
                    )
                )
        summary["generation"] = {
            action: _summarize_generations(records)
            for action, records in by_action.items()
        }
        summary["generation_records"] = by_action

    encoded = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True)
    (arguments.output / "summary.json").write_text(encoded, encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
