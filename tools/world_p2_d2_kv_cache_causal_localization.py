#!/usr/bin/env python3
"""Run preregistered WORLD P2-D2 KV-cache causal localization."""

from __future__ import annotations

import argparse
from collections import defaultdict
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

from alifelm.model.p2_d1_boundary import D1_ACTION_ORDER  # noqa: E402
from alifelm.model.p2_d2_cache_patch import transplant_cache_layers  # noqa: E402
from alifelm.model.p2_d2_metrics import (  # noqa: E402
    mediator_values,
    median_symmetric_score,
    select_top_blocks,
    select_top_layers,
    union_localization_label,
)
from alifelm.model.p2_d2_scoring import (  # noqa: E402
    D2_SCREEN_ACTIONS,
    build_prefill_caches,
    score_i3_from_prefill_cache,
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
    PIP_FREEZE_SHA256,
    RUNTIME_PACKAGE_COUNT,
    _compile_cohort,
    _policy,
    _profile,
    _runtime_freeze_sha256,
    _static_preflight,
)


STUDY_ID = "WORLD_P2_D2_KV_CACHE_CAUSAL_LOCALIZATION_V1"
RUNNER_VERSION = "1.0.0"
PREREG_COMMIT = "9bce60555f1dbb9c2bd9ec4d9fae279ab0f61761"
SOURCE_D1_STUDY_ID = "WORLD_P2_D1_DECISION_BOUNDARY_LOCALIZATION_V1"
SOURCE_D1_RESULT_DIGEST = "865616cdb65e5f4c969a9302c02bb285167db06a905e1497b05e4e0912935c20"
SOURCE_D1_DETAILS_SHA256 = "0e5e62709d58168c9922645c1d05d54a7f5c417b68b3f461b4558d3706ca3b17"
SOURCE_D1_ARCHIVE_SHA256 = "c42999e001c789a4a43fa14962119315066b2df6c66e3b472ce76a6f27cad2f1"
SOURCE_D1_ROOT_NAME = "WORLD_P2_D1_DECISION_BOUNDARY_LOCALIZATION_V1_R2"
SOURCE_D1_STDOUT_NAME = f"{SOURCE_D1_ROOT_NAME}.stdout.log"
SCREEN_CASES = range(4000, 4004)
FULL_CASES = range(4000, 4032)
BLOCKS = {
    "Q0": (0, 1, 2, 3),
    "Q1": (4, 5, 6, 7),
    "Q2": (8, 9, 10, 11),
    "Q3": (12, 13, 14, 15),
}
CONTEXTS = (
    "QUIET",
    "MESSAGE_RECEIVED",
    "PROPOSAL_RECEIVED",
    "OWN_PROPOSAL_PENDING",
    "RECENT_INTERACTION",
)


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


def _load_config(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    config = json.loads(raw.decode("utf-8"))
    if config.get("study_id") != STUDY_ID or config.get("status") != "PREREGISTERED_MECHANISTIC_DIAGNOSTIC":
        raise SmokePreflightError("P2-D2 config identity drift")
    if config.get("source_d1_result_digest") != SOURCE_D1_RESULT_DIGEST:
        raise SmokePreflightError("P2-D2 source D1 result identity drift")
    if config.get("model", {}).get("expected_transformer_layers") != 16:
        raise SmokePreflightError("P2-D2 frozen layer count drift")
    return config, _sha256(raw)


def _archive_member_bytes(archive: Path, suffix: str) -> bytes:
    with tarfile.open(archive, "r:gz") as handle:
        matches = [m for m in handle.getmembers() if m.isfile() and m.name.lstrip("./").endswith(suffix)]
        if len(matches) != 1:
            raise SmokePreflightError(f"P2-D2 could not uniquely resolve D1 archive member: {suffix}")
        stream = handle.extractfile(matches[0])
        if stream is None:
            raise SmokePreflightError("P2-D2 D1 archive member is unreadable")
        return stream.read()


def _verify_source_d1(root: Path, stdout: Path, archive: Path) -> tuple[dict[str, str], dict[str, Any]]:
    summary = root / "summary.json"
    details = root / "details.json"
    if any(not path.is_file() for path in (summary, details, stdout, archive)):
        raise SmokePreflightError("P2-D2 source D1 evidence is incomplete")
    if _file_sha256(archive) != SOURCE_D1_ARCHIVE_SHA256:
        raise SmokePreflightError("P2-D2 source D1 canonical archive SHA-256 drift")
    summary_bytes, details_bytes, stdout_bytes = summary.read_bytes(), details.read_bytes(), stdout.read_bytes()
    if _sha256(details_bytes) != SOURCE_D1_DETAILS_SHA256:
        raise SmokePreflightError("P2-D2 source D1 details SHA-256 drift")
    payload = json.loads(summary_bytes.decode("utf-8"))
    if (
        payload.get("study_id") != SOURCE_D1_STUDY_ID
        or payload.get("status") != "P2_D1_MEASUREMENT_COMPLETE"
        or payload.get("result_digest") != SOURCE_D1_RESULT_DIGEST
        or payload.get("integrity", {}).get("pass") is not True
    ):
        raise SmokePreflightError("P2-D2 source D1 semantic identity drift")
    checks = {
        f"alifelm/evidence/{SOURCE_D1_ROOT_NAME}/summary.json": summary_bytes,
        f"alifelm/evidence/{SOURCE_D1_ROOT_NAME}/details.json": details_bytes,
        SOURCE_D1_STDOUT_NAME: stdout_bytes,
    }
    for suffix, local in checks.items():
        if _archive_member_bytes(archive, suffix) != local:
            raise SmokePreflightError("P2-D2 unpacked D1 source differs from canonical archive")
    observed = {
        "d1_summary_sha256": _sha256(summary_bytes),
        "d1_details_sha256": _sha256(details_bytes),
        "d1_stdout_sha256": _sha256(stdout_bytes),
        "d1_archive_sha256": SOURCE_D1_ARCHIVE_SHA256,
    }
    return observed, json.loads(details_bytes.decode("utf-8"))


def _source_map(details: dict[str, Any], condition: str) -> dict[tuple[str, int], dict[str, Any]]:
    rows = details.get("primary", {}).get(condition)
    if not isinstance(rows, list) or len(rows) != 160:
        raise SmokePreflightError(f"P2-D2 source D1 {condition} cohort is incomplete")
    result = {(row["context_class"], int(row["case_index"])): row for row in rows}
    if len(result) != 160:
        raise SmokePreflightError("P2-D2 source D1 record keys are not unique")
    return result


def _compile_and_verify(store, profile, policy, details: dict[str, Any]):
    cohort = _compile_cohort(store=store, profile=profile, policy=policy)
    c00, c10 = _source_map(details, "C00"), _source_map(details, "C10")
    for context, case, compiled in cohort:
        key = (context, case)
        request = I3_CONDITIONAL_TYPED_CODEC.render(compiled.rendered_input)
        context_sha = _sha256(compiled.rendered_input)
        request_sha = _sha256(request)
        for source in (c00[key], c10[key]):
            if source["rendered_context_sha256"] != context_sha or source["rendered_request_sha256"] != request_sha:
                raise SmokePreflightError("P2-D2 compiled bytes differ from source D1")
    return cohort


def _score_record(score, *, condition: str, layers: tuple[int, ...]) -> dict[str, Any]:
    branch = [
        {
            "internal_action": item.internal_action,
            "model_label": item.model_label,
            "token_ids": list(item.token_ids),
            "token_count": len(item.token_ids),
            "total_log_probability": item.total_log_probability,
            "mean_log_probability": item.mean_log_probability,
            "total_rank": item.total_rank,
            "mean_rank": item.mean_rank,
        }
        for item in score.branch_scores
    ]
    totals = score.total_scores()
    means = score.mean_scores()
    return {
        "condition": condition,
        "patch_layers": list(layers),
        "actions_scored": list(score.actions_scored),
        "common_prefix_token_ids": list(score.common_prefix_token_ids),
        "divergence_step": score.divergence_step,
        "selector_prefix_forward_count": score.selector_prefix_forward_count,
        "common_prefix_forward_count": score.common_prefix_forward_count,
        "branch_continuation_forward_count": score.branch_continuation_forward_count,
        "branch_scores": branch,
        "total_scores": totals,
        "mean_scores": means,
        "wait_send_total_gap": score.wait_send_total_gap(),
        "wait_send_mean_gap": score.wait_send_mean_gap(),
        "total_rank1": min(branch, key=lambda row: row["total_rank"])["internal_action"],
        "mean_rank1": min(branch, key=lambda row: row["mean_rank"])["internal_action"],
    }


def _assert_matches_d1(score, source: dict[str, Any], actions: tuple[str, ...]) -> None:
    if (
        list(score.context_token_ids) != source["context_token_ids"]
        or list(score.prefix_token_ids) != source["prefix_token_ids"]
        or list(score.combined_token_ids) != source["combined_token_ids"]
        or list(score.common_prefix_token_ids) != source["common_prefix_token_ids"]
        or score.divergence_step != source["divergence_step"]
    ):
        raise SmokePreflightError("P2-D2 baseline topology differs from source D1")
    observed = {row.internal_action: row for row in score.branch_scores}
    expected = {row["internal_action"]: row for row in source["branch_scores"]}
    for action in actions:
        left, right = observed[action], expected[action]
        if (
            list(left.token_ids) != right["token_ids"]
            or left.total_log_probability != right["total_log_probability"]
            or left.mean_log_probability != right["mean_log_probability"]
        ):
            raise SmokePreflightError(f"P2-D2 baseline {action} score differs from source D1")


def _screen_rows(cohort):
    return [row for row in cohort if row[1] in SCREEN_CASES]


def _source_gap(source: dict[str, Any]) -> float:
    return float(source["total_scores"]["WAIT"] - source["total_scores"]["SEND"])


def _patch_score(runtime, rendered: bytes, target, donor, layers: tuple[int, ...], actions: tuple[str, ...]):
    cache = transplant_cache_layers(target, donor, layers)
    return score_i3_from_prefill_cache(runtime, rendered_input=rendered, phase_a_cache=cache, actions_to_score=actions)


def _run_stage_a(runtime, cohort, d1_details):
    c00, c10 = _source_map(d1_details, "C00"), _source_map(d1_details, "C10")
    records = []
    all_layers = tuple(range(16))
    for ordinal, (context, case, compiled) in enumerate(_screen_rows(cohort), 1):
        key = (context, case)
        rendered = I3_CONDITIONAL_TYPED_CODEC.render(compiled.rendered_input)
        pair = build_prefill_caches(runtime, rendered_input=rendered)
        base = score_i3_from_prefill_cache(runtime, rendered_input=rendered, phase_a_cache=pair.base_cache, actions_to_score=D2_SCREEN_ACTIONS)
        fa = score_i3_from_prefill_cache(runtime, rendered_input=rendered, phase_a_cache=pair.fa_cache, actions_to_score=D2_SCREEN_ACTIONS)
        _assert_matches_d1(base, c00[key], D2_SCREEN_ACTIONS)
        _assert_matches_d1(fa, c10[key], D2_SCREEN_ACTIONS)
        g_base, g_fa = base.wait_send_total_gap(), fa.wait_send_total_gap()
        if g_fa - g_base <= 0:
            raise SmokePreflightError("P2-D2 source WAIT-SEND gap direction is not positive")

        all_rescue = _patch_score(runtime, rendered, pair.fa_cache, pair.base_cache, all_layers, D2_SCREEN_ACTIONS)
        all_induction = _patch_score(runtime, rendered, pair.base_cache, pair.fa_cache, all_layers, D2_SCREEN_ACTIONS)
        if _score_record(all_rescue, condition="ALL_RESCUE", layers=all_layers)["branch_scores"] != _score_record(base, condition="B", layers=())["branch_scores"]:
            raise SmokePreflightError("P2-D2 all-layer rescue control failed")
        if _score_record(all_induction, condition="ALL_INDUCTION", layers=all_layers)["branch_scores"] != _score_record(fa, condition="F", layers=())["branch_scores"]:
            raise SmokePreflightError("P2-D2 all-layer induction control failed")

        patches = {}
        for name, layers in BLOCKS.items():
            rescue = _patch_score(runtime, rendered, pair.fa_cache, pair.base_cache, layers, D2_SCREEN_ACTIONS)
            induction = _patch_score(runtime, rendered, pair.base_cache, pair.fa_cache, layers, D2_SCREEN_ACTIONS)
            metrics = mediator_values(g_base, g_fa, rescue.wait_send_total_gap(), induction.wait_send_total_gap())
            patches[name] = {
                "layers": list(layers),
                **metrics,
                "rescue": _score_record(rescue, condition=f"RESCUE_{name}", layers=layers),
                "induction": _score_record(induction, condition=f"INDUCTION_{name}", layers=layers),
            }
        records.append({"context_class": context, "case_index": case, "g_base": g_base, "g_fa": g_fa, "patches": patches})
        if ordinal % 5 == 0:
            print(f"P2_D2_STAGEA {ordinal}/20", flush=True)

    block_scores = {
        name: median_symmetric_score([row["patches"][name] for row in records]) for name in BLOCKS
    }
    selected = select_top_blocks(block_scores)
    return records, block_scores, selected


def _run_stage_b(runtime, cohort, d1_details, selected_blocks):
    c00, c10 = _source_map(d1_details, "C00"), _source_map(d1_details, "C10")
    candidates = tuple(sorted(layer for block in selected_blocks for layer in BLOCKS[block]))
    records = []
    for ordinal, (context, case, compiled) in enumerate(_screen_rows(cohort), 1):
        key = (context, case)
        rendered = I3_CONDITIONAL_TYPED_CODEC.render(compiled.rendered_input)
        pair = build_prefill_caches(runtime, rendered_input=rendered)
        g_base, g_fa = _source_gap(c00[key]), _source_gap(c10[key])
        layers_payload = {}
        for layer in candidates:
            one = (layer,)
            rescue = _patch_score(runtime, rendered, pair.fa_cache, pair.base_cache, one, D2_SCREEN_ACTIONS)
            induction = _patch_score(runtime, rendered, pair.base_cache, pair.fa_cache, one, D2_SCREEN_ACTIONS)
            layers_payload[str(layer)] = {
                **mediator_values(g_base, g_fa, rescue.wait_send_total_gap(), induction.wait_send_total_gap()),
                "rescue": _score_record(rescue, condition=f"RESCUE_L{layer}", layers=one),
                "induction": _score_record(induction, condition=f"INDUCTION_L{layer}", layers=one),
            }
        records.append({"context_class": context, "case_index": case, "layers": layers_payload})
        if ordinal % 5 == 0:
            print(f"P2_D2_STAGEB {ordinal}/20", flush=True)
    layer_scores = {
        layer: median_symmetric_score([row["layers"][str(layer)] for row in records]) for layer in candidates
    }
    selected = select_top_layers(layer_scores)
    return records, layer_scores, selected


def _run_stage_c(runtime, cohort, d1_details, selected_layers, *, repeat_union: bool = False):
    c00, c10 = _source_map(d1_details, "C00"), _source_map(d1_details, "C10")
    l1, l2 = selected_layers
    specs = (
        (f"RESCUE_L{l1}", (l1,), "rescue"),
        (f"INDUCTION_L{l1}", (l1,), "induction"),
        (f"RESCUE_L{l2}", (l2,), "rescue"),
        (f"INDUCTION_L{l2}", (l2,), "induction"),
        ("RESCUE_L1_L2_UNION", tuple(sorted({l1, l2})), "rescue"),
        ("INDUCTION_L1_L2_UNION", tuple(sorted({l1, l2})), "induction"),
    )
    records = []
    for ordinal, (context, case, compiled) in enumerate(cohort, 1):
        key = (context, case)
        rendered = I3_CONDITIONAL_TYPED_CODEC.render(compiled.rendered_input)
        pair = build_prefill_caches(runtime, rendered_input=rendered)
        payload = {"context_class": context, "case_index": case, "conditions": {}}
        if not repeat_union:
            base = score_i3_from_prefill_cache(runtime, rendered_input=rendered, phase_a_cache=pair.base_cache)
            fa = score_i3_from_prefill_cache(runtime, rendered_input=rendered, phase_a_cache=pair.fa_cache)
            _assert_matches_d1(base, c00[key], D1_ACTION_ORDER)
            _assert_matches_d1(fa, c10[key], D1_ACTION_ORDER)
            payload["conditions"]["B_BASELINE"] = _score_record(base, condition="B_BASELINE", layers=())
            payload["conditions"]["F_BASELINE"] = _score_record(fa, condition="F_BASELINE", layers=())
            active_specs = specs
        else:
            active_specs = specs[-2:]

        for condition, layers, direction in active_specs:
            if direction == "rescue":
                score = _patch_score(runtime, rendered, pair.fa_cache, pair.base_cache, layers, D1_ACTION_ORDER)
            else:
                score = _patch_score(runtime, rendered, pair.base_cache, pair.fa_cache, layers, D1_ACTION_ORDER)
            payload["conditions"][condition] = _score_record(score, condition=condition, layers=layers)
        records.append(payload)
        if ordinal % 20 == 0:
            label = "REPEAT" if repeat_union else "STAGEC"
            print(f"P2_D2_{label} {ordinal}/160", flush=True)
    return records


def _stage_c_summary(records, selected_layers):
    l1, l2 = selected_layers
    names = (
        "B_BASELINE", "F_BASELINE", f"RESCUE_L{l1}", f"INDUCTION_L{l1}",
        f"RESCUE_L{l2}", f"INDUCTION_L{l2}", "RESCUE_L1_L2_UNION", "INDUCTION_L1_L2_UNION",
    )
    rank1 = {name: defaultdict(int) for name in names}
    gaps = {name: [] for name in names}
    by_context = {name: defaultdict(list) for name in names}
    for row in records:
        context = row["context_class"]
        for name in names:
            rec = row["conditions"][name]
            rank1[name][rec["total_rank1"]] += 1
            gaps[name].append(rec["wait_send_total_gap"])
            by_context[name][context].append(rec["wait_send_total_gap"])
    return {
        "rank1_distribution": {name: dict(rank1[name]) for name in names},
        "gap_min_median_max": {
            name: {"min": min(values), "median": sorted(values)[len(values)//2-1:len(values)//2+1], "max": max(values)}
            for name, values in gaps.items()
        },
        "union_rescue_flip_count": sum(value < 0 for value in gaps["RESCUE_L1_L2_UNION"]),
        "union_induction_flip_count": sum(value > 0 for value in gaps["INDUCTION_L1_L2_UNION"]),
        "localization": union_localization_label(gaps["RESCUE_L1_L2_UNION"], gaps["INDUCTION_L1_L2_UNION"]),
    }


def _repeat_union_view(records):
    return [
        {
            "context_class": row["context_class"],
            "case_index": row["case_index"],
            "conditions": row["conditions"],
        }
        for row in records
    ]


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
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--expected-git-commit", required=True)
    args = parser.parse_args()

    config, config_sha = _load_config(args.config)
    if _git_head() != args.expected_git_commit:
        raise SmokePreflightError("P2-D2 expected git commit mismatch")
    source_paths = {"root": args.d1_root, "stdout": args.d1_stdout, "archive": args.d1_archive}
    source_before, d1_details = _verify_source_d1(**source_paths)
    freeze_sha, package_count = _runtime_freeze_sha256()
    if freeze_sha != PIP_FREEZE_SHA256 or package_count != RUNTIME_PACKAGE_COUNT:
        raise SmokePreflightError("P2-D2 canonical runtime freeze drift")
    model_config = json.loads((args.base_model_dir / "config.json").read_text(encoding="utf-8"))
    if int(model_config.get("num_hidden_layers", -1)) != 16:
        raise SmokePreflightError("P2-D2 model config does not expose 16 hidden layers")

    paths = DeploymentPaths(args.base_model_dir, args.adapter_path, args.output_root)
    preflight = _static_preflight(paths, args.expected_git_commit)
    profile, policy = _profile(args.base_model_dir), _policy()

    if args.validate_only:
        with tempfile.TemporaryDirectory(prefix="world-p2-d2-validate-") as tmp:
            cohort = _compile_and_verify(FileSystemArtifactStore(Path(tmp) / "cas"), profile, policy, d1_details)
        print(json.dumps({
            "status": "P2_D2_STATIC_PREFLIGHT_OK",
            "study_id": STUDY_ID,
            "git_commit": _git_head(),
            "prereg_commit": PREREG_COMMIT,
            "config_sha256": config_sha,
            "source_d1": source_before,
            "runtime_pip_freeze_sha256": freeze_sha,
            "runtime_package_count": package_count,
            "compiled_contexts": len(cohort),
            "screening_contexts": 20,
            "model_hidden_layers": 16,
            "model_loaded": False,
            "simulation_state_commit": False,
            "weight_update": False,
        }, sort_keys=True))
        return 0

    if args.output_root.exists():
        raise SmokePreflightError("P2-D2 output root already exists; failed attempts are immutable")
    args.output_root.mkdir(parents=True, exist_ok=False)
    environment = ensure_execute_environment()
    (args.output_root / "run_plan.json").write_bytes(canonical_bytes({
        "study_id": STUDY_ID,
        "runner_version": RUNNER_VERSION,
        "git_commit": _git_head(),
        "prereg_commit": PREREG_COMMIT,
        "config_sha256": config_sha,
        "source_d1": source_before,
        "screening_cases": [4000, 4001, 4002, 4003],
        "blocks": {name: list(layers) for name, layers in BLOCKS.items()},
        "simulation_state_commit": False,
        "weight_update": False,
    }))
    store = FileSystemArtifactStore(args.output_root / "cas")
    cohort = _compile_and_verify(store, profile, policy, d1_details)
    runtime = PeftTransformersLoader(base_model_dir=args.base_model_dir, adapter_path=args.adapter_path)(profile)

    stage_a, block_scores, selected_blocks = _run_stage_a(runtime, cohort, d1_details)
    stage_b, layer_scores, selected_layers = _run_stage_b(runtime, cohort, d1_details, selected_blocks)
    stage_c = _run_stage_c(runtime, cohort, d1_details, selected_layers)
    repeat_union = _run_stage_c(runtime, cohort, d1_details, selected_layers, repeat_union=True)

    primary_union = [
        {"context_class": row["context_class"], "case_index": row["case_index"], "conditions": {
            "RESCUE_L1_L2_UNION": row["conditions"]["RESCUE_L1_L2_UNION"],
            "INDUCTION_L1_L2_UNION": row["conditions"]["INDUCTION_L1_L2_UNION"],
        }} for row in stage_c
    ]
    repeat_equal = primary_union == _repeat_union_view(repeat_union)
    source_after, _ = _verify_source_d1(**source_paths)
    integrity = bool(repeat_equal and source_before == source_after)
    summary_metrics = _stage_c_summary(stage_c, selected_layers)

    details = {
        "study_id": STUDY_ID,
        "stageA": stage_a,
        "stageA_block_scores": block_scores,
        "stageA_selected_blocks": list(selected_blocks),
        "stageB": stage_b,
        "stageB_layer_scores": {str(k): v for k, v in layer_scores.items()},
        "stageB_selected_layers": list(selected_layers),
        "stageC": stage_c,
        "stageC_union_repeat": repeat_union,
    }
    details_bytes = canonical_bytes(details)
    details_sha = _sha256(details_bytes)
    (args.output_root / "details.json").write_bytes(details_bytes)

    summary_core = {
        "study_id": STUDY_ID,
        "runner_version": RUNNER_VERSION,
        "status": "P2_D2_MEASUREMENT_COMPLETE" if integrity else "P2_D2_INTEGRITY_FAIL",
        "localization": summary_metrics["localization"] if integrity else "NOT_EVALUABLE",
        "git_commit": _git_head(),
        "prereg_commit": PREREG_COMMIT,
        "source_d1_result_digest": SOURCE_D1_RESULT_DIGEST,
        "p2_result_unchanged": "C10_NOT_BEHAVIORALLY_ADMITTED",
        "environment": environment,
        "preflight": preflight,
        "selected_blocks": list(selected_blocks),
        "selected_layers": list(selected_layers),
        "stageA_block_scores": block_scores,
        "stageB_layer_scores": {str(k): v for k, v in layer_scores.items()},
        "stageC": summary_metrics,
        "integrity": {
            "pass": integrity,
            "union_exact_repeat_serialized_equal": repeat_equal,
            "source_d1_unchanged": source_before == source_after,
            "runtime_freeze": {"sha256": freeze_sha, "package_count": package_count},
            "action_intent_generation": False,
            "simulation_state_commits": 0,
            "weight_updates": 0,
            "retries": 0,
            "repairs": 0,
            "fallbacks": 0,
        },
        "details_sha256": details_sha,
    }
    digest = _sha256(canonical_bytes(summary_core))
    summary = dict(summary_core)
    summary["result_digest"] = digest
    (args.output_root / "summary.json").write_bytes(canonical_bytes(summary))
    print(json.dumps({
        "status": summary["status"],
        "localization": summary["localization"],
        "integrity": integrity,
        "selected_blocks": list(selected_blocks),
        "selected_layers": list(selected_layers),
        "result_digest": digest,
        "summary": str(args.output_root / "summary.json"),
    }, sort_keys=True))
    return 0 if integrity else 2


if __name__ == "__main__":
    raise SystemExit(main())
