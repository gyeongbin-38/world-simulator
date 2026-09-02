#!/usr/bin/env python3
"""Run frozen WORLD P2 phase-decoupled behavioral admission.

P2 performs research-only I3 generation under four cached phase conditions.
Generated candidates remain non-canonical; no simulation commit or weight update
is reachable from this runner.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from alifelm.domain import ArtifactId, ArtifactRef, Duration  # noqa: E402
from alifelm.kernel import SimulationRun  # noqa: E402
from alifelm.model.autonomous_admission import (  # noqa: E402
    A0TreatmentMetrics,
    evaluate_i3_branch_order_audit,
    evaluate_treatment,
)
from alifelm.model.evidence import RealCognitionDryRunner, raw_generation_bytes  # noqa: E402
from alifelm.model.generation import GenerationPolicy  # noqa: E402
from alifelm.model.p2_metrics import (  # noqa: E402
    P2_CONTEXT_CLASSES,
    P2_MATCHED_CASES,
    P2_STUDY_ID,
    action_distribution_by_context,
    generated_context_sensitivity,
    paired_label_agreement,
    token_count_summary,
    wait_escape_reversal,
    wait_rates_by_context,
)
from alifelm.model.peft_runtime import PeftTransformersLoader  # noqa: E402
from alifelm.model.phase_generation import PhaseSwitchedGenerationRuntime  # noqa: E402
from alifelm.model.profile import ModelProfile  # noqa: E402
from alifelm.model.r3_fixtures import R3ContextClass, compile_r3_fixture  # noqa: E402
from alifelm.model.treatments import (  # noqa: E402
    I3_BRANCH_ORDERS,
    I3_CONDITIONAL_TYPED_CODEC,
    build_transformers_constraint,
    i3_branch_order_treatment,
    typed_action_codec_json_schema,
)
from alifelm.model.typed_codec import (  # noqa: E402
    CodecValidityStatus,
    CommitValidityStatus,
    DomainValidityStatus,
    evaluate_typed_codec,
    typed_codec_evaluation_bytes,
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


RUNNER_VERSION = "1.0.0"
PROTOCOL_COMMIT = "299b5ff29a14aef92b977ee53d0cf8e792067f11"
SOURCE_RESULTS_COMMIT = "1059b03e28668e2b8563c4aa81d39e1a2e65576f"
CONFIG_SHA256 = "c53bb0d0f037e70df0553cbd17d181b3402cc825812dd8ba1e481f096588e92b"
BASE_REVISION = "48d788eca847d4d7548f375ad03d3c9312f6139e"
BASE_SHA256 = "36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f"
TOKENIZER_SHA256 = "c448b9e69576a2af5fccdb905c4d6c9f6c0d06509b15d2459a3bc92bb33d42ff"
ADAPTER_SHA256 = "46917511362243be67e0783ddb7411a96f26613c1083bc4f95117d910d0998ec"
ADAPTER_CONFIG_SHA256 = "687100a0b6340b6096ca1e86066d3c13224b3c8e14ce9fb1b0cf78a52a8bdb7d"
PIP_FREEZE_SHA256 = "a98b9c11baf90a5e7717b1f108029838e9c917d46d1f499bf93e9adffad087bf"
RUNTIME_PACKAGE_COUNT = 60
CASE_START = 4000
CASE_END = 4031
CONTEXT_ENUMS = tuple(R3ContextClass(name) for name in P2_CONTEXT_CLASSES)
PHASE_CONDITIONS: tuple[tuple[str, bool, bool], ...] = (
    ("C00", False, False),
    ("C01", False, True),
    ("C10", True, False),
    ("C11", True, True),
)
PROFILE_ID = "WORLD_P2_FA_V1_BF16"
GENERATION_POLICY_ID = "P2_GREEDY_PHASE_DECOUPLED_I3_V1"
GENERATION_SEED_ID = "P2_GREEDY_SEED_V1"
GENERATION_SEED = 35020260831
MAX_NEW_TOKENS = 128

P1C_V2_RESULT_DIGEST = "0e19ae757ee07121102e1bd278125fe41d92e55b30add75f1e5895a1c315df04"
P1C_V2_SUMMARY_SHA256 = "8632473c2e13983d535a8b16381b3f8e4dc1eea68741ccb0ad2e9cfd4ef1c40a"
P1C_V2_DETAILS_SHA256 = "c03e4370cf077c0c7c492727375141ecb66623762bcc96b0881ae147c5a272ea"
P1C_V2_STDOUT_SHA256 = "061d50db2eb7dec80af44c251bf5586c13df64f1a8a486e530ab693a7800e004"
P1C_V2_ARCHIVE_SHA256 = "b34f60b98868bf9a26b3d726fb4b6fd9093e9d2ec462b247cb82553900b0c39d"


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
        raise SmokePreflightError("cannot resolve P2 repository commit") from error


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
    digest = _sha256(raw)
    if digest != CONFIG_SHA256:
        raise SmokePreflightError("P2 frozen config SHA-256 drift")
    config = json.loads(raw.decode("utf-8"))
    if config.get("study_id") != P2_STUDY_ID:
        raise SmokePreflightError("P2 config study_id drift")
    if config.get("protocol_commit") != PROTOCOL_COMMIT:
        raise SmokePreflightError("P2 protocol commit drift")
    if config.get("source_results_commit") != SOURCE_RESULTS_COMMIT:
        raise SmokePreflightError("P2 source-results commit drift")
    return config, digest


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
    checks = {
        "base_checkpoint_sha256": BASE_SHA256,
        "adapter_sha256": ADAPTER_SHA256,
        "adapter_config_sha256": ADAPTER_CONFIG_SHA256,
        "tokenizer_digest": TOKENIZER_SHA256,
    }
    for name, expected in checks.items():
        if result.get(name) != expected:
            raise SmokePreflightError(f"P2 static identity mismatch: {name}")
    return result


def _verify_source_evidence(root: Path, stdout: Path, archive: Path) -> dict[str, str]:
    summary = root / "summary.json"
    details = root / "details.json"
    required = (summary, details, stdout, archive)
    if any(not path.is_file() for path in required):
        raise SmokePreflightError("P2 source P1C-v2 evidence is incomplete")
    observed = {
        "p1c_v2_summary_sha256": _file_sha256(summary),
        "p1c_v2_details_sha256": _file_sha256(details),
        "p1c_v2_stdout_sha256": _file_sha256(stdout),
        "p1c_v2_archive_sha256": _file_sha256(archive),
    }
    expected = {
        "p1c_v2_summary_sha256": P1C_V2_SUMMARY_SHA256,
        "p1c_v2_details_sha256": P1C_V2_DETAILS_SHA256,
        "p1c_v2_stdout_sha256": P1C_V2_STDOUT_SHA256,
        "p1c_v2_archive_sha256": P1C_V2_ARCHIVE_SHA256,
    }
    if observed != expected:
        raise SmokePreflightError("P2 source P1C-v2 evidence SHA-256 drift")
    payload = json.loads(summary.read_text(encoding="utf-8"))
    if (
        payload.get("status") != "P1C_V2_MEASUREMENT_COMPLETE"
        or payload.get("localization") != "INTERPRETABLE"
        or payload.get("result_digest") != P1C_V2_RESULT_DIGEST
    ):
        raise SmokePreflightError("P2 source P1C-v2 semantic identity drift")
    return observed


def _profile(base_model_dir: Path) -> ModelProfile:
    return ModelProfile(
        profile_id=PROFILE_ID,
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
        adapter_ref=ArtifactRef(ArtifactId("F0_FA_V1_FORMAL"), ADAPTER_SHA256),
        trust_remote_code=False,
        add_special_tokens=True,
    )


def _policy() -> GenerationPolicy:
    return GenerationPolicy(
        policy_id=GENERATION_POLICY_ID,
        version="1.0.0",
        max_new_tokens=MAX_NEW_TOKENS,
        do_sample=False,
        temperature=None,
        top_p=None,
        top_k=None,
        repetition_penalty=1.0,
        seed_id=GENERATION_SEED_ID,
        stop_policy_id=None,
    )


def _compile_cohort(*, store, profile: ModelProfile, policy: GenerationPolicy):
    context_policy = build_context_policy()
    cohort = []
    for context_class in CONTEXT_ENUMS:
        for case_index in range(CASE_START, CASE_END + 1):
            compiled = compile_r3_fixture(
                context_class,
                case_index,
                policy=context_policy,
                model_profile_id=profile.profile_id,
                generation_policy_id=policy.policy_id,
                generation_seed_id=GENERATION_SEED_ID,
                artifact_store=store,
            )
            cohort.append((context_class.value, case_index, compiled))
    if len(cohort) != 160:
        raise AssertionError("P2 cohort size drifted from preregistration")
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
        bool(all(ref.digest for ref in refs))
        and resolved[1] == rendered_expected
        and resolved[2] == result.raw_generation.raw_text.encode("utf-8")
        and bool(resolved[0])
        and bool(resolved[3])
        and bool(resolved[4])
    )


def _raw_signature(result) -> bytes:
    return raw_generation_bytes(result.raw_generation)


def _labels_validity(records: list[dict[str, Any]]):
    labels = {name: [] for name in P2_CONTEXT_CLASSES}
    valid = {name: [] for name in P2_CONTEXT_CLASSES}
    for name in P2_CONTEXT_CLASSES:
        selected = sorted(
            (row for row in records if row["context_class"] == name),
            key=lambda row: row["case_index"],
        )
        if len(selected) != P2_MATCHED_CASES:
            raise AssertionError("P2 records do not partition into matched context classes")
        labels[name] = [row["candidate_label"] for row in selected]
        valid[name] = [bool(row["domain_valid"]) for row in selected]
    return labels, valid


def _condition_metrics(records: list[dict[str, Any]], *, exact_repeat: bool, treatment_name: str):
    class_counts = Counter()
    class_valid = Counter()
    codec_valid = domain_valid = evidence_complete = first_eos = 0
    for row in records:
        name = row["context_class"]
        class_counts[name] += 1
        codec_valid += int(row["codec_valid"])
        domain_valid += int(row["domain_valid"])
        evidence_complete += int(row["evidence_complete"])
        first_eos += int(row["first_token_eos"])
        class_valid[name] += int(row["domain_valid"])
    metrics = A0TreatmentMetrics(
        treatment=treatment_name,
        attempts=len(records),
        codec_valid=codec_valid,
        domain_valid=domain_valid,
        first_token_eos=first_eos,
        evidence_complete=evidence_complete,
        infrastructure_failures=0,
        exact_repeat_equal=exact_repeat,
        context_class_domain_valid=tuple(
            (name, class_valid[name], class_counts[name]) for name in P2_CONTEXT_CLASSES
        ),
    )
    return metrics, evaluate_treatment(metrics)


def _run_condition(
    *,
    fa_runtime,
    profile,
    policy,
    store,
    cohort,
    condition: str,
    prefill_adapter: bool,
    selector_adapter: bool,
    branch_order: tuple[str, ...] | None = None,
    audit_index: int | None = None,
):
    phase_runtime = PhaseSwitchedGenerationRuntime(
        fa_runtime,
        prefill_adapter=prefill_adapter,
        selector_adapter=selector_adapter,
    )
    if branch_order is None:
        treatment = I3_CONDITIONAL_TYPED_CODEC
        schema = typed_action_codec_json_schema()
        metric_treatment = "I3"
    else:
        if audit_index is None:
            raise ValueError("branch audit requires an index")
        treatment = i3_branch_order_treatment(audit_index)
        schema = typed_action_codec_json_schema(action_order=branch_order)
        metric_treatment = f"I3_ORDER_{audit_index}"
    constraint = build_transformers_constraint(fa_runtime.tokenizer, schema=schema)
    runner = RealCognitionDryRunner(
        phase_runtime,
        profile,
        policy,
        store,
        generation_seed=GENERATION_SEED,
        interface_treatment=treatment,
        prefix_allowed_tokens_fn=constraint,
    )

    records: list[dict[str, Any]] = []
    for ordinal, (context_name, case_index, compiled) in enumerate(cohort, 1):
        result = runner.run(compiled)
        trace = phase_runtime.last_trace
        if trace is None:
            raise AssertionError("P2 phase runtime did not expose generation trace")
        if tuple(result.raw_generation.token_ids or ()) != trace.generated_token_ids:
            raise AssertionError("P2 raw generation token IDs differ from phase trace")
        typed = evaluate_typed_codec(
            result.raw_generation.raw_text,
            compiled.opportunity,
            _diagnostic_run(compiled),
        )
        typed_ref = store.put_bytes(
            typed_codec_evaluation_bytes(
                typed,
                generation_id=result.evidence.generation_id,
                context_hash=result.evidence.context_hash,
                treatment_id=treatment.treatment_id,
                treatment_version=treatment.version,
            ),
            media_type="application/json",
            contract_id="p2-typed-codec-diagnostic-1.0.0",
        )
        is_codec = typed.codec_status is CodecValidityStatus.CODEC_VALID
        is_domain = typed.domain_status is DomainValidityStatus.DOMAIN_VALID
        is_commit = typed.commit_status is CommitValidityStatus.COMMIT_VALID
        candidate_label = (
            typed.candidate.action_label
            if is_codec and typed.candidate is not None
            else None
        )
        expected_rendered = treatment.render(compiled.rendered_input)
        complete = _evidence_complete(store, result, expected_rendered)
        token_ids = tuple(result.raw_generation.token_ids or ())
        row = {
            "condition": condition,
            "audit_index": audit_index,
            "context_class": context_name,
            "case_index": case_index,
            "rendered_context_sha256": _sha256(compiled.rendered_input),
            "rendered_request_sha256": _sha256(expected_rendered),
            "context_token_ids": list(trace.context_token_ids),
            "prefix_token_ids": list(trace.prefix_token_ids),
            "combined_token_ids": list(trace.combined_token_ids),
            "prefill_adapter": trace.prefill_adapter,
            "selector_adapter": trace.selector_adapter,
            "phase_boundary_token_aligned": trace.phase_boundary_token_aligned,
            "world_prefill_forward_count": trace.world_prefill_forward_count,
            "selector_prefix_forward_count": trace.selector_prefix_forward_count,
            "selector_continuation_forward_count": trace.selector_continuation_forward_count,
            "world_context_recomputed_after_switch": trace.world_context_recomputed_after_switch,
            "generation_id": result.evidence.generation_id,
            "raw_text_ref": result.evidence.raw_text_ref.digest,
            "raw_generation_ref": result.evidence.raw_generation_ref.digest,
            "evidence_ref": result.evidence_ref.digest,
            "typed_diagnostic_ref": typed_ref.digest,
            "finish_reason": result.raw_generation.finish_reason,
            "generated_token_count": len(token_ids),
            "first_token_eos": token_ids[:1] == (100257,) and result.raw_generation.finish_reason == "eos_token",
            "parse_status": result.evidence.parse_status.value,
            "codec_status": typed.codec_status.value,
            "domain_status": typed.domain_status.value,
            "commit_status": typed.commit_status.value,
            "codec_valid": is_codec,
            "domain_valid": is_domain,
            "commit_valid": is_commit,
            "candidate_label": candidate_label,
            "domain_valid_intent_kind": typed.intent.kind.value if is_domain and typed.intent is not None else None,
            "evidence_complete": complete,
        }
        records.append(row)
        if ordinal % 20 == 0 or ordinal == len(cohort):
            label = f"P2_AUDIT_{audit_index}" if audit_index is not None else f"P2_{condition}"
            print(f"{label} {ordinal}/{len(cohort)}", flush=True)

    first_compiled = cohort[0][2]
    first_signature = _raw_signature(type("R", (), {"raw_generation": None})()) if False else _raw_signature_result(records, store)
    repeat = runner.run(first_compiled)
    exact_repeat = raw_generation_bytes(repeat.raw_generation) == first_signature
    metrics, evaluation = _condition_metrics(
        records,
        exact_repeat=exact_repeat,
        treatment_name=metric_treatment,
    )
    labels, valid = _labels_validity(records)
    sensitivity = generated_context_sensitivity(labels, valid)
    return {
        "records": records,
        "metrics": metrics,
        "evaluation": evaluation,
        "labels_by_context": labels,
        "valid_by_context": valid,
        "sensitivity": sensitivity,
        "exact_repeat": exact_repeat,
        "repeat_raw_generation_ref": repeat.evidence.raw_generation_ref.digest,
    }


def _raw_signature_result(records: list[dict[str, Any]], store) -> bytes:
    if not records:
        raise ValueError("cannot resolve first raw generation from empty P2 records")
    digest = records[0]["raw_generation_ref"]
    # FileSystemArtifactStore resolves by ArtifactRef, so use the raw text-free
    # canonical bytes already stored by raw-generation-result evidence.
    from alifelm.domain import ArtifactId, ArtifactRef
    return store.resolve(ArtifactRef(ArtifactId(digest), digest)) if False else _resolve_digest(store, digest)


def _resolve_digest(store, digest: str) -> bytes:
    """Resolve a CAS digest without assuming its ArtifactId naming convention."""
    root = getattr(store, "root", None)
    if root is None:
        root = getattr(store, "_root", None)
    if root is None:
        raise RuntimeError("P2 requires filesystem CAS access for exact-repeat evidence")
    candidates = list(Path(root).rglob(digest))
    if len(candidates) != 1:
        raise RuntimeError("P2 could not uniquely resolve raw-generation CAS digest")
    return candidates[0].read_bytes()


def _flatten_labels(result: dict[str, Any]) -> list[str | None]:
    return [row["candidate_label"] for row in result["records"]]


def _descriptive_condition(result: dict[str, Any]) -> dict[str, Any]:
    records = result["records"]
    return {
        "validity_metrics": result["metrics"].as_dict(),
        "validity_evaluation": result["evaluation"],
        "generated_sensitivity": result["sensitivity"].as_dict(),
        "action_distribution_by_context": action_distribution_by_context(
            result["labels_by_context"], result["valid_by_context"]
        ),
        "wait_rate_by_context": wait_rates_by_context(result["labels_by_context"]),
        "commit_status_distribution": dict(sorted(Counter(row["commit_status"] for row in records).items())),
        "generated_token_count": token_count_summary([row["generated_token_count"] for row in records]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--base-model-dir", type=Path, required=True)
    parser.add_argument("--adapter-path", type=Path, required=True)
    parser.add_argument("--p1c-v2-root", type=Path, required=True)
    parser.add_argument("--p1c-v2-stdout", type=Path, required=True)
    parser.add_argument("--p1c-v2-archive", type=Path, required=True)
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
    source_paths = {
        "root": args.p1c_v2_root,
        "stdout": args.p1c_v2_stdout,
        "archive": args.p1c_v2_archive,
    }
    source_before = _verify_source_evidence(**source_paths)
    freeze_sha, package_count = _runtime_freeze_sha256()
    if freeze_sha != PIP_FREEZE_SHA256 or package_count != RUNTIME_PACKAGE_COUNT:
        raise SmokePreflightError("P2 canonical runtime freeze drift")
    profile = _profile(args.base_model_dir)
    policy = _policy()

    if args.validate_only:
        with tempfile.TemporaryDirectory(prefix="world-p2-validate-") as tmp:
            store = FileSystemArtifactStore(Path(tmp) / "cas")
            cohort = _compile_cohort(store=store, profile=profile, policy=policy)
        print(
            json.dumps(
                {
                    "status": "P2_STATIC_PREFLIGHT_OK",
                    "git_commit": _git_head(),
                    "protocol_commit": PROTOCOL_COMMIT,
                    "config_sha256": config_sha256,
                    "runtime_pip_freeze_sha256": freeze_sha,
                    "runtime_package_count": package_count,
                    "source_evidence": source_before,
                    "compiled_contexts": len(cohort),
                    "planned_measurements": {
                        "primary_generation_attempts": 640,
                        "primary_exact_repeats": 4,
                        "conditional_branch_audit_attempts_max": 640,
                        "conditional_branch_audit_exact_repeats_max": 4,
                        "ordinary_full_sequence_primary_generation_calls": 0,
                    },
                    "model_loaded": False,
                    "generation": False,
                    "state_commit": False,
                    "weight_update": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0

    if args.output_root.exists():
        raise SmokePreflightError("P2 output root already exists; failed runs are immutable")
    args.output_root.mkdir(parents=True, exist_ok=False)
    environment = ensure_execute_environment()
    plan = {
        "study_id": P2_STUDY_ID,
        "runner_version": RUNNER_VERSION,
        "git_commit": _git_head(),
        "protocol_commit": PROTOCOL_COMMIT,
        "config_sha256": config_sha256,
        "source_evidence": source_before,
        "conditions": [name for name, _, _ in PHASE_CONDITIONS],
        "cohort": {"case_start": CASE_START, "case_end": CASE_END, "contexts": 160},
        "generation_policy": config["generation"],
        "simulation_state_commit": False,
        "weight_update": False,
    }
    (args.output_root / "run_plan.json").write_bytes(canonical_bytes(plan))
    store = FileSystemArtifactStore(args.output_root / "cas")
    cohort = _compile_cohort(store=store, profile=profile, policy=policy)
    loader = PeftTransformersLoader(
        base_model_dir=args.base_model_dir,
        adapter_path=args.adapter_path,
    )
    fa_runtime = loader(profile)

    primary: dict[str, dict[str, Any]] = {}
    for condition, prefill, selector in PHASE_CONDITIONS:
        primary[condition] = _run_condition(
            fa_runtime=fa_runtime,
            profile=profile,
            policy=policy,
            store=store,
            cohort=cohort,
            condition=condition,
            prefill_adapter=prefill,
            selector_adapter=selector,
        )

    expected_flags = {name: (prefill, selector) for name, prefill, selector in PHASE_CONDITIONS}
    primary_complete = all(len(primary[name]["records"]) == 160 for name, _, _ in PHASE_CONDITIONS)
    primary_repeats = {name: bool(primary[name]["exact_repeat"]) for name, _, _ in PHASE_CONDITIONS}
    keys = [(context, index) for context in P2_CONTEXT_CLASSES for index in range(CASE_START, CASE_END + 1)]
    maps = {
        condition: {(row["context_class"], row["case_index"]): row for row in primary[condition]["records"]}
        for condition, _, _ in PHASE_CONDITIONS
    }
    context_identity = True
    phase_integrity = True
    for key in keys:
        reference = maps["C00"][key]
        for condition, _, _ in PHASE_CONDITIONS:
            row = maps[condition][key]
            context_identity = context_identity and (
                row["rendered_context_sha256"] == reference["rendered_context_sha256"]
                and row["context_token_ids"] == reference["context_token_ids"]
                and row["prefix_token_ids"] == reference["prefix_token_ids"]
                and row["combined_token_ids"] == reference["combined_token_ids"]
            )
            phase_integrity = phase_integrity and (
                (row["prefill_adapter"], row["selector_adapter"]) == expected_flags[condition]
                and row["phase_boundary_token_aligned"]
                and row["world_prefill_forward_count"] == 1
                and row["selector_prefix_forward_count"] == 1
                and not row["world_context_recomputed_after_switch"]
            )

    source_mid = _verify_source_evidence(**source_paths)
    g0_pre_audit = bool(
        primary_complete
        and context_identity
        and phase_integrity
        and all(primary_repeats.values())
        and freeze_sha == PIP_FREEZE_SHA256
        and package_count == RUNTIME_PACKAGE_COUNT
        and source_before == source_mid
    )
    c10_metrics = primary["C10"]["metrics"]
    c10_eval = primary["C10"]["evaluation"]
    g1 = bool(c10_eval["autonomous_pass"]) if g0_pre_audit else None
    g2 = bool(primary["C10"]["sensitivity"].passed) if g0_pre_audit else None

    audit_results: list[dict[str, Any]] = []
    g3_payload: dict[str, Any] | None = None
    g3_gate: bool | str | None
    if g0_pre_audit and g1 and g2:
        summaries = []
        labels_by_order = []
        for index, order in enumerate(I3_BRANCH_ORDERS):
            audit = _run_condition(
                fa_runtime=fa_runtime,
                profile=profile,
                policy=policy,
                store=store,
                cohort=cohort,
                condition="C10",
                prefill_adapter=True,
                selector_adapter=False,
                branch_order=order,
                audit_index=index,
            )
            audit_results.append(audit)
            summaries.append(audit["metrics"])
            labels_by_order.append(_flatten_labels(audit))
        g3_payload = evaluate_i3_branch_order_audit(summaries, labels_by_order)
        g3_gate = bool(g3_payload["pass"])
    else:
        g3_gate = "NOT_RUN_BY_PROTOCOL"

    source_after = _verify_source_evidence(**source_paths)
    g0 = bool(g0_pre_audit and source_before == source_after)
    if not g0:
        g1 = None
        g2 = None
        g3_gate = None
    g4 = bool(g0 and g1 and g2 and g3_gate is True)

    descriptive = {condition: _descriptive_condition(primary[condition]) for condition, _, _ in PHASE_CONDITIONS}
    c10_flat = _flatten_labels(primary["C10"])
    comparator_agreement = {
        condition: paired_label_agreement(c10_flat, _flatten_labels(primary[condition]))
        for condition in ("C00", "C01", "C11")
    }
    comparator_diagnostics = {
        "C10_pairwise_action_label_agreement": comparator_agreement,
        "paired_C11_to_C10_wait_escape_and_reversal": wait_escape_reversal(
            _flatten_labels(primary["C11"]), c10_flat
        ),
    }

    details = {
        "study_id": P2_STUDY_ID,
        "primary_conditions": {name: primary[name]["records"] for name, _, _ in PHASE_CONDITIONS},
        "branch_order_audits": [
            {
                "index": index,
                "order": list(I3_BRANCH_ORDERS[index]),
                "records": audit_results[index]["records"],
            }
            for index in range(len(audit_results))
        ],
    }
    details_bytes = canonical_bytes(details)
    details_sha256 = _sha256(details_bytes)
    (args.output_root / "details.json").write_bytes(details_bytes)

    result = {
        "study_id": P2_STUDY_ID,
        "runner_version": RUNNER_VERSION,
        "status": "P2_MEASUREMENT_COMPLETE" if g0 else "P2_INTEGRITY_FAIL",
        "localization": "INTERPRETABLE" if g0 else "BEHAVIORAL_ATTRIBUTION_NOT_EVALUABLE",
        "git_commit": _git_head(),
        "protocol_commit": PROTOCOL_COMMIT,
        "config_sha256": config_sha256,
        "environment": environment,
        "preflight": preflight,
        "source_before": source_before,
        "source_after": source_after,
        "gates": {
            "P2-G0": g0,
            "P2-G1": g1,
            "P2-G2": g2,
            "P2-G3": g3_gate,
            "P2-G4": g4,
        },
        "C10_G1_motor_domain": {
            "metrics": c10_metrics.as_dict(),
            "evaluation": c10_eval,
        } if g0 else None,
        "C10_G2_generated_context_sensitivity": primary["C10"]["sensitivity"].as_dict() if g0 else None,
        "C10_G3_branch_order_audit": g3_payload if g0 else None,
        "candidate_promotion": (
            "C10_PHASE_DECOUPLED_BEHAVIORAL_ADMISSION_PASS"
            if g4
            else "C10_NOT_BEHAVIORALLY_ADMITTED"
        ) if g0 else "NOT_EVALUABLE",
        "condition_diagnostics": descriptive,
        "comparator_diagnostics": comparator_diagnostics,
        "integrity": {
            "primary_condition_attempts": {name: len(primary[name]["records"]) for name, _, _ in PHASE_CONDITIONS},
            "primary_exact_repeats": primary_repeats,
            "exact_context_bytes_and_tokenization_across_conditions": context_identity,
            "phase_execution_integrity": phase_integrity,
            "runtime_freeze": {"sha256": freeze_sha, "package_count": package_count, "frozen": freeze_sha == PIP_FREEZE_SHA256 and package_count == RUNTIME_PACKAGE_COUNT},
            "source_evidence_unchanged": source_before == source_after,
            "branch_audit_orders_run": len(audit_results),
            "ordinary_full_sequence_primary_generation_calls": 0,
            "simulation_state_commits": 0,
            "weight_updates": 0,
            "retries": 0,
            "fallbacks": 0,
            "repairs": 0,
        },
        "details_sha256": details_sha256,
        "behavioral_admission": g4,
        "founder_freeze": "NOT_ESTABLISHED",
    }
    result["result_digest"] = canonical_digest(result)
    (args.output_root / "summary.json").write_bytes(canonical_bytes(result))
    print(
        json.dumps(
            {
                "status": result["status"],
                "localization": result["localization"],
                "gates": result["gates"],
                "candidate_promotion": result["candidate_promotion"],
                "result_digest": result["result_digest"],
                "summary": str(args.output_root / "summary.json"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
