#!/usr/bin/env python3
"""Run WORLD P1 context-sensitive policy study on exact FA-v1.

P1 performs two researcher-side measurements over the same frozen R3 context
cohort: canonical I3 generation and teacher-forced action-label ranking. It
never commits simulation state and never treats a particular action as good.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from alifelm.domain import ArtifactId, ArtifactRef, Duration  # noqa: E402
from alifelm.kernel import SimulationRun  # noqa: E402
from alifelm.model import (  # noqa: E402
    CodecValidityStatus,
    CommitValidityStatus,
    DomainValidityStatus,
    GenerationPolicy,
    I3_CONDITIONAL_TYPED_CODEC,
    ModelProfile,
    PeftTransformersLoader,
    RealCognitionDryRunner,
    WORLD_V0_FA_V1_IDENTITY,
    build_transformers_constraint,
    compile_r3_fixture,
    evaluate_typed_codec,
    typed_action_codec_json_schema,
    typed_codec_evaluation_bytes,
    validate_live_runtime_identity,
)
from alifelm.model.action_diagnostics import (  # noqa: E402
    action_label_score_bytes,
    score_action_labels,
)
from alifelm.model.p1_policy import (  # noqa: E402
    P1_CASES_PER_CONTEXT,
    P1_CONTEXT_CLASSES,
    P1_MATCHED_SENSITIVITY_RATE_MIN,
    P1_NONCONTROL_TVD_CLASSES_MIN,
    P1_STUDY_ID,
    P1_TVD_MIN,
    classify_p1,
    evaluate_context_sensitivity,
)
from alifelm.model.r3_fixtures import R3ContextClass  # noqa: E402
from alifelm.model.world_v0_smoke import (  # noqa: E402
    DeploymentPaths,
    SmokePreflightError,
    build_context_policy,
    canonical_bytes,
    canonical_digest,
    ensure_execute_environment,
    verify_static_deployment,
)
from alifelm.persistence import FileSystemArtifactStore  # noqa: E402


P1_RUNNER_VERSION = "1.0.0"
P1_PREREG_COMMIT = "eac7d109ea8f84ece9ac4c0f57e4e1882a55e9eb"
P1_CONFIG_FILENAME = "WORLD_P1_CONTEXT_SENSITIVE_POLICY_CONFIG_V1.json"
P1_GENERATION_POLICY_ID = "WORLD_P1_GREEDY_I3_V1"
P1_GENERATION_SEED_ID = "WORLD_P1_SEED_V1"
P1_GENERATION_SEED = 35020260831
P1_PROFILE_ID = "WORLD_P1_FA_V1_BF16"
P1_MAX_NEW_TOKENS = 128
P1_ATTEMPTS = len(P1_CONTEXT_CLASSES) * P1_CASES_PER_CONTEXT
P1_CONTEXT_ENUMS = tuple(R3ContextClass(name) for name in P1_CONTEXT_CLASSES)


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


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_config(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    config = json.loads(raw.decode("utf-8"))
    if config.get("study_id") != P1_STUDY_ID:
        raise SmokePreflightError("P1 config study_id drift")
    if config.get("preregistration_commit") != P1_PREREG_COMMIT:
        raise SmokePreflightError("P1 preregistration commit drift")
    cohort = config.get("cohort", {})
    if tuple(cohort.get("context_classes", ())) != P1_CONTEXT_CLASSES:
        raise SmokePreflightError("P1 context cohort drift")
    if cohort.get("cases_per_context") != P1_CASES_PER_CONTEXT:
        raise SmokePreflightError("P1 case-count drift")
    gates = config.get("gates", {})
    for name in ("G1", "G2"):
        gate = gates.get(name, {})
        if gate.get("matched_sensitivity_rate_min") != P1_MATCHED_SENSITIVITY_RATE_MIN:
            raise SmokePreflightError(f"P1 {name} matched sensitivity threshold drift")
        if gate.get("tvd_min") != P1_TVD_MIN:
            raise SmokePreflightError(f"P1 {name} TVD threshold drift")
        if gate.get("nonquiet_tvd_classes_min") != P1_NONCONTROL_TVD_CLASSES_MIN:
            raise SmokePreflightError(f"P1 {name} TVD class threshold drift")
    return config, _sha256(raw)


def _generation_policy() -> GenerationPolicy:
    return GenerationPolicy(
        policy_id=P1_GENERATION_POLICY_ID,
        version="1.0.0",
        max_new_tokens=P1_MAX_NEW_TOKENS,
        do_sample=False,
        temperature=None,
        top_p=None,
        top_k=None,
        repetition_penalty=1.0,
        seed_id=P1_GENERATION_SEED_ID,
        stop_policy_id=None,
    )


def _model_profile(base_model_dir: Path) -> ModelProfile:
    identity = WORLD_V0_FA_V1_IDENTITY
    return ModelProfile(
        profile_id=P1_PROFILE_ID,
        profile_version="1.0.0",
        model_identifier=str(base_model_dir),
        model_revision=identity.base_model_revision,
        model_digest=identity.base_checkpoint_sha256,
        tokenizer_identifier=str(base_model_dir),
        tokenizer_revision=identity.tokenizer_revision,
        tokenizer_digest=identity.tokenizer_digest,
        model_class="AUTO_CAUSAL_LM",
        generation_policy_id=P1_GENERATION_POLICY_ID,
        device="cuda:0",
        dtype="bfloat16",
        adapter_ref=ArtifactRef(ArtifactId("F0_FA_V1_FORMAL"), identity.adapter_sha256),
        trust_remote_code=False,
        add_special_tokens=True,
    )


def _static_preflight(paths: DeploymentPaths, expected_git_commit: str) -> dict[str, Any]:
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
    for context_class in P1_CONTEXT_ENUMS:
        for case_index in range(P1_CASES_PER_CONTEXT):
            compiled = compile_r3_fixture(
                context_class,
                case_index,
                policy=context_policy,
                model_profile_id=profile.profile_id,
                generation_policy_id=policy.policy_id,
                generation_seed_id=P1_GENERATION_SEED_ID,
                artifact_store=store,
            )
            cohort.append((context_class, case_index, compiled))
    if len(cohort) != P1_ATTEMPTS:
        raise AssertionError("P1 cohort size drifted")
    return tuple(cohort)


def _diagnostic_run(compiled) -> SimulationRun:
    snapshot = compiled.opportunity.snapshot
    return SimulationRun(
        run_id=snapshot.run_id,
        lifespan_ticks=Duration(100),
        maturity_delay_ticks=Duration(0),
        refractory_interval_ticks=Duration(0),
        _snapshot=snapshot,
    )


def _evidence_complete(store, result, rendered_expected: bytes) -> bool:
    evidence = result.evidence
    refs = (
        evidence.context_pack_ref,
        evidence.rendered_input_ref,
        evidence.raw_text_ref,
        evidence.raw_generation_ref,
        result.evidence_ref,
    )
    try:
        resolved = tuple(store.resolve(ref) for ref in refs)
    except Exception:
        return False
    return (
        all(bool(ref.digest) for ref in refs)
        and resolved[1] == rendered_expected
        and resolved[2] == result.raw_generation.raw_text.encode("utf-8")
        and all(bool(value) for value in (resolved[0], resolved[3], resolved[4]))
    )


def _planned_document(
    *, paths: DeploymentPaths, git_commit: str, config_sha256: str
) -> dict[str, Any]:
    identity = WORLD_V0_FA_V1_IDENTITY
    document = {
        "study_id": P1_STUDY_ID,
        "schema_version": "1.0.0",
        "runner_version": P1_RUNNER_VERSION,
        "status": "PLANNED",
        "git_commit": git_commit,
        "preregistration_commit": P1_PREREG_COMMIT,
        "config_sha256": config_sha256,
        "deployment": {
            "base_model_dir": str(paths.base_model_dir),
            "adapter_path": str(paths.adapter_path),
            "base_revision": identity.base_model_revision,
            "base_checkpoint_sha256": identity.base_checkpoint_sha256,
            "tokenizer_digest": identity.tokenizer_digest,
            "adapter_sha256": identity.adapter_sha256,
        },
        "cohort": {
            "context_classes": list(P1_CONTEXT_CLASSES),
            "cases_per_context": P1_CASES_PER_CONTEXT,
            "attempts": P1_ATTEMPTS,
        },
        "measurements": [
            "CANONICAL_I3_GENERATION",
            "TEACHER_FORCED_ACTION_LABEL_RANKING",
        ],
        "no_state_commit": True,
    }
    document["identity_digest"] = canonical_digest(document)
    return document


def _execute(
    *,
    paths: DeploymentPaths,
    config: dict[str, Any],
    config_sha256: str,
    expected_git_commit: str,
) -> dict[str, Any]:
    if paths.output_root.exists() and any(paths.output_root.iterdir()):
        raise SmokePreflightError("P1 output root already exists and is non-empty")
    paths.output_root.mkdir(parents=True, exist_ok=True)
    planned = _planned_document(
        paths=paths, git_commit=_git_head(), config_sha256=config_sha256
    )
    (paths.output_root / "planned.json").write_bytes(canonical_bytes(planned))

    preflight = _static_preflight(paths, expected_git_commit)
    environment = ensure_execute_environment()
    store = FileSystemArtifactStore(paths.output_root / "cas")
    profile = _model_profile(paths.base_model_dir)
    policy = _generation_policy()
    validate_live_runtime_identity(profile, WORLD_V0_FA_V1_IDENTITY)
    loader = PeftTransformersLoader(
        base_model_dir=paths.base_model_dir,
        adapter_path=paths.adapter_path,
    )
    runtime = loader(profile)
    constraint = build_transformers_constraint(
        runtime.tokenizer, schema=typed_action_codec_json_schema()
    )
    runner = RealCognitionDryRunner(
        runtime,
        profile,
        policy,
        store,
        generation_seed=P1_GENERATION_SEED,
        interface_treatment=I3_CONDITIONAL_TYPED_CODEC,
        prefix_allowed_tokens_fn=constraint,
    )
    cohort = _compile_cohort(store=store, profile=profile, policy=policy)

    generated_by_context: dict[str, list[str]] = {
        name: [] for name in P1_CONTEXT_CLASSES
    }
    latent_by_context: dict[str, list[str]] = {
        name: [] for name in P1_CONTEXT_CLASSES
    }
    generated_distribution: dict[str, Counter[str]] = {
        name: Counter() for name in P1_CONTEXT_CLASSES
    }
    latent_distribution: dict[str, Counter[str]] = {
        name: Counter() for name in P1_CONTEXT_CLASSES
    }
    codec_valid = 0
    domain_valid = 0
    evidence_complete = 0
    first_token_eos = 0
    teacher_measurements = 0
    details = []

    for ordinal, (context_class, case_index, compiled) in enumerate(cohort, 1):
        context_name = context_class.value
        result = runner.run(compiled)
        evidence = result.evidence
        raw = result.raw_generation
        typed = evaluate_typed_codec(
            raw.raw_text,
            compiled.opportunity,
            _diagnostic_run(compiled),
        )
        typed_ref = store.put_bytes(
            typed_codec_evaluation_bytes(
                typed,
                generation_id=evidence.generation_id,
                context_hash=evidence.context_hash,
                treatment_id=I3_CONDITIONAL_TYPED_CODEC.treatment_id,
                treatment_version=I3_CONDITIONAL_TYPED_CODEC.version,
            ),
            media_type="application/json",
            contract_id="p1-typed-codec-diagnostic-1.0.0",
        )

        is_codec_valid = typed.codec_status is CodecValidityStatus.CODEC_VALID
        is_domain_valid = typed.domain_status is DomainValidityStatus.DOMAIN_VALID
        is_commit_valid = typed.commit_status is CommitValidityStatus.COMMIT_VALID
        codec_valid += int(is_codec_valid)
        domain_valid += int(is_domain_valid)
        candidate_label = (
            typed.candidate.action_label
            if is_codec_valid and typed.candidate is not None
            else "__INVALID__"
        )
        generated_by_context[context_name].append(candidate_label)
        generated_distribution[context_name][candidate_label] += 1

        ids = tuple(raw.token_ids or ())
        is_first_eos = ids[:1] == (100257,) and raw.finish_reason == "eos_token"
        first_token_eos += int(is_first_eos)
        rendered_expected = I3_CONDITIONAL_TYPED_CODEC.render(compiled.rendered_input)
        complete = _evidence_complete(store, result, rendered_expected)
        evidence_complete += int(complete)

        if compiled.artifact_ref is None:
            raise RuntimeError("P1 compiled context must have a CAS artifact reference")
        base_rendered_ref = store.put_bytes(
            compiled.rendered_input,
            media_type="text/plain; charset=utf-8",
            contract_id="p1-base-rendered-input-1.0.0",
        )
        score = score_action_labels(
            runtime,
            rendered_input=compiled.rendered_input,
            context_hash=evidence.context_hash,
            context_pack_ref=compiled.artifact_ref.digest,
            rendered_input_ref=base_rendered_ref.digest,
        )
        score_ref = store.put_bytes(
            action_label_score_bytes(score),
            media_type="application/json",
            contract_id="p1-action-label-score-1.0.0",
        )
        rank1 = next(value.model_label for value in score.scores if value.rank == 1)
        latent_by_context[context_name].append(rank1)
        latent_distribution[context_name][rank1] += 1
        teacher_measurements += 1

        details.append(
            {
                "ordinal": ordinal,
                "context_class": context_name,
                "case_index": case_index,
                "context_hash": evidence.context_hash,
                "context_pack_ref": compiled.artifact_ref.digest,
                "i3_rendered_input_ref": evidence.rendered_input_ref.digest,
                "base_rendered_input_ref": base_rendered_ref.digest,
                "raw_generation_ref": evidence.raw_generation_ref.digest,
                "evidence_ref": result.evidence_ref.digest,
                "typed_diagnostic_ref": typed_ref.digest,
                "score_ref": score_ref.digest,
                "codec_status": typed.codec_status.value,
                "domain_status": typed.domain_status.value,
                "commit_status": typed.commit_status.value,
                "commit_valid": is_commit_valid,
                "candidate_label": candidate_label,
                "latent_rank1_label": rank1,
                "latent_ranking": [
                    {
                        "label": value.model_label,
                        "rank": value.rank,
                        "total_log_probability": value.total_log_probability,
                        "mean_log_probability": value.mean_log_probability,
                    }
                    for value in score.scores
                ],
                "first_token_eos": is_first_eos,
                "evidence_complete": complete,
            }
        )
        if ordinal % 10 == 0 or ordinal == P1_ATTEMPTS:
            print(f"P1_PROGRESS {ordinal}/{P1_ATTEMPTS}", flush=True)

    first_primary_ref = details[0]["raw_generation_ref"]
    repeat = runner.run(cohort[0][2])
    exact_repeat_equal = repeat.evidence.raw_generation_ref.digest == first_primary_ref

    integrity_pass = (
        len(details) == P1_ATTEMPTS
        and codec_valid == P1_ATTEMPTS
        and domain_valid == P1_ATTEMPTS
        and evidence_complete == P1_ATTEMPTS
        and first_token_eos == 0
        and teacher_measurements == P1_ATTEMPTS
        and exact_repeat_equal
    )

    generated_metrics = (
        evaluate_context_sensitivity(generated_by_context) if codec_valid == P1_ATTEMPTS else None
    )
    latent_metrics = (
        evaluate_context_sensitivity(latent_by_context)
        if teacher_measurements == P1_ATTEMPTS
        else None
    )
    generated_pass = bool(generated_metrics and generated_metrics.passed)
    latent_pass = bool(latent_metrics and latent_metrics.passed)
    classification = classify_p1(
        integrity_pass=integrity_pass,
        generated_pass=generated_pass,
        latent_pass=latent_pass,
    )

    detail_payload = {
        "study_id": P1_STUDY_ID,
        "attempts": details,
    }
    detail_ref = store.put_bytes(
        canonical_bytes(detail_payload),
        media_type="application/json",
        contract_id="p1-attempt-details-1.0.0",
    )

    result = {
        "study_id": P1_STUDY_ID,
        "status": "P1_MEASUREMENT_COMPLETE" if integrity_pass else "P1_INTEGRITY_FAIL",
        "classification": classification,
        "git_commit": _git_head(),
        "preregistration_commit": P1_PREREG_COMMIT,
        "config_sha256": config_sha256,
        "environment": environment,
        "preflight": preflight,
        "gates": {
            "P1-G0": integrity_pass,
            "P1-G1": generated_pass if integrity_pass else None,
            "P1-G2": latent_pass if integrity_pass else None,
        },
        "integrity": {
            "attempts": len(details),
            "codec_valid": codec_valid,
            "domain_valid": domain_valid,
            "evidence_complete": evidence_complete,
            "first_token_eos": first_token_eos,
            "teacher_forced_measurements": teacher_measurements,
            "exact_first_repeat_equal": exact_repeat_equal,
            "repeat_raw_generation_ref": repeat.evidence.raw_generation_ref.digest,
        },
        "generated_sensitivity": (
            generated_metrics.as_dict() if generated_metrics is not None else None
        ),
        "latent_rank1_sensitivity": (
            latent_metrics.as_dict() if latent_metrics is not None else None
        ),
        "generated_distribution_by_context": {
            name: dict(sorted(counter.items()))
            for name, counter in generated_distribution.items()
        },
        "latent_rank1_distribution_by_context": {
            name: dict(sorted(counter.items()))
            for name, counter in latent_distribution.items()
        },
        "detail_ref": detail_ref.digest,
        "founder_freeze": "NOT_ESTABLISHED_BY_P1_ALONE",
        "nontrivial_generated_policy_competence_established": (
            True if integrity_pass and generated_pass else False
        ),
    }
    result["result_digest"] = canonical_digest(result)
    (paths.output_root / "summary.json").write_bytes(canonical_bytes(result))
    return result


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

    config, config_sha256 = _load_config(args.config)
    paths = DeploymentPaths(
        base_model_dir=args.base_model_dir,
        adapter_path=args.adapter_path,
        output_root=args.output_root,
    )
    preflight = _static_preflight(paths, args.expected_git_commit)
    if args.validate_only:
        print(
            json.dumps(
                {
                    "status": "P1_STATIC_PREFLIGHT_OK",
                    "git_commit": _git_head(),
                    "config_sha256": config_sha256,
                    "preflight": preflight,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0

    try:
        result = _execute(
            paths=paths,
            config=config,
            config_sha256=config_sha256,
            expected_git_commit=args.expected_git_commit,
        )
    except Exception as error:
        paths.output_root.mkdir(parents=True, exist_ok=True)
        failure = {
            "study_id": P1_STUDY_ID,
            "status": "P1_EXECUTION_EXCEPTION",
            "git_commit": _git_head(),
            "error_type": type(error).__name__,
            "error_message": str(error),
        }
        (paths.output_root / "failure.json").write_bytes(canonical_bytes(failure))
        raise

    print(
        json.dumps(
            {
                "status": result["status"],
                "classification": result["classification"],
                "gates": result["gates"],
                "generated_distribution_by_context": result[
                    "generated_distribution_by_context"
                ],
                "latent_rank1_distribution_by_context": result[
                    "latent_rank1_distribution_by_context"
                ],
                "summary": str(paths.output_root / "summary.json"),
                "result_digest": result["result_digest"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if result["gates"]["P1-G0"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
