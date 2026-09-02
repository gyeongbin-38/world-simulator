#!/usr/bin/env python3
"""Run frozen WORLD P1C foundation-policy phase ablation.

P1C is a researcher-only mechanistic study. It performs teacher-forced
five-label scoring under four adapter phase conditions and a separate exact-base
control. It never generates executable actions, commits simulation state, or
updates model weights.
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
from alifelm.model.action_diagnostics import score_action_labels  # noqa: E402
from alifelm.model.generation import GenerationPolicy  # noqa: E402
from alifelm.model.p1b_metrics import (  # noqa: E402
    ACTION_LABELS,
    score_structure,
    structural_contrasts,
)
from alifelm.model.p1c_metrics import (  # noqa: E402
    P1C_CASES_PER_CONTEXT,
    P1C_CONDITIONS,
    P1C_CONTEXT_CLASSES,
    P1C_EQUIVALENCE_TOLERANCE,
    P1C_STUDY_ID,
    evaluate_base_wrapper_equivalence,
    evaluate_decoupling_candidate,
    matched_phase_effect,
    rank1_sensitivity,
    structural_gain,
)
from alifelm.model.peft_runtime import PeftTransformersLoader  # noqa: E402
from alifelm.model.phase_scoring import score_phase_switched_labels  # noqa: E402
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


P1C_RUNNER_VERSION = "1.0.0"
P1C_PREREG_COMMIT = "8573d7a57c0a24bf480cb149d457d491e6a9d2ae"
P1C_BASE_MODEL_REVISION = "48d788eca847d4d7548f375ad03d3c9312f6139e"
P1C_BASE_CHECKPOINT_SHA256 = "36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f"
P1C_TOKENIZER_DIGEST = "c448b9e69576a2af5fccdb905c4d6c9f6c0d06509b15d2459a3bc92bb33d42ff"
P1C_ADAPTER_SHA256 = "46917511362243be67e0783ddb7411a96f26613c1083bc4f95117d910d0998ec"
P1C_ADAPTER_CONFIG_SHA256 = "687100a0b6340b6096ca1e86066d3c13224b3c8e14ce9fb1b0cf78a52a8bdb7d"
P1C_PIP_FREEZE_SHA256 = "a98b9c11baf90a5e7717b1f108029838e9c917d46d1f499bf93e9adffad087bf"
P1C_BASE_PROFILE_ID = "WORLD_P1C_BASE_ONLY_BF16"
P1C_FA_PROFILE_ID = "WORLD_P1C_FA_V1_BF16"
P1C_GENERATION_POLICY_ID = "WORLD_P1C_DIAGNOSTIC_ONLY_V1"
P1C_GENERATION_SEED_ID = "WORLD_P1C_NO_GENERATION_V1"
HELDOUT_START = 2000
HELDOUT_END = 2031
CONTEXT_ENUMS = tuple(R3ContextClass(name) for name in P1C_CONTEXT_CLASSES)
PHASE_CONDITIONS: tuple[tuple[str, bool, bool], ...] = (
    ("C00", False, False),
    ("C11", True, True),
    ("C10", True, False),
    ("C01", False, True),
)


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
        raise SmokePreflightError("cannot resolve repository commit") from error


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
    if config.get("study_id") != P1C_STUDY_ID:
        raise SmokePreflightError("P1C config study_id drift")
    if config.get("preregistration_commit") != P1C_PREREG_COMMIT:
        raise SmokePreflightError("P1C preregistration commit drift")
    heldout = config.get("heldout_cohort", {})
    if (
        heldout.get("case_index_start") != HELDOUT_START
        or heldout.get("case_index_end") != HELDOUT_END
        or heldout.get("cases_per_context") != P1C_CASES_PER_CONTEXT
        or heldout.get("contexts") != 160
        or tuple(heldout.get("context_classes", ())) != P1C_CONTEXT_CLASSES
    ):
        raise SmokePreflightError("P1C held-out cohort drift")
    expected_conditions = {
        "C00": {"prefill_adapter": False, "selector_adapter": False},
        "C11": {"prefill_adapter": True, "selector_adapter": True},
        "C10": {"prefill_adapter": True, "selector_adapter": False},
        "C01": {"prefill_adapter": False, "selector_adapter": True},
    }
    if config.get("conditions") != expected_conditions:
        raise SmokePreflightError("P1C phase-condition drift")
    if tuple(config.get("action_labels", ())) != ACTION_LABELS:
        raise SmokePreflightError("P1C action-label drift")
    boundary = config.get("phase_boundary", {})
    if boundary.get("phase_a") != "canonical_r3_world_context_only":
        raise SmokePreflightError("P1C phase-A boundary drift")
    if boundary.get("phase_b_prefix") != '\nAction selection JSON:\n{"action_label":"':
        raise SmokePreflightError("P1C phase-B prefix drift")
    if boundary.get("reuse_past_key_values_without_context_recompute") is not True:
        raise SmokePreflightError("P1C cache-reuse requirement drift")
    equivalence = config.get("base_wrapper_equivalence", {})
    if (
        equivalence.get("contexts") != 160
        or equivalence.get("token_ids_exact") is not True
        or equivalence.get("total_log_probability_abs_tolerance") != P1C_EQUIVALENCE_TOLERANCE
        or equivalence.get("mean_log_probability_abs_tolerance") != P1C_EQUIVALENCE_TOLERANCE
    ):
        raise SmokePreflightError("P1C base-wrapper equivalence drift")
    expected_thresholds = {
        "P1C_G1": {"positive_fraction_min": 0.75, "median_strictly_positive": True},
        "P1C_G2": {"positive_fraction_min": 0.75, "median_strictly_positive": True},
        "P1C_G3": {
            "positive_fraction_min": 0.75,
            "median_strictly_positive": True,
            "structural_contrasts_required": 2,
            "structural_contrasts_total": 3,
        },
        "P1C_G4": {
            "positive_fraction_min": 0.75,
            "median_strictly_positive": True,
            "requires_P1C_G3": True,
        },
        "P1C_G5": {
            "matched_sensitivity_rate_min": 0.25,
            "tvd_min": 0.25,
            "nonquiet_tvd_classes_min": 2,
        },
    }
    if config.get("thresholds") != expected_thresholds:
        raise SmokePreflightError("P1C threshold drift")
    prior = config.get("prior_evidence", {})
    expected_prior = {
        "p1b_results_freeze_commit": "06ee82298fec14c9ac3bc4cfd5bf3c7ec1be9f4c",
        "p1b_summary_sha256": "114c8a894edf80ba5d2dfd4c6b64239ca4d621aa603142bc108976be5416d2b1",
        "p1b_stdout_sha256": "11106dd00171305c7ac6787c140969f67ad701d7ce706d3930282013dcf27bb3",
        "p1b_archive_sha256": "87d815436254d2ed4eafeeeb49fb1d03edd5ccac3dc9949753c2b46dfcd51e6a",
        "p1b_archive_roundtrip_verified": True,
        "p1b_windows_backup_sha256_verified": True,
    }
    if prior != expected_prior:
        raise SmokePreflightError("P1C frozen prior-evidence identity drift")
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
    if result["base_checkpoint_sha256"] != P1C_BASE_CHECKPOINT_SHA256:
        raise SmokePreflightError("P1C base checkpoint identity drift")
    if result["tokenizer_digest"] != P1C_TOKENIZER_DIGEST:
        raise SmokePreflightError("P1C tokenizer identity drift")
    if result["adapter_sha256"] != P1C_ADAPTER_SHA256:
        raise SmokePreflightError("P1C adapter identity drift")
    if result["adapter_config_sha256"] != P1C_ADAPTER_CONFIG_SHA256:
        raise SmokePreflightError("P1C adapter config identity drift")
    return result


def _profile(base_model_dir: Path, *, adapter: bool) -> ModelProfile:
    adapter_ref = (
        ArtifactRef(ArtifactId("F0_FA_V1_FORMAL"), P1C_ADAPTER_SHA256) if adapter else None
    )
    return ModelProfile(
        profile_id=P1C_FA_PROFILE_ID if adapter else P1C_BASE_PROFILE_ID,
        profile_version="1.0.0",
        model_identifier=str(base_model_dir),
        model_revision=P1C_BASE_MODEL_REVISION,
        model_digest=P1C_BASE_CHECKPOINT_SHA256,
        tokenizer_identifier=str(base_model_dir),
        tokenizer_revision=P1C_BASE_MODEL_REVISION,
        tokenizer_digest=P1C_TOKENIZER_DIGEST,
        model_class="AUTO_CAUSAL_LM",
        generation_policy_id=P1C_GENERATION_POLICY_ID,
        device="cuda:0",
        dtype="bfloat16",
        adapter_ref=adapter_ref,
        trust_remote_code=False,
        add_special_tokens=True,
    )


def _diagnostic_policy() -> GenerationPolicy:
    return GenerationPolicy(
        policy_id=P1C_GENERATION_POLICY_ID,
        version="1.0.0",
        max_new_tokens=1,
        do_sample=False,
        temperature=None,
        top_p=None,
        top_k=None,
        repetition_penalty=1.0,
        seed_id=P1C_GENERATION_SEED_ID,
        stop_policy_id=None,
    )


def _compile_cohort(*, store: FileSystemArtifactStore, profile: ModelProfile):
    policy = build_context_policy()
    diagnostic = _diagnostic_policy()
    rows = []
    for context_class in CONTEXT_ENUMS:
        for case_index in range(HELDOUT_START, HELDOUT_END + 1):
            compiled = compile_r3_fixture(
                context_class,
                case_index,
                policy=policy,
                model_profile_id=profile.profile_id,
                generation_policy_id=diagnostic.policy_id,
                generation_seed_id=P1C_GENERATION_SEED_ID,
                artifact_store=store,
            )
            rows.append((context_class.value, case_index, compiled))
    if len(rows) != 160:
        raise SmokePreflightError("P1C compiled cohort size drift")
    return tuple(rows)


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
        kwargs: dict[str, Any] = {"local_files_only": True, "trust_remote_code": False}
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
    parameters = tuple(runtime.model.parameters())
    trainable = sum(int(parameter.requires_grad) for parameter in parameters)
    training = bool(getattr(runtime.model, "training", False))
    return {
        "training": training,
        "parameter_tensors": len(parameters),
        "trainable_parameter_tensors": trainable,
        "frozen": (not training and trainable == 0),
    }


def _ordinary_base_score(runtime: TransformersModelRuntime, compiled) -> dict[str, Any]:
    if compiled.artifact_ref is None:
        raise RuntimeError("P1C compiled context requires CAS artifact ref")
    result = score_action_labels(
        runtime,
        rendered_input=compiled.rendered_input,
        context_hash=compiled.context_pack.context_hash,
        context_pack_ref=compiled.artifact_ref.digest,
        rendered_input_ref=_sha256(compiled.rendered_input),
    )
    return {
        "totals": {row.model_label: row.total_log_probability for row in result.scores},
        "means": {row.model_label: row.mean_log_probability for row in result.scores},
        "ranks": {row.model_label: row.rank for row in result.scores},
        "token_ids": {row.model_label: list(row.token_ids) for row in result.scores},
    }


def _phase_score(runtime: TransformersModelRuntime, compiled, *, prefill: bool, selector: bool):
    result = score_phase_switched_labels(
        runtime,
        rendered_input=compiled.rendered_input,
        prefill_adapter=prefill,
        selector_adapter=selector,
    )
    return result, {
        "prefill_adapter": prefill,
        "selector_adapter": selector,
        "context_token_ids": list(result.context_token_ids),
        "prefix_token_ids": list(result.prefix_token_ids),
        "combined_token_ids": list(result.combined_token_ids),
        "phase_boundary_token_aligned": result.phase_boundary_token_aligned,
        "prefill_forward_count": result.prefill_forward_count,
        "selector_prefix_forward_count": result.selector_prefix_forward_count,
        "totals": result.totals(),
        "means": result.means(),
        "ranks": {row.model_label: row.rank for row in result.scores},
        "token_ids": {row.model_label: list(row.token_ids) for row in result.scores},
        "rank1": result.rank1_label(),
    }


def _phase_equal(left, right) -> bool:
    return (
        left.context_token_ids == right.context_token_ids
        and left.prefix_token_ids == right.prefix_token_ids
        and left.combined_token_ids == right.combined_token_ids
        and left.scores == right.scores
    )


def _planned_document(*, paths: DeploymentPaths, git_commit: str, config_sha256: str):
    value = {
        "study_id": P1C_STUDY_ID,
        "schema_version": "1.0.0",
        "runner_version": P1C_RUNNER_VERSION,
        "status": "PLANNED",
        "git_commit": git_commit,
        "preregistration_commit": P1C_PREREG_COMMIT,
        "config_sha256": config_sha256,
        "deployment": {
            "base_model_dir": str(paths.base_model_dir),
            "adapter_path": str(paths.adapter_path),
            "base_checkpoint_sha256": P1C_BASE_CHECKPOINT_SHA256,
            "tokenizer_digest": P1C_TOKENIZER_DIGEST,
            "adapter_sha256": P1C_ADAPTER_SHA256,
        },
        "heldout": {"case_start": HELDOUT_START, "case_end": HELDOUT_END, "contexts": 160},
        "conditions": list(P1C_CONDITIONS),
        "ordinary_base_score_sets": 160,
        "phase_score_sets": 640,
        "phase_repeat_score_sets": 4,
        "state_commit": False,
        "weight_update": False,
        "behavioral_admission": False,
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
) -> dict[str, Any]:
    if paths.output_root.exists() and any(paths.output_root.iterdir()):
        raise SmokePreflightError("P1C output root already exists and is non-empty")
    paths.output_root.mkdir(parents=True, exist_ok=True)
    planned = _planned_document(
        paths=paths, git_commit=_git_head(), config_sha256=config_sha256
    )
    (paths.output_root / "planned.json").write_bytes(canonical_bytes(planned))

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
            "context_class": context_name,
            "case_index": case_index,
            "context_hash": compiled.context_pack.context_hash,
            "rendered_sha256": _sha256(compiled.rendered_input),
        }
        for context_name, case_index, compiled in cohort
    ]
    context_audit_ref = store.put_bytes(
        canonical_bytes(context_audit),
        media_type="application/json",
        contract_id="p1c-context-audit-1.0.0",
    )

    base_runtime = _load_base_runtime(base_profile, paths.base_model_dir)
    fa_runtime = PeftTransformersLoader(
        base_model_dir=paths.base_model_dir,
        adapter_path=paths.adapter_path,
    )(fa_profile)
    base_freeze = _runtime_freeze_status(base_runtime)
    fa_freeze = _runtime_freeze_status(fa_runtime)
    if not base_freeze["frozen"] or not fa_freeze["frozen"]:
        raise SmokePreflightError("P1C model runtime is not frozen")

    # Mandatory equivalence control is evaluated first. If it fails, no
    # phase-attribution inference is spent on C11/C10/C01.
    base_details: list[dict[str, Any]] = []
    c00_details: list[dict[str, Any]] = []
    token_equal: list[bool] = []
    total_diffs: list[float] = []
    mean_diffs: list[float] = []
    c00_first = None
    c00_first_compiled = None

    for ordinal, (context_name, case_index, compiled) in enumerate(cohort, 1):
        base = _ordinary_base_score(base_runtime, compiled)
        c00, c00_record = _phase_score(
            fa_runtime, compiled, prefill=False, selector=False
        )
        base_details.append(
            {
                "context_class": context_name,
                "case_index": case_index,
                "rendered_sha256": _sha256(compiled.rendered_input),
                **base,
            }
        )
        c00_record.update(
            {
                "condition": "C00",
                "context_class": context_name,
                "case_index": case_index,
                "rendered_sha256": _sha256(compiled.rendered_input),
            }
        )
        c00_details.append(c00_record)
        for label in ACTION_LABELS:
            token_equal.append(base["token_ids"][label] == c00_record["token_ids"][label])
            total_diffs.append(abs(base["totals"][label] - c00_record["totals"][label]))
            mean_diffs.append(abs(base["means"][label] - c00_record["means"][label]))
        if c00_first is None:
            c00_first = c00
            c00_first_compiled = compiled
        if ordinal % 20 == 0 or ordinal == len(cohort):
            print(f"P1C_EQUIVALENCE {ordinal}/{len(cohort)}", flush=True)

    equivalence = evaluate_base_wrapper_equivalence(
        token_ids_equal=token_equal,
        total_abs_differences=total_diffs,
        mean_abs_differences=mean_diffs,
    )
    base_ref = store.put_bytes(
        canonical_bytes(base_details),
        media_type="application/json",
        contract_id="p1c-ordinary-base-details-1.0.0",
    )
    c00_ref = store.put_bytes(
        canonical_bytes(c00_details),
        media_type="application/json",
        contract_id="p1c-c00-details-1.0.0",
    )

    if c00_first is None or c00_first_compiled is None:
        raise RuntimeError("P1C C00 cohort unexpectedly empty")
    c00_repeat, _ = _phase_score(
        fa_runtime, c00_first_compiled, prefill=False, selector=False
    )
    repeat_equal: dict[str, bool] = {"C00": _phase_equal(c00_first, c00_repeat)}

    if not equivalence.passed:
        result = {
            "study_id": P1C_STUDY_ID,
            "status": "P1C_BASE_WRAPPER_EQUIVALENCE_FAIL",
            "git_commit": _git_head(),
            "preregistration_commit": P1C_PREREG_COMMIT,
            "config_sha256": config_sha256,
            "environment": environment,
            "preflight": preflight,
            "gates": {
                "P1C-G0": False,
                "P1C-G1": None,
                "P1C-G2": None,
                "P1C-G3": None,
                "P1C-G4": None,
                "P1C-G5": None,
            },
            "base_wrapper_equivalence": equivalence.as_dict(),
            "integrity": {
                "ordinary_base_score_sets": len(base_details),
                "C00_score_sets": len(c00_details),
                "C00_exact_repeat_equal": repeat_equal["C00"],
                "runtime_freeze": {"BASE_ONLY": base_freeze, "FA_V1": fa_freeze},
                "state_commits": 0,
                "weight_updates": 0,
            },
            "ordinary_base_details_ref": base_ref.digest,
            "C00_details_ref": c00_ref.digest,
            "context_audit_ref": context_audit_ref.digest,
            "founder_freeze": "NOT_ESTABLISHABLE_BY_P1C",
            "behavioral_admission": False,
        }
        result["result_digest"] = canonical_digest(result)
        (paths.output_root / "summary.json").write_bytes(canonical_bytes(result))
        return result

    phase_details: dict[str, list[dict[str, Any]]] = {"C00": c00_details, "C11": [], "C10": [], "C01": []}
    score_maps: dict[str, dict[tuple[str, int], dict[str, float]]] = {
        condition: {} for condition in P1C_CONDITIONS
    }
    rank1_by_context: dict[str, dict[str, list[str]]] = {
        condition: {name: [] for name in P1C_CONTEXT_CLASSES}
        for condition in P1C_CONDITIONS
    }
    token_signatures: dict[tuple[str, int], tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]] = {}

    for record in c00_details:
        key = (record["context_class"], record["case_index"])
        score_maps["C00"][key] = dict(record["totals"])
        rank1_by_context["C00"][record["context_class"]].append(record["rank1"])
        token_signatures[key] = (
            tuple(record["context_token_ids"]),
            tuple(record["prefix_token_ids"]),
            tuple(record["combined_token_ids"]),
        )

    for condition, prefill, selector in PHASE_CONDITIONS[1:]:
        first_result = None
        first_compiled = None
        for ordinal, (context_name, case_index, compiled) in enumerate(cohort, 1):
            phase_result, record = _phase_score(
                fa_runtime, compiled, prefill=prefill, selector=selector
            )
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
                raise SmokePreflightError("P1C tokenization differs across phase conditions")
            phase_details[condition].append(record)
            score_maps[condition][key] = dict(record["totals"])
            rank1_by_context[condition][context_name].append(record["rank1"])
            if first_result is None:
                first_result = phase_result
                first_compiled = compiled
            if ordinal % 20 == 0 or ordinal == len(cohort):
                print(f"P1C_SCORE_{condition} {ordinal}/{len(cohort)}", flush=True)
        if first_result is None or first_compiled is None:
            raise RuntimeError(f"P1C {condition} cohort unexpectedly empty")
        repeat, _ = _phase_score(
            fa_runtime, first_compiled, prefill=prefill, selector=selector
        )
        repeat_equal[condition] = _phase_equal(first_result, repeat)

    details_ref = store.put_bytes(
        canonical_bytes(phase_details),
        media_type="application/json",
        contract_id="p1c-phase-score-details-1.0.0",
    )

    complete = all(len(phase_details[name]) == 160 for name in P1C_CONDITIONS)
    labels_complete = all(
        set(record["totals"]) == set(ACTION_LABELS)
        for name in P1C_CONDITIONS
        for record in phase_details[name]
    )
    one_prefill_each = all(
        record["prefill_forward_count"] == 1 and record["selector_prefix_forward_count"] == 1
        for name in P1C_CONDITIONS
        for record in phase_details[name]
    )
    phase_flags_correct = all(
        record["prefill_adapter"] == dict((c, (p, s)) for c, p, s in PHASE_CONDITIONS)[name][0]
        and record["selector_adapter"] == dict((c, (p, s)) for c, p, s in PHASE_CONDITIONS)[name][1]
        for name in P1C_CONDITIONS
        for record in phase_details[name]
    )
    g0 = (
        equivalence.passed
        and complete
        and labels_complete
        and one_prefill_each
        and phase_flags_correct
        and all(repeat_equal.values())
        and base_freeze["frozen"]
        and fa_freeze["frozen"]
    )

    g1 = g2 = g3 = g4_reduction = None
    g4_pass = None
    g5 = None
    if g0:
        margins: dict[str, list[float]] = {name: [] for name in P1C_CONDITIONS}
        for condition in P1C_CONDITIONS:
            for context_name in P1C_CONTEXT_CLASSES:
                for case_index in range(HELDOUT_START, HELDOUT_END + 1):
                    margins[condition].append(
                        score_structure(score_maps[condition][(context_name, case_index)]).wait_margin
                    )
        g1 = matched_phase_effect(margins["C00"], margins["C01"])
        g2 = matched_phase_effect(margins["C00"], margins["C10"])

        contrasts: dict[str, dict[str, list[float]]] = {
            condition: {"S_msg": [], "S_prop": [], "S_owner": []}
            for condition in P1C_CONDITIONS
        }
        for condition in P1C_CONDITIONS:
            for case_index in range(HELDOUT_START, HELDOUT_END + 1):
                matched = {
                    context_name: score_maps[condition][(context_name, case_index)]
                    for context_name in P1C_CONTEXT_CLASSES
                }
                values = structural_contrasts(matched)
                for name, value in values.items():
                    contrasts[condition][name].append(value)
        g3 = structural_gain(contrasts["C00"], contrasts["C10"])
        g4_reduction, g4_pass = evaluate_decoupling_candidate(
            structural_carryover_pass=g3.passed,
            c11_margins=margins["C11"],
            c10_margins=margins["C10"],
        )
        g5 = {
            condition: rank1_sensitivity(rank1_by_context[condition]).as_dict()
            for condition in P1C_CONDITIONS
        }

    result = {
        "study_id": P1C_STUDY_ID,
        "status": "P1C_MEASUREMENT_COMPLETE" if g0 else "P1C_INTEGRITY_FAIL",
        "git_commit": _git_head(),
        "preregistration_commit": P1C_PREREG_COMMIT,
        "config_sha256": config_sha256,
        "environment": environment,
        "preflight": preflight,
        "gates": {
            "P1C-G0": g0,
            "P1C-G1": g1.passed if g1 is not None else None,
            "P1C-G2": g2.passed if g2 is not None else None,
            "P1C-G3": g3.passed if g3 is not None else None,
            "P1C-G4": g4_pass,
            "P1C-G5": (
                {condition: g5[condition]["pass"] for condition in P1C_CONDITIONS}
                if g5 is not None
                else None
            ),
        },
        "base_wrapper_equivalence": equivalence.as_dict(),
        "P1C_G1_decode_side_wait_induction": g1.as_dict() if g1 is not None else None,
        "P1C_G2_prefill_side_wait_induction": g2.as_dict() if g2 is not None else None,
        "P1C_G3_structural_carryover": g3.as_dict() if g3 is not None else None,
        "P1C_G4_decoupling_candidate": (
            {"wait_reduction": g4_reduction.as_dict(), "pass": g4_pass}
            if g4_reduction is not None
            else None
        ),
        "P1C_G5_rank1_sensitivity": g5,
        "integrity": {
            "ordinary_base_score_sets": len(base_details),
            "phase_score_sets": {name: len(phase_details[name]) for name in P1C_CONDITIONS},
            "phase_tokenization_identical": True,
            "phase_boundary_token_aligned": all(
                record["phase_boundary_token_aligned"]
                for name in P1C_CONDITIONS
                for record in phase_details[name]
            ),
            "cache_prefill_once_per_score_set": one_prefill_each,
            "phase_flags_correct": phase_flags_correct,
            "exact_repeat_equal": repeat_equal,
            "runtime_freeze": {"BASE_ONLY": base_freeze, "FA_V1": fa_freeze},
            "state_commits": 0,
            "weight_updates": 0,
        },
        "ordinary_base_details_ref": base_ref.digest,
        "C00_details_ref": c00_ref.digest,
        "phase_details_ref": details_ref.digest,
        "context_audit_ref": context_audit_ref.digest,
        "founder_freeze": "NOT_ESTABLISHABLE_BY_P1C",
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
    runtime_freeze_sha256, runtime_package_count = _runtime_freeze_sha256()
    if runtime_freeze_sha256 != P1C_PIP_FREEZE_SHA256:
        raise SmokePreflightError(
            f"P1C runtime freeze drift: expected {P1C_PIP_FREEZE_SHA256}, got {runtime_freeze_sha256}"
        )

    if args.validate_only:
        print(
            json.dumps(
                {
                    "status": "P1C_STATIC_PREFLIGHT_OK",
                    "git_commit": _git_head(),
                    "config_sha256": config_sha256,
                    "runtime_pip_freeze_sha256": runtime_freeze_sha256,
                    "runtime_package_count": runtime_package_count,
                    "preflight": preflight,
                    "planned_measurements": {
                        "ordinary_base_score_sets": 160,
                        "phase_score_sets": 640,
                        "phase_repeat_score_sets": 4,
                        "base_wrapper_label_comparisons": 800,
                    },
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
            runtime_freeze_sha256=runtime_freeze_sha256,
            runtime_package_count=runtime_package_count,
        )
    except Exception as error:
        paths.output_root.mkdir(parents=True, exist_ok=True)
        failure = {
            "study_id": P1C_STUDY_ID,
            "status": "P1C_EXECUTION_EXCEPTION",
            "git_commit": _git_head(),
            "error_type": type(error).__name__,
            "error_message": str(error),
        }
        (paths.output_root / "failure.json").write_bytes(canonical_bytes(failure))
        raise

    compact = {
        "status": result["status"],
        "gates": result["gates"],
        "base_wrapper_equivalence": result["base_wrapper_equivalence"],
        "result_digest": result["result_digest"],
        "summary": str(paths.output_root / "summary.json"),
    }
    print(json.dumps(compact, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
