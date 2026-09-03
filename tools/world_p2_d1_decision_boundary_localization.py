#!/usr/bin/env python3
"""Run preregistered WORLD P2-D1 decision-boundary localization.

D1 is a researcher-only scoring diagnostic. It cannot generate or commit a
WORLD ActionIntent and cannot reopen the frozen P2 admission result.
"""

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

from alifelm.model.p2_d1_boundary import (  # noqa: E402
    D1_ACTION_ORDER,
    score_i3_decision_boundary,
)
from alifelm.model.p2_d1_metrics import (  # noqa: E402
    D1_CONTEXT_CLASSES,
    exact_repeat_deltas,
    localization_tag,
    matched_nonquiet_vs_quiet,
    paired_condition_shift,
)
from alifelm.model.peft_runtime import PeftTransformersLoader  # noqa: E402
from alifelm.model.treatments import I3_CONDITIONAL_TYPED_CODEC  # noqa: E402
from alifelm.model.world_v0_smoke import (  # noqa: E402
    DeploymentPaths,
    SmokePreflightError,
    canonical_bytes,
    ensure_execute_environment,
)
from alifelm.persistence import FileSystemArtifactStore  # noqa: E402
from tools.world_p2_phase_decoupled_behavioral_admission import (  # noqa: E402
    ADAPTER_CONFIG_SHA256,
    ADAPTER_SHA256,
    BASE_REVISION,
    BASE_SHA256,
    CASE_END,
    CASE_START,
    PIP_FREEZE_SHA256,
    PROFILE_ID,
    RUNTIME_PACKAGE_COUNT,
    TOKENIZER_SHA256,
    _compile_cohort,
    _policy,
    _profile,
    _runtime_freeze_sha256,
    _static_preflight,
)


STUDY_ID = "WORLD_P2_D1_DECISION_BOUNDARY_LOCALIZATION_V1"
RUNNER_VERSION = "1.0.0"
PREREG_COMMIT = "44d8df09b452143ac8007a82d8d9ffd6f2593322"
CONFIG_SHA256 = "8657707069a464ab598cb5fbb11c8675768f3e762cd8e2ba9df3a46dcb98e795"
SOURCE_P2_STUDY_ID = "WORLD_P2_PHASE_DECOUPLED_BEHAVIORAL_ADMISSION_V1"
SOURCE_P2_RESULT_DIGEST = "4226c5909fd13d8d769436d344a221d6f0c1746b08466ff6f5eb03303c0be563"
SOURCE_P2_ARCHIVE_SHA256 = "61a19717cf089fb59b43e2b52efc31e28036449418e3aeba69c8dd0bbad17790"
SOURCE_P2_GIT_COMMIT = "7bbe51abf539e5451db83c33b2a24b6a8b55b1de"
SOURCE_P2_PROMOTION = "C10_NOT_BEHAVIORALLY_ADMITTED"
SOURCE_P2_ROOT_NAME = "WORLD_P2_PHASE_DECOUPLED_BEHAVIORAL_ADMISSION_V1_R3"
SOURCE_P2_STDOUT_NAME = f"{SOURCE_P2_ROOT_NAME}.stdout.log"
CONDITIONS = (("C00", False, False), ("C10", True, False))


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
        raise SmokePreflightError("cannot resolve P2-D1 repository commit") from error


def _load_config(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    digest = _sha256(raw)
    if digest != CONFIG_SHA256:
        raise SmokePreflightError("P2-D1 frozen config SHA-256 drift")
    config = json.loads(raw.decode("utf-8"))
    if config.get("study_id") != STUDY_ID or config.get("status") != "PREREGISTERED_DIAGNOSTIC":
        raise SmokePreflightError("P2-D1 config identity drift")
    if config.get("source_p2_result_digest") != SOURCE_P2_RESULT_DIGEST:
        raise SmokePreflightError("P2-D1 source result identity drift")
    if tuple(config.get("action_branch_order", ())) != D1_ACTION_ORDER:
        raise SmokePreflightError("P2-D1 frozen action order drift")
    return config, digest


def _archive_member_bytes(archive: Path, suffix: str) -> bytes:
    with tarfile.open(archive, "r:gz") as handle:
        matches = [member for member in handle.getmembers() if member.isfile() and member.name.lstrip("./").endswith(suffix)]
        if len(matches) != 1:
            raise SmokePreflightError(f"P2-D1 could not uniquely resolve source archive member: {suffix}")
        stream = handle.extractfile(matches[0])
        if stream is None:
            raise SmokePreflightError("P2-D1 source archive member is unreadable")
        return stream.read()


def _verify_source_p2(root: Path, stdout: Path, archive: Path) -> tuple[dict[str, str], dict[str, Any]]:
    summary = root / "summary.json"
    details = root / "details.json"
    if any(not path.is_file() for path in (summary, details, stdout, archive)):
        raise SmokePreflightError("P2-D1 source P2 R3 evidence is incomplete")
    if _file_sha256(archive) != SOURCE_P2_ARCHIVE_SHA256:
        raise SmokePreflightError("P2-D1 source P2 canonical archive SHA-256 drift")

    summary_bytes = summary.read_bytes()
    details_bytes = details.read_bytes()
    stdout_bytes = stdout.read_bytes()
    payload = json.loads(summary_bytes.decode("utf-8"))
    if (
        payload.get("study_id") != SOURCE_P2_STUDY_ID
        or payload.get("status") != "P2_MEASUREMENT_COMPLETE"
        or payload.get("localization") != "INTERPRETABLE"
        or payload.get("result_digest") != SOURCE_P2_RESULT_DIGEST
        or payload.get("candidate_promotion") != SOURCE_P2_PROMOTION
        or payload.get("git_commit") != SOURCE_P2_GIT_COMMIT
    ):
        raise SmokePreflightError("P2-D1 source P2 semantic identity drift")
    if payload.get("details_sha256") != _sha256(details_bytes):
        raise SmokePreflightError("P2-D1 source P2 details digest drift")

    archive_checks = {
        f"alifelm/evidence/{SOURCE_P2_ROOT_NAME}/summary.json": summary_bytes,
        f"alifelm/evidence/{SOURCE_P2_ROOT_NAME}/details.json": details_bytes,
        SOURCE_P2_STDOUT_NAME: stdout_bytes,
    }
    for suffix, local_bytes in archive_checks.items():
        if _archive_member_bytes(archive, suffix) != local_bytes:
            raise SmokePreflightError("P2-D1 unpacked P2 source differs from canonical archive")

    observed = {
        "p2_summary_sha256": _sha256(summary_bytes),
        "p2_details_sha256": _sha256(details_bytes),
        "p2_stdout_sha256": _sha256(stdout_bytes),
        "p2_archive_sha256": SOURCE_P2_ARCHIVE_SHA256,
    }
    return observed, json.loads(details_bytes.decode("utf-8"))


def _source_record_map(details: dict[str, Any], condition: str) -> dict[tuple[str, int], dict[str, Any]]:
    records = details.get("primary_conditions", {}).get(condition)
    if not isinstance(records, list) or len(records) != 160:
        raise SmokePreflightError(f"P2-D1 source {condition} cohort is incomplete")
    result = {(row["context_class"], int(row["case_index"])): row for row in records}
    if len(result) != 160:
        raise SmokePreflightError("P2-D1 source P2 record key duplication")
    return result


def _compile_and_verify_cohort(*, store, profile, policy, p2_details: dict[str, Any]):
    cohort = _compile_cohort(store=store, profile=profile, policy=policy)
    source = _source_record_map(p2_details, "C10")
    for context_name, case_index, compiled in cohort:
        key = (context_name, case_index)
        row = source.get(key)
        if row is None:
            raise SmokePreflightError("P2-D1 compiled cohort key absent from source P2")
        rendered_request = I3_CONDITIONAL_TYPED_CODEC.render(compiled.rendered_input)
        if _sha256(compiled.rendered_input) != row["rendered_context_sha256"]:
            raise SmokePreflightError("P2-D1 WORLD context bytes differ from source P2")
        if _sha256(rendered_request) != row["rendered_request_sha256"]:
            raise SmokePreflightError("P2-D1 I3 request bytes differ from source P2")
    return cohort


def _record_from_probe(condition: str, context_name: str, case_index: int, compiled, probe) -> dict[str, Any]:
    scores = {score.internal_action: score for score in probe.branch_scores}
    total_scores = {action: scores[action].total_log_probability for action in D1_ACTION_ORDER}
    mean_scores = {action: scores[action].mean_log_probability for action in D1_ACTION_ORDER}
    total_ranks = {action: scores[action].total_rank for action in D1_ACTION_ORDER}
    mean_ranks = {action: scores[action].mean_rank for action in D1_ACTION_ORDER}
    return {
        "condition": condition,
        "context_class": context_name,
        "case_index": case_index,
        "rendered_context_sha256": _sha256(compiled.rendered_input),
        "rendered_request_sha256": _sha256(I3_CONDITIONAL_TYPED_CODEC.render(compiled.rendered_input)),
        "prefill_adapter": probe.prefill_adapter,
        "selector_adapter": probe.selector_adapter,
        "context_token_ids": list(probe.context_token_ids),
        "prefix_token_ids": list(probe.prefix_token_ids),
        "combined_token_ids": list(probe.combined_token_ids),
        "common_prefix_token_ids": list(probe.common_prefix_token_ids),
        "divergence_step": probe.divergence_step,
        "phase_boundary_token_aligned": probe.phase_boundary_token_aligned,
        "world_prefill_forward_count": probe.world_prefill_forward_count,
        "selector_prefix_forward_count": probe.selector_prefix_forward_count,
        "common_prefix_forward_count": probe.common_prefix_forward_count,
        "branch_continuation_forward_count": probe.branch_continuation_forward_count,
        "world_context_recomputed_after_switch": probe.world_context_recomputed_after_switch,
        "branch_scores": [
            {
                "internal_action": score.internal_action,
                "model_label": score.model_label,
                "token_ids": list(score.token_ids),
                "total_log_probability": score.total_log_probability,
                "mean_log_probability": score.mean_log_probability,
                "total_rank": score.total_rank,
                "mean_rank": score.mean_rank,
            }
            for score in probe.branch_scores
        ],
        "total_scores": total_scores,
        "mean_scores": mean_scores,
        "total_ranks": total_ranks,
        "mean_ranks": mean_ranks,
        "total_rank1": probe.total_rank1(),
        "mean_rank1": probe.mean_rank1(),
        "nda_total_margin": probe.nda_total_margin(),
    }


def _run_condition(*, runtime, cohort, condition: str, prefill_adapter: bool, selector_adapter: bool, source_map):
    records: list[dict[str, Any]] = []
    for ordinal, (context_name, case_index, compiled) in enumerate(cohort, 1):
        rendered = I3_CONDITIONAL_TYPED_CODEC.render(compiled.rendered_input)
        probe = score_i3_decision_boundary(
            runtime,
            rendered_input=rendered,
            prefill_adapter=prefill_adapter,
            selector_adapter=selector_adapter,
        )
        row = _record_from_probe(condition, context_name, case_index, compiled, probe)
        source = source_map[(context_name, case_index)]
        if (
            row["rendered_context_sha256"] != source["rendered_context_sha256"]
            or row["rendered_request_sha256"] != source["rendered_request_sha256"]
            or row["context_token_ids"] != source["context_token_ids"]
            or row["prefix_token_ids"] != source["prefix_token_ids"]
            or row["combined_token_ids"] != source["combined_token_ids"]
        ):
            raise SmokePreflightError("P2-D1 probe input/token identity differs from source P2")
        records.append(row)
        if ordinal % 20 == 0 or ordinal == len(cohort):
            print(f"P2_D1_{condition} {ordinal}/{len(cohort)}", flush=True)
    return records


def _integrity_records(records: list[dict[str, Any]], condition: str, prefill: bool, selector: bool) -> bool:
    if len(records) != 160:
        return False
    keys = {(row["context_class"], row["case_index"]) for row in records}
    expected = {(context, index) for context in D1_CONTEXT_CLASSES for index in range(CASE_START, CASE_END + 1)}
    if keys != expected:
        return False
    return all(
        row["condition"] == condition
        and (row["prefill_adapter"], row["selector_adapter"]) == (prefill, selector)
        and row["phase_boundary_token_aligned"]
        and row["world_prefill_forward_count"] == 1
        and row["selector_prefix_forward_count"] == 1
        and not row["world_context_recomputed_after_switch"]
        and tuple(score["internal_action"] for score in row["branch_scores"]) == D1_ACTION_ORDER
        for row in records
    )


def _summary_without_cases(matched: dict[str, Any]) -> dict[str, Any]:
    return {context: {key: value for key, value in payload.items() if key != "cases"} for context, payload in matched.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--base-model-dir", type=Path, required=True)
    parser.add_argument("--adapter-path", type=Path, required=True)
    parser.add_argument("--p2-root", type=Path, required=True)
    parser.add_argument("--p2-stdout", type=Path, required=True)
    parser.add_argument("--p2-archive", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--expected-git-commit", required=True)
    args = parser.parse_args()

    config, config_sha = _load_config(args.config)
    if _git_head() != args.expected_git_commit:
        raise SmokePreflightError("P2-D1 expected git commit mismatch")
    source_paths = {"root": args.p2_root, "stdout": args.p2_stdout, "archive": args.p2_archive}
    source_before, p2_details = _verify_source_p2(**source_paths)
    freeze_sha, package_count = _runtime_freeze_sha256()
    if freeze_sha != PIP_FREEZE_SHA256 or package_count != RUNTIME_PACKAGE_COUNT:
        raise SmokePreflightError("P2-D1 canonical runtime freeze drift")

    paths = DeploymentPaths(args.base_model_dir, args.adapter_path, args.output_root)
    preflight = _static_preflight(paths, args.expected_git_commit)
    profile = _profile(args.base_model_dir)
    policy = _policy()

    if args.validate_only:
        with tempfile.TemporaryDirectory(prefix="world-p2-d1-validate-") as tmp:
            store = FileSystemArtifactStore(Path(tmp) / "cas")
            cohort = _compile_and_verify_cohort(store=store, profile=profile, policy=policy, p2_details=p2_details)
        print(json.dumps({
            "status": "P2_D1_STATIC_PREFLIGHT_OK",
            "study_id": STUDY_ID,
            "git_commit": _git_head(),
            "prereg_commit": PREREG_COMMIT,
            "config_sha256": config_sha,
            "source_p2": source_before,
            "runtime_pip_freeze_sha256": freeze_sha,
            "runtime_package_count": package_count,
            "compiled_contexts": len(cohort),
            "planned_scored_probes": 640,
            "conditions": [name for name, _, _ in CONDITIONS],
            "exact_repeat_full_conditions": 2,
            "model_loaded": False,
            "action_intent_generation": False,
            "simulation_state_commit": False,
            "weight_update": False,
        }, ensure_ascii=False, sort_keys=True))
        return 0

    if args.output_root.exists():
        raise SmokePreflightError("P2-D1 output root already exists; failed attempts are immutable")
    args.output_root.mkdir(parents=True, exist_ok=False)
    environment = ensure_execute_environment()
    (args.output_root / "run_plan.json").write_bytes(canonical_bytes({
        "study_id": STUDY_ID,
        "runner_version": RUNNER_VERSION,
        "git_commit": _git_head(),
        "prereg_commit": PREREG_COMMIT,
        "config_sha256": config_sha,
        "source_p2": source_before,
        "conditions": [name for name, _, _ in CONDITIONS],
        "cohort": {"case_start": CASE_START, "case_end": CASE_END, "contexts": 160},
        "probe": config["probe"],
        "action_intent_generation": False,
        "simulation_state_commit": False,
        "weight_update": False,
    }))

    store = FileSystemArtifactStore(args.output_root / "cas")
    cohort = _compile_and_verify_cohort(store=store, profile=profile, policy=policy, p2_details=p2_details)
    loader = PeftTransformersLoader(base_model_dir=args.base_model_dir, adapter_path=args.adapter_path)
    runtime = loader(profile)
    source_maps = {condition: _source_record_map(p2_details, condition) for condition, _, _ in CONDITIONS}

    primary: dict[str, list[dict[str, Any]]] = {}
    repeat: dict[str, list[dict[str, Any]]] = {}
    for condition, prefill, selector in CONDITIONS:
        primary[condition] = _run_condition(
            runtime=runtime,
            cohort=cohort,
            condition=condition,
            prefill_adapter=prefill,
            selector_adapter=selector,
            source_map=source_maps[condition],
        )
    for condition, prefill, selector in CONDITIONS:
        repeat[condition] = _run_condition(
            runtime=runtime,
            cohort=cohort,
            condition=condition,
            prefill_adapter=prefill,
            selector_adapter=selector,
            source_map=source_maps[condition],
        )

    repeat_metrics = {condition: exact_repeat_deltas(primary[condition], repeat[condition]) for condition, _, _ in CONDITIONS}
    matched = matched_nonquiet_vs_quiet(primary["C10"])
    paired_shift = paired_condition_shift(primary["C10"], primary["C00"])
    source_after, _ = _verify_source_p2(**source_paths)
    structure_ok = all(
        _integrity_records(primary[name], name, prefill, selector)
        and _integrity_records(repeat[name], name, prefill, selector)
        for name, prefill, selector in CONDITIONS
    )
    exact_repeat_ok = all(repeat_metrics[name]["serialized_equal"] for name, _, _ in CONDITIONS)
    integrity = bool(
        structure_ok
        and exact_repeat_ok
        and source_before == source_after
        and freeze_sha == PIP_FREEZE_SHA256
        and package_count == RUNTIME_PACKAGE_COUNT
    )
    tag = localization_tag(primary["C10"], matched, repeat_metrics["C10"]) if integrity else "NOT_EVALUABLE"

    details = {
        "study_id": STUDY_ID,
        "primary": primary,
        "repeat": repeat,
        "matched_nonquiet_vs_quiet_C10": matched,
        "paired_C10_vs_C00": paired_shift,
        "repeat_metrics": repeat_metrics,
    }
    details_bytes = canonical_bytes(details)
    details_sha = _sha256(details_bytes)
    (args.output_root / "details.json").write_bytes(details_bytes)

    summary_core = {
        "study_id": STUDY_ID,
        "runner_version": RUNNER_VERSION,
        "status": "P2_D1_MEASUREMENT_COMPLETE" if integrity else "P2_D1_INTEGRITY_FAIL",
        "localization": tag,
        "p2_result_unchanged": SOURCE_P2_PROMOTION,
        "founder_freeze": "NOT_ESTABLISHED",
        "git_commit": _git_head(),
        "prereg_commit": PREREG_COMMIT,
        "config_sha256": config_sha,
        "environment": environment,
        "preflight": preflight,
        "source_before": source_before,
        "source_after": source_after,
        "integrity": {
            "pass": integrity,
            "condition_structure": structure_ok,
            "exact_repeat_serialized_equal": exact_repeat_ok,
            "source_p2_unchanged": source_before == source_after,
            "runtime_freeze": {"sha256": freeze_sha, "package_count": package_count},
            "action_intent_generation": False,
            "simulation_state_commits": 0,
            "weight_updates": 0,
            "retries": 0,
            "repairs": 0,
            "fallbacks": 0,
        },
        "C10_total_rank1_distribution": {
            action: sum(row["total_rank1"] == action for row in primary["C10"])
            for action in D1_ACTION_ORDER
        },
        "C00_total_rank1_distribution": {
            action: sum(row["total_rank1"] == action for row in primary["C00"])
            for action in D1_ACTION_ORDER
        },
        "C10_matched_nonquiet_vs_quiet": _summary_without_cases(matched),
        "paired_C10_vs_C00": paired_shift,
        "exact_repeat": repeat_metrics,
        "details_sha256": details_sha,
    }
    digest = _sha256(canonical_bytes(summary_core))
    summary = dict(summary_core)
    summary["result_digest"] = digest
    (args.output_root / "summary.json").write_bytes(canonical_bytes(summary))
    print(json.dumps({
        "status": summary["status"],
        "localization": tag,
        "integrity": integrity,
        "p2_result_unchanged": SOURCE_P2_PROMOTION,
        "result_digest": digest,
        "summary": str(args.output_root / "summary.json"),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if integrity else 2


if __name__ == "__main__":
    raise SystemExit(main())
