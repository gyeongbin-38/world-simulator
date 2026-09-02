#!/usr/bin/env python3
"""Run frozen WORLD P1B adapter-selector decomposition.

P1B compares BASE_ONLY with exact FA-v1 on a held-out R3 cohort using
teacher-forced action-label scores and a payload-free label-only selector. It
never commits simulation state and never updates model weights.
"""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from alifelm.domain import ArtifactId, ArtifactRef  # noqa: E402
from alifelm.model.action_diagnostics import (  # noqa: E402
    action_label_score_bytes,
    score_action_labels,
)
from alifelm.model.adapter import (  # noqa: E402
    generation_request_for,
    validate_raw_generation_result,
)
from alifelm.model.evidence import raw_generation_bytes  # noqa: E402
from alifelm.model.generation import GenerationPolicy  # noqa: E402
from alifelm.model.p1b_metrics import (  # noqa: E402
    ACTION_LABELS,
    DIRECTED_LABELS,
    P1B_CONTEXT_CLASSES,
    P1B_HELDOUT_CASES,
    P1B_PAIRED_CASES,
    P1B_STUDY_ID,
    WAIT_LABEL,
    evaluate_adapter_structural_gain,
    evaluate_label_sensitivity,
    evaluate_structural_presence,
    evaluate_wait_amplification,
    evaluate_wait_dominance,
    score_structure,
    structural_contrasts,
)
from alifelm.model.peft_runtime import PeftTransformersLoader  # noqa: E402
from alifelm.model.profile import ModelProfile  # noqa: E402
from alifelm.model.r3_fixtures import R3ContextClass, compile_r3_fixture  # noqa: E402
from alifelm.model.treatments import (  # noqa: E402
    InterfaceMode,
    InterfaceTreatment,
    build_transformers_constraint,
)
from alifelm.model.transformers_backend import (  # noqa: E402
    ModelLoadError,
    TransformersModelRuntime,
)
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


P1B_RUNNER_VERSION = "1.0.0"
P1B_PREREG_COMMIT = "13634bc13122f8b194a4bdba0e6feadee0f0e54d"
P1B_CONFIG_FILENAME = "WORLD_P1B_ADAPTER_SELECTOR_DECOMPOSITION_CONFIG_V1.json"
P1B_GENERATION_POLICY_ID = "WORLD_P1B_LABEL_ONLY_GREEDY_V1"
P1B_GENERATION_SEED_ID = "WORLD_P1B_GREEDY_SEED_V1"
P1B_GENERATION_SEED = 35020260831
P1B_MAX_NEW_TOKENS = 48
P1B_BASE_PROFILE_ID = "WORLD_P1B_BASE_ONLY_BF16"
P1B_FA_PROFILE_ID = "WORLD_P1B_FA_V1_BF16"
P1B_BASE_MODEL_REVISION = "48d788eca847d4d7548f375ad03d3c9312f6139e"
P1B_BASE_CHECKPOINT_SHA256 = "36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f"
P1B_TOKENIZER_DIGEST = "c448b9e69576a2af5fccdb905c4d6c9f6c0d06509b15d2459a3bc92bb33d42ff"
P1B_ADAPTER_SHA256 = "46917511362243be67e0783ddb7411a96f26613c1083bc4f95117d910d0998ec"
P1B_ADAPTER_CONFIG_SHA256 = "687100a0b6340b6096ca1e86066d3c13224b3c8e14ce9fb1b0cf78a52a8bdb7d"
P1B_PIP_FREEZE_SHA256 = "a98b9c11baf90a5e7717b1f108029838e9c917d46d1f499bf93e9adffad087bf"
P1_CANONICAL_SUMMARY_SHA256 = "3d0627c3dbe874a3da512c2a1273f1bfb8069cbf0cab069a79de5b7858a07bc1"
P1_CANONICAL_RESULT_DIGEST = "90552c4bc38cdfbc882d96954c0f00d8cdb193896cc686eed4b70788c213b847"
HELDOUT_START = 1000
HELDOUT_END = 1031
PAIRED_START = 0
PAIRED_END = 15
CONTEXT_ENUMS = tuple(R3ContextClass(name) for name in P1B_CONTEXT_CLASSES)

LABEL_ONLY_SCHEMA = {
    "type": "object",
    "properties": {"action_label": {"type": "string", "enum": list(ACTION_LABELS)}},
    "required": ["action_label"],
    "additionalProperties": False,
}
LABEL_ONLY_TREATMENT = InterfaceTreatment(
    treatment_id="world-p1b-label-only-selector",
    version="1.0.0",
    mode=InterfaceMode.I4,
    completion_suffix="\nAction selection JSON:\n",
    constraint_policy_id="world-p1b-label-only-action-json-v1",
)


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
    if config.get("study_id") != P1B_STUDY_ID:
        raise SmokePreflightError("P1B config study_id drift")
    if config.get("preregistration_commit") != P1B_PREREG_COMMIT:
        raise SmokePreflightError("P1B preregistration commit drift")
    if config.get("model_conditions") != ["BASE_ONLY", "FA_V1"]:
        raise SmokePreflightError("P1B model-condition drift")
    if tuple(config.get("context_classes", ())) != P1B_CONTEXT_CLASSES:
        raise SmokePreflightError("P1B context-class drift")
    heldout = config.get("cohorts", {}).get("heldout", {})
    paired = config.get("cohorts", {}).get("paired_p1_interface", {})
    if (
        heldout.get("case_index_start") != HELDOUT_START
        or heldout.get("case_index_end") != HELDOUT_END
        or heldout.get("cases_per_context") != P1B_HELDOUT_CASES
        or heldout.get("contexts") != 160
    ):
        raise SmokePreflightError("P1B held-out cohort drift")
    if (
        paired.get("case_index_start") != PAIRED_START
        or paired.get("case_index_end") != PAIRED_END
        or paired.get("cases_per_context") != P1B_PAIRED_CASES
        or paired.get("contexts") != 80
    ):
        raise SmokePreflightError("P1B paired cohort drift")
    if tuple(config.get("action_labels", ())) != ACTION_LABELS:
        raise SmokePreflightError("P1B action-label drift")
    selector = config.get("label_only_selector", {})
    if selector.get("schema") != LABEL_ONLY_SCHEMA:
        raise SmokePreflightError("P1B label-only schema drift")
    generation = selector.get("generation", {})
    if (
        generation.get("max_new_tokens") != P1B_MAX_NEW_TOKENS
        or generation.get("seed") != P1B_GENERATION_SEED
        or generation.get("seed_id") != P1B_GENERATION_SEED_ID
        or generation.get("do_sample") is not False
    ):
        raise SmokePreflightError("P1B generation policy drift")
    thresholds = config.get("thresholds", {})
    expected_thresholds = {
        "P1B_G1": {"overall_wait_rate_min": 0.95, "per_context_wait_rate_min": 0.90},
        "P1B_G2": {"positive_fraction_min": 0.75, "median_strictly_positive": True},
        "P1B_G3": {
            "positive_fraction_min": 0.75,
            "median_strictly_positive": True,
            "structural_contrasts_required": 2,
            "structural_contrasts_total": 3,
        },
        "P1B_G4": {
            "positive_fraction_min": 0.75,
            "median_strictly_positive": True,
            "adapter_gain_contrasts_required": 2,
            "adapter_gain_contrasts_total": 3,
        },
        "P1B_G5": {
            "matched_sensitivity_rate_min": 0.25,
            "tvd_min": 0.25,
            "nonquiet_tvd_classes_min": 2,
        },
    }
    if thresholds != expected_thresholds:
        raise SmokePreflightError("P1B threshold drift")
    return config, _sha256(raw)


def _generation_policy() -> GenerationPolicy:
    return GenerationPolicy(
        policy_id=P1B_GENERATION_POLICY_ID,
        version="1.0.0",
        max_new_tokens=P1B_MAX_NEW_TOKENS,
        do_sample=False,
        temperature=None,
        top_p=None,
        top_k=None,
        repetition_penalty=1.0,
        seed_id=P1B_GENERATION_SEED_ID,
        stop_policy_id=None,
    )


def _profile(base_model_dir: Path, *, condition: str) -> ModelProfile:
    if condition not in {"BASE_ONLY", "FA_V1"}:
        raise ValueError(condition)
    adapter_ref = (
        None
        if condition == "BASE_ONLY"
        else ArtifactRef(ArtifactId("F0_FA_V1_FORMAL"), P1B_ADAPTER_SHA256)
    )
    return ModelProfile(
        profile_id=P1B_BASE_PROFILE_ID if condition == "BASE_ONLY" else P1B_FA_PROFILE_ID,
        profile_version="1.0.0",
        model_identifier=str(base_model_dir),
        model_revision=P1B_BASE_MODEL_REVISION,
        model_digest=P1B_BASE_CHECKPOINT_SHA256,
        tokenizer_identifier=str(base_model_dir),
        tokenizer_revision=P1B_BASE_MODEL_REVISION,
        tokenizer_digest=P1B_TOKENIZER_DIGEST,
        model_class="AUTO_CAUSAL_LM",
        generation_policy_id=P1B_GENERATION_POLICY_ID,
        device="cuda:0",
        dtype="bfloat16",
        adapter_ref=adapter_ref,
        trust_remote_code=False,
        add_special_tokens=True,
    )


def _static_preflight(paths: DeploymentPaths, expected_git_commit: str) -> dict[str, Any]:
    sentinel = DeploymentPaths(
        base_model_dir=paths.base_model_dir,
        adapter_path=paths.adapter_path,
        output_root=paths.output_root / "_world_v0_static_identity_only",
    )
    result = verify_static_deployment(
        sentinel,
        expected_git_commit=expected_git_commit,
        repository_root=REPOSITORY_ROOT,
    )
    if result["base_checkpoint_sha256"] != P1B_BASE_CHECKPOINT_SHA256:
        raise SmokePreflightError("P1B base checkpoint identity drift")
    if result["tokenizer_digest"] != P1B_TOKENIZER_DIGEST:
        raise SmokePreflightError("P1B tokenizer identity drift")
    if result["adapter_sha256"] != P1B_ADAPTER_SHA256:
        raise SmokePreflightError("P1B adapter identity drift")
    if result["adapter_config_sha256"] != P1B_ADAPTER_CONFIG_SHA256:
        raise SmokePreflightError("P1B adapter config identity drift")
    return result


def _verify_p1_archive(p1_root: Path) -> dict[str, Any]:
    summary_path = p1_root / "summary.json"
    data = summary_path.read_bytes()
    digest = _sha256(data)
    if digest != P1_CANONICAL_SUMMARY_SHA256:
        raise SmokePreflightError(
            f"P1 canonical summary drift: expected {P1_CANONICAL_SUMMARY_SHA256}, got {digest}"
        )
    summary = json.loads(data.decode("utf-8"))
    if summary.get("result_digest") != P1_CANONICAL_RESULT_DIGEST:
        raise SmokePreflightError("P1 canonical result digest drift")
    if summary.get("gates") != {"P1-G0": True, "P1-G1": False, "P1-G2": False}:
        raise SmokePreflightError("P1 frozen gate result drift")
    generated = summary.get("generated_distribution_by_context", {})
    expected = {name: {WAIT_LABEL: 16} for name in P1B_CONTEXT_CLASSES}
    if generated != expected:
        raise SmokePreflightError("P1 archived I3 distribution drift")
    return {
        "summary_sha256": digest,
        "result_digest": summary["result_digest"],
        "gates": summary["gates"],
        "generated_distribution_by_context": generated,
    }


def _compile_cohort(
    *,
    store: FileSystemArtifactStore,
    profile: ModelProfile,
    policy: GenerationPolicy,
    case_start: int,
    case_end: int,
):
    context_policy = build_context_policy()
    rows = []
    for context_class in CONTEXT_ENUMS:
        for case_index in range(case_start, case_end + 1):
            compiled = compile_r3_fixture(
                context_class,
                case_index,
                policy=context_policy,
                model_profile_id=profile.profile_id,
                generation_policy_id=policy.policy_id,
                generation_seed_id=P1B_GENERATION_SEED_ID,
                artifact_store=store,
            )
            rows.append((context_class.value, case_index, compiled))
    expected = len(P1B_CONTEXT_CLASSES) * (case_end - case_start + 1)
    if len(rows) != expected:
        raise AssertionError("P1B cohort size drift")
    return tuple(rows)


def _cohort_map(cohort) -> dict[tuple[str, int], Any]:
    return {(context, case, compiled): None for context, case, compiled in ()} if False else {
        (context, case): compiled for context, case, compiled in cohort
    }


def _verify_identical_inputs(base_cohort, fa_cohort) -> tuple[bool, list[dict[str, Any]]]:
    base = _cohort_map(base_cohort)
    fa = _cohort_map(fa_cohort)
    if set(base) != set(fa):
        raise SmokePreflightError("P1B B0/B1 cohort key mismatch")
    details = []
    all_equal = True
    for key in sorted(base):
        left = base[key].rendered_input
        right = fa[key].rendered_input
        equal = left == right
        all_equal = all_equal and equal
        details.append(
            {
                "context_class": key[0],
                "case_index": key[1],
                "base_rendered_sha256": _sha256(left),
                "fa_rendered_sha256": _sha256(right),
                "byte_identical": equal,
            }
        )
    return all_equal, details


def _load_base_runtime(profile: ModelProfile, base_model_dir: Path) -> TransformersModelRuntime:
    try:
        import torch
        import transformers

        tokenizer = transformers.AutoTokenizer.from_pretrained(
            str(base_model_dir), local_files_only=True, trust_remote_code=False
        )
        for name, expected in (
            ("bos_token_id", 100257),
            ("eos_token_id", 100257),
            ("pad_token_id", 100277),
        ):
            if getattr(tokenizer, name, None) != expected:
                raise ModelLoadError(f"BASE_ONLY tokenizer {name} identity mismatch")
        kwargs: dict[str, Any] = {
            "local_files_only": True,
            "trust_remote_code": False,
        }
        major = int(str(transformers.__version__).split(".", 1)[0])
        kwargs["dtype" if major >= 5 else "torch_dtype"] = torch.bfloat16
        model = transformers.AutoModelForCausalLM.from_pretrained(str(base_model_dir), **kwargs)
        model = model.to(profile.device)
        model.eval()
        for parameter in model.parameters():
            parameter.requires_grad_(False)
        if model.training or any(parameter.requires_grad for parameter in model.parameters()):
            raise ModelLoadError("BASE_ONLY model must be eval and frozen")
        return TransformersModelRuntime.from_components(
            profile, tokenizer=tokenizer, model=model, torch_module=torch
        )
    except ModelLoadError:
        raise
    except Exception as error:
        raise ModelLoadError("failed to load exact BASE_ONLY runtime") from error


def _runtime_freeze_status(runtime: TransformersModelRuntime) -> dict[str, Any]:
    model = runtime.model
    parameters = tuple(model.parameters())
    trainable = sum(int(parameter.requires_grad) for parameter in parameters)
    return {
        "training": bool(getattr(model, "training", False)),
        "parameter_tensors": len(parameters),
        "trainable_parameter_tensors": trainable,
        "frozen": (not bool(getattr(model, "training", False)) and trainable == 0),
    }


def _score_equal(left, right) -> bool:
    left_values = {
        item.model_label: (item.token_ids, item.total_log_probability, item.mean_log_probability, item.rank)
        for item in left.scores
    }
    right_values = {
        item.model_label: (item.token_ids, item.total_log_probability, item.mean_log_probability, item.rank)
        for item in right.scores
    }
    return left_values == right_values


def _score_one(
    runtime: TransformersModelRuntime,
    compiled,
    store: FileSystemArtifactStore,
) -> tuple[Any, str, dict[str, Any]]:
    if compiled.artifact_ref is None:
        raise RuntimeError("P1B compiled context requires CAS artifact ref")
    rendered_ref = store.put_bytes(
        compiled.rendered_input,
        media_type="text/plain; charset=utf-8",
        contract_id="p1b-base-rendered-input-1.0.0",
    )
    score = score_action_labels(
        runtime,
        rendered_input=compiled.rendered_input,
        context_hash=compiled.context_pack.context_hash,
        context_pack_ref=compiled.artifact_ref.digest,
        rendered_input_ref=rendered_ref.digest,
    )
    score_bytes = action_label_score_bytes(score)
    score_ref = store.put_bytes(
        score_bytes,
        media_type="application/json",
        contract_id="p1b-action-label-score-1.0.0",
    )
    totals = {item.model_label: item.total_log_probability for item in score.scores}
    means = {item.model_label: item.mean_log_probability for item in score.scores}
    ranks = {item.model_label: item.rank for item in score.scores}
    token_ids = {item.model_label: list(item.token_ids) for item in score.scores}
    if set(totals) != set(ACTION_LABELS):
        raise RuntimeError("P1B teacher-forced score label-set drift")
    return score, score_ref.digest, {
        "score_ref": score_ref.digest,
        "rendered_input_ref": rendered_ref.digest,
        "totals": totals,
        "means": means,
        "ranks": ranks,
        "token_ids": token_ids,
    }


def _parse_label_only(raw_text: str) -> str:
    value = json.loads(raw_text)
    if not isinstance(value, dict) or set(value) != {"action_label"}:
        raise ValueError("label-only output must contain exactly action_label")
    label = value["action_label"]
    if label not in ACTION_LABELS:
        raise ValueError("label-only output contains unknown action label")
    return label


def _generate_label_only(
    runtime: TransformersModelRuntime,
    profile: ModelProfile,
    policy: GenerationPolicy,
    compiled,
    constraint,
    store: FileSystemArtifactStore,
) -> tuple[Any, str | None, str, dict[str, Any]]:
    request = generation_request_for(
        compiled,
        profile,
        policy,
        generation_seed=P1B_GENERATION_SEED,
        interface_treatment=LABEL_ONLY_TREATMENT,
        prefix_allowed_tokens_fn=constraint,
    )
    result = runtime.generate(request)
    validate_raw_generation_result(request, result, profile, policy)
    rendered_ref = store.put_bytes(
        request.rendered_input,
        media_type="text/plain; charset=utf-8",
        contract_id="p1b-label-only-rendered-input-1.0.0",
    )
    raw_text_ref = store.put_bytes(
        result.raw_text.encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        contract_id="p1b-label-only-raw-text-1.0.0",
    )
    raw_bytes = raw_generation_bytes(result)
    raw_ref = store.put_bytes(
        raw_bytes,
        media_type="application/json",
        contract_id="p1b-label-only-raw-generation-1.0.0",
    )
    label = None
    parse_error = None
    try:
        label = _parse_label_only(result.raw_text)
    except Exception as error:
        parse_error = f"{type(error).__name__}: {error}"
    evidence = {
        "context_hash": compiled.context_pack.context_hash,
        "context_pack_ref": compiled.artifact_ref.digest if compiled.artifact_ref else None,
        "rendered_input_ref": rendered_ref.digest,
        "raw_text_ref": raw_text_ref.digest,
        "raw_generation_ref": raw_ref.digest,
        "raw_text": result.raw_text,
        "token_ids": list(result.token_ids or ()),
        "finish_reason": result.finish_reason,
        "label": label,
        "parse_error": parse_error,
        "model_profile_id": profile.profile_id,
    }
    evidence_ref = store.put_bytes(
        canonical_bytes(evidence),
        media_type="application/json",
        contract_id="p1b-label-only-evidence-1.0.0",
    )
    evidence["evidence_ref"] = evidence_ref.digest
    return result, label, raw_ref.digest, evidence


def _planned_document(
    *, paths: DeploymentPaths, git_commit: str, config_sha256: str, p1_archive: dict[str, Any]
) -> dict[str, Any]:
    value = {
        "study_id": P1B_STUDY_ID,
        "schema_version": "1.0.0",
        "runner_version": P1B_RUNNER_VERSION,
        "status": "PLANNED",
        "git_commit": git_commit,
        "preregistration_commit": P1B_PREREG_COMMIT,
        "config_sha256": config_sha256,
        "deployment": {
            "base_model_dir": str(paths.base_model_dir),
            "adapter_path": str(paths.adapter_path),
            "base_checkpoint_sha256": P1B_BASE_CHECKPOINT_SHA256,
            "tokenizer_digest": P1B_TOKENIZER_DIGEST,
            "adapter_sha256": P1B_ADAPTER_SHA256,
        },
        "p1_archive": p1_archive,
        "heldout": {"case_start": HELDOUT_START, "case_end": HELDOUT_END, "contexts": 160},
        "paired": {"case_start": PAIRED_START, "case_end": PAIRED_END, "contexts": 80},
        "model_conditions": ["BASE_ONLY", "FA_V1"],
        "measurements": ["TEACHER_FORCED_FIVE_LABEL", "LABEL_ONLY_SELECTOR"],
        "state_commit": False,
        "weight_update": False,
    }
    value["identity_digest"] = canonical_digest(value)
    return value


def _execute(
    *,
    paths: DeploymentPaths,
    p1_root: Path,
    config: dict[str, Any],
    config_sha256: str,
    expected_git_commit: str,
) -> dict[str, Any]:
    del config
    if paths.output_root.exists() and any(paths.output_root.iterdir()):
        raise SmokePreflightError("P1B output root already exists and is non-empty")
    paths.output_root.mkdir(parents=True, exist_ok=True)

    p1_archive = _verify_p1_archive(p1_root)
    planned = _planned_document(
        paths=paths,
        git_commit=_git_head(),
        config_sha256=config_sha256,
        p1_archive=p1_archive,
    )
    (paths.output_root / "planned.json").write_bytes(canonical_bytes(planned))

    preflight = _static_preflight(paths, expected_git_commit)
    environment = ensure_execute_environment()
    if environment.get("pip_freeze_sha256") != P1B_PIP_FREEZE_SHA256:
        raise SmokePreflightError("P1B canonical runtime freeze drift")

    store = FileSystemArtifactStore(paths.output_root / "cas")
    policy = _generation_policy()
    base_profile = _profile(paths.base_model_dir, condition="BASE_ONLY")
    fa_profile = _profile(paths.base_model_dir, condition="FA_V1")

    # Compile all model-visible contexts before loading or measuring a model.
    heldout_base = _compile_cohort(
        store=store,
        profile=base_profile,
        policy=policy,
        case_start=HELDOUT_START,
        case_end=HELDOUT_END,
    )
    heldout_fa = _compile_cohort(
        store=store,
        profile=fa_profile,
        policy=policy,
        case_start=HELDOUT_START,
        case_end=HELDOUT_END,
    )
    paired_fa = _compile_cohort(
        store=store,
        profile=fa_profile,
        policy=policy,
        case_start=PAIRED_START,
        case_end=PAIRED_END,
    )
    identical_inputs, identical_details = _verify_identical_inputs(heldout_base, heldout_fa)
    if not identical_inputs:
        raise SmokePreflightError("P1B identical-input requirement failed before inference")
    identical_ref = store.put_bytes(
        canonical_bytes(identical_details),
        media_type="application/json",
        contract_id="p1b-identical-input-audit-1.0.0",
    )

    base_runtime = _load_base_runtime(base_profile, paths.base_model_dir)
    fa_runtime = PeftTransformersLoader(
        base_model_dir=paths.base_model_dir,
        adapter_path=paths.adapter_path,
    )(fa_profile)
    base_freeze = _runtime_freeze_status(base_runtime)
    fa_freeze = _runtime_freeze_status(fa_runtime)
    if not base_freeze["frozen"] or not fa_freeze["frozen"]:
        raise SmokePreflightError("P1B model runtime is not frozen")

    base_constraint = build_transformers_constraint(base_runtime.tokenizer, schema=LABEL_ONLY_SCHEMA)
    fa_constraint = build_transformers_constraint(fa_runtime.tokenizer, schema=LABEL_ONLY_SCHEMA)

    score_details: dict[str, list[dict[str, Any]]] = {"BASE_ONLY": [], "FA_V1": []}
    score_maps: dict[str, dict[tuple[str, int], dict[str, float]]] = {
        "BASE_ONLY": {},
        "FA_V1": {},
    }
    score_repeat_equal: dict[str, bool] = {}

    for condition, runtime, cohort in (
        ("BASE_ONLY", base_runtime, heldout_base),
        ("FA_V1", fa_runtime, heldout_fa),
    ):
        first_score = None
        first_compiled = None
        for ordinal, (context_name, case_index, compiled) in enumerate(cohort, 1):
            score, score_ref, record = _score_one(runtime, compiled, store)
            record.update(
                {
                    "condition": condition,
                    "context_class": context_name,
                    "case_index": case_index,
                    "context_hash": compiled.context_pack.context_hash,
                }
            )
            score_details[condition].append(record)
            score_maps[condition][(context_name, case_index)] = dict(record["totals"])
            if first_score is None:
                first_score = score
                first_compiled = compiled
            if ordinal % 20 == 0 or ordinal == len(cohort):
                print(f"P1B_SCORE_{condition} {ordinal}/{len(cohort)}", flush=True)
        if first_score is None or first_compiled is None:
            raise RuntimeError("P1B score cohort unexpectedly empty")
        repeat, _, _ = _score_one(runtime, first_compiled, store)
        score_repeat_equal[condition] = _score_equal(first_score, repeat)

    label_details: dict[str, dict[str, list[dict[str, Any]]]] = {
        "BASE_ONLY": {"HELDOUT": []},
        "FA_V1": {"HELDOUT": [], "PAIRED_P1": []},
    }
    heldout_labels: dict[str, dict[str, list[str]]] = {
        "BASE_ONLY": {name: [] for name in P1B_CONTEXT_CLASSES},
        "FA_V1": {name: [] for name in P1B_CONTEXT_CLASSES},
    }
    paired_labels = {name: [] for name in P1B_CONTEXT_CLASSES}
    generation_repeat_equal: dict[str, bool] = {}
    generation_valid_counts = {"BASE_ONLY_HELDOUT": 0, "FA_V1_HELDOUT": 0, "FA_V1_PAIRED": 0}

    for condition, runtime, profile, constraint, cohort in (
        ("BASE_ONLY", base_runtime, base_profile, base_constraint, heldout_base),
        ("FA_V1", fa_runtime, fa_profile, fa_constraint, heldout_fa),
    ):
        first_raw_ref = None
        first_compiled = None
        for ordinal, (context_name, case_index, compiled) in enumerate(cohort, 1):
            _, label, raw_ref, evidence = _generate_label_only(
                runtime, profile, policy, compiled, constraint, store
            )
            evidence.update(
                {
                    "condition": condition,
                    "cohort": "HELDOUT",
                    "context_class": context_name,
                    "case_index": case_index,
                }
            )
            label_details[condition]["HELDOUT"].append(evidence)
            if label is not None:
                heldout_labels[condition][context_name].append(label)
                generation_valid_counts[f"{condition}_HELDOUT"] += 1
            else:
                heldout_labels[condition][context_name].append("__INVALID__")
            if first_raw_ref is None:
                first_raw_ref = raw_ref
                first_compiled = compiled
            if ordinal % 20 == 0 or ordinal == len(cohort):
                print(f"P1B_LABEL_{condition}_HELDOUT {ordinal}/{len(cohort)}", flush=True)
        if first_raw_ref is None or first_compiled is None:
            raise RuntimeError("P1B generation cohort unexpectedly empty")
        _, _, repeat_ref, _ = _generate_label_only(
            runtime, profile, policy, first_compiled, constraint, store
        )
        generation_repeat_equal[condition] = repeat_ref == first_raw_ref

    for ordinal, (context_name, case_index, compiled) in enumerate(paired_fa, 1):
        _, label, _, evidence = _generate_label_only(
            fa_runtime, fa_profile, policy, compiled, fa_constraint, store
        )
        evidence.update(
            {
                "condition": "FA_V1",
                "cohort": "PAIRED_P1",
                "context_class": context_name,
                "case_index": case_index,
            }
        )
        label_details["FA_V1"]["PAIRED_P1"].append(evidence)
        if label is not None:
            paired_labels[context_name].append(label)
            generation_valid_counts["FA_V1_PAIRED"] += 1
        else:
            paired_labels[context_name].append("__INVALID__")
        if ordinal % 20 == 0 or ordinal == len(paired_fa):
            print(f"P1B_LABEL_FA_V1_PAIRED {ordinal}/{len(paired_fa)}", flush=True)

    # Integrity is evaluated before scientific/mechanistic gates.
    score_complete = all(len(score_details[name]) == 160 for name in ("BASE_ONLY", "FA_V1"))
    score_label_complete = all(
        set(record["totals"]) == set(ACTION_LABELS)
        for name in ("BASE_ONLY", "FA_V1")
        for record in score_details[name]
    )
    generation_complete = (
        generation_valid_counts["BASE_ONLY_HELDOUT"] == 160
        and generation_valid_counts["FA_V1_HELDOUT"] == 160
        and generation_valid_counts["FA_V1_PAIRED"] == 80
    )
    g0 = (
        identical_inputs
        and score_complete
        and score_label_complete
        and generation_complete
        and all(score_repeat_equal.values())
        and all(generation_repeat_equal.values())
        and base_freeze["frozen"]
        and fa_freeze["frozen"]
    )

    # The scientific gates are computed only on complete valid measurements.
    g1_metrics = None
    g2_metrics = None
    g3_metrics = None
    g4_metrics = None
    g5_metrics = None
    if g0:
        g1 = evaluate_wait_dominance(paired_labels, cases_per_context=P1B_PAIRED_CASES)
        g1_metrics = g1.as_dict()

        base_margins = []
        fa_margins = []
        for context_name in P1B_CONTEXT_CLASSES:
            for case_index in range(HELDOUT_START, HELDOUT_END + 1):
                base_margins.append(score_structure(score_maps["BASE_ONLY"][(context_name, case_index)]).wait_margin)
                fa_margins.append(score_structure(score_maps["FA_V1"][(context_name, case_index)]).wait_margin)
        g2, wait_effects = evaluate_wait_amplification(base_margins, fa_margins)
        g2_metrics = g2.as_dict()
        g2_metrics["effects"] = list(wait_effects)

        contrasts: dict[str, dict[str, list[float]]] = {
            "BASE_ONLY": {"S_msg": [], "S_prop": [], "S_owner": []},
            "FA_V1": {"S_msg": [], "S_prop": [], "S_owner": []},
        }
        for condition in ("BASE_ONLY", "FA_V1"):
            for case_index in range(HELDOUT_START, HELDOUT_END + 1):
                matched = {
                    context_name: score_maps[condition][(context_name, case_index)]
                    for context_name in P1B_CONTEXT_CLASSES
                }
                values = structural_contrasts(matched)
                for name, value in values.items():
                    contrasts[condition][name].append(value)

        g3_results, g3_pass = evaluate_structural_presence(contrasts["FA_V1"])
        g3_metrics = {
            "contrasts": {name: result.as_dict() for name, result in g3_results.items()},
            "values": contrasts["FA_V1"],
            "pass": g3_pass,
        }
        g4_results, gains, g4_pass = evaluate_adapter_structural_gain(
            contrasts["BASE_ONLY"], contrasts["FA_V1"]
        )
        g4_metrics = {
            "contrasts": {name: result.as_dict() for name, result in g4_results.items()},
            "values": {name: list(values) for name, values in gains.items()},
            "pass": g4_pass,
        }
        base_sensitivity = evaluate_label_sensitivity(
            heldout_labels["BASE_ONLY"], cases_per_context=P1B_HELDOUT_CASES
        )
        fa_sensitivity = evaluate_label_sensitivity(
            heldout_labels["FA_V1"], cases_per_context=P1B_HELDOUT_CASES
        )
        g5_metrics = {
            "BASE_ONLY": base_sensitivity.as_dict(),
            "FA_V1": fa_sensitivity.as_dict(),
        }
    else:
        g1 = None
        g2 = None
        g3_pass = None
        g4_pass = None

    score_ref = store.put_bytes(
        canonical_bytes(score_details),
        media_type="application/json",
        contract_id="p1b-teacher-forced-details-1.0.0",
    )
    label_ref = store.put_bytes(
        canonical_bytes(label_details),
        media_type="application/json",
        contract_id="p1b-label-only-details-1.0.0",
    )

    distributions = {
        condition: {
            context: dict(sorted(Counter(values).items()))
            for context, values in heldout_labels[condition].items()
        }
        for condition in ("BASE_ONLY", "FA_V1")
    }
    paired_distribution = {
        context: dict(sorted(Counter(values).items())) for context, values in paired_labels.items()
    }

    result = {
        "study_id": P1B_STUDY_ID,
        "status": "P1B_MEASUREMENT_COMPLETE" if g0 else "P1B_INTEGRITY_FAIL",
        "git_commit": _git_head(),
        "preregistration_commit": P1B_PREREG_COMMIT,
        "config_sha256": config_sha256,
        "environment": environment,
        "preflight": preflight,
        "p1_archive": p1_archive,
        "gates": {
            "P1B-G0": g0,
            "P1B-G1": (g1.passed if g1 is not None else None),
            "P1B-G2": (g2.passed if g2 is not None else None),
            "P1B-G3": g3_pass,
            "P1B-G4": g4_pass,
            "P1B-G5": (
                {
                    "BASE_ONLY": g5_metrics["BASE_ONLY"]["pass"],
                    "FA_V1": g5_metrics["FA_V1"]["pass"],
                }
                if g5_metrics is not None
                else None
            ),
        },
        "integrity": {
            "identical_input_160": identical_inputs,
            "identical_input_audit_ref": identical_ref.digest,
            "teacher_forced_score_sets": {
                "BASE_ONLY": len(score_details["BASE_ONLY"]),
                "FA_V1": len(score_details["FA_V1"]),
            },
            "teacher_forced_label_sets_complete": score_label_complete,
            "label_only_valid": generation_valid_counts,
            "score_exact_repeat_equal": score_repeat_equal,
            "label_only_exact_repeat_equal": generation_repeat_equal,
            "runtime_freeze": {"BASE_ONLY": base_freeze, "FA_V1": fa_freeze},
            "state_commits": 0,
            "weight_updates": 0,
        },
        "P1B_G1_interface_wait_dominance": g1_metrics,
        "P1B_G2_adapter_wait_amplification": g2_metrics,
        "P1B_G3_fa_structural_presence": g3_metrics,
        "P1B_G4_adapter_structural_gain": g4_metrics,
        "P1B_G5_label_only_sensitivity": g5_metrics,
        "heldout_label_only_distribution": distributions,
        "paired_p1_fa_label_only_distribution": paired_distribution,
        "teacher_forced_details_ref": score_ref.digest,
        "label_only_details_ref": label_ref.digest,
        "founder_freeze": "NOT_ESTABLISHABLE_BY_P1B",
        "behavioral_admission": False,
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
    parser.add_argument("--p1-root", type=Path, required=True)
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
    p1_archive = _verify_p1_archive(args.p1_root)
    if args.validate_only:
        print(
            json.dumps(
                {
                    "status": "P1B_STATIC_PREFLIGHT_OK",
                    "git_commit": _git_head(),
                    "config_sha256": config_sha256,
                    "preflight": preflight,
                    "p1_archive": p1_archive,
                    "planned_model_inference_calls": {
                        "teacher_forced_score_sets": 320,
                        "label_only_generations": 400,
                        "repeat_score_sets": 2,
                        "repeat_label_only_generations": 2,
                    },
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0

    try:
        result = _execute(
            paths=paths,
            p1_root=args.p1_root,
            config=config,
            config_sha256=config_sha256,
            expected_git_commit=args.expected_git_commit,
        )
    except Exception as error:
        paths.output_root.mkdir(parents=True, exist_ok=True)
        failure = {
            "study_id": P1B_STUDY_ID,
            "status": "P1B_EXECUTION_EXCEPTION",
            "git_commit": _git_head(),
            "error_type": type(error).__name__,
            "error_message": str(error),
        }
        (paths.output_root / "failure.json").write_bytes(canonical_bytes(failure))
        raise

    compact = {
        "status": result["status"],
        "gates": result["gates"],
        "heldout_label_only_distribution": result["heldout_label_only_distribution"],
        "paired_p1_fa_label_only_distribution": result["paired_p1_fa_label_only_distribution"],
        "result_digest": result["result_digest"],
        "summary": str(paths.output_root / "summary.json"),
    }
    print(json.dumps(compact, ensure_ascii=False, sort_keys=True))
    return 0 if result["gates"]["P1B-G0"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
