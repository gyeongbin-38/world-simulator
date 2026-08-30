#!/usr/bin/env python3
"""Run the preregistered A0 autonomous-interface admission on the exact FA-v1.

The study is a researcher-side dry run. It loads the accepted BF16 base plus
FA-v1 once, compiles a fixed cohort of real WORLD ContextPacks, and compares
I0/I1/I2/I3 on the exact same contexts. It never commits simulation state and
never uses action-frequency targets as an admission criterion.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from alifelm.domain import ArtifactId, ArtifactRef  # noqa: E402
from alifelm.model import (  # noqa: E402
    GenerationPolicy,
    I0_STRICT_FREE_GENERATION,
    I1_NEUTRAL_CODEC_SCAFFOLD,
    I2_SYNTAX_CONSTRAINED_CODEC,
    I3_BRANCH_ORDERS,
    I3_CONDITIONAL_TYPED_CODEC,
    ModelProfile,
    PeftTransformersLoader,
    RealCognitionDryRunner,
    WORLD_V0_FA_V1_IDENTITY,
    action_codec_json_schema,
    build_transformers_constraint,
    compile_r3_fixture,
    i3_branch_order_treatment,
    typed_action_codec_json_schema,
)
from alifelm.model.autonomous_admission import (  # noqa: E402
    A0_ADMISSION_ID,
    A0_ATTEMPTS_PER_TREATMENT,
    A0_CASES_PER_CONTEXT_CLASS,
    A0_CONTEXT_CLASSES,
    A0_SCHEMA_VERSION,
    A0_TREATMENT_ORDER,
    A0TreatmentMetrics,
    choose_minimal_treatment,
    evaluate_i3_branch_order_audit,
    evaluate_treatment,
)
from alifelm.model.world_v0_smoke import (  # noqa: E402
    ADAPTER_CONFIG_SHA256,
    ADAPTER_SHA256,
    BASE_CHECKPOINT_SHA256,
    BASE_MODEL_REPO,
    BASE_MODEL_REVISION,
    DeploymentPaths,
    SmokePreflightError,
    TOKENIZER_DIGEST,
    TOKENIZER_REVISION,
    build_context_policy,
    canonical_bytes,
    canonical_digest,
    ensure_execute_environment,
    inspect_existing_manifest,
    verify_static_deployment,
    write_immutable_manifest,
)
from alifelm.persistence import FileSystemArtifactStore  # noqa: E402


A0_GENERATION_POLICY_ID = "A0_GREEDY_DIRECT_COMPLETION_V1"
A0_GENERATION_SEED_ID = "A0_GREEDY_SEED_V1"
A0_GENERATION_SEED = 35020260831
A0_PROFILE_ID = "A0_WORLD_V0_FA_V1_BF16"
A0_MAX_NEW_TOKENS = 128
A0_DISCOVERY_SMOKE_MANIFEST = (
    "717bdd81c388c47beb7d5e2777867762b7cd223e61a50f7195840c72315ccf89"
)
A0_DISCOVERY_SMOKE_OBSERVATION = "6/6 first-token EOS under I0"


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
        raise SmokePreflightError("cannot resolve repository commit") from error


def _generation_policy() -> GenerationPolicy:
    return GenerationPolicy(
        policy_id=A0_GENERATION_POLICY_ID,
        version="1.0.0",
        max_new_tokens=A0_MAX_NEW_TOKENS,
        do_sample=False,
        temperature=None,
        top_p=None,
        top_k=None,
        repetition_penalty=1.0,
        seed_id=A0_GENERATION_SEED_ID,
        stop_policy_id=None,
    )


def _model_profile(base_model_dir: Path) -> ModelProfile:
    identity = WORLD_V0_FA_V1_IDENTITY
    return ModelProfile(
        profile_id=A0_PROFILE_ID,
        profile_version="1.0.0",
        model_identifier=str(base_model_dir),
        model_revision=identity.base_model_revision,
        model_digest=identity.base_checkpoint_sha256,
        tokenizer_identifier=str(base_model_dir),
        tokenizer_revision=identity.tokenizer_revision,
        tokenizer_digest=identity.tokenizer_digest,
        model_class="AUTO_CAUSAL_LM",
        generation_policy_id=A0_GENERATION_POLICY_ID,
        device="cuda:0",
        dtype="bfloat16",
        adapter_ref=ArtifactRef(
            ArtifactId("F0_FA_V1_FORMAL"), identity.adapter_sha256
        ),
        trust_remote_code=False,
        add_special_tokens=True,
    )


def _planned_manifest(*, paths: DeploymentPaths, git_commit: str) -> dict[str, Any]:
    identity = {
        "admission_id": A0_ADMISSION_ID,
        "schema_version": A0_SCHEMA_VERSION,
        "git_commit": git_commit,
        "scientific_identity": {
            "base_model_repo": BASE_MODEL_REPO,
            "base_model_revision": BASE_MODEL_REVISION,
            "base_checkpoint_sha256": BASE_CHECKPOINT_SHA256,
            "tokenizer_revision": TOKENIZER_REVISION,
            "tokenizer_digest": TOKENIZER_DIGEST,
            "adapter_sha256": ADAPTER_SHA256,
            "adapter_config_sha256": ADAPTER_CONFIG_SHA256,
        },
        "generation": {
            "policy_id": A0_GENERATION_POLICY_ID,
            "max_new_tokens": A0_MAX_NEW_TOKENS,
            "do_sample": False,
            "seed_id": A0_GENERATION_SEED_ID,
            "seed": A0_GENERATION_SEED,
        },
        "cohort": {
            "context_classes": [value.value for value in A0_CONTEXT_CLASSES],
            "cases_per_context_class": A0_CASES_PER_CONTEXT_CLASS,
            "attempts_per_treatment": A0_ATTEMPTS_PER_TREATMENT,
            "fixture": "R3ContextClass/compile_r3_fixture",
            "contexts_reused_across_treatments": True,
        },
        "treatments": list(A0_TREATMENT_ORDER),
        "promotion_rule": (
            "FIRST_MINIMAL_TREATMENT_PASSING_MOTOR_AND_AUTONOMOUS_GATES"
        ),
        "i3_branch_audit": {
            "conditional": True,
            "orders": [list(order) for order in I3_BRANCH_ORDERS],
            "runs_only_if": "I3_IS_MINIMAL_CORE_PASS",
        },
        "forbidden_admission_targets": [
            "action_frequency",
            "SEND_rate",
            "PROPOSE_rate",
            "social_desirability",
            "mate_preference",
            "fitness_score",
        ],
        "prior_discovery": {
            "classification": "DISCOVERY_ONLY_NOT_IN_A0_DENOMINATOR",
            "smoke_manifest_digest": A0_DISCOVERY_SMOKE_MANIFEST,
            "observation": A0_DISCOVERY_SMOKE_OBSERVATION,
        },
    }
    return {
        "schema_version": A0_SCHEMA_VERSION,
        "run_id": A0_ADMISSION_ID,
        "status": "PLANNED",
        "manifest_identity": identity,
        "manifest_identity_digest": canonical_digest(identity),
        "deployment": {
            "base_model_dir": str(paths.base_model_dir),
            "adapter_path": str(paths.adapter_path),
            "output_root": str(paths.output_root),
        },
        "evidence_policy": {
            "raw_model_text": "CAS_ONLY",
            "no_simulation_commit": True,
            "no_retry": True,
            "no_fallback": True,
            "no_repair": True,
            "same_compiled_contexts_across_treatments": True,
        },
    }


def _static_preflight(
    paths: DeploymentPaths, expected_git_commit: str
) -> dict[str, Any]:
    # Reuse the accepted artifact/tokenizer verifier without colliding with the
    # A0 manifest namespace. The sentinel path is never written by preflight.
    sentinel = DeploymentPaths(
        base_model_dir=paths.base_model_dir,
        adapter_path=paths.adapter_path,
        output_root=paths.output_root / "_world_v0_static_identity_only",
    )
    return verify_static_deployment(
        sentinel,
        expected_git_commit=expected_git_commit,
        repository_root=REPOSITORY_ROOT,
    )


def _compile_cohort(*, store, profile: ModelProfile, policy: GenerationPolicy):
    context_policy = build_context_policy()
    cohort = []
    for context_class in A0_CONTEXT_CLASSES:
        for case_index in range(A0_CASES_PER_CONTEXT_CLASS):
            compiled = compile_r3_fixture(
                context_class,
                case_index,
                policy=context_policy,
                model_profile_id=profile.profile_id,
                generation_policy_id=policy.policy_id,
                generation_seed_id=A0_GENERATION_SEED_ID,
                artifact_store=store,
            )
            cohort.append((context_class, case_index, compiled))
    if len(cohort) != A0_ATTEMPTS_PER_TREATMENT:
        raise AssertionError("A0 cohort size drifted from preregistration")
    return tuple(cohort)


def _constraint(runtime, treatment_name: str, *, branch_order=None):
    if treatment_name in {"I0", "I1"}:
        return None
    if treatment_name == "I2":
        schema = action_codec_json_schema()
    elif treatment_name == "I3" or treatment_name.startswith("I3_ORDER_"):
        schema = typed_action_codec_json_schema(action_order=branch_order)
    else:
        raise ValueError(treatment_name)
    return build_transformers_constraint(runtime.tokenizer, schema=schema)


def _evidence_complete(store, result, rendered_expected: bytes) -> bool:
    evidence = result.evidence
    refs = (
        evidence.context_pack_ref,
        evidence.rendered_input_ref,
        evidence.raw_text_ref,
        evidence.raw_generation_ref,
    )
    try:
        resolved = tuple(store.resolve(ref) for ref in refs)
    except Exception:
        return False
    return (
        bool(all(ref.digest for ref in refs))
        and resolved[1] == rendered_expected
        and resolved[2] == result.raw_generation.raw_text.encode("utf-8")
    )


def _artifact_ref(digest: str) -> ArtifactRef:
    return ArtifactRef(ArtifactId(f"artifact-{digest}"), digest)


def _run_treatment(
    *,
    runtime,
    profile,
    policy,
    store,
    cohort,
    treatment_name: str,
    treatment,
    branch_order=None,
):
    prefix_allowed_tokens_fn = _constraint(
        runtime, treatment_name, branch_order=branch_order
    )
    runner = RealCognitionDryRunner(
        runtime,
        profile,
        policy,
        store,
        generation_seed=A0_GENERATION_SEED,
        interface_treatment=treatment,
        prefix_allowed_tokens_fn=prefix_allowed_tokens_fn,
    )
    details = []
    class_valid: Counter[str] = Counter()
    class_total: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    candidate_labels: list[str | None] = []
    action_distribution: Counter[str] = Counter()
    candidate_distribution: Counter[str] = Counter()
    codec_valid = 0
    domain_valid = 0
    first_token_eos = 0
    evidence_complete = 0

    for context_class, case_index, compiled in cohort:
        result = runner.run(compiled)
        evidence = result.evidence
        raw = result.raw_generation
        class_name = context_class.value
        class_total[class_name] += 1
        statuses[evidence.parse_status.value] += 1
        candidate = evidence.candidate
        candidate_label = candidate.action_label if candidate is not None else None
        candidate_labels.append(candidate_label)
        if candidate is not None:
            codec_valid += 1
            candidate_distribution[candidate_label] += 1
        if evidence.action_intent is not None:
            domain_valid += 1
            class_valid[class_name] += 1
            action_distribution[evidence.action_intent.kind.value] += 1
        ids = tuple(raw.token_ids or ())
        is_first_eos = ids[:1] == (100257,) and raw.finish_reason == "eos_token"
        first_token_eos += int(is_first_eos)
        rendered_expected = treatment.render(compiled.rendered_input)
        complete = _evidence_complete(store, result, rendered_expected)
        evidence_complete += int(complete)
        details.append(
            {
                "context_class": class_name,
                "case_index": case_index,
                "context_hash": evidence.context_hash,
                "context_pack_ref": evidence.context_pack_ref.digest,
                "rendered_input_ref": evidence.rendered_input_ref.digest,
                "raw_text_ref": evidence.raw_text_ref.digest,
                "raw_generation_ref": evidence.raw_generation_ref.digest,
                "evidence_ref": result.evidence_ref.digest,
                "parse_status": evidence.parse_status.value,
                "candidate_label": candidate_label,
                "intent_kind": (
                    evidence.action_intent.kind.value
                    if evidence.action_intent is not None
                    else None
                ),
                "finish_reason": raw.finish_reason,
                "generated_token_count": len(ids),
                "first_token_eos": is_first_eos,
                "evidence_complete": complete,
            }
        )

    # Repeat one exact request after the cohort. This is not a retry and does
    # not replace the primary observation.
    first_compiled = cohort[0][2]
    first_primary_ref = details[0]["raw_generation_ref"]
    repeat = runner.run(first_compiled)
    primary_raw = json.loads(
        store.resolve(_artifact_ref(first_primary_ref)).decode("utf-8")
    )
    exact_repeat_equal = (
        primary_raw.get("raw_text") == repeat.raw_generation.raw_text
        and tuple(primary_raw.get("token_ids") or ())
        == tuple(repeat.raw_generation.token_ids or ())
        and primary_raw.get("generation_id") == repeat.raw_generation.generation_id
    )

    metrics = A0TreatmentMetrics(
        treatment=treatment_name,
        attempts=len(cohort),
        codec_valid=codec_valid,
        domain_valid=domain_valid,
        first_token_eos=first_token_eos,
        evidence_complete=evidence_complete,
        infrastructure_failures=0,
        exact_repeat_equal=exact_repeat_equal,
        context_class_domain_valid=tuple(
            (
                context_class.value,
                class_valid[context_class.value],
                class_total[context_class.value],
            )
            for context_class in A0_CONTEXT_CLASSES
        ),
    )
    detail_payload = {
        "admission_id": A0_ADMISSION_ID,
        "treatment": treatment_name,
        "treatment_id": treatment.treatment_id,
        "treatment_version": treatment.version,
        "treatment_digest": treatment.digest,
        "constraint_policy_id": treatment.constraint_policy_id,
        "branch_order": list(branch_order) if branch_order is not None else None,
        "statuses": dict(sorted(statuses.items())),
        "candidate_distribution": dict(sorted(candidate_distribution.items())),
        "action_distribution": dict(sorted(action_distribution.items())),
        "metrics": metrics.as_dict(),
        "evaluation": evaluate_treatment(metrics),
        "attempts": details,
        "repeat_evidence_ref": repeat.evidence_ref.digest,
    }
    detail_ref = store.put_bytes(
        canonical_bytes(detail_payload),
        media_type="application/json",
        contract_id="a0-treatment-details-1.0.0",
    )
    return metrics, detail_ref, tuple(candidate_labels), detail_payload


def _final_manifest(
    planned: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    final = dict(planned)
    final["status"] = "COMPLETE"
    final["result"] = result
    final["manifest_digest"] = canonical_digest(final)
    return final


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--base-model-dir", type=Path, required=True)
    parser.add_argument("--adapter-path", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--expected-git-commit", required=True)
    args = parser.parse_args()

    paths = DeploymentPaths(
        base_model_dir=args.base_model_dir,
        adapter_path=args.adapter_path,
        output_root=args.output_root,
    )
    preflight = _static_preflight(paths, args.expected_git_commit)
    commit = _git_head()
    planned = _planned_manifest(paths=paths, git_commit=commit)
    existing = inspect_existing_manifest(
        paths.output_root, planned["manifest_identity_digest"]
    )

    if args.validate_only:
        print(
            json.dumps(
                {
                    "status": "A0_STATIC_PREFLIGHT_OK",
                    "preflight": preflight,
                    "planned_manifest_identity_digest": planned[
                        "manifest_identity_digest"
                    ],
                    "existing_manifest_status": existing,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0

    if existing == "ALREADY_COMPLETE":
        manifest = json.loads(
            (paths.output_root / "manifest.json").read_text(encoding="utf-8")
        )
        print(
            json.dumps(
                {"status": "ALREADY_COMPLETE", "manifest": manifest},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0

    environment = ensure_execute_environment()
    store = FileSystemArtifactStore(paths.output_root / "cas")
    profile = _model_profile(paths.base_model_dir)
    policy = _generation_policy()
    loader = PeftTransformersLoader(
        base_model_dir=paths.base_model_dir,
        adapter_path=paths.adapter_path,
    )
    runtime = loader(profile)
    cohort = _compile_cohort(store=store, profile=profile, policy=policy)

    treatments = {
        "I0": I0_STRICT_FREE_GENERATION,
        "I1": I1_NEUTRAL_CODEC_SCAFFOLD,
        "I2": I2_SYNTAX_CONSTRAINED_CODEC,
        "I3": I3_CONDITIONAL_TYPED_CODEC,
    }
    metrics_by_treatment: dict[str, A0TreatmentMetrics] = {}
    treatment_results = {}
    for treatment_name in A0_TREATMENT_ORDER:
        metrics, detail_ref, candidate_labels, detail_payload = _run_treatment(
            runtime=runtime,
            profile=profile,
            policy=policy,
            store=store,
            cohort=cohort,
            treatment_name=treatment_name,
            treatment=treatments[treatment_name],
        )
        metrics_by_treatment[treatment_name] = metrics
        treatment_results[treatment_name] = {
            "metrics": metrics.as_dict(),
            "evaluation": evaluate_treatment(metrics),
            "detail_ref": detail_ref.digest,
            "candidate_labels_digest": canonical_digest(candidate_labels),
            "candidate_distribution": detail_payload["candidate_distribution"],
            "action_distribution": detail_payload["action_distribution"],
        }

    minimal_core = choose_minimal_treatment(metrics_by_treatment)
    branch_audit = None
    final_selected = minimal_core
    if minimal_core == "I3":
        order_metrics = []
        order_labels = []
        order_results = []
        for index, order in enumerate(I3_BRANCH_ORDERS):
            treatment = i3_branch_order_treatment(index)
            metrics, detail_ref, labels, detail_payload = _run_treatment(
                runtime=runtime,
                profile=profile,
                policy=policy,
                store=store,
                cohort=cohort,
                treatment_name=f"I3_ORDER_{index}",
                treatment=treatment,
                branch_order=order,
            )
            order_metrics.append(metrics)
            order_labels.append(labels)
            order_results.append(
                {
                    "order_index": index,
                    "order": list(order),
                    "metrics": metrics.as_dict(),
                    "evaluation": evaluate_treatment(metrics),
                    "detail_ref": detail_ref.digest,
                    "candidate_distribution": detail_payload[
                        "candidate_distribution"
                    ],
                    "action_distribution": detail_payload[
                        "action_distribution"
                    ],
                }
            )
        branch_audit = evaluate_i3_branch_order_audit(
            order_metrics, order_labels
        )
        branch_audit["orders"] = order_results
        if not branch_audit["pass"]:
            final_selected = None

    minimal_motor = next(
        (
            name
            for name in A0_TREATMENT_ORDER
            if bool(evaluate_treatment(metrics_by_treatment[name])["motor_pass"])
        ),
        None,
    )
    result = {
        "status": (
            "ADMISSION_PASS" if final_selected is not None else "ADMISSION_FAIL"
        ),
        "environment": environment,
        "preflight": preflight,
        "attempts_per_treatment": A0_ATTEMPTS_PER_TREATMENT,
        "minimal_motor_treatment": minimal_motor,
        "minimal_autonomous_core_treatment": minimal_core,
        "selected_treatment": final_selected,
        "founder_freeze": "NOT_ESTABLISHED_BY_A0_ALONE",
        "treatments": treatment_results,
        "i3_branch_order_audit": branch_audit,
        "action_distribution_used_for_admission": False,
        "prior_discovery_used_in_denominator": False,
    }
    manifest = _final_manifest(planned, result)
    write_status = write_immutable_manifest(paths.output_root, manifest)
    print(
        json.dumps(
            {
                "status": result["status"],
                "selected_treatment": final_selected,
                "minimal_motor_treatment": minimal_motor,
                "manifest": str(paths.output_root / "manifest.json"),
                "manifest_digest": manifest["manifest_digest"],
                "write_status": write_status,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
