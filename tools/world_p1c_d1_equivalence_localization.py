#!/usr/bin/env python3
"""Run frozen WORLD P1C-D1 equivalence localization diagnostic.

D1 is post-hoc and cannot alter P1C primary. It compares full versus cached
five-label scoring on bare BASE and PEFT-disabled BASE, plus a fixed FP32 bare
subset. No generation, simulation commit, or weight update is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Callable, Mapping, Sequence

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from alifelm.domain import ArtifactId, ArtifactRef  # noqa: E402
from alifelm.model.action_diagnostics import score_action_labels  # noqa: E402
from alifelm.model.d1_equivalence import (  # noqa: E402
    compare_score_records,
    peft_disabled_state,
    score_cached_labels,
)
from alifelm.model.generation import GenerationPolicy  # noqa: E402
from alifelm.model.p1b_metrics import ACTION_LABELS  # noqa: E402
from alifelm.model.peft_runtime import PeftTransformersLoader  # noqa: E402
from alifelm.model.phase_scoring import (  # noqa: E402
    phase_boundary_token_ids,
    score_phase_switched_labels,
)
from alifelm.model.profile import ModelProfile  # noqa: E402
from alifelm.model.r3_fixtures import R3ContextClass, compile_r3_fixture  # noqa: E402
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


D1_STUDY_ID = "WORLD_P1C_D1_EQUIVALENCE_LOCALIZATION_V1"
D1_RUNNER_VERSION = "1.0.0"
D1_PROTOCOL_COMMIT = "7dca63312efd01350c597b41c24b4ab1fa9dd4ad"
D1_SOURCE_P1C_COMMIT = "f2e9e4dc9e7cdee6034ff33c663ffe434fa7c6ae"
D1_SOURCE_P1C_RESULTS_COMMIT = "274a51ed5f93805a6cbf41f1c757666cedf3cca1"
D1_SOURCE_P1C_CONFIG_SHA256 = "1ee7e53e8e8efd67e9868702138e89bf2532e737fa41329ad276c8a10ef98589"
D1_SOURCE_P1C_RESULT_DIGEST = "e38870bbf1b0232987be9a73dabd8955148f4521c2c56f78ece931557b214065"
D1_SOURCE_P1C_SUMMARY_SHA256 = "47e9cbf2962bdbb6c3f59e4ae70fcc71bc204fbcb86a7e54bf1420085e492ee2"
D1_SOURCE_P1C_STDOUT_SHA256 = "188688bc311198b4e6028973a578c33ef27ed310951439ca05632a479db56867"
D1_SOURCE_P1C_ARCHIVE_SHA256 = "90eef02128d2caad16ef736170b28e1f8be76cb1331a53a2edb9e4d69bdff39d"
D1_EXPECTED_RECON_TOTAL = 0.21875
D1_EXPECTED_RECON_MEAN = 0.0703125
D1_ORIGINAL_P1C_TOLERANCE = 1e-5
D1_BASE_MODEL_REVISION = "48d788eca847d4d7548f375ad03d3c9312f6139e"
D1_BASE_CHECKPOINT_SHA256 = "36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f"
D1_TOKENIZER_DIGEST = "c448b9e69576a2af5fccdb905c4d6c9f6c0d06509b15d2459a3bc92bb33d42ff"
D1_ADAPTER_SHA256 = "46917511362243be67e0783ddb7411a96f26613c1083bc4f95117d910d0998ec"
D1_ADAPTER_CONFIG_SHA256 = "687100a0b6340b6096ca1e86066d3c13224b3c8e14ce9fb1b0cf78a52a8bdb7d"
D1_PIP_FREEZE_SHA256 = "a98b9c11baf90a5e7717b1f108029838e9c917d46d1f499bf93e9adffad087bf"
D1_RUNTIME_PACKAGE_COUNT = 60
D1_BF16_START = 2000
D1_BF16_END = 2031
D1_FP32_END = 2003
D1_CONTEXT_CLASSES = (
    "QUIET",
    "MESSAGE_RECEIVED",
    "PROPOSAL_RECEIVED",
    "OWN_PROPOSAL_PENDING",
    "RECENT_INTERACTION",
)
D1_CONTEXT_ENUMS = tuple(R3ContextClass(name) for name in D1_CONTEXT_CLASSES)
D1_BF16_PATHS = (
    "E0_BARE_FULL_BF16",
    "E1_BARE_CACHED_BF16",
    "E2_PEFT_DISABLED_FULL_BF16",
    "E3_PEFT_DISABLED_CACHED_BF16",
)
D1_FP32_PATHS = ("F0_BARE_FULL_FP32", "F1_BARE_CACHED_FP32")
D1_DIAGNOSTIC_POLICY_ID = "WORLD_P1C_D1_DIAGNOSTIC_ONLY_V1"
D1_DIAGNOSTIC_SEED_ID = "WORLD_P1C_D1_NO_GENERATION_V1"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


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
        raise SmokePreflightError("cannot resolve D1 repository commit") from error


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
    if config.get("study_id") != D1_STUDY_ID:
        raise SmokePreflightError("D1 config study_id drift")
    if config.get("protocol_commit") != D1_PROTOCOL_COMMIT:
        raise SmokePreflightError("D1 protocol commit drift")
    source = config.get("source_p1c", {})
    expected_source = {
        "primary_git_commit": D1_SOURCE_P1C_COMMIT,
        "results_freeze_commit": D1_SOURCE_P1C_RESULTS_COMMIT,
        "config_sha256": D1_SOURCE_P1C_CONFIG_SHA256,
        "result_digest": D1_SOURCE_P1C_RESULT_DIGEST,
        "summary_sha256": D1_SOURCE_P1C_SUMMARY_SHA256,
        "stdout_sha256": D1_SOURCE_P1C_STDOUT_SHA256,
        "archive_sha256": D1_SOURCE_P1C_ARCHIVE_SHA256,
        "observed_max_total_abs_difference": D1_EXPECTED_RECON_TOTAL,
        "observed_max_mean_abs_difference": D1_EXPECTED_RECON_MEAN,
        "original_equivalence_tolerance": D1_ORIGINAL_P1C_TOLERANCE,
    }
    if source != expected_source:
        raise SmokePreflightError("D1 source-P1C identity drift")
    identities = config.get("identities", {})
    expected_identities = {
        "base_revision": D1_BASE_MODEL_REVISION,
        "base_checkpoint_sha256": D1_BASE_CHECKPOINT_SHA256,
        "tokenizer_digest": D1_TOKENIZER_DIGEST,
        "adapter_sha256": D1_ADAPTER_SHA256,
        "adapter_config_sha256": D1_ADAPTER_CONFIG_SHA256,
        "pip_freeze_sha256": D1_PIP_FREEZE_SHA256,
        "runtime_package_count": D1_RUNTIME_PACKAGE_COUNT,
    }
    if identities != expected_identities:
        raise SmokePreflightError("D1 frozen identity drift")
    cohort = config.get("bf16_cohort", {})
    if (
        cohort.get("case_index_start") != D1_BF16_START
        or cohort.get("case_index_end") != D1_BF16_END
        or cohort.get("cases_per_context") != 32
        or cohort.get("contexts") != 160
        or tuple(cohort.get("context_classes", ())) != D1_CONTEXT_CLASSES
    ):
        raise SmokePreflightError("D1 BF16 cohort drift")
    fp32 = config.get("fp32_subset", {})
    if (
        fp32.get("case_index_start") != D1_BF16_START
        or fp32.get("case_index_end") != D1_FP32_END
        or fp32.get("cases_per_context") != 4
        or fp32.get("contexts") != 20
    ):
        raise SmokePreflightError("D1 FP32 subset drift")
    if tuple(config.get("action_labels", ())) != ACTION_LABELS:
        raise SmokePreflightError("D1 action-label drift")
    expected_bf16 = {
        "E0": "BARE_FULL_BF16",
        "E1": "BARE_CACHED_BF16",
        "E2": "PEFT_DISABLED_FULL_BF16",
        "E3": "PEFT_DISABLED_CACHED_BF16",
    }
    expected_fp32 = {"F0": "BARE_FULL_FP32", "F1": "BARE_CACHED_FP32"}
    if config.get("bf16_conditions") != expected_bf16 or config.get("fp32_conditions") != expected_fp32:
        raise SmokePreflightError("D1 condition drift")
    reconstruction = config.get("reconstruction", {})
    if reconstruction != {
        "expected_max_total_abs_difference": D1_EXPECTED_RECON_TOTAL,
        "expected_max_mean_abs_difference": D1_EXPECTED_RECON_MEAN,
        "exact_numeric_match_required": True,
    }:
        raise SmokePreflightError("D1 reconstruction contract drift")
    execution = config.get("execution", {})
    if execution != {
        "generation": False,
        "state_commit": False,
        "weight_update": False,
        "retry": False,
        "fallback": False,
        "repair": False,
        "eos_manipulation": False,
        "scalar_calibration": False,
        "action_hints": False,
        "exact_first_score_repeat": True,
    }:
        raise SmokePreflightError("D1 execution contract drift")
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
    if result["base_checkpoint_sha256"] != D1_BASE_CHECKPOINT_SHA256:
        raise SmokePreflightError("D1 base checkpoint identity drift")
    if result["tokenizer_digest"] != D1_TOKENIZER_DIGEST:
        raise SmokePreflightError("D1 tokenizer identity drift")
    if result["adapter_sha256"] != D1_ADAPTER_SHA256:
        raise SmokePreflightError("D1 adapter identity drift")
    if result["adapter_config_sha256"] != D1_ADAPTER_CONFIG_SHA256:
        raise SmokePreflightError("D1 adapter config identity drift")
    return result


def _verify_source_p1c(p1c_root: Path, p1c_stdout: Path, p1c_archive: Path) -> dict[str, Any]:
    summary = p1c_root / "summary.json"
    if not summary.is_file() or not p1c_stdout.is_file() or not p1c_archive.is_file():
        raise SmokePreflightError("D1 source P1C evidence is missing")
    summary_sha = _sha256_file(summary)
    stdout_sha = _sha256_file(p1c_stdout)
    archive_sha = _sha256_file(p1c_archive)
    if summary_sha != D1_SOURCE_P1C_SUMMARY_SHA256:
        raise SmokePreflightError("D1 source P1C summary hash drift")
    if stdout_sha != D1_SOURCE_P1C_STDOUT_SHA256:
        raise SmokePreflightError("D1 source P1C stdout hash drift")
    if archive_sha != D1_SOURCE_P1C_ARCHIVE_SHA256:
        raise SmokePreflightError("D1 source P1C canonical archive hash drift")
    parsed = json.loads(summary.read_text(encoding="utf-8"))
    if parsed.get("result_digest") != D1_SOURCE_P1C_RESULT_DIGEST:
        raise SmokePreflightError("D1 source P1C result digest drift")
    if parsed.get("status") != "P1C_BASE_WRAPPER_EQUIVALENCE_FAIL":
        raise SmokePreflightError("D1 source P1C status drift")
    return {
        "summary_sha256": summary_sha,
        "stdout_sha256": stdout_sha,
        "archive_sha256": archive_sha,
        "result_digest": parsed["result_digest"],
        "status": parsed["status"],
    }


def _profile(base_model_dir: Path, *, dtype: str, adapter: bool) -> ModelProfile:
    if dtype not in {"bfloat16", "float32"}:
        raise ValueError(dtype)
    if adapter and dtype != "bfloat16":
        raise ValueError("D1 does not define an FP32 PEFT path")
    adapter_ref = (
        ArtifactRef(ArtifactId("F0_FA_V1_FORMAL"), D1_ADAPTER_SHA256) if adapter else None
    )
    suffix = "FA_BF16" if adapter else ("BASE_FP32" if dtype == "float32" else "BASE_BF16")
    return ModelProfile(
        profile_id=f"WORLD_P1C_D1_{suffix}",
        profile_version="1.0.0",
        model_identifier=str(base_model_dir),
        model_revision=D1_BASE_MODEL_REVISION,
        model_digest=D1_BASE_CHECKPOINT_SHA256,
        tokenizer_identifier=str(base_model_dir),
        tokenizer_revision=D1_BASE_MODEL_REVISION,
        tokenizer_digest=D1_TOKENIZER_DIGEST,
        model_class="AUTO_CAUSAL_LM",
        generation_policy_id=D1_DIAGNOSTIC_POLICY_ID,
        device="cuda:0",
        dtype=dtype,
        adapter_ref=adapter_ref,
        trust_remote_code=False,
        add_special_tokens=True,
    )


def _diagnostic_policy() -> GenerationPolicy:
    return GenerationPolicy(
        policy_id=D1_DIAGNOSTIC_POLICY_ID,
        version="1.0.0",
        max_new_tokens=1,
        do_sample=False,
        temperature=None,
        top_p=None,
        top_k=None,
        repetition_penalty=1.0,
        seed_id=D1_DIAGNOSTIC_SEED_ID,
        stop_policy_id=None,
    )


def _compile_cohort(*, store: FileSystemArtifactStore, profile: ModelProfile):
    context_policy = build_context_policy()
    diagnostic = _diagnostic_policy()
    rows = []
    for context_class in D1_CONTEXT_ENUMS:
        for case_index in range(D1_BF16_START, D1_BF16_END + 1):
            compiled = compile_r3_fixture(
                context_class,
                case_index,
                policy=context_policy,
                model_profile_id=profile.profile_id,
                generation_policy_id=diagnostic.policy_id,
                generation_seed_id=D1_DIAGNOSTIC_SEED_ID,
                artifact_store=store,
            )
            rows.append((context_class.value, case_index, compiled))
    if len(rows) != 160:
        raise SmokePreflightError("D1 compiled cohort size drift")
    return tuple(rows)


def _load_bare_runtime(profile: ModelProfile, base_model_dir: Path) -> TransformersModelRuntime:
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
                raise ModelLoadError(f"D1 tokenizer {name} identity mismatch")
        dtype = torch.bfloat16 if profile.dtype == "bfloat16" else torch.float32
        kwargs: dict[str, Any] = {"local_files_only": True, "trust_remote_code": False}
        major = int(str(transformers.__version__).split(".", 1)[0])
        kwargs["dtype" if major >= 5 else "torch_dtype"] = dtype
        model = transformers.AutoModelForCausalLM.from_pretrained(str(base_model_dir), **kwargs)
        model = model.to(profile.device)
        model.eval()
        for parameter in model.parameters():
            parameter.requires_grad_(False)
        if model.training or any(parameter.requires_grad for parameter in model.parameters()):
            raise ModelLoadError("D1 bare model must be eval and frozen")
        return TransformersModelRuntime.from_components(
            profile, tokenizer=tokenizer, model=model, torch_module=torch
        )
    except ModelLoadError:
        raise
    except Exception as error:
        raise ModelLoadError(f"failed to load D1 bare {profile.dtype} runtime") from error


def _runtime_freeze_status(runtime: TransformersModelRuntime) -> dict[str, Any]:
    parameters = tuple(runtime.model.parameters())
    training = bool(getattr(runtime.model, "training", False))
    trainable = sum(int(parameter.requires_grad) for parameter in parameters)
    return {
        "training": training,
        "parameter_tensors": len(parameters),
        "trainable_parameter_tensors": trainable,
        "frozen": (not training and trainable == 0),
    }


def _normalize_full_result(runtime: TransformersModelRuntime, compiled, result) -> dict[str, Any]:
    context_ids, prefix_ids, combined_ids = phase_boundary_token_ids(runtime, compiled.rendered_input)
    by_label = {row.model_label: row for row in result.scores}
    return {
        "context_token_ids": list(context_ids),
        "prefix_token_ids": list(prefix_ids),
        "combined_token_ids": list(combined_ids),
        "scores": [
            {
                "model_label": label,
                "token_ids": list(by_label[label].token_ids),
                "total_log_probability": by_label[label].total_log_probability,
                "mean_log_probability": by_label[label].mean_log_probability,
                "rank": by_label[label].rank,
            }
            for label in ACTION_LABELS
        ],
    }


def _full_score(runtime: TransformersModelRuntime, compiled, *, peft_disabled: bool) -> dict[str, Any]:
    if compiled.artifact_ref is None:
        raise RuntimeError("D1 compiled context requires artifact ref")
    with peft_disabled_state(runtime.model, peft_disabled):
        result = score_action_labels(
            runtime,
            rendered_input=compiled.rendered_input,
            context_hash=compiled.context_pack.context_hash,
            context_pack_ref=compiled.artifact_ref.digest,
            rendered_input_ref=_sha256(compiled.rendered_input),
        )
    record = _normalize_full_result(runtime, compiled, result)
    record["peft_disabled"] = peft_disabled
    record["execution_path"] = "FULL"
    return record


def _bare_cached_score(runtime: TransformersModelRuntime, compiled) -> dict[str, Any]:
    result = score_cached_labels(
        runtime,
        rendered_input=compiled.rendered_input,
        peft_disabled=False,
    )
    record = result.as_record()
    record["execution_path"] = "CACHED"
    return record


def _p1c_cached_score(runtime: TransformersModelRuntime, compiled) -> dict[str, Any]:
    result = score_phase_switched_labels(
        runtime,
        rendered_input=compiled.rendered_input,
        prefill_adapter=False,
        selector_adapter=False,
    )
    return {
        "context_token_ids": list(result.context_token_ids),
        "prefix_token_ids": list(result.prefix_token_ids),
        "combined_token_ids": list(result.combined_token_ids),
        "peft_disabled": True,
        "execution_path": "P1C_CACHED",
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


def _score_path(
    path_name: str,
    runtime: TransformersModelRuntime,
    cohort: Sequence[tuple[str, int, Any]],
    scorer: Callable[[TransformersModelRuntime, Any], dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    records: list[dict[str, Any]] = []
    first_score: dict[str, Any] | None = None
    first_compiled = None
    total_count = len(cohort)
    for ordinal, (context_name, case_index, compiled) in enumerate(cohort, 1):
        score = scorer(runtime, compiled)
        score["context_class"] = context_name
        score["case_index"] = case_index
        score["rendered_input_sha256"] = _sha256(compiled.rendered_input)
        records.append(score)
        if first_score is None:
            first_score = {key: value for key, value in score.items() if key not in {"context_class", "case_index", "rendered_input_sha256"}}
            first_compiled = compiled
        if ordinal % 20 == 0 or ordinal == total_count:
            print(f"D1_{path_name} {ordinal}/{total_count}", flush=True)
    if first_score is None or first_compiled is None:
        raise RuntimeError(f"D1 path {path_name} unexpectedly empty")
    repeat = scorer(runtime, first_compiled)
    repeat_equal = canonical_bytes(first_score) == canonical_bytes(repeat)
    return records, repeat_equal


def _input_identity(paths: Mapping[str, Sequence[Mapping[str, Any]]]) -> bool:
    signatures = []
    for name in sorted(paths):
        signatures.append(
            tuple(
                (row["context_class"], row["case_index"], row["rendered_input_sha256"])
                for row in paths[name]
            )
        )
    return bool(signatures) and all(value == signatures[0] for value in signatures[1:])


def _compact_comparison(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "comparisons": value["comparisons"],
        "token_ids_exact": value["token_ids_exact"],
        "rank_exact": value["rank_exact"],
        "total": value["total"],
        "mean": value["mean"],
    }


def _planned_document(*, paths: DeploymentPaths, git_commit: str, config_sha256: str) -> dict[str, Any]:
    value = {
        "study_id": D1_STUDY_ID,
        "runner_version": D1_RUNNER_VERSION,
        "status": "PLANNED",
        "git_commit": git_commit,
        "protocol_commit": D1_PROTOCOL_COMMIT,
        "config_sha256": config_sha256,
        "base_model_dir": str(paths.base_model_dir),
        "adapter_path": str(paths.adapter_path),
        "bf16_score_sets": 640,
        "fp32_score_sets": 40,
        "repeat_score_sets": 6,
        "generation": False,
        "state_commit": False,
        "weight_update": False,
        "source_p1c_mutation": False,
    }
    value["identity_digest"] = canonical_digest(value)
    return value


def _execute(
    *,
    paths: DeploymentPaths,
    p1c_root: Path,
    p1c_stdout: Path,
    p1c_archive: Path,
    config_sha256: str,
    expected_git_commit: str,
    runtime_freeze_sha256: str,
    runtime_package_count: int,
) -> dict[str, Any]:
    if paths.output_root.exists() and any(paths.output_root.iterdir()):
        raise SmokePreflightError("D1 output root already exists and is non-empty")
    output_resolved = paths.output_root.resolve()
    p1c_resolved = p1c_root.resolve()
    if output_resolved == p1c_resolved or p1c_resolved in output_resolved.parents:
        raise SmokePreflightError("D1 output root must be separate from P1C primary evidence")
    paths.output_root.mkdir(parents=True, exist_ok=True)
    (paths.output_root / "planned.json").write_bytes(
        canonical_bytes(
            _planned_document(paths=paths, git_commit=_git_head(), config_sha256=config_sha256)
        )
    )

    source_before = _verify_source_p1c(p1c_root, p1c_stdout, p1c_archive)
    preflight = _static_preflight(paths, expected_git_commit)
    environment = ensure_execute_environment()
    environment["pip_freeze_sha256"] = runtime_freeze_sha256
    environment["pip_freeze_package_count"] = runtime_package_count

    store = FileSystemArtifactStore(paths.output_root / "cas")
    bf16_profile = _profile(paths.base_model_dir, dtype="bfloat16", adapter=False)
    peft_profile = _profile(paths.base_model_dir, dtype="bfloat16", adapter=True)
    fp32_profile = _profile(paths.base_model_dir, dtype="float32", adapter=False)
    cohort = _compile_cohort(store=store, profile=bf16_profile)
    fp32_subset = tuple(row for row in cohort if row[1] <= D1_FP32_END)
    if len(fp32_subset) != 20:
        raise SmokePreflightError("D1 fixed FP32 subset size drift")

    bare_bf16 = _load_bare_runtime(bf16_profile, paths.base_model_dir)
    peft_bf16 = PeftTransformersLoader(
        base_model_dir=paths.base_model_dir,
        adapter_path=paths.adapter_path,
    )(peft_profile)
    bare_fp32 = _load_bare_runtime(fp32_profile, paths.base_model_dir)
    freeze_status = {
        "BARE_BF16": _runtime_freeze_status(bare_bf16),
        "PEFT_BF16": _runtime_freeze_status(peft_bf16),
        "BARE_FP32": _runtime_freeze_status(bare_fp32),
    }
    if not all(value["frozen"] for value in freeze_status.values()):
        raise SmokePreflightError("D1 runtime freeze requirement failed")

    paths_records: dict[str, list[dict[str, Any]]] = {}
    repeats: dict[str, bool] = {}

    paths_records["E0_BARE_FULL_BF16"], repeats["E0_BARE_FULL_BF16"] = _score_path(
        "E0", bare_bf16, cohort, lambda runtime, compiled: _full_score(runtime, compiled, peft_disabled=False)
    )
    paths_records["E1_BARE_CACHED_BF16"], repeats["E1_BARE_CACHED_BF16"] = _score_path(
        "E1", bare_bf16, cohort, _bare_cached_score
    )
    paths_records["E2_PEFT_DISABLED_FULL_BF16"], repeats["E2_PEFT_DISABLED_FULL_BF16"] = _score_path(
        "E2", peft_bf16, cohort, lambda runtime, compiled: _full_score(runtime, compiled, peft_disabled=True)
    )
    paths_records["E3_PEFT_DISABLED_CACHED_BF16"], repeats["E3_PEFT_DISABLED_CACHED_BF16"] = _score_path(
        "E3", peft_bf16, cohort, _p1c_cached_score
    )
    paths_records["F0_BARE_FULL_FP32"], repeats["F0_BARE_FULL_FP32"] = _score_path(
        "F0", bare_fp32, fp32_subset, lambda runtime, compiled: _full_score(runtime, compiled, peft_disabled=False)
    )
    paths_records["F1_BARE_CACHED_FP32"], repeats["F1_BARE_CACHED_FP32"] = _score_path(
        "F1", bare_fp32, fp32_subset, _bare_cached_score
    )

    bf16_paths = {name: paths_records[name] for name in D1_BF16_PATHS}
    fp32_paths = {name: paths_records[name] for name in D1_FP32_PATHS}
    bf16_inputs_identical = _input_identity(bf16_paths)
    fp32_inputs_identical = _input_identity(fp32_paths)
    matched_subset = tuple(
        (row["context_class"], row["case_index"], row["rendered_input_sha256"])
        for row in paths_records["E0_BARE_FULL_BF16"]
        if int(row["case_index"]) <= D1_FP32_END
    ) == tuple(
        (row["context_class"], row["case_index"], row["rendered_input_sha256"])
        for row in paths_records["F0_BARE_FULL_FP32"]
    )

    contrast_pairs = {
        "CACHE_BARE_BF16": ("E0_BARE_FULL_BF16", "E1_BARE_CACHED_BF16"),
        "WRAPPER_FULL_BF16": ("E0_BARE_FULL_BF16", "E2_PEFT_DISABLED_FULL_BF16"),
        "WRAPPER_CACHED_BF16": ("E1_BARE_CACHED_BF16", "E3_PEFT_DISABLED_CACHED_BF16"),
        "CACHE_PEFT_DISABLED_BF16": ("E2_PEFT_DISABLED_FULL_BF16", "E3_PEFT_DISABLED_CACHED_BF16"),
        "P1C_RECONSTRUCTED": ("E0_BARE_FULL_BF16", "E3_PEFT_DISABLED_CACHED_BF16"),
    }
    contrasts = {
        name: compare_score_records(paths_records[left], paths_records[right])
        for name, (left, right) in contrast_pairs.items()
    }
    e0_subset = [row for row in paths_records["E0_BARE_FULL_BF16"] if int(row["case_index"]) <= D1_FP32_END]
    e1_subset = [row for row in paths_records["E1_BARE_CACHED_BF16"] if int(row["case_index"]) <= D1_FP32_END]
    precision = {
        "CACHE_BARE_BF16_SUBSET": compare_score_records(e0_subset, e1_subset),
        "CACHE_BARE_FP32_SUBSET": compare_score_records(
            paths_records["F0_BARE_FULL_FP32"], paths_records["F1_BARE_CACHED_FP32"]
        ),
    }

    reconstruction = contrasts["P1C_RECONSTRUCTED"]
    reconstruction_exact = (
        reconstruction["total"]["max"] == D1_EXPECTED_RECON_TOTAL
        and reconstruction["mean"]["max"] == D1_EXPECTED_RECON_MEAN
    )
    token_ids_exact = all(value["token_ids_exact"] for value in contrasts.values()) and all(
        value["token_ids_exact"] for value in precision.values()
    )
    complete_counts = all(len(paths_records[name]) == 160 for name in D1_BF16_PATHS) and all(
        len(paths_records[name]) == 20 for name in D1_FP32_PATHS
    )
    repeats_exact = all(repeats.values())
    source_after = _verify_source_p1c(p1c_root, p1c_stdout, p1c_archive)
    source_unchanged = source_after == source_before
    integrity = (
        bf16_inputs_identical
        and fp32_inputs_identical
        and matched_subset
        and token_ids_exact
        and complete_counts
        and repeats_exact
        and source_unchanged
        and all(value["frozen"] for value in freeze_status.values())
    )

    if not reconstruction_exact:
        status = "PRIMARY_RECONSTRUCTION_MISMATCH"
        localization = "NOT_INTERPRETABLE"
    elif not integrity:
        status = "D1_INTEGRITY_FAIL"
        localization = "NOT_INTERPRETABLE"
    else:
        status = "D1_MEASUREMENT_COMPLETE"
        localization = "INTERPRETABLE"

    details = {
        "study_id": D1_STUDY_ID,
        "paths": paths_records,
        "contrasts": contrasts,
        "precision": precision,
        "repeat_exact": repeats,
    }
    details_bytes = canonical_bytes(details)
    details_sha256 = _sha256(details_bytes)
    (paths.output_root / "details.json").write_bytes(details_bytes)

    result = {
        "study_id": D1_STUDY_ID,
        "runner_version": D1_RUNNER_VERSION,
        "status": status,
        "localization": localization,
        "git_commit": _git_head(),
        "protocol_commit": D1_PROTOCOL_COMMIT,
        "config_sha256": config_sha256,
        "environment": environment,
        "preflight": preflight,
        "source_p1c_before": source_before,
        "source_p1c_after": source_after,
        "integrity": {
            "bf16_inputs_identical_160": bf16_inputs_identical,
            "fp32_inputs_identical_20": fp32_inputs_identical,
            "bf16_fp32_subset_inputs_identical_20": matched_subset,
            "token_ids_exact": token_ids_exact,
            "score_set_counts_complete": complete_counts,
            "first_score_exact_repeat": repeats,
            "first_score_exact_repeat_all": repeats_exact,
            "runtime_freeze": freeze_status,
            "source_p1c_unchanged": source_unchanged,
            "state_commits": 0,
            "weight_updates": 0,
            "generation_calls": 0,
        },
        "reconstruction": {
            "expected_max_total_abs_difference": D1_EXPECTED_RECON_TOTAL,
            "observed_max_total_abs_difference": reconstruction["total"]["max"],
            "expected_max_mean_abs_difference": D1_EXPECTED_RECON_MEAN,
            "observed_max_mean_abs_difference": reconstruction["mean"]["max"],
            "exact": reconstruction_exact,
            "original_p1c_tolerance_unchanged": D1_ORIGINAL_P1C_TOLERANCE,
        },
        "contrasts": {name: _compact_comparison(value) for name, value in contrasts.items()},
        "precision": {name: _compact_comparison(value) for name, value in precision.items()},
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
    parser.add_argument("--p1c-root", type=Path, required=True)
    parser.add_argument("--p1c-stdout", type=Path, required=True)
    parser.add_argument("--p1c-archive", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--expected-git-commit", required=True)
    args = parser.parse_args()

    _, config_sha256 = _load_config(args.config)
    paths = DeploymentPaths(
        base_model_dir=args.base_model_dir,
        adapter_path=args.adapter_path,
        output_root=args.output_root,
    )
    preflight = _static_preflight(paths, args.expected_git_commit)
    source_p1c = _verify_source_p1c(args.p1c_root, args.p1c_stdout, args.p1c_archive)
    runtime_freeze_sha256, runtime_package_count = _runtime_freeze_sha256()
    if runtime_freeze_sha256 != D1_PIP_FREEZE_SHA256 or runtime_package_count != D1_RUNTIME_PACKAGE_COUNT:
        raise SmokePreflightError("D1 canonical runtime freeze drift")

    if args.validate_only:
        with tempfile.TemporaryDirectory(prefix="world-p1c-d1-validate-") as temp_dir:
            store = FileSystemArtifactStore(Path(temp_dir) / "cas")
            profile = _profile(args.base_model_dir, dtype="bfloat16", adapter=False)
            cohort = _compile_cohort(store=store, profile=profile)
            fp32_subset = tuple(row for row in cohort if row[1] <= D1_FP32_END)
        print(
            json.dumps(
                {
                    "status": "P1C_D1_STATIC_PREFLIGHT_OK",
                    "git_commit": _git_head(),
                    "config_sha256": config_sha256,
                    "runtime_pip_freeze_sha256": runtime_freeze_sha256,
                    "runtime_package_count": runtime_package_count,
                    "preflight": preflight,
                    "source_p1c": source_p1c,
                    "compiled_contexts": len(cohort),
                    "fp32_subset_contexts": len(fp32_subset),
                    "planned_measurements": {
                        "bf16_score_sets": 640,
                        "fp32_score_sets": 40,
                        "repeat_score_sets": 6,
                        "bf16_label_comparisons_per_contrast": 800,
                        "fp32_label_comparisons": 100,
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
            p1c_root=args.p1c_root,
            p1c_stdout=args.p1c_stdout,
            p1c_archive=args.p1c_archive,
            config_sha256=config_sha256,
            expected_git_commit=args.expected_git_commit,
            runtime_freeze_sha256=runtime_freeze_sha256,
            runtime_package_count=runtime_package_count,
        )
    except Exception as error:
        paths.output_root.mkdir(parents=True, exist_ok=True)
        failure = {
            "study_id": D1_STUDY_ID,
            "status": "D1_EXECUTION_EXCEPTION",
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
                "reconstruction": result["reconstruction"],
                "contrasts": result["contrasts"],
                "precision": result["precision"],
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
