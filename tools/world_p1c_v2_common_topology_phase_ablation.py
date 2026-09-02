#!/usr/bin/env python3
"""Run frozen WORLD P1C-v2 common-topology phase ablation.

All primary phase conditions use one cached split-prefill topology.  The runner
performs researcher-only teacher-forced label scoring and never generates or
commits simulation actions, updates weights, retries, repairs, or calibrates
model outputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from alifelm.domain import ArtifactId, ArtifactRef  # noqa: E402
from alifelm.model.d1_equivalence import score_cached_labels  # noqa: E402
from alifelm.model.generation import GenerationPolicy  # noqa: E402
from alifelm.model.p1b_metrics import ACTION_LABELS, score_structure, structural_contrasts  # noqa: E402
from alifelm.model.p1c_v2_metrics import (  # noqa: E402
    P1C_V2_CASES_PER_CONTEXT,
    P1C_V2_CONDITIONS,
    P1C_V2_CONTEXT_CLASSES,
    P1C_V2_STUDY_ID,
    evaluate_decoupling_candidate_v2,
    evaluate_structural_replication_carryover,
    factorial_interaction,
    matched_phase_effect,
    rank1_sensitivity,
)
from alifelm.model.peft_runtime import PeftTransformersLoader  # noqa: E402
from alifelm.model.phase_scoring import score_phase_switched_labels  # noqa: E402
from alifelm.model.profile import ModelProfile  # noqa: E402
from alifelm.model.r3_fixtures import R3ContextClass, compile_r3_fixture  # noqa: E402
from alifelm.model.transformers_backend import ModelLoadError, TransformersModelRuntime  # noqa: E402
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


RUNNER_VERSION = "1.0.0"
PROTOCOL_COMMIT = "9d6e7831c54c5aea3cb23f61c4dc26b5a2668a6f"
BASE_REVISION = "48d788eca847d4d7548f375ad03d3c9312f6139e"
BASE_SHA256 = "36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f"
TOKENIZER_SHA256 = "c448b9e69576a2af5fccdb905c4d6c9f6c0d06509b15d2459a3bc92bb33d42ff"
ADAPTER_SHA256 = "46917511362243be67e0783ddb7411a96f26613c1083bc4f95117d910d0998ec"
ADAPTER_CONFIG_SHA256 = "687100a0b6340b6096ca1e86066d3c13224b3c8e14ce9fb1b0cf78a52a8bdb7d"
PIP_FREEZE_SHA256 = "a98b9c11baf90a5e7717b1f108029838e9c917d46d1f499bf93e9adffad087bf"
RUNTIME_PACKAGE_COUNT = 60
CASE_START = 3000
CASE_END = 3031
CONTEXT_ENUMS = tuple(R3ContextClass(name) for name in P1C_V2_CONTEXT_CLASSES)
PHASE_CONDITIONS: tuple[tuple[str, bool, bool], ...] = (
    ("C00", False, False),
    ("C11", True, True),
    ("C10", True, False),
    ("C01", False, True),
)
BASE_PROFILE_ID = "WORLD_P1C_V2_BARE_BASE_BF16"
FA_PROFILE_ID = "WORLD_P1C_V2_FA_V1_BF16"
GENERATION_POLICY_ID = "WORLD_P1C_V2_DIAGNOSTIC_ONLY_V1"
GENERATION_SEED_ID = "WORLD_P1C_V2_NO_GENERATION_V1"

P1C_V1_SUMMARY_SHA256 = "47e9cbf2962bdbb6c3f59e4ae70fcc71bc204fbcb86a7e54bf1420085e492ee2"
P1C_V1_STDOUT_SHA256 = "188688bc311198b4e6028973a578c33ef27ed310951439ca05632a479db56867"
P1C_V1_ARCHIVE_SHA256 = "90eef02128d2caad16ef736170b28e1f8be76cb1331a53a2edb9e4d69bdff39d"
D1_SUMMARY_SHA256 = "b35075335a15f230d23e226644c09baae0020783ebfa389b74f8e62f11dc85b5"
D1_DETAILS_SHA256 = "2f6cb06c2271944afd27fff293dedc0613aa2d4fbf9bf99887aeb82065576563"
D1_STDOUT_SHA256 = "e75811f85219c4eefb4980892d2f67cb9f6e1965eb356b280792ad2e0fe69659"
D1_ARCHIVE_SHA256 = "300b064a9b29822c307655918cfa76cd63dd07f3a9382c2218bd0c9f0300eb9d"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        raise SmokePreflightError("cannot resolve P1C-v2 repository commit") from error


def _runtime_freeze_sha256() -> tuple[str, int]:
    completed = subprocess.run(
        [sys.executable, "-m", "pip", "freeze", "--all"],
        check=True,
        capture_output=True,
        text=True,
    )
    lines = sorted(line for line in completed.stdout.splitlines() if line)
    return _sha256(("\n".join(lines) + "\n").encode("utf-8")), len(lines)


def _load_config(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    config = json.loads(raw.decode("utf-8"))
    if config.get("study_id") != P1C_V2_STUDY_ID:
        raise SmokePreflightError("P1C-v2 config study_id drift")
    if config.get("schema_version") != "1.0.0":
        raise SmokePreflightError("P1C-v2 config schema drift")
    if config.get("protocol_commit") != PROTOCOL_COMMIT:
        raise SmokePreflightError("P1C-v2 protocol commit drift")

    cohort = config.get("cohort", {})
    if (
        cohort.get("fixture_family") != "R3"
        or cohort.get("case_index_start") != CASE_START
        or cohort.get("case_index_end") != CASE_END
        or cohort.get("cases_per_context_class") != P1C_V2_CASES_PER_CONTEXT
        or cohort.get("total_contexts") != 160
        or tuple(cohort.get("context_classes", ())) != P1C_V2_CONTEXT_CLASSES
        or cohort.get("iid_population_sample") is not False
    ):
        raise SmokePreflightError("P1C-v2 cohort drift")

    expected_conditions = {
        "C00": {"phase_a": "BASE", "phase_b": "BASE"},
        "C11": {"phase_a": "FA_V1", "phase_b": "FA_V1"},
        "C10": {"phase_a": "FA_V1", "phase_b": "BASE"},
        "C01": {"phase_a": "BASE", "phase_b": "FA_V1"},
    }
    if config.get("conditions") != expected_conditions:
        raise SmokePreflightError("P1C-v2 phase-condition drift")
    if tuple(config.get("action_labels", ())) != ACTION_LABELS:
        raise SmokePreflightError("P1C-v2 action-label drift")

    boundary = config.get("phase_boundary", {})
    if (
        boundary.get("phase_a") != "canonical_rendered_world_context_bytes_only"
        or boundary.get("phase_b_prefix") != '\nAction selection JSON:\n{"action_label":"'
        or boundary.get("cache_reuse") is not True
        or boundary.get("world_context_recompute_after_switch") is not False
        or boundary.get("candidate_cache_clone") is not True
        or boundary.get("ordinary_full_sequence_primary_scoring") is not False
    ):
        raise SmokePreflightError("P1C-v2 common-topology boundary drift")

    parity = config.get("cached_wrapper_parity_control", {})
    if (
        parity.get("contexts") != 160
        or parity.get("label_comparisons") != 800
        or parity.get("rendered_bytes_exact") is not True
        or parity.get("token_ids_exact") is not True
        or parity.get("total_log_probability_exact") is not True
        or parity.get("mean_log_probability_exact") is not True
        or parity.get("rank_exact") is not True
        or parity.get("posthoc_tolerance") is not None
    ):
        raise SmokePreflightError("P1C-v2 cached-wrapper parity drift")

    gates = config.get("gates", {})
    if gates.get("G1") != {
        "contrast": "M_C01_minus_M_C00",
        "median_gt": 0.0,
        "positive_fraction_gte": 0.75,
    }:
        raise SmokePreflightError("P1C-v2 G1 drift")
    if gates.get("G2") != {
        "contrast": "M_C10_minus_M_C00",
        "median_gt": 0.0,
        "positive_fraction_gte": 0.75,
    }:
        raise SmokePreflightError("P1C-v2 G2 drift")
    g3 = gates.get("G3", {})
    if (
        g3.get("required_same_contrasts_passing_both") != 2
        or g3.get("total_structural_contrasts") != 3
        or g3.get("per_contrast_full_gain") != {"median_gt": 0.0, "positive_fraction_gte": 0.75}
        or g3.get("per_contrast_prefill_carryover") != {"median_gt": 0.0, "positive_fraction_gte": 0.75}
    ):
        raise SmokePreflightError("P1C-v2 G3 drift")
    if gates.get("G4") != {
        "requires_G3": True,
        "contrast": "M_C11_minus_M_C10",
        "median_gt": 0.0,
        "positive_fraction_gte": 0.75,
    }:
        raise SmokePreflightError("P1C-v2 G4 drift")
    if gates.get("G5") != {
        "matched_sensitivity_rate_gte": 0.25,
        "nonquiet_tvd_gte": 0.25,
        "required_nonquiet_classes": 2,
        "total_nonquiet_classes": 4,
        "reported_per_condition": True,
    }:
        raise SmokePreflightError("P1C-v2 G5 drift")

    execution = config.get("execution", {})
    forbidden_true = (
        "generation",
        "state_commit",
        "weight_update",
        "retry",
        "fallback",
        "repair",
        "eos_manipulation",
        "scalar_calibration",
        "action_hints",
        "failed_run_overwrite",
    )
    if any(execution.get(name) is not False for name in forbidden_true):
        raise SmokePreflightError("P1C-v2 execution boundary drift")
    if execution.get("exact_first_score_repeat") is not True or execution.get("primary_archive_before_posthoc") is not True:
        raise SmokePreflightError("P1C-v2 preservation boundary drift")

    source = config.get("source_results", {})
    if (
        source.get("p1c_v1_results_freeze_commit") != "274a51ed5f93805a6cbf41f1c757666cedf3cca1"
        or source.get("p1c_v1_status") != "P1C_BASE_WRAPPER_EQUIVALENCE_FAIL"
        or source.get("p1c_v1_result_digest") != "e38870bbf1b0232987be9a73dabd8955148f4521c2c56f78ece931557b214065"
        or source.get("d1_results_freeze_commit") != "34bc6881754fe206faf66cf17b3548373da2a9ff"
        or source.get("d1_status") != "D1_MEASUREMENT_COMPLETE"
        or source.get("d1_result_digest") != "0aac4e02a50f4fa4c6a847b8a84937c23d5ea1c58f5fb9b82d2c424324838cd2"
        or source.get("d1_canonical_archive_sha256") != D1_ARCHIVE_SHA256
    ):
        raise SmokePreflightError("P1C-v2 source-results drift")
    return config, _sha256(raw)


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
    if result["base_checkpoint_sha256"] != BASE_SHA256:
        raise SmokePreflightError("P1C-v2 base checkpoint identity drift")
    if result["tokenizer_digest"] != TOKENIZER_SHA256:
        raise SmokePreflightError("P1C-v2 tokenizer identity drift")
    if result["adapter_sha256"] != ADAPTER_SHA256:
        raise SmokePreflightError("P1C-v2 adapter identity drift")
    if result["adapter_config_sha256"] != ADAPTER_CONFIG_SHA256:
        raise SmokePreflightError("P1C-v2 adapter config identity drift")
    return result


def _verify_source_evidence(
    *,
    p1c_v1_root: Path,
    p1c_v1_stdout: Path,
    p1c_v1_archive: Path,
    d1_root: Path,
    d1_stdout: Path,
    d1_archive: Path,
) -> dict[str, Any]:
    p1c_summary = p1c_v1_root / "summary.json"
    d1_summary = d1_root / "summary.json"
    d1_details = d1_root / "details.json"
    paths = (p1c_summary, p1c_v1_stdout, p1c_v1_archive, d1_summary, d1_details, d1_stdout, d1_archive)
    if not all(path.is_file() for path in paths):
        raise SmokePreflightError("P1C-v2 frozen source evidence is missing")
    observed = {
        "p1c_v1_summary_sha256": _file_sha256(p1c_summary),
        "p1c_v1_stdout_sha256": _file_sha256(p1c_v1_stdout),
        "p1c_v1_archive_sha256": _file_sha256(p1c_v1_archive),
        "d1_summary_sha256": _file_sha256(d1_summary),
        "d1_details_sha256": _file_sha256(d1_details),
        "d1_stdout_sha256": _file_sha256(d1_stdout),
        "d1_archive_sha256": _file_sha256(d1_archive),
    }
    expected = {
        "p1c_v1_summary_sha256": P1C_V1_SUMMARY_SHA256,
        "p1c_v1_stdout_sha256": P1C_V1_STDOUT_SHA256,
        "p1c_v1_archive_sha256": P1C_V1_ARCHIVE_SHA256,
        "d1_summary_sha256": D1_SUMMARY_SHA256,
        "d1_details_sha256": D1_DETAILS_SHA256,
        "d1_stdout_sha256": D1_STDOUT_SHA256,
        "d1_archive_sha256": D1_ARCHIVE_SHA256,
    }
    if observed != expected:
        raise SmokePreflightError("P1C-v2 frozen source evidence identity drift")
    return observed


def _profile(base_model_dir: Path, *, adapter: bool) -> ModelProfile:
    adapter_ref = ArtifactRef(ArtifactId("F0_FA_V1_FORMAL"), ADAPTER_SHA256) if adapter else None
    return ModelProfile(
        profile_id=FA_PROFILE_ID if adapter else BASE_PROFILE_ID,
        profile_version="1.0.0",
        model_identifier=str(base_model_dir),
        model_revision=BASE_REVISION,
        model_digest=BASE_SHA256,
        tokenizer_identifier=str(base_model_dir),
        tokenizer_revision=BASE_REVISION,
        tokenizer_digest=TOKENIZER_SHA256,
        model_class="AUTO_CAUSAL_LM",
        generation_policy_id=GENERATION_POLICY_ID,
        device="cuda:0",
        dtype="bfloat16",
        adapter_ref=adapter_ref,
        trust_remote_code=False,
        add_special_tokens=True,
    )


def _diagnostic_policy() -> GenerationPolicy:
    return GenerationPolicy(
        policy_id=GENERATION_POLICY_ID,
        version="1.0.0",
        max_new_tokens=1,
        do_sample=False,
        temperature=None,
        top_p=None,
        top_k=None,
        repetition_penalty=1.0,
        seed_id=GENERATION_SEED_ID,
        stop_policy_id=None,
    )


def _compile_cohort(*, store: FileSystemArtifactStore, profile: ModelProfile):
    policy = build_context_policy()
    diagnostic = _diagnostic_policy()
    rows = []
    for context_class in CONTEXT_ENUMS:
        for case_index in range(CASE_START, CASE_END + 1):
            compiled = compile_r3_fixture(
                context_class,
                case_index,
                policy=policy,
                model_profile_id=profile.profile_id,
                generation_policy_id=diagnostic.policy_id,
                generation_seed_id=GENERATION_SEED_ID,
                artifact_store=store,
            )
            rows.append((context_class.value, case_index, compiled))
    if len(rows) != 160:
        raise SmokePreflightError("P1C-v2 compiled cohort size drift")
    return tuple(rows)


def _load_bare_runtime(profile: ModelProfile, base_model_dir: Path) -> TransformersModelRuntime:
    try:
        import torch
        import transformers

        tokenizer = transformers.AutoTokenizer.from_pretrained(
            str(base_model_dir), local_files_only=True, trust_remote_code=False
        )
        for name, expected in (("bos_token_id", 100257), ("eos_token_id", 100257), ("pad_token_id", 100277)):
            if getattr(tokenizer, name, None) != expected:
                raise ModelLoadError(f"P1C-v2 bare tokenizer {name} mismatch")
        kwargs: dict[str, Any] = {"local_files_only": True, "trust_remote_code": False}
        major = int(str(transformers.__version__).split(".", 1)[0])
        kwargs["dtype" if major >= 5 else "torch_dtype"] = torch.bfloat16
        model = transformers.AutoModelForCausalLM.from_pretrained(str(base_model_dir), **kwargs)
        model = model.to(profile.device)
        model.eval()
        for parameter in model.parameters():
            parameter.requires_grad_(False)
        if model.training or any(parameter.requires_grad for parameter in model.parameters()):
            raise ModelLoadError("P1C-v2 bare runtime must be eval and frozen")
        return TransformersModelRuntime.from_components(profile, tokenizer=tokenizer, model=model, torch_module=torch)
    except ModelLoadError:
        raise
    except Exception as error:
        raise ModelLoadError("failed to load P1C-v2 bare BASE runtime") from error


def _runtime_freeze_status(runtime: TransformersModelRuntime) -> dict[str, Any]:
    parameters = tuple(runtime.model.parameters())
    trainable = sum(int(parameter.requires_grad) for parameter in parameters)
    training = bool(getattr(runtime.model, "training", False))
    return {
        "training": training,
        "parameter_tensors": len(parameters),
        "trainable_parameter_tensors": trainable,
        "frozen": (not training and trainable == 0),
    }


def _phase_record(runtime: TransformersModelRuntime, compiled, *, prefill: bool, selector: bool):
    result = score_phase_switched_labels(
        runtime,
        rendered_input=compiled.rendered_input,
        prefill_adapter=prefill,
        selector_adapter=selector,
    )
    record = {
        "prefill_adapter": prefill,
        "selector_adapter": selector,
        "context_token_ids": list(result.context_token_ids),
        "prefix_token_ids": list(result.prefix_token_ids),
        "combined_token_ids": list(result.combined_token_ids),
        "phase_boundary_token_aligned": result.phase_boundary_token_aligned,
        "prefill_forward_count": result.prefill_forward_count,
        "selector_prefix_forward_count": result.selector_prefix_forward_count,
        "scores": [
            {
                "model_label": row.model_label,
                "token_ids": list(row.token_ids),
                "total_log_probability": row.total_log_probability,
                "mean_log_probability": row.mean_log_probability,
                "rank": row.rank,
            }
            for row in result.scores
        ],
    }
    return result, record


def _bare_record(runtime: TransformersModelRuntime, compiled):
    result = score_cached_labels(
        runtime,
        rendered_input=compiled.rendered_input,
        peft_disabled=False,
    )
    return result, result.as_record()


def _score_map(record: dict[str, Any]) -> dict[str, float]:
    return {row["model_label"]: float(row["total_log_probability"]) for row in record["scores"]}


def _rank1(record: dict[str, Any]) -> str:
    return next(row["model_label"] for row in record["scores"] if int(row["rank"]) == 1)


def _result_signature(result: Any) -> bytes:
    if hasattr(result, "as_record"):
        value = result.as_record()
    else:
        value = {
            "prefill_adapter": result.prefill_adapter,
            "selector_adapter": result.selector_adapter,
            "context_token_ids": list(result.context_token_ids),
            "prefix_token_ids": list(result.prefix_token_ids),
            "combined_token_ids": list(result.combined_token_ids),
            "scores": [
                {
                    "model_label": row.model_label,
                    "token_ids": list(row.token_ids),
                    "total_log_probability": row.total_log_probability,
                    "mean_log_probability": row.mean_log_probability,
                    "rank": row.rank,
                }
                for row in result.scores
            ],
        }
    return canonical_bytes(value)


def _cached_parity(bare_records: list[dict[str, Any]], c00_records: list[dict[str, Any]]) -> dict[str, Any]:
    if len(bare_records) != 160 or len(c00_records) != 160:
        raise ValueError("P1C-v2 cached parity requires 160 matched score sets")
    comparisons = 0
    rendered_exact = True
    context_tokens_exact = True
    prefix_tokens_exact = True
    combined_tokens_exact = True
    label_tokens_exact = True
    totals_exact = True
    means_exact = True
    ranks_exact = True
    for bare, c00 in zip(bare_records, c00_records, strict=True):
        rendered_exact &= bare["rendered_sha256"] == c00["rendered_sha256"]
        context_tokens_exact &= bare["context_token_ids"] == c00["context_token_ids"]
        prefix_tokens_exact &= bare["prefix_token_ids"] == c00["prefix_token_ids"]
        combined_tokens_exact &= bare["combined_token_ids"] == c00["combined_token_ids"]
        b_rows = {row["model_label"]: row for row in bare["scores"]}
        c_rows = {row["model_label"]: row for row in c00["scores"]}
        if tuple(b_rows) != ACTION_LABELS or tuple(c_rows) != ACTION_LABELS:
            raise ValueError("P1C-v2 parity label order drift")
        for label in ACTION_LABELS:
            b = b_rows[label]
            c = c_rows[label]
            comparisons += 1
            label_tokens_exact &= b["token_ids"] == c["token_ids"]
            totals_exact &= b["total_log_probability"] == c["total_log_probability"]
            means_exact &= b["mean_log_probability"] == c["mean_log_probability"]
            ranks_exact &= b["rank"] == c["rank"]
    passed = all(
        (
            rendered_exact,
            context_tokens_exact,
            prefix_tokens_exact,
            combined_tokens_exact,
            label_tokens_exact,
            totals_exact,
            means_exact,
            ranks_exact,
        )
    ) and comparisons == 800
    return {
        "score_sets": len(bare_records),
        "comparisons": comparisons,
        "rendered_bytes_exact": rendered_exact,
        "context_token_ids_exact": context_tokens_exact,
        "prefix_token_ids_exact": prefix_tokens_exact,
        "combined_token_ids_exact": combined_tokens_exact,
        "candidate_token_ids_exact": label_tokens_exact,
        "total_log_probability_exact": totals_exact,
        "mean_log_probability_exact": means_exact,
        "rank_exact": ranks_exact,
        "posthoc_tolerance": None,
        "pass": passed,
    }


def _planned_document(*, paths: DeploymentPaths, config_sha256: str) -> dict[str, Any]:
    value = {
        "study_id": P1C_V2_STUDY_ID,
        "runner_version": RUNNER_VERSION,
        "status": "PLANNED",
        "git_commit": _git_head(),
        "protocol_commit": PROTOCOL_COMMIT,
        "config_sha256": config_sha256,
        "base_model_dir": str(paths.base_model_dir),
        "adapter_path": str(paths.adapter_path),
        "cohort": {"case_start": CASE_START, "case_end": CASE_END, "contexts": 160},
        "bare_cached_score_sets": 160,
        "phase_score_sets": 640,
        "repeat_score_sets": 5,
        "cached_wrapper_label_comparisons": 800,
        "ordinary_full_sequence_primary_score_sets": 0,
        "generation": False,
        "state_commit": False,
        "weight_update": False,
        "founder_freeze": "NOT_ESTABLISHED",
    }
    value["identity_digest"] = canonical_digest(value)
    return value


def _execute(
    *,
    paths: DeploymentPaths,
    config_sha256: str,
    expected_git_commit: str,
    runtime_freeze_sha256: str,
    runtime_package_count: int,
    source_paths: dict[str, Path],
) -> dict[str, Any]:
    if paths.output_root.exists() and any(paths.output_root.iterdir()):
        raise SmokePreflightError("P1C-v2 output root already exists and is non-empty")
    paths.output_root.mkdir(parents=True, exist_ok=True)
    (paths.output_root / "planned.json").write_bytes(canonical_bytes(_planned_document(paths=paths, config_sha256=config_sha256)))

    source_before = _verify_source_evidence(**source_paths)
    preflight = _static_preflight(paths, expected_git_commit)
    environment = ensure_execute_environment()
    environment["pip_freeze_sha256"] = runtime_freeze_sha256
    environment["pip_freeze_package_count"] = runtime_package_count

    store = FileSystemArtifactStore(paths.output_root / "cas")
    base_profile = _profile(paths.base_model_dir, adapter=False)
    fa_profile = _profile(paths.base_model_dir, adapter=True)
    cohort = _compile_cohort(store=store, profile=fa_profile)

    context_audit = [
        {
            "context_class": name,
            "case_index": index,
            "context_hash": compiled.context_pack.context_hash,
            "rendered_sha256": _sha256(compiled.rendered_input),
        }
        for name, index, compiled in cohort
    ]

    bare_runtime = _load_bare_runtime(base_profile, paths.base_model_dir)
    fa_runtime = PeftTransformersLoader(base_model_dir=paths.base_model_dir, adapter_path=paths.adapter_path)(fa_profile)
    freeze = {
        "BARE_BASE": _runtime_freeze_status(bare_runtime),
        "FA_WRAPPED": _runtime_freeze_status(fa_runtime),
    }
    if not all(value["frozen"] for value in freeze.values()):
        raise SmokePreflightError("P1C-v2 runtime freeze failed")

    bare_records: list[dict[str, Any]] = []
    c00_records: list[dict[str, Any]] = []
    bare_first = c00_first = None
    first_compiled = None

    for ordinal, (context_name, case_index, compiled) in enumerate(cohort, 1):
        bare_result, bare_record = _bare_record(bare_runtime, compiled)
        c00_result, c00_record = _phase_record(fa_runtime, compiled, prefill=False, selector=False)
        common = {
            "context_class": context_name,
            "case_index": case_index,
            "rendered_sha256": _sha256(compiled.rendered_input),
        }
        bare_record.update({"path": "BARE_CACHED_BASE", **common})
        c00_record.update({"condition": "C00", **common})
        bare_records.append(bare_record)
        c00_records.append(c00_record)
        if bare_first is None:
            bare_first = bare_result
            c00_first = c00_result
            first_compiled = compiled
        if ordinal % 20 == 0 or ordinal == len(cohort):
            print(f"P1C_V2_PARITY {ordinal}/{len(cohort)}", flush=True)

    if bare_first is None or c00_first is None or first_compiled is None:
        raise RuntimeError("P1C-v2 cohort unexpectedly empty")
    bare_repeat, _ = _bare_record(bare_runtime, first_compiled)
    c00_repeat, _ = _phase_record(fa_runtime, first_compiled, prefill=False, selector=False)
    repeats = {
        "BARE_CACHED_BASE": _result_signature(bare_first) == _result_signature(bare_repeat),
        "C00": _result_signature(c00_first) == _result_signature(c00_repeat),
    }

    parity = _cached_parity(bare_records, c00_records)
    if not parity["pass"]:
        source_after = _verify_source_evidence(**source_paths)
        details = {"context_audit": context_audit, "bare_cached": bare_records, "C00": c00_records}
        details_bytes = canonical_bytes(details)
        (paths.output_root / "details.json").write_bytes(details_bytes)
        result = {
            "study_id": P1C_V2_STUDY_ID,
            "runner_version": RUNNER_VERSION,
            "status": "P1C_V2_CACHED_WRAPPER_PARITY_FAIL",
            "localization": "PHASE_ATTRIBUTION_NOT_EVALUABLE",
            "git_commit": _git_head(),
            "protocol_commit": PROTOCOL_COMMIT,
            "config_sha256": config_sha256,
            "environment": environment,
            "preflight": preflight,
            "source_before": source_before,
            "source_after": source_after,
            "gates": {"P1C-V2-G0": False, "P1C-V2-G1": None, "P1C-V2-G2": None, "P1C-V2-G3": None, "P1C-V2-G4": None, "P1C-V2-G5": None},
            "cached_wrapper_parity": parity,
            "integrity": {
                "bare_cached_score_sets": len(bare_records),
                "C00_score_sets": len(c00_records),
                "first_score_exact_repeat": repeats,
                "runtime_freeze": freeze,
                "source_evidence_unchanged": source_before == source_after,
                "generation_calls": 0,
                "state_commits": 0,
                "weight_updates": 0,
            },
            "details_sha256": _sha256(details_bytes),
            "founder_freeze": "NOT_ESTABLISHED",
            "behavioral_admission": False,
        }
        result["result_digest"] = canonical_digest(result)
        (paths.output_root / "summary.json").write_bytes(canonical_bytes(result))
        return result

    phase_records: dict[str, list[dict[str, Any]]] = {"C00": c00_records, "C11": [], "C10": [], "C01": []}
    condition_first: dict[str, Any] = {}
    token_signatures: dict[tuple[str, int], tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]] = {}
    for record in c00_records:
        key = (record["context_class"], int(record["case_index"]))
        token_signatures[key] = (
            tuple(record["context_token_ids"]),
            tuple(record["prefix_token_ids"]),
            tuple(record["combined_token_ids"]),
        )

    for condition, prefill, selector in PHASE_CONDITIONS[1:]:
        first_result = None
        first_row = None
        for ordinal, (context_name, case_index, compiled) in enumerate(cohort, 1):
            result, record = _phase_record(fa_runtime, compiled, prefill=prefill, selector=selector)
            record.update(
                {
                    "condition": condition,
                    "context_class": context_name,
                    "case_index": case_index,
                    "rendered_sha256": _sha256(compiled.rendered_input),
                }
            )
            key = (context_name, case_index)
            signature = (
                tuple(record["context_token_ids"]),
                tuple(record["prefix_token_ids"]),
                tuple(record["combined_token_ids"]),
            )
            if signature != token_signatures[key]:
                raise SmokePreflightError("P1C-v2 tokenization differs across common-topology conditions")
            phase_records[condition].append(record)
            if first_result is None:
                first_result = result
                first_row = compiled
            if ordinal % 20 == 0 or ordinal == len(cohort):
                print(f"P1C_V2_{condition} {ordinal}/{len(cohort)}", flush=True)
        if first_result is None or first_row is None:
            raise RuntimeError(f"P1C-v2 {condition} cohort unexpectedly empty")
        repeated, _ = _phase_record(fa_runtime, first_row, prefill=prefill, selector=selector)
        repeats[condition] = _result_signature(first_result) == _result_signature(repeated)
        condition_first[condition] = first_result

    score_maps: dict[str, dict[tuple[str, int], dict[str, float]]] = {name: {} for name in P1C_V2_CONDITIONS}
    rank1_by_context: dict[str, dict[str, list[str]]] = {
        name: {context: [] for context in P1C_V2_CONTEXT_CLASSES} for name in P1C_V2_CONDITIONS
    }
    for condition in P1C_V2_CONDITIONS:
        for record in phase_records[condition]:
            key = (record["context_class"], int(record["case_index"]))
            score_maps[condition][key] = _score_map(record)
            rank1_by_context[condition][record["context_class"]].append(_rank1(record))

    complete = all(len(phase_records[name]) == 160 for name in P1C_V2_CONDITIONS)
    labels_complete = all(
        tuple(row["model_label"] for row in record["scores"]) == ACTION_LABELS
        for name in P1C_V2_CONDITIONS
        for record in phase_records[name]
    )
    one_prefill = all(
        record["prefill_forward_count"] == 1 and record["selector_prefix_forward_count"] == 1
        for name in P1C_V2_CONDITIONS
        for record in phase_records[name]
    )
    expected_flags = {name: (prefill, selector) for name, prefill, selector in PHASE_CONDITIONS}
    flags_correct = all(
        record["prefill_adapter"] == expected_flags[name][0]
        and record["selector_adapter"] == expected_flags[name][1]
        for name in P1C_V2_CONDITIONS
        for record in phase_records[name]
    )

    source_after = _verify_source_evidence(**source_paths)
    source_unchanged = source_before == source_after
    g0 = bool(
        parity["pass"]
        and complete
        and labels_complete
        and one_prefill
        and flags_correct
        and all(repeats.values())
        and all(value["frozen"] for value in freeze.values())
        and source_unchanged
    )

    g1 = g2 = g3 = g4_reduction = None
    g4_pass = None
    g5 = None
    companion = None
    interactions = None
    structural_values = None

    if g0:
        margins: dict[str, list[float]] = {name: [] for name in P1C_V2_CONDITIONS}
        for condition in P1C_V2_CONDITIONS:
            for context_name in P1C_V2_CONTEXT_CLASSES:
                for case_index in range(CASE_START, CASE_END + 1):
                    margins[condition].append(score_structure(score_maps[condition][(context_name, case_index)]).wait_margin)

        g1 = matched_phase_effect(margins["C00"], margins["C01"])
        g2 = matched_phase_effect(margins["C00"], margins["C10"])
        decode_fa = matched_phase_effect(margins["C10"], margins["C11"])
        prefill_fa = matched_phase_effect(margins["C01"], margins["C11"])
        companion = {
            "D_decode_FA_C11_minus_C10": decode_fa.as_dict(),
            "D_prefill_FA_C11_minus_C01": prefill_fa.as_dict(),
        }

        structural_values = {
            condition: {"S_msg": [], "S_prop": [], "S_owner": []}
            for condition in P1C_V2_CONDITIONS
        }
        for condition in P1C_V2_CONDITIONS:
            for case_index in range(CASE_START, CASE_END + 1):
                matched = {
                    context: score_maps[condition][(context, case_index)]
                    for context in P1C_V2_CONTEXT_CLASSES
                }
                values = structural_contrasts(matched)
                for name, value in values.items():
                    structural_values[condition][name].append(float(value))

        g3 = evaluate_structural_replication_carryover(
            c00=structural_values["C00"],
            c11=structural_values["C11"],
            c10=structural_values["C10"],
        )
        g4_reduction, g4_pass = evaluate_decoupling_candidate_v2(
            structural_replication_carryover_pass=g3.passed,
            c10_margins=margins["C10"],
            c11_margins=margins["C11"],
        )
        g5 = {
            condition: rank1_sensitivity(rank1_by_context[condition]).as_dict()
            for condition in P1C_V2_CONDITIONS
        }

        wait_values, wait_summary = factorial_interaction(
            c00=margins["C00"], c10=margins["C10"], c01=margins["C01"], c11=margins["C11"]
        )
        structural_interactions = {}
        for name in ("S_msg", "S_prop", "S_owner"):
            values, summary = factorial_interaction(
                c00=structural_values["C00"][name],
                c10=structural_values["C10"][name],
                c01=structural_values["C01"][name],
                c11=structural_values["C11"][name],
            )
            structural_interactions[name] = {"values": list(values), "summary": summary.as_dict()}
        interactions = {
            "WAIT": {"values": list(wait_values), "summary": wait_summary.as_dict()},
            "structural": structural_interactions,
            "pass_fail_thresholds": False,
        }

    details = {
        "study_id": P1C_V2_STUDY_ID,
        "context_audit": context_audit,
        "bare_cached_control": bare_records,
        "phase_conditions": phase_records,
        "structural_values": structural_values,
    }
    details_bytes = canonical_bytes(details)
    details_sha256 = _sha256(details_bytes)
    (paths.output_root / "details.json").write_bytes(details_bytes)

    result = {
        "study_id": P1C_V2_STUDY_ID,
        "runner_version": RUNNER_VERSION,
        "status": "P1C_V2_MEASUREMENT_COMPLETE" if g0 else "P1C_V2_INTEGRITY_FAIL",
        "localization": "INTERPRETABLE" if g0 else "PHASE_ATTRIBUTION_NOT_EVALUABLE",
        "git_commit": _git_head(),
        "protocol_commit": PROTOCOL_COMMIT,
        "config_sha256": config_sha256,
        "environment": environment,
        "preflight": preflight,
        "source_before": source_before,
        "source_after": source_after,
        "gates": {
            "P1C-V2-G0": g0,
            "P1C-V2-G1": g1.passed if g1 is not None else None,
            "P1C-V2-G2": g2.passed if g2 is not None else None,
            "P1C-V2-G3": g3.passed if g3 is not None else None,
            "P1C-V2-G4": g4_pass,
            "P1C-V2-G5": ({condition: g5[condition]["pass"] for condition in P1C_V2_CONDITIONS} if g5 is not None else None),
        },
        "cached_wrapper_parity": parity,
        "G1_decode_side_wait_induction": g1.as_dict() if g1 is not None else None,
        "G2_prefill_side_wait_induction": g2.as_dict() if g2 is not None else None,
        "factorial_companion_wait_effects": companion,
        "G3_structural_replication_and_carryover": g3.as_dict() if g3 is not None else None,
        "G4_decoupling_candidate": ({"wait_reduction": g4_reduction.as_dict(), "pass": g4_pass} if g4_reduction is not None else None),
        "G5_rank1_sensitivity": g5,
        "factorial_interactions": interactions,
        "integrity": {
            "bare_cached_score_sets": len(bare_records),
            "phase_score_sets": {name: len(phase_records[name]) for name in P1C_V2_CONDITIONS},
            "phase_tokenization_identical": complete,
            "phase_boundary_token_aligned": all(
                record["phase_boundary_token_aligned"]
                for name in P1C_V2_CONDITIONS
                for record in phase_records[name]
            ),
            "cache_prefill_once_per_score_set": one_prefill,
            "phase_flags_correct": flags_correct,
            "first_score_exact_repeat": repeats,
            "runtime_freeze": freeze,
            "source_evidence_unchanged": source_unchanged,
            "ordinary_full_sequence_primary_score_sets": 0,
            "generation_calls": 0,
            "state_commits": 0,
            "weight_updates": 0,
        },
        "details_sha256": details_sha256,
        "founder_freeze": "NOT_ESTABLISHED",
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
    parser.add_argument("--p1c-v1-root", type=Path, required=True)
    parser.add_argument("--p1c-v1-stdout", type=Path, required=True)
    parser.add_argument("--p1c-v1-archive", type=Path, required=True)
    parser.add_argument("--d1-root", type=Path, required=True)
    parser.add_argument("--d1-stdout", type=Path, required=True)
    parser.add_argument("--d1-archive", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--expected-git-commit", required=True)
    args = parser.parse_args()

    _, config_sha256 = _load_config(args.config)
    paths = DeploymentPaths(base_model_dir=args.base_model_dir, adapter_path=args.adapter_path, output_root=args.output_root)
    preflight = _static_preflight(paths, args.expected_git_commit)
    source_paths = {
        "p1c_v1_root": args.p1c_v1_root,
        "p1c_v1_stdout": args.p1c_v1_stdout,
        "p1c_v1_archive": args.p1c_v1_archive,
        "d1_root": args.d1_root,
        "d1_stdout": args.d1_stdout,
        "d1_archive": args.d1_archive,
    }
    source = _verify_source_evidence(**source_paths)
    runtime_sha, package_count = _runtime_freeze_sha256()
    if runtime_sha != PIP_FREEZE_SHA256 or package_count != RUNTIME_PACKAGE_COUNT:
        raise SmokePreflightError("P1C-v2 canonical runtime freeze drift")

    if args.validate_only:
        with __import__("tempfile").TemporaryDirectory(prefix="world-p1c-v2-validate-") as temp_dir:
            store = FileSystemArtifactStore(Path(temp_dir) / "cas")
            cohort = _compile_cohort(store=store, profile=_profile(args.base_model_dir, adapter=True))
        print(
            json.dumps(
                {
                    "status": "P1C_V2_STATIC_PREFLIGHT_OK",
                    "git_commit": _git_head(),
                    "config_sha256": config_sha256,
                    "runtime_pip_freeze_sha256": runtime_sha,
                    "runtime_package_count": package_count,
                    "preflight": preflight,
                    "source_evidence": source,
                    "compiled_contexts": len(cohort),
                    "planned_measurements": {
                        "bare_cached_score_sets": 160,
                        "phase_score_sets": 640,
                        "repeat_score_sets": 5,
                        "cached_wrapper_label_comparisons": 800,
                        "ordinary_full_sequence_primary_score_sets": 0,
                    },
                    "generation": False,
                    "state_commit": False,
                    "weight_update": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0

    try:
        result = _execute(
            paths=paths,
            config_sha256=config_sha256,
            expected_git_commit=args.expected_git_commit,
            runtime_freeze_sha256=runtime_sha,
            runtime_package_count=package_count,
            source_paths=source_paths,
        )
    except Exception as error:
        paths.output_root.mkdir(parents=True, exist_ok=True)
        failure = {
            "study_id": P1C_V2_STUDY_ID,
            "status": "P1C_V2_EXECUTION_EXCEPTION",
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
                "localization": result["localization"],
                "gates": result["gates"],
                "cached_wrapper_parity": result["cached_wrapper_parity"],
                "result_digest": result["result_digest"],
                "summary": str(paths.output_root / "summary.json"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
