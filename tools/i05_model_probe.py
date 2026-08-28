"""Run bounded M0/M1 real-model probes without committing simulation state."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import statistics
import time

from alifelm.context import (
    ContextCognitionPipeline,
    ContextPolicy,
    DEFAULT_ACTION_PRESENTATION,
    OrderingPolicy,
    action_presentation_digest,
)
from alifelm.domain import (
    AgentId,
    AgentState,
    Duration,
    MessageId,
    MessageRecord,
    RunId,
    StateVersion,
    Tick,
)
from alifelm.kernel import EqualOpportunityScheduler, SimulationRun, Snapshot
from alifelm.model import (
    GenerationPolicy,
    I0_STRICT_FREE_GENERATION,
    I1_NEUTRAL_CODEC_SCAFFOLD,
    I2_SYNTAX_CONSTRAINED_CODEC,
    I3_CONDITIONAL_TYPED_CODEC,
    ModelProfile,
    ModelOutputStatus,
    RealCognitionDryRunner,
    TransformersModelRuntime,
    collect_runtime_environment,
    build_transformers_constraint,
    diagnose_generation,
    evaluate_typed_codec,
    generation_request_for,
    inspect_chat_template,
    inspect_generation_semantics,
    typed_action_codec_json_schema,
    typed_codec_evaluation_bytes,
)
from alifelm.persistence import FileSystemArtifactStore


def context_policy() -> ContextPolicy:
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


def compiled_case(
    *,
    suite_id: str,
    case_index: int,
    model_profile_id: str,
    generation_policy_id: str,
    generation_seed_id: str,
    artifact_store: FileSystemArtifactStore,
):
    agents = tuple(
        AgentState(
            agent_id=AgentId(value),
            birth_tick=Tick(0),
            first_active_tick=Tick(0),
            lifespan_ticks=Duration(100),
            maturity_delay_ticks=Duration(0),
        )
        for value in ("A", "B", "C")
    )
    messages = ()
    if case_index % 3:
        messages = (
            MessageRecord(
                message_id=MessageId(f"message-{case_index}"),
                sender_id=AgentId("B"),
                recipient_id=AgentId("A"),
                body=f"record {case_index}",
                committed_tick=Tick(0),
                available_tick=Tick(1),
            ),
        )
    snapshot = Snapshot(
        run_id=RunId(f"{suite_id}-{case_index}"),
        tick=Tick(1),
        state_version=StateVersion(1),
        agents=agents,
        messages=messages,
        proposals=(),
        events=(),
    )
    opportunity = next(
        item
        for item in EqualOpportunityScheduler().enumerate(snapshot)
        if item.agent_id == AgentId("A")
    )
    pipeline = ContextCognitionPipeline(
        context_policy(),
        model_profile_id=model_profile_id,
        generation_policy_id=generation_policy_id,
        generation_seed_id=generation_seed_id,
        artifact_store=artifact_store,
    )
    return pipeline.compile_all((opportunity,))[0]


def _jsonable(value):
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--family", required=True)
    parser.add_argument("--license", required=True)
    parser.add_argument("--training-status", default="BASE_PRETRAINED")
    parser.add_argument("--mode", choices=("D", "S"), required=True)
    parser.add_argument(
        "--interface", choices=("I0", "I1", "I2", "I3"), default="I0"
    )
    parser.add_argument("--cases", type=int, default=1)
    parser.add_argument("--case-start", type=int, default=0)
    parser.add_argument("--max-new-tokens", type=int, default=64)
    parser.add_argument("--seed", type=int, default=1729)
    parser.add_argument("--suite-id", default="i05-probe")
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    arguments.output.mkdir(parents=True, exist_ok=True)
    cas = FileSystemArtifactStore(arguments.output / "cas")

    generation_policy_id = f"mode-{arguments.mode.lower()}"
    seed_id = f"mode-{arguments.mode.lower()}-seed"
    profile = ModelProfile(
        profile_id=arguments.profile_id,
        profile_version="1.0.0",
        model_identifier=arguments.model,
        model_revision=arguments.revision,
        model_digest=None,
        tokenizer_identifier=arguments.model,
        tokenizer_revision=arguments.revision,
        tokenizer_digest=None,
        model_class="AUTO_CAUSAL_LM",
        generation_policy_id=generation_policy_id,
        device="cpu",
        dtype="float32",
        adapter_ref=None,
        trust_remote_code=False,
        add_special_tokens=True,
    )
    policy = GenerationPolicy(
        policy_id=generation_policy_id,
        version="1.0.0",
        max_new_tokens=arguments.max_new_tokens,
        do_sample=arguments.mode == "S",
        temperature=0.8 if arguments.mode == "S" else None,
        top_p=0.95 if arguments.mode == "S" else None,
        top_k=50 if arguments.mode == "S" else None,
        repetition_penalty=1.0,
        seed_id=seed_id if arguments.mode == "S" else None,
        stop_policy_id=None,
    )

    load_started = time.perf_counter()
    runtime = TransformersModelRuntime.load(profile)
    load_seconds = time.perf_counter() - load_started
    import torch
    import transformers

    first = compiled_case(
        suite_id=arguments.suite_id,
        case_index=arguments.case_start,
        model_profile_id=profile.profile_id,
        generation_policy_id=policy.policy_id,
        generation_seed_id=seed_id,
        artifact_store=cas,
    )
    environment = collect_runtime_environment(
        profile, torch_module=torch, transformers_module=transformers
    )
    template_audit = inspect_chat_template(
        runtime.tokenizer,
        first.rendered_input.decode("utf-8"),
        add_special_tokens=profile.add_special_tokens,
    )
    treatment = {
        "I0": I0_STRICT_FREE_GENERATION,
        "I1": I1_NEUTRAL_CODEC_SCAFFOLD,
        "I2": I2_SYNTAX_CONSTRAINED_CODEC,
        "I3": I3_CONDITIONAL_TYPED_CODEC,
    }[arguments.interface]
    first_request = generation_request_for(
        first,
        profile,
        policy,
        generation_seed=arguments.seed if arguments.mode == "S" else None,
        interface_treatment=treatment,
    )
    generation_audit = inspect_generation_semantics(runtime, first_request)
    prefix_allowed_tokens_fn = None
    if arguments.interface in {"I2", "I3"}:
        prefix_allowed_tokens_fn = build_transformers_constraint(
            runtime.tokenizer,
            schema=(
                typed_action_codec_json_schema()
                if arguments.interface == "I3"
                else None
            ),
        )

    statuses: Counter[str] = Counter()
    actions: Counter[str] = Counter()
    raw_lengths: list[int] = []
    latencies: list[float] = []
    samples: list[dict] = []
    prior_markers = Counter()
    diagnostics: Counter[str] = Counter()
    diagnostic_labels: Counter[str] = Counter()
    prompt_echo_count = 0
    evidence_complete_count = 0
    codec_statuses: Counter[str] = Counter()
    domain_statuses: Counter[str] = Counter()
    commit_statuses: Counter[str] = Counter()
    codec_actions: Counter[str] = Counter()
    typed_diagnostic_refs: list[str] = []
    results = []
    for case_index in range(arguments.case_start, arguments.case_start + arguments.cases):
        compiled = first if case_index == arguments.case_start else compiled_case(
            suite_id=arguments.suite_id,
            case_index=case_index,
            model_profile_id=profile.profile_id,
            generation_policy_id=policy.policy_id,
            generation_seed_id=seed_id,
            artifact_store=cas,
        )
        runner = RealCognitionDryRunner(
            runtime,
            profile,
            policy,
            cas,
            generation_seed=arguments.seed if arguments.mode == "S" else None,
            interface_treatment=treatment,
            prefix_allowed_tokens_fn=prefix_allowed_tokens_fn,
        )
        started = time.perf_counter()
        result = runner.run(compiled)
        latencies.append(time.perf_counter() - started)
        results.append(result)
        status = result.evidence.parse_status.value
        statuses[status] += 1
        raw = result.raw_generation.raw_text
        raw_lengths.append(len(result.raw_generation.token_ids or ()))
        if result.evidence.action_intent is not None:
            actions[result.evidence.action_intent.kind.value] += 1
        typed_evaluation = None
        if arguments.interface == "I3":
            snapshot = compiled.opportunity.snapshot
            diagnostic_run = SimulationRun(
                run_id=snapshot.run_id,
                lifespan_ticks=Duration(100),
                maturity_delay_ticks=Duration(0),
                refractory_interval_ticks=Duration(0),
                _snapshot=snapshot,
            )
            typed_evaluation = evaluate_typed_codec(
                raw, compiled.opportunity, diagnostic_run
            )
            codec_statuses[typed_evaluation.codec_status.value] += 1
            domain_statuses[typed_evaluation.domain_status.value] += 1
            commit_statuses[typed_evaluation.commit_status.value] += 1
            if typed_evaluation.candidate is not None:
                codec_actions[typed_evaluation.candidate.action_label] += 1
            typed_ref = cas.put_bytes(
                typed_codec_evaluation_bytes(
                    typed_evaluation,
                    generation_id=result.evidence.generation_id,
                    context_hash=result.evidence.context_hash,
                    treatment_id=treatment.treatment_id,
                    treatment_version=treatment.version,
                ),
                media_type="application/json",
                contract_id="typed-codec-diagnostic-1.0.0",
            )
            typed_diagnostic_refs.append(typed_ref.digest)
        rendered = treatment.render(compiled.rendered_input).decode("utf-8")
        diagnostic = diagnose_generation(
            raw,
            rendered,
            strict_valid=(
                typed_evaluation.codec_status.value == "CODEC_VALID"
                if typed_evaluation is not None
                else status == ModelOutputStatus.VALID.value
            ),
        )
        diagnostics[diagnostic.primary_label.value] += 1
        diagnostic_labels.update(label.value for label in diagnostic.labels)
        prompt_echo_count += int(diagnostic.prompt_echo)
        evidence_refs = (
            result.evidence.context_pack_ref,
            result.evidence.rendered_input_ref,
            result.evidence.raw_text_ref,
            result.evidence.raw_generation_ref,
        )
        resolved = tuple(cas.resolve(reference) for reference in evidence_refs)
        if (
            resolved[1] == treatment.render(compiled.rendered_input)
            and resolved[2] == raw.encode("utf-8")
            and all(reference.digest for reference in evidence_refs)
        ):
            evidence_complete_count += 1
        lowered = raw.lower()
        for marker in (
            "surviv",
            "romance",
            "family",
            "friend",
            "cooperat",
            "hierarch",
            "status",
            "persona",
            "role",
        ):
            if marker in lowered:
                prior_markers[marker] += 1
        if len(samples) < 5:
            samples.append(
                {
                    "case": case_index,
                    "context_hash": result.evidence.context_hash,
                    "generation_id": result.evidence.generation_id,
                    "status": status,
                    "raw_text": raw,
                    "raw_text_ref": result.evidence.raw_text_ref.digest,
                    "raw_generation_ref": result.evidence.raw_generation_ref.digest,
                    "rendered_input_ref": result.evidence.rendered_input_ref.digest,
                    "context_pack_ref": result.evidence.context_pack_ref.digest,
                    "evidence_ref": result.evidence_ref.digest,
                    "diagnostic_labels": [label.value for label in diagnostic.labels],
                    "codec_status": (
                        typed_evaluation.codec_status.value
                        if typed_evaluation is not None
                        else None
                    ),
                    "domain_status": (
                        typed_evaluation.domain_status.value
                        if typed_evaluation is not None
                        else None
                    ),
                    "commit_status": (
                        typed_evaluation.commit_status.value
                        if typed_evaluation is not None
                        else None
                    ),
                    "typed_diagnostic_ref": (
                        typed_diagnostic_refs[-1]
                        if typed_evaluation is not None
                        else None
                    ),
                }
            )

    # Repeat the exact first request after the suite. No retry/corrective prompt.
    repeat_runner = RealCognitionDryRunner(
        runtime,
        profile,
        policy,
        cas,
        generation_seed=arguments.seed if arguments.mode == "S" else None,
        interface_treatment=treatment,
        prefix_allowed_tokens_fn=prefix_allowed_tokens_fn,
    )
    repeat = repeat_runner.run(first)
    first_result = results[0]
    repeat_equal = (
        first_result.raw_generation.raw_text == repeat.raw_generation.raw_text
        and first_result.raw_generation.token_ids == repeat.raw_generation.token_ids
        and first_result.raw_generation.generation_id
        == repeat.raw_generation.generation_id
    )

    summary = {
        "model": arguments.model,
        "revision": arguments.revision,
        "profile_id": profile.profile_id,
        "model_metadata": {
            "family": arguments.family,
            "parameter_count": (
                int(runtime.model.num_parameters())
                if hasattr(runtime.model, "num_parameters")
                else None
            ),
            "training_status": arguments.training_status,
            "tokenizer_class": type(runtime.tokenizer).__name__,
            "architecture": list(getattr(runtime.model.config, "architectures", ()) or ()),
            "model_type": getattr(runtime.model.config, "model_type", None),
            "context_length": getattr(runtime.model.config, "max_position_embeddings", None),
            "license": arguments.license,
        },
        "mode": arguments.mode,
        "interface": arguments.interface,
        "interface_treatment": {
            "treatment_id": treatment.treatment_id,
            "version": treatment.version,
            "digest": treatment.digest,
            "completion_suffix": treatment.completion_suffix,
            "constraint_policy_id": treatment.constraint_policy_id,
        },
        "cases": arguments.cases,
        "case_start": arguments.case_start,
        "environment": _jsonable(asdict(environment)),
        "chat_template_audit": _jsonable(asdict(template_audit)),
        "generation_semantics": _jsonable(asdict(generation_audit)),
        "load_seconds": load_seconds,
        "parse_status": dict(statuses),
        "research_diagnostics": dict(diagnostics),
        "research_diagnostic_labels": dict(diagnostic_labels),
        "prompt_echo_rate": prompt_echo_count / arguments.cases,
        "raw_evidence_complete": evidence_complete_count,
        "typed_codec_status": dict(codec_statuses),
        "domain_validity_status": dict(domain_statuses),
        "commit_validity_status": dict(commit_statuses),
        "codec_action_distribution": dict(codec_actions),
        "typed_diagnostic_refs": typed_diagnostic_refs,
        "parse_success_rate": statuses[ModelOutputStatus.VALID.value] / arguments.cases,
        "action_distribution": dict(actions),
        "average_generated_tokens": statistics.mean(raw_lengths),
        "average_latency_seconds": statistics.mean(latencies),
        "prior_marker_cases": dict(prior_markers),
        "exact_repeat_equal": repeat_equal,
        "samples": samples,
    }
    encoded = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True)
    (arguments.output / "summary.json").write_text(encoded, encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
