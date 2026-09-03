#!/usr/bin/env python3
"""Run preregistered WORLD P2-D3 targeted adapter scaling repair diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))
sys.path.insert(0, str(REPOSITORY_ROOT))

from alifelm.model.p2_d1_boundary import D1_ACTION_ORDER, score_i3_decision_boundary  # noqa: E402
from alifelm.model.p2_d3_adapter_scale import lora_layer_scale  # noqa: E402
from alifelm.model.p2_d3_metrics import full_cohort_summary, select_scale, summarize_scale  # noqa: E402
from alifelm.model.peft_runtime import PeftTransformersLoader  # noqa: E402
from alifelm.model.treatments import I3_CONDITIONAL_TYPED_CODEC  # noqa: E402
from alifelm.model.world_v0_smoke import (  # noqa: E402
    DeploymentPaths,
    SmokePreflightError,
    canonical_bytes,
    ensure_execute_environment,
)
from alifelm.persistence import FileSystemArtifactStore  # noqa: E402
from tools.world_p2_d2_kv_cache_causal_localization import (  # noqa: E402
    PIP_FREEZE_SHA256,
    RUNTIME_PACKAGE_COUNT,
    _archive_member_bytes,
    _assert_matches_d1,
    _compile_and_verify,
    _profile,
    _policy,
    _runtime_freeze_sha256,
    _score_record,
    _source_map,
    _static_preflight,
    _verify_source_d1,
)


STUDY_ID = "WORLD_P2_D3_TARGETED_ADAPTER_SCALING_V1"
RUNNER_VERSION = "1.0.0"
PREREG_COMMIT = "8cbba8828fbb3f5b6bb496f2476c78b420036296"
CONFIG_RELPATH = "docs/research/world/WORLD_P2_D3_TARGETED_ADAPTER_SCALING_CONFIG_V1.json"
SOURCE_D2_STUDY_ID = "WORLD_P2_D2_KV_CACHE_CAUSAL_LOCALIZATION_V1"
SOURCE_D2_RESULT_DIGEST = "cf03450cdcde79e0f2fe78b4caf7bda6df99bec159246a15817194dcc61b9a61"
SOURCE_D2_DETAILS_SHA256 = "e554f6a113597cd8d3f1d9c923f7ee4e17c59c51e9933cd398a2118f15731608"
SOURCE_D2_ARCHIVE_SHA256 = "f811de72d5faf1e9d56de534f73c8ecac101d5e22f12256ea00c14be6b101559"
SOURCE_D2_ROOT_NAME = "WORLD_P2_D2_KV_CACHE_CAUSAL_LOCALIZATION_V1_R2"
SOURCE_D2_STDOUT_NAME = f"{SOURCE_D2_ROOT_NAME}.stdout.log"
TARGET_LAYERS = (9, 10)
SCALE_CANDIDATES = (0.0, 0.25, 0.5, 0.75, 1.0)
SCREEN_CASES = range(4000, 4004)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPOSITORY_ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _verify_prereg_config(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    frozen = subprocess.run(
        ["git", "show", f"{PREREG_COMMIT}:{CONFIG_RELPATH}"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
    ).stdout
    if raw != frozen:
        raise SmokePreflightError("P2-D3 preregistered config bytes drifted")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", PREREG_COMMIT, "HEAD"], cwd=REPOSITORY_ROOT
    )
    if ancestor.returncode != 0:
        raise SmokePreflightError("P2-D3 preregistration commit is not an ancestor of HEAD")
    config = json.loads(raw.decode("utf-8"))
    if (
        config.get("study_id") != STUDY_ID
        or config.get("status") != "PREREGISTERED_REPAIR_DIAGNOSTIC"
        or tuple(config.get("source_d2_selected_layers", ())) != TARGET_LAYERS
        or tuple(float(value) for value in config.get("intervention", {}).get("scale_candidates", ())) != SCALE_CANDIDATES
    ):
        raise SmokePreflightError("P2-D3 config semantic identity drift")
    return config, _sha256(raw)


def _verify_source_d2(root: Path, stdout: Path, archive: Path) -> tuple[dict[str, str], dict[str, Any]]:
    summary = root / "summary.json"
    details = root / "details.json"
    if any(not path.is_file() for path in (summary, details, stdout, archive)):
        raise SmokePreflightError("P2-D3 source D2 evidence is incomplete")
    if _file_sha256(archive) != SOURCE_D2_ARCHIVE_SHA256:
        raise SmokePreflightError("P2-D3 source D2 canonical archive SHA-256 drift")
    summary_bytes, details_bytes, stdout_bytes = summary.read_bytes(), details.read_bytes(), stdout.read_bytes()
    if _sha256(details_bytes) != SOURCE_D2_DETAILS_SHA256:
        raise SmokePreflightError("P2-D3 source D2 details SHA-256 drift")
    payload = json.loads(summary_bytes.decode("utf-8"))
    if (
        payload.get("study_id") != SOURCE_D2_STUDY_ID
        or payload.get("status") != "P2_D2_MEASUREMENT_COMPLETE"
        or payload.get("result_digest") != SOURCE_D2_RESULT_DIGEST
        or payload.get("integrity", {}).get("pass") is not True
        or payload.get("localization") != "UNION_BIDIRECTIONAL_NONUNIVERSAL"
        or payload.get("selected_layers") != [9, 10]
    ):
        raise SmokePreflightError("P2-D3 source D2 semantic identity drift")
    checks = {
        f"alifelm/evidence/{SOURCE_D2_ROOT_NAME}/summary.json": summary_bytes,
        f"alifelm/evidence/{SOURCE_D2_ROOT_NAME}/details.json": details_bytes,
        SOURCE_D2_STDOUT_NAME: stdout_bytes,
    }
    for suffix, local in checks.items():
        if _archive_member_bytes(archive, suffix) != local:
            raise SmokePreflightError("P2-D3 unpacked D2 source differs from canonical archive")
    observed = {
        "d2_summary_sha256": _sha256(summary_bytes),
        "d2_details_sha256": _sha256(details_bytes),
        "d2_stdout_sha256": _sha256(stdout_bytes),
        "d2_archive_sha256": SOURCE_D2_ARCHIVE_SHA256,
    }
    return observed, payload


def _screen_rows(cohort):
    return [row for row in cohort if row[1] in SCREEN_CASES]


def _lora_scaling_snapshot(model: Any) -> tuple[tuple[str, tuple[tuple[str, str], ...]], ...]:
    rows = []
    for name, module in model.named_modules():
        scaling = getattr(module, "scaling", None)
        if isinstance(scaling, dict) and scaling and (hasattr(module, "lora_A") or hasattr(module, "lora_B")):
            rows.append((name, tuple(sorted((str(key), repr(value)) for key, value in scaling.items()))))
    return tuple(rows)


def _scaled_score(runtime, rendered: bytes, scale: float):
    with lora_layer_scale(runtime.model, {9: scale, 10: scale}) as applied:
        score = score_i3_decision_boundary(
            runtime,
            rendered_input=rendered,
            prefill_adapter=True,
            selector_adapter=False,
        )
    return score, applied


def _record(score, *, context: str, case: int, scale: float, applied) -> dict[str, Any]:
    payload = _score_record(score, condition=f"L9_L10_SCALE_{scale:.2f}", layers=TARGET_LAYERS)
    payload.update({
        "context_class": context,
        "case_index": case,
        "scale": scale,
        "matched_modules_by_layer": [list(item) for item in applied.matched_modules_by_layer],
        "matched_module_names": list(applied.matched_module_names),
    })
    return payload


def _run_stage_a(runtime, cohort, d1_details):
    c10 = _source_map(d1_details, "C10")
    records_by_scale: dict[float, list[dict[str, Any]]] = {scale: [] for scale in SCALE_CANDIDATES}
    expected_modules = None
    for scale in SCALE_CANDIDATES:
        for ordinal, (context, case, compiled) in enumerate(_screen_rows(cohort), 1):
            rendered = I3_CONDITIONAL_TYPED_CODEC.render(compiled.rendered_input)
            score, applied = _scaled_score(runtime, rendered, scale)
            if scale == 1.0:
                _assert_matches_d1(score, c10[(context, case)], D1_ACTION_ORDER)
            module_identity = (applied.matched_modules_by_layer, applied.matched_module_names)
            if expected_modules is None:
                expected_modules = module_identity
            elif module_identity != expected_modules:
                raise SmokePreflightError("P2-D3 LoRA target-module identity changed during Stage A")
            records_by_scale[scale].append(_record(score, context=context, case=case, scale=scale, applied=applied))
            if ordinal % 5 == 0:
                print(f"P2_D3_STAGEA SCALE={scale:.2f} {ordinal}/20", flush=True)
    summaries = {scale: summarize_scale(records, scale) for scale, records in records_by_scale.items()}
    selected = select_scale(summaries)
    return records_by_scale, summaries, selected, expected_modules


def _run_stage_b(runtime, cohort, d1_details, selected_scale: float, *, repeat: bool = False):
    c10 = _source_map(d1_details, "C10")
    records = []
    expected_modules = None
    for ordinal, (context, case, compiled) in enumerate(cohort, 1):
        rendered = I3_CONDITIONAL_TYPED_CODEC.render(compiled.rendered_input)
        score, applied = _scaled_score(runtime, rendered, selected_scale)
        if selected_scale == 1.0:
            _assert_matches_d1(score, c10[(context, case)], D1_ACTION_ORDER)
        module_identity = (applied.matched_modules_by_layer, applied.matched_module_names)
        if expected_modules is None:
            expected_modules = module_identity
        elif module_identity != expected_modules:
            raise SmokePreflightError("P2-D3 LoRA target-module identity changed during Stage B")
        records.append(_record(score, context=context, case=case, scale=selected_scale, applied=applied))
        if ordinal % 20 == 0:
            label = "REPEAT" if repeat else "STAGEB"
            print(f"P2_D3_{label} {ordinal}/160", flush=True)
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--base-model-dir", type=Path, required=True)
    parser.add_argument("--adapter-path", type=Path, required=True)
    parser.add_argument("--d1-root", type=Path, required=True)
    parser.add_argument("--d1-stdout", type=Path, required=True)
    parser.add_argument("--d1-archive", type=Path, required=True)
    parser.add_argument("--d2-root", type=Path, required=True)
    parser.add_argument("--d2-stdout", type=Path, required=True)
    parser.add_argument("--d2-archive", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--expected-git-commit", required=True)
    args = parser.parse_args()

    config, config_sha = _verify_prereg_config(args.config)
    if _git_head() != args.expected_git_commit:
        raise SmokePreflightError("P2-D3 expected git commit mismatch")
    source_d1_paths = {"root": args.d1_root, "stdout": args.d1_stdout, "archive": args.d1_archive}
    source_d2_paths = {"root": args.d2_root, "stdout": args.d2_stdout, "archive": args.d2_archive}
    d1_before, d1_details = _verify_source_d1(**source_d1_paths)
    d2_before, _ = _verify_source_d2(**source_d2_paths)
    freeze_sha, package_count = _runtime_freeze_sha256()
    if freeze_sha != PIP_FREEZE_SHA256 or package_count != RUNTIME_PACKAGE_COUNT:
        raise SmokePreflightError("P2-D3 canonical runtime freeze drift")
    model_config = json.loads((args.base_model_dir / "config.json").read_text(encoding="utf-8"))
    if int(model_config.get("num_hidden_layers", -1)) != 16:
        raise SmokePreflightError("P2-D3 model config does not expose 16 hidden layers")

    paths = DeploymentPaths(args.base_model_dir, args.adapter_path, args.output_root)
    preflight = _static_preflight(paths, args.expected_git_commit)
    profile, policy = _profile(args.base_model_dir), _policy()

    if args.validate_only:
        with tempfile.TemporaryDirectory(prefix="world-p2-d3-validate-") as tmp:
            cohort = _compile_and_verify(FileSystemArtifactStore(Path(tmp) / "cas"), profile, policy, d1_details)
        print(json.dumps({
            "status": "P2_D3_STATIC_PREFLIGHT_OK",
            "study_id": STUDY_ID,
            "git_commit": _git_head(),
            "prereg_commit": PREREG_COMMIT,
            "config_sha256": config_sha,
            "source_d1": d1_before,
            "source_d2": d2_before,
            "runtime_pip_freeze_sha256": freeze_sha,
            "runtime_package_count": package_count,
            "compiled_contexts": len(cohort),
            "screening_contexts": 20,
            "target_layers": list(TARGET_LAYERS),
            "scale_candidates": list(SCALE_CANDIDATES),
            "model_loaded": False,
            "simulation_state_commit": False,
            "weight_update": False,
        }, sort_keys=True))
        return 0

    if args.output_root.exists():
        raise SmokePreflightError("P2-D3 output root already exists; failed attempts are immutable")
    args.output_root.mkdir(parents=True, exist_ok=False)
    environment = ensure_execute_environment()
    (args.output_root / "run_plan.json").write_bytes(canonical_bytes({
        "study_id": STUDY_ID,
        "runner_version": RUNNER_VERSION,
        "git_commit": _git_head(),
        "prereg_commit": PREREG_COMMIT,
        "config_sha256": config_sha,
        "source_d1": d1_before,
        "source_d2": d2_before,
        "screening_cases": list(SCREEN_CASES),
        "target_layers": list(TARGET_LAYERS),
        "scale_candidates": list(SCALE_CANDIDATES),
        "selection_rule": config["stageA"]["selection_rule_lexicographic"],
        "simulation_state_commit": False,
        "weight_update": False,
    }))

    store = FileSystemArtifactStore(args.output_root / "cas")
    cohort = _compile_and_verify(store, profile, policy, d1_details)
    runtime = PeftTransformersLoader(base_model_dir=args.base_model_dir, adapter_path=args.adapter_path)(profile)
    scaling_before = _lora_scaling_snapshot(runtime.model)
    if not scaling_before:
        raise SmokePreflightError("P2-D3 loaded runtime exposes no LoRA scaling metadata")

    stage_a, stage_a_summaries, selected_scale, module_identity = _run_stage_a(runtime, cohort, d1_details)
    stage_b = _run_stage_b(runtime, cohort, d1_details, selected_scale)
    repeat = _run_stage_b(runtime, cohort, d1_details, selected_scale, repeat=True)
    scaling_after = _lora_scaling_snapshot(runtime.model)

    repeat_equal = stage_b == repeat
    scaling_restored = scaling_before == scaling_after
    d1_after, _ = _verify_source_d1(**source_d1_paths)
    d2_after, _ = _verify_source_d2(**source_d2_paths)
    integrity = bool(repeat_equal and scaling_restored and d1_before == d1_after and d2_before == d2_after)
    stage_b_summary = full_cohort_summary(stage_b)
    proxy_label = (
        "SCORE_CONTEXT_SENSITIVE_REPAIR_CANDIDATE"
        if stage_b_summary["score_proxy_g5_shape_pass"]
        else "SCORE_PROXY_NOT_REPAIRED"
    )

    details = {
        "study_id": STUDY_ID,
        "stageA": {f"{scale:.2f}": records for scale, records in stage_a.items()},
        "stageA_scale_summaries": {f"{scale:.2f}": summary for scale, summary in stage_a_summaries.items()},
        "stageA_selected_scale": selected_scale,
        "target_module_identity": {
            "matched_modules_by_layer": [list(item) for item in module_identity[0]],
            "matched_module_names": list(module_identity[1]),
        },
        "stageB": stage_b,
        "stageB_exact_repeat": repeat,
    }
    details_bytes = canonical_bytes(details)
    details_sha = _sha256(details_bytes)
    (args.output_root / "details.json").write_bytes(details_bytes)

    result_digest = _sha256(canonical_bytes({
        "study_id": STUDY_ID,
        "selected_scale": selected_scale,
        "proxy_label": proxy_label,
        "stageB_summary": stage_b_summary,
        "details_sha256": details_sha,
    }))
    summary = {
        "study_id": STUDY_ID,
        "runner_version": RUNNER_VERSION,
        "status": "P2_D3_MEASUREMENT_COMPLETE" if integrity else "P2_D3_INTEGRITY_FAIL",
        "repair_proxy": proxy_label if integrity else "NOT_EVALUABLE",
        "git_commit": _git_head(),
        "prereg_commit": PREREG_COMMIT,
        "source_d1_result_digest": "865616cdb65e5f4c969a9302c02bb285167db06a905e1497b05e4e0912935c20",
        "source_d2_result_digest": SOURCE_D2_RESULT_DIGEST,
        "source_d2_selected_layers": list(TARGET_LAYERS),
        "p2_result_unchanged": "C10_NOT_BEHAVIORALLY_ADMITTED",
        "selected_scale": selected_scale,
        "stageA_scale_summaries": {f"{scale:.2f}": summary for scale, summary in stage_a_summaries.items()},
        "stageB": stage_b_summary,
        "integrity": {
            "pass": integrity,
            "union_exact_repeat_serialized_equal": repeat_equal,
            "lora_scaling_metadata_restored": scaling_restored,
            "source_d1_unchanged": d1_before == d1_after,
            "source_d2_unchanged": d2_before == d2_after,
            "retries": 0,
            "repairs": 0,
            "fallbacks": 0,
            "action_intent_generation": False,
            "simulation_state_commits": 0,
            "weight_updates": 0,
            "runtime_freeze": {"sha256": freeze_sha, "package_count": package_count},
        },
        "environment": environment,
        "preflight": preflight,
        "details_sha256": details_sha,
        "result_digest": result_digest,
    }
    (args.output_root / "summary.json").write_bytes(canonical_bytes(summary))
    print(json.dumps({
        "status": summary["status"],
        "integrity": integrity,
        "repair_proxy": summary["repair_proxy"],
        "selected_scale": selected_scale,
        "result_digest": result_digest,
        "summary": str(args.output_root / "summary.json"),
    }, sort_keys=True))
    return 0 if integrity else 1


if __name__ == "__main__":
    raise SystemExit(main())
