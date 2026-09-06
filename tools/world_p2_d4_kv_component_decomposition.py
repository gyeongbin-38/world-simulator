#!/usr/bin/env python3
"""Run preregistered WORLD P2-D4 K/V cache-component decomposition."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from statistics import median
import subprocess
import sys
import tempfile
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))
sys.path.insert(0, str(REPOSITORY_ROOT))

from alifelm.model.p2_d1_boundary import D1_ACTION_ORDER  # noqa: E402
from alifelm.model.p2_d2_cache_patch import (  # noqa: E402
    _clone_tensor,
    _legacy_cache,
    cache_signature,
    transplant_cache_layers,
    validate_cache_pair,
)
from alifelm.model.p2_d2_metrics import mediator_values, median_symmetric_score  # noqa: E402
from alifelm.model.p2_d2_scoring import (  # noqa: E402
    D2_SCREEN_ACTIONS,
    build_prefill_caches,
    score_i3_from_prefill_cache,
)
from alifelm.model.p2_d4_cache_component_patch import transplant_cache_components  # noqa: E402
from alifelm.model.p2_d4_metrics import D4_CANDIDATE_ORDER, select_component_candidate  # noqa: E402
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
    _assert_matches_d1,
    _compile_and_verify,
    _profile,
    _policy,
    _runtime_freeze_sha256,
    _score_record,
    _source_gap,
    _source_map,
    _static_preflight,
)


STUDY_ID = "WORLD_P2_D4_KV_COMPONENT_DECOMPOSITION_V1"
RUNNER_VERSION = "1.0.0"
PREREG_COMMIT = "80e449ee464c8c682ae33f2cd026e88ea6fa351c"
CONFIG_RELPATH = "docs/research/world/WORLD_P2_D4_KV_COMPONENT_DECOMPOSITION_CONFIG_V1.json"
SCREEN_CASES = range(4000, 4004)
TARGET_LAYERS = (9, 10)
CANDIDATES = (
    ("L9_K", (9,), "K"),
    ("L9_V", (9,), "V"),
    ("L10_K", (10,), "K"),
    ("L10_V", (10,), "V"),
    ("L9_L10_K", (9, 10), "K"),
    ("L9_L10_V", (9, 10), "V"),
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
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
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
        raise SmokePreflightError("P2-D4 preregistered config bytes drifted")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", PREREG_COMMIT, "HEAD"],
        cwd=REPOSITORY_ROOT,
    )
    if ancestor.returncode != 0:
        raise SmokePreflightError("P2-D4 preregistration commit is not an ancestor of HEAD")
    config = json.loads(raw.decode("utf-8"))
    if (
        config.get("study_id") != STUDY_ID
        or config.get("status") != "PREREGISTERED_MECHANISTIC_DIAGNOSTIC"
        or tuple(config.get("intervention", {}).get("target_layers", ())) != TARGET_LAYERS
        or tuple(item.get("id") for item in config.get("component_candidates", ())) != D4_CANDIDATE_ORDER
    ):
        raise SmokePreflightError("P2-D4 config semantic identity drift")
    return config, _sha256(raw)


def _integrity_pass(payload: dict[str, Any]) -> bool:
    value = payload.get("integrity")
    return value is True or (isinstance(value, dict) and value.get("pass") is True)


def _verify_recovery_hashes(
    *,
    root: Path,
    stdout: Path,
    archive: Path,
    expected_summary: str,
    expected_details: str,
    expected_stdout: str,
    expected_archive: str,
    label: str,
) -> tuple[Path, Path, dict[str, str]]:
    summary = root / "summary.json"
    details = root / "details.json"
    for path in (summary, details, stdout, archive):
        if not path.is_file():
            raise SmokePreflightError(f"P2-D4 {label} recovery evidence missing: {path}")
    observed = {
        "summary_sha256": _file_sha256(summary),
        "details_sha256": _file_sha256(details),
        "stdout_sha256": _file_sha256(stdout),
        "archive_sha256": _file_sha256(archive),
    }
    expected = {
        "summary_sha256": expected_summary,
        "details_sha256": expected_details,
        "stdout_sha256": expected_stdout,
        "archive_sha256": expected_archive,
    }
    if observed != expected:
        raise SmokePreflightError(f"P2-D4 {label} recovery hash drift: {observed}")
    return summary, details, observed


def _verify_source_d1(root: Path, stdout: Path, archive: Path, config: dict[str, Any]):
    source = config["source_d1"]
    summary, details, observed = _verify_recovery_hashes(
        root=root,
        stdout=stdout,
        archive=archive,
        expected_summary=source["recovery_summary_sha256"],
        expected_details=source["historical_details_sha256"],
        expected_stdout=source["recovery_stdout_sha256"],
        expected_archive=source["recovery_archive_sha256"],
        label="D1",
    )
    summary_payload = json.loads(summary.read_text(encoding="utf-8"))
    details_payload = json.loads(details.read_text(encoding="utf-8"))
    if (
        summary_payload.get("study_id") != source["study_id"]
        or summary_payload.get("status") != "P2_D1_MEASUREMENT_COMPLETE"
        or summary_payload.get("localization") != "RANK_CONTEXT_SENSITIVE"
        or summary_payload.get("p2_result_unchanged") != "C10_NOT_BEHAVIORALLY_ADMITTED"
        or not _integrity_pass(summary_payload)
        or details_payload.get("study_id") != source["study_id"]
    ):
        raise SmokePreflightError("P2-D4 D1 recovery semantic identity drift")
    return {f"d1_{key}": value for key, value in observed.items()}, details_payload


def _verify_source_d2(root: Path, stdout: Path, archive: Path, config: dict[str, Any]):
    source = config["source_d2"]
    summary, details, observed = _verify_recovery_hashes(
        root=root,
        stdout=stdout,
        archive=archive,
        expected_summary=source["recovery_summary_sha256"],
        expected_details=source["details_sha256"],
        expected_stdout=source["recovery_stdout_sha256"],
        expected_archive=source["recovery_archive_sha256"],
        label="D2",
    )
    summary_payload = json.loads(summary.read_text(encoding="utf-8"))
    details_payload = json.loads(details.read_text(encoding="utf-8"))
    if (
        summary_payload.get("study_id") != source["study_id"]
        or summary_payload.get("status") != "P2_D2_MEASUREMENT_COMPLETE"
        or summary_payload.get("localization") != source["localization"]
        or summary_payload.get("selected_layers") != source["selected_layers"]
        or summary_payload.get("selected_blocks") != ["Q2", "Q1"]
        or not _integrity_pass(summary_payload)
        or details_payload.get("study_id") != source["study_id"]
    ):
        raise SmokePreflightError("P2-D4 D2 recovery semantic identity drift")
    return {f"d2_{key}": value for key, value in observed.items()}, details_payload


def _verify_source_d3(root: Path, stdout: Path, archive: Path, config: dict[str, Any]):
    source = config["source_d3"]
    summary, details, observed = _verify_recovery_hashes(
        root=root,
        stdout=stdout,
        archive=archive,
        expected_summary=source["summary_sha256"],
        expected_details=source["details_sha256"],
        expected_stdout=source["stdout_sha256"],
        expected_archive=source["archive_sha256"],
        label="D3",
    )
    summary_payload = json.loads(summary.read_text(encoding="utf-8"))
    details_payload = json.loads(details.read_text(encoding="utf-8"))
    if (
        summary_payload.get("study_id") != source["study_id"]
        or summary_payload.get("status") != "P2_D3_MEASUREMENT_COMPLETE"
        or summary_payload.get("result_digest") != source["result_digest"]
        or summary_payload.get("selected_scale") != source["selected_scale"]
        or summary_payload.get("repair_proxy") != source["repair_proxy"]
        or not _integrity_pass(summary_payload)
        or details_payload.get("study_id") != source["study_id"]
    ):
        raise SmokePreflightError("P2-D4 D3 semantic identity drift")
    return {f"d3_{key}": value for key, value in observed.items()}, summary_payload


def _screen_rows(cohort):
    return [row for row in cohort if row[1] in SCREEN_CASES]


def _tensor_equal(left: Any, right: Any) -> bool:
    equal = getattr(left, "equal", None)
    if callable(equal):
        return bool(equal(right))
    comparison = left == right
    all_fn = getattr(comparison, "all", None)
    if callable(all_fn):
        comparison = all_fn()
    item = getattr(comparison, "item", None)
    if callable(item):
        comparison = item()
    return bool(comparison)


def _snapshot_cache(cache: Any):
    layers, _, _ = _legacy_cache(cache)
    return tuple((_clone_tensor(key), _clone_tensor(value)) for key, value in layers)


def _cache_matches_layers(cache: Any, layers: tuple[tuple[Any, Any], ...]) -> bool:
    observed, _, _ = _legacy_cache(cache)
    return len(observed) == len(layers) and all(
        _tensor_equal(left_key, right_key) and _tensor_equal(left_value, right_value)
        for (left_key, left_value), (right_key, right_value) in zip(observed, layers)
    )


def _cache_equal(left: Any, right: Any) -> bool:
    right_layers, _, _ = _legacy_cache(right)
    return _cache_matches_layers(left, right_layers)


def _assert_component_structure(
    patched: Any,
    target: Any,
    donor: Any,
    layers: tuple[int, ...],
    component: str,
) -> None:
    patched_layers, _, _ = _legacy_cache(patched)
    target_layers, _, _ = _legacy_cache(target)
    donor_layers, _, _ = _legacy_cache(donor)
    selected = set(layers)
    for index, ((pk, pv), (tk, tv), (dk, dv)) in enumerate(
        zip(patched_layers, target_layers, donor_layers)
    ):
        expected_k = dk if index in selected and component == "K" else tk
        expected_v = dv if index in selected and component == "V" else tv
        if not _tensor_equal(pk, expected_k) or not _tensor_equal(pv, expected_v):
            raise SmokePreflightError("P2-D4 component patch changed a nonselected cache component")


def _run_stage0(runtime, cohort, d1_details) -> dict[str, Any]:
    c00, c10 = _source_map(d1_details, "C00"), _source_map(d1_details, "C10")
    checked = 0
    for context, case, compiled in _screen_rows(cohort):
        key = (context, case)
        rendered = I3_CONDITIONAL_TYPED_CODEC.render(compiled.rendered_input)
        pair = build_prefill_caches(runtime, rendered_input=rendered)
        validate_cache_pair(pair.base_cache, pair.fa_cache)
        base_before = _snapshot_cache(pair.base_cache)
        fa_before = _snapshot_cache(pair.fa_cache)

        base_score = score_i3_from_prefill_cache(
            runtime,
            rendered_input=rendered,
            phase_a_cache=pair.base_cache,
            actions_to_score=D2_SCREEN_ACTIONS,
        )
        fa_score = score_i3_from_prefill_cache(
            runtime,
            rendered_input=rendered,
            phase_a_cache=pair.fa_cache,
            actions_to_score=D2_SCREEN_ACTIONS,
        )
        _assert_matches_d1(base_score, c00[key], D2_SCREEN_ACTIONS)
        _assert_matches_d1(fa_score, c10[key], D2_SCREEN_ACTIONS)

        for target, donor in (
            (pair.fa_cache, pair.base_cache),
            (pair.base_cache, pair.fa_cache),
        ):
            k_patch = transplant_cache_components(target, donor, TARGET_LAYERS, "K")
            v_patch = transplant_cache_components(target, donor, TARGET_LAYERS, "V")
            _assert_component_structure(k_patch, target, donor, TARGET_LAYERS, "K")
            _assert_component_structure(v_patch, target, donor, TARGET_LAYERS, "V")
            if cache_signature(k_patch) != cache_signature(target):
                raise SmokePreflightError("P2-D4 K patch changed cache signature")
            if cache_signature(v_patch) != cache_signature(target):
                raise SmokePreflightError("P2-D4 V patch changed cache signature")

            self_k = transplant_cache_components(target, target, TARGET_LAYERS, "K")
            self_v = transplant_cache_components(target, target, TARGET_LAYERS, "V")
            if not _cache_equal(self_k, target) or not _cache_equal(self_v, target):
                raise SmokePreflightError("P2-D4 component self-donor patch is not a no-op")

            composed_kv = transplant_cache_components(k_patch, donor, TARGET_LAYERS, "V")
            composed_vk = transplant_cache_components(v_patch, donor, TARGET_LAYERS, "K")
            full_kv = transplant_cache_layers(target, donor, TARGET_LAYERS)
            if not _cache_equal(composed_kv, full_kv) or not _cache_equal(composed_vk, full_kv):
                raise SmokePreflightError("P2-D4 K/V composition differs from D2 full-KV transplant")

        if not _cache_matches_layers(pair.base_cache, base_before):
            raise SmokePreflightError("P2-D4 Stage-0 mutated BASE source cache")
        if not _cache_matches_layers(pair.fa_cache, fa_before):
            raise SmokePreflightError("P2-D4 Stage-0 mutated FA source cache")
        checked += 1

    if checked != 20:
        raise SmokePreflightError("P2-D4 Stage-0 did not cover frozen screening cohort")
    return {
        "status": "PASS",
        "contexts_checked": checked,
        "baseline_matches_d1": True,
        "component_self_donor_noop": True,
        "component_composition_matches_d2_full_kv": True,
        "nonselected_component_preserved": True,
        "source_cache_immutability": True,
        "cache_signature_preserved": True,
    }


def _component_patch_score(runtime, rendered: bytes, target: Any, donor: Any, layers, component, actions):
    patched = transplant_cache_components(target, donor, layers, component)
    return score_i3_from_prefill_cache(
        runtime,
        rendered_input=rendered,
        phase_a_cache=patched,
        actions_to_score=actions,
    )


def _run_stage_a(runtime, cohort, d1_details):
    c00, c10 = _source_map(d1_details, "C00"), _source_map(d1_details, "C10")
    rows = []
    for ordinal, (context, case, compiled) in enumerate(_screen_rows(cohort), 1):
        key = (context, case)
        rendered = I3_CONDITIONAL_TYPED_CODEC.render(compiled.rendered_input)
        pair = build_prefill_caches(runtime, rendered_input=rendered)
        g_base, g_fa = _source_gap(c00[key]), _source_gap(c10[key])
        if g_fa - g_base <= 0:
            raise SmokePreflightError("P2-D4 source WAIT-SEND gap direction is not positive")
        candidates = {}
        for candidate, layers, component in CANDIDATES:
            rescue = _component_patch_score(
                runtime, rendered, pair.fa_cache, pair.base_cache, layers, component, D2_SCREEN_ACTIONS
            )
            induction = _component_patch_score(
                runtime, rendered, pair.base_cache, pair.fa_cache, layers, component, D2_SCREEN_ACTIONS
            )
            metrics = mediator_values(
                g_base,
                g_fa,
                rescue.wait_send_total_gap(),
                induction.wait_send_total_gap(),
            )
            candidates[candidate] = {
                "layers": list(layers),
                "component": component,
                **metrics,
                "rescue": _score_record(rescue, condition=f"RESCUE_{candidate}", layers=layers),
                "induction": _score_record(induction, condition=f"INDUCTION_{candidate}", layers=layers),
            }
        rows.append(
            {
                "context_class": context,
                "case_index": case,
                "g_base": g_base,
                "g_fa": g_fa,
                "candidates": candidates,
            }
        )
        if ordinal % 5 == 0:
            print(f"P2_D4_STAGEA {ordinal}/20", flush=True)

    scores = {
        candidate: median_symmetric_score([row["candidates"][candidate] for row in rows])
        for candidate in D4_CANDIDATE_ORDER
    }
    selected = select_component_candidate(scores)
    return rows, scores, selected


def _candidate_spec(candidate: str) -> tuple[tuple[int, ...], str]:
    for name, layers, component in CANDIDATES:
        if name == candidate:
            return layers, component
    raise SmokePreflightError("P2-D4 selected candidate is outside frozen candidate set")


def _run_stage_b(runtime, cohort, d1_details, selected: str, *, repeat: bool = False):
    c00, c10 = _source_map(d1_details, "C00"), _source_map(d1_details, "C10")
    layers, component = _candidate_spec(selected)
    rows = []
    for ordinal, (context, case, compiled) in enumerate(cohort, 1):
        key = (context, case)
        rendered = I3_CONDITIONAL_TYPED_CODEC.render(compiled.rendered_input)
        pair = build_prefill_caches(runtime, rendered_input=rendered)
        conditions = {}
        if not repeat:
            base = score_i3_from_prefill_cache(
                runtime, rendered_input=rendered, phase_a_cache=pair.base_cache, actions_to_score=D1_ACTION_ORDER
            )
            fa = score_i3_from_prefill_cache(
                runtime, rendered_input=rendered, phase_a_cache=pair.fa_cache, actions_to_score=D1_ACTION_ORDER
            )
            _assert_matches_d1(base, c00[key], D1_ACTION_ORDER)
            _assert_matches_d1(fa, c10[key], D1_ACTION_ORDER)
            conditions["B_BASELINE"] = _score_record(base, condition="B_BASELINE", layers=())
            conditions["F_BASELINE"] = _score_record(fa, condition="F_BASELINE", layers=())
            g_base, g_fa = base.wait_send_total_gap(), fa.wait_send_total_gap()
        else:
            g_base, g_fa = _source_gap(c00[key]), _source_gap(c10[key])

        rescue = _component_patch_score(
            runtime, rendered, pair.fa_cache, pair.base_cache, layers, component, D1_ACTION_ORDER
        )
        induction = _component_patch_score(
            runtime, rendered, pair.base_cache, pair.fa_cache, layers, component, D1_ACTION_ORDER
        )
        conditions[f"RESCUE_{selected}"] = _score_record(
            rescue, condition=f"RESCUE_{selected}", layers=layers
        )
        conditions[f"INDUCTION_{selected}"] = _score_record(
            induction, condition=f"INDUCTION_{selected}", layers=layers
        )
        metrics = mediator_values(
            g_base,
            g_fa,
            rescue.wait_send_total_gap(),
            induction.wait_send_total_gap(),
        )
        rows.append(
            {
                "context_class": context,
                "case_index": case,
                "selected_candidate": selected,
                "layers": list(layers),
                "component": component,
                "g_base": g_base,
                "g_fa": g_fa,
                "metrics": metrics,
                "conditions": conditions,
            }
        )
        if ordinal % 20 == 0:
            label = "REPEAT" if repeat else "STAGEB"
            print(f"P2_D4_{label} {ordinal}/160", flush=True)
    return rows


def _repeat_view(rows, selected: str):
    return [
        {
            "context_class": row["context_class"],
            "case_index": row["case_index"],
            "selected_candidate": row["selected_candidate"],
            "layers": row["layers"],
            "component": row["component"],
            "g_base": row["g_base"],
            "g_fa": row["g_fa"],
            "metrics": row["metrics"],
            "conditions": {
                f"RESCUE_{selected}": row["conditions"][f"RESCUE_{selected}"],
                f"INDUCTION_{selected}": row["conditions"][f"INDUCTION_{selected}"],
            },
        }
        for row in rows
    ]


def _condition_summary(rows, condition: str) -> dict[str, Any]:
    gaps = []
    rank1 = defaultdict(int)
    by_context = defaultdict(list)
    for row in rows:
        record = row["conditions"][condition]
        gap = float(record["wait_send_total_gap"])
        gaps.append(gap)
        rank1[record["total_rank1"]] += 1
        by_context[row["context_class"]].append(gap)
    return {
        "rank1_distribution": dict(rank1),
        "gap_min": min(gaps),
        "gap_median": float(median(gaps)),
        "gap_max": max(gaps),
        "gap_median_by_context": {
            context: float(median(values)) for context, values in sorted(by_context.items())
        },
    }


def _stage_b_summary(rows, selected: str) -> dict[str, Any]:
    rescue_name = f"RESCUE_{selected}"
    induction_name = f"INDUCTION_{selected}"
    rescue_gaps = [float(row["conditions"][rescue_name]["wait_send_total_gap"]) for row in rows]
    induction_gaps = [float(row["conditions"][induction_name]["wait_send_total_gap"]) for row in rows]
    return {
        "selected_candidate": selected,
        "median_symmetric_mediator_score": float(median(row["metrics"]["symmetric_score"] for row in rows)),
        "rescue_sign_flip_count": sum(gap < 0 for gap in rescue_gaps),
        "induction_sign_flip_count": sum(gap > 0 for gap in induction_gaps),
        "baseline": _condition_summary(rows, "B_BASELINE"),
        "fa": _condition_summary(rows, "F_BASELINE"),
        "rescue": _condition_summary(rows, rescue_name),
        "induction": _condition_summary(rows, induction_name),
    }


def _matching_d2_conditions(selected: str) -> tuple[str, str]:
    if selected.startswith("L9_L10_"):
        return "RESCUE_L1_L2_UNION", "INDUCTION_L1_L2_UNION"
    if selected.startswith("L9_"):
        return "RESCUE_L9", "INDUCTION_L9"
    if selected.startswith("L10_"):
        return "RESCUE_L10", "INDUCTION_L10"
    raise SmokePreflightError("P2-D4 selected candidate has no matching D2 full-KV condition")


def _d2_reference_summary(d2_details: dict[str, Any], selected: str) -> dict[str, Any]:
    rows = d2_details.get("stageC")
    if not isinstance(rows, list) or len(rows) != 160:
        raise SmokePreflightError("P2-D4 source D2 Stage-C evidence is incomplete")
    rescue_name, induction_name = _matching_d2_conditions(selected)
    return {
        "rescue_condition": rescue_name,
        "induction_condition": induction_name,
        "rescue": _condition_summary(rows, rescue_name),
        "induction": _condition_summary(rows, induction_name),
    }


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
    parser.add_argument("--d3-root", type=Path, required=True)
    parser.add_argument("--d3-stdout", type=Path, required=True)
    parser.add_argument("--d3-archive", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--expected-git-commit", required=True)
    args = parser.parse_args()

    config, config_sha = _verify_prereg_config(args.config)
    if _git_head() != args.expected_git_commit:
        raise SmokePreflightError("P2-D4 expected git commit mismatch")

    d1_paths = {"root": args.d1_root, "stdout": args.d1_stdout, "archive": args.d1_archive}
    d2_paths = {"root": args.d2_root, "stdout": args.d2_stdout, "archive": args.d2_archive}
    d3_paths = {"root": args.d3_root, "stdout": args.d3_stdout, "archive": args.d3_archive}
    d1_before, d1_details = _verify_source_d1(**d1_paths, config=config)
    d2_before, d2_details = _verify_source_d2(**d2_paths, config=config)
    d3_before, _ = _verify_source_d3(**d3_paths, config=config)

    freeze_sha, package_count = _runtime_freeze_sha256()
    if freeze_sha != PIP_FREEZE_SHA256 or package_count != RUNTIME_PACKAGE_COUNT:
        raise SmokePreflightError("P2-D4 canonical runtime freeze drift")
    model_config = json.loads((args.base_model_dir / "config.json").read_text(encoding="utf-8"))
    if int(model_config.get("num_hidden_layers", -1)) != 16:
        raise SmokePreflightError("P2-D4 model config does not expose 16 hidden layers")

    paths = DeploymentPaths(args.base_model_dir, args.adapter_path, args.output_root)
    preflight = _static_preflight(paths, args.expected_git_commit)
    profile, policy = _profile(args.base_model_dir), _policy()

    if args.validate_only:
        with tempfile.TemporaryDirectory(prefix="world-p2-d4-validate-") as tmp:
            cohort = _compile_and_verify(FileSystemArtifactStore(Path(tmp) / "cas"), profile, policy, d1_details)
        print(json.dumps({
            "status": "P2_D4_STATIC_PREFLIGHT_OK",
            "study_id": STUDY_ID,
            "git_commit": _git_head(),
            "prereg_commit": PREREG_COMMIT,
            "config_sha256": config_sha,
            "source_d1": d1_before,
            "source_d2": d2_before,
            "source_d3": d3_before,
            "runtime_pip_freeze_sha256": freeze_sha,
            "runtime_package_count": package_count,
            "compiled_contexts": len(cohort),
            "screening_contexts": 20,
            "target_layers": list(TARGET_LAYERS),
            "component_candidates": list(D4_CANDIDATE_ORDER),
            "model_loaded": False,
            "simulation_state_commit": False,
            "weight_update": False,
        }, sort_keys=True))
        return 0

    if args.output_root.exists():
        raise SmokePreflightError("P2-D4 output root already exists; failed attempts are immutable")
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
        "source_d3": d3_before,
        "target_layers": list(TARGET_LAYERS),
        "component_candidates": list(D4_CANDIDATE_ORDER),
        "selection_rule": config["stageA"]["selection_rule"],
        "simulation_state_commit": False,
        "weight_update": False,
    }))

    store = FileSystemArtifactStore(args.output_root / "cas")
    cohort = _compile_and_verify(store, profile, policy, d1_details)
    runtime = PeftTransformersLoader(base_model_dir=args.base_model_dir, adapter_path=args.adapter_path)(profile)

    stage0 = _run_stage0(runtime, cohort, d1_details)
    stage_a, stage_a_scores, selected = _run_stage_a(runtime, cohort, d1_details)
    stage_b = _run_stage_b(runtime, cohort, d1_details, selected)
    repeat = _run_stage_b(runtime, cohort, d1_details, selected, repeat=True)

    repeat_equal = _repeat_view(stage_b, selected) == repeat
    d1_after, _ = _verify_source_d1(**d1_paths, config=config)
    d2_after, _ = _verify_source_d2(**d2_paths, config=config)
    d3_after, _ = _verify_source_d3(**d3_paths, config=config)
    integrity = bool(
        stage0["status"] == "PASS"
        and repeat_equal
        and d1_before == d1_after
        and d2_before == d2_after
        and d3_before == d3_after
    )
    stage_b_summary = _stage_b_summary(stage_b, selected)
    d2_reference = _d2_reference_summary(d2_details, selected)

    details = {
        "study_id": STUDY_ID,
        "stage0": stage0,
        "stageA": stage_a,
        "stageA_candidate_scores": stage_a_scores,
        "stageA_selected_candidate": selected,
        "stageB": stage_b,
        "stageB_exact_repeat": repeat,
        "matching_d2_full_kv_reference": d2_reference,
    }
    details_bytes = canonical_bytes(details)
    details_sha = _sha256(details_bytes)
    (args.output_root / "details.json").write_bytes(details_bytes)

    result_digest = _sha256(canonical_bytes({
        "study_id": STUDY_ID,
        "selected_candidate": selected,
        "stageA_candidate_scores": stage_a_scores,
        "stageB_summary": stage_b_summary,
        "details_sha256": details_sha,
    }))
    summary = {
        "study_id": STUDY_ID,
        "runner_version": RUNNER_VERSION,
        "status": "P2_D4_MEASUREMENT_COMPLETE" if integrity else "P2_D4_INTEGRITY_FAIL",
        "git_commit": _git_head(),
        "prereg_commit": PREREG_COMMIT,
        "source_p2_interpretation": "C10_NOT_BEHAVIORALLY_ADMITTED",
        "selected_candidate": selected,
        "stageA_candidate_scores": stage_a_scores,
        "stageB": stage_b_summary,
        "matching_d2_full_kv_reference": d2_reference,
        "integrity": {
            "pass": integrity,
            "stage0_pass": stage0["status"] == "PASS",
            "exact_repeat_serialized_equal": repeat_equal,
            "source_d1_unchanged": d1_before == d1_after,
            "source_d2_unchanged": d2_before == d2_after,
            "source_d3_unchanged": d3_before == d3_after,
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
        "selected_candidate": selected,
        "result_digest": result_digest,
        "summary": str(args.output_root / "summary.json"),
    }, sort_keys=True))
    return 0 if integrity else 1


if __name__ == "__main__":
    raise SystemExit(main())
