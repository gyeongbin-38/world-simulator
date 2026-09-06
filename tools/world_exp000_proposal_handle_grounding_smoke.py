#!/usr/bin/env python3
"""Validate or execute the preregistered EXP-000 proposal-handle grounding smoke.

The smoke is deliberately payload-only.  It reconstructs three exact source
contexts from the sealed LIVE EXP-000 R1 trajectory, verifies those contexts
against their original CAS evidence, and then (execute mode only) runs the
already-selected ACCEPT/REJECT payload stage with context-local proposal
handles.  It never reruns the action selector and never commits simulation
state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))
sys.path.insert(0, str(REPOSITORY_ROOT))

from alifelm.context import (  # noqa: E402
    CognitionGateway,
    ContextCognitionPipeline,
    serialize_context_pack,
)
from alifelm.domain import AgentId, Duration, IntentBatch, RunId, StateVersion, Tick  # noqa: E402
from alifelm.kernel import EqualOpportunityScheduler, LawValidator, SimulationRun  # noqa: E402
from alifelm.model.evidence import cognition_evidence_bytes  # noqa: E402
from alifelm.model.peft_runtime import PeftTransformersLoader  # noqa: E402
from alifelm.model.proposal_handle_grounding import (  # noqa: E402
    C10ProposalHandlePayloadProvider,
    proposal_handle_map,
    render_with_proposal_handles,
)
from alifelm.model.treatments import i3_forced_branch_treatment  # noqa: E402
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
from alifelm.persistence.serialization import snapshot_from_dict  # noqa: E402
from tools.world_p2_phase_decoupled_behavioral_admission import (  # noqa: E402
    GENERATION_SEED,
    GENERATION_SEED_ID,
    PIP_FREEZE_SHA256,
    RUNTIME_PACKAGE_COUNT,
    _policy,
    _profile,
    _runtime_freeze_sha256,
)


STUDY_ID = "WORLD_EXP000_PROPOSAL_HANDLE_GROUNDING_SMOKE_V1"
SCHEMA_VERSION = "1.0.0"
PREREG_COMMIT = "8f77bbefd70bcdb54c7fb8d36542166375057281"
SOURCE_RUN_ID = "WORLD_EXP000_LIVE_PILOT_V1_R1"
SOURCE_RESULT_DIGEST = "b82267d7769cbc4dc56aaa3c5f82e5e66b1b669ef407b4c58d1a994b4ae29f00"
SOURCE_MANIFEST_SHA256 = "8c239e0c3550ec435ccd8ef2a718845a88d623d43cdcb7151d0b11825768e4e2"
SOURCE_SEAL_SUMS_SHA256 = "6abbbc19b44cbd0111927e5052098795f5e83ee74de9acca506a315457dbbbfa"
SOURCE_ARCHIVE_SHA256 = "b9d6e31df6e01e1ddabd943b40601255c7d80361b3eb5b3c217f25f5cc5b36e3"

TARGET_CASES: tuple[tuple[int, str, str], ...] = (
    (2, "EXP000_FOUNDER_A", "ACCEPT"),
    (8, "EXP000_FOUNDER_A", "ACCEPT"),
    (14, "EXP000_FOUNDER_C", "REJECT"),
)


class GroundingSmokeError(RuntimeError):
    """Fail-closed source-trajectory grounding smoke error."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--base-model-dir", required=True, type=Path)
    parser.add_argument("--adapter-path", required=True, type=Path)
    parser.add_argument("--source-seal-root", required=True, type=Path)
    parser.add_argument("--source-archive", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--expected-git-commit", required=True)
    return parser


def _sha256_file(path: Path) -> str:
    if not path.is_file():
        raise GroundingSmokeError(f"required file is missing: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
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


def _git_clean() -> bool:
    return not subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _verify_source_seal(source_seal_root: Path, source_archive: Path) -> dict[str, Any]:
    sums_path = source_seal_root / "SHA256SUMS"
    if _sha256_file(sums_path) != SOURCE_SEAL_SUMS_SHA256:
        raise GroundingSmokeError("source seal SHA256SUMS identity drift")
    if _sha256_file(source_archive) != SOURCE_ARCHIVE_SHA256:
        raise GroundingSmokeError("source LIVE pilot canonical archive identity drift")

    rows = []
    for raw in sums_path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            digest, relative = raw.split("  ", 1)
        except ValueError as error:
            raise GroundingSmokeError("source SHA256SUMS is malformed") from error
        target = source_seal_root / relative
        if _sha256_file(target) != digest:
            raise GroundingSmokeError(f"source sealed evidence hash drift: {relative}")
        rows.append(relative)

    manifest = source_seal_root / "evidence" / "manifest.json"
    if _sha256_file(manifest) != SOURCE_MANIFEST_SHA256:
        raise GroundingSmokeError("source LIVE pilot manifest SHA-256 drift")
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GroundingSmokeError("source LIVE pilot manifest is invalid JSON") from error
    if (
        payload.get("status") != "LIVE_PILOT_COMPLETE"
        or payload.get("result_digest") != SOURCE_RESULT_DIGEST
        or payload.get("gates") != {"G0": True, "G1": True, "G2": True, "G3": True}
    ):
        raise GroundingSmokeError("source LIVE pilot semantic identity drift")
    return {
        "verified_file_count": len(rows),
        "manifest_sha256": SOURCE_MANIFEST_SHA256,
        "seal_sums_sha256": SOURCE_SEAL_SUMS_SHA256,
        "archive_sha256": SOURCE_ARCHIVE_SHA256,
        "result_digest": SOURCE_RESULT_DIGEST,
    }


def _cas_bytes(evidence_root: Path, reference: dict[str, str]) -> bytes:
    digest = reference["digest"]
    path = evidence_root / "cas" / digest[:2] / digest
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise GroundingSmokeError("source CAS artifact digest mismatch")
    return data


def _snapshot_rows_from_copy(evidence_root: Path) -> dict[int, Any]:
    """Read source snapshots from a temporary SQLite copy, never the sealed DB."""

    with tempfile.TemporaryDirectory(prefix="exp000-grounding-source-db-") as tmp:
        temp = Path(tmp)
        for name in ("run.sqlite", "run.sqlite-wal", "run.sqlite-shm"):
            source = evidence_root / name
            if source.exists():
                shutil.copy2(source, temp / name)
        db = temp / "run.sqlite"
        if not db.is_file():
            raise GroundingSmokeError("source sealed run.sqlite is missing")
        connection = sqlite3.connect(str(db))
        connection.row_factory = sqlite3.Row
        try:
            result = {}
            for tick, _, _ in TARGET_CASES:
                row = connection.execute(
                    "SELECT state_hash, snapshot_json FROM snapshots "
                    "WHERE run_id = ? AND state_version = ?",
                    (SOURCE_RUN_ID, tick),
                ).fetchone()
                if row is None:
                    raise GroundingSmokeError(f"source snapshot is missing at state version {tick}")
                snapshot = snapshot_from_dict(json.loads(row["snapshot_json"]))
                if (
                    snapshot.run_id != RunId(SOURCE_RUN_ID)
                    or snapshot.state_version != StateVersion(tick)
                    or snapshot.tick != Tick(tick)
                    or snapshot.state_hash() != row["state_hash"]
                ):
                    raise GroundingSmokeError("source snapshot durable identity mismatch")
                result[tick] = snapshot
            return result
        finally:
            connection.close()


def _compile_source_case(
    evidence_root: Path,
    snapshot,
    *,
    tick: int,
    actor: str,
    action: str,
    profile,
    policy,
):
    tick_path = evidence_root / "ticks" / f"tick_{tick:04d}.json"
    tick_record = json.loads(tick_path.read_text(encoding="utf-8"))
    if (
        tick_record.get("tick") != tick
        or tick_record.get("state_version_before") != tick
        or tick_record.get("state_hash_before") != snapshot.state_hash()
    ):
        raise GroundingSmokeError("source tick record does not match durable source snapshot")

    cognition = next(
        (item for item in tick_record["cognition"] if item["agent_id"] == actor),
        None,
    )
    if cognition is None:
        raise GroundingSmokeError("source cognition record is missing target actor")
    if (
        cognition.get("selected_action") != action
        or cognition.get("law_admitted") is not False
        or cognition.get("evidence_ref") is None
    ):
        raise GroundingSmokeError("source target cognition semantic identity drift")

    opportunity = next(
        (
            item
            for item in EqualOpportunityScheduler().enumerate(snapshot)
            if item.agent_id == AgentId(actor)
        ),
        None,
    )
    if opportunity is None:
        raise GroundingSmokeError("source target opportunity cannot be reconstructed")
    if opportunity.opportunity_id.value != cognition["opportunity_id"]:
        raise GroundingSmokeError("reconstructed source opportunity identity drift")

    pipeline = ContextCognitionPipeline(
        build_context_policy(),
        model_profile_id=profile.profile_id,
        generation_policy_id=policy.policy_id,
        generation_seed_id=GENERATION_SEED_ID,
        artifact_store=None,
    )
    compiled = pipeline.compile_all((opportunity,))[0]

    final_evidence = json.loads(
        _cas_bytes(evidence_root, cognition["evidence_ref"]).decode("utf-8")
    )
    source_context = _cas_bytes(evidence_root, final_evidence["context_pack_ref"])
    current_context = serialize_context_pack(compiled.context_pack)
    if source_context != current_context:
        raise GroundingSmokeError("recompiled ContextPack differs from frozen source evidence")

    source_rendered = _cas_bytes(evidence_root, final_evidence["rendered_input_ref"])
    expected_rendered = i3_forced_branch_treatment(action).render(compiled.rendered_input)
    if source_rendered != expected_rendered:
        raise GroundingSmokeError("recompiled baseline payload input differs from frozen source evidence")

    handled_rendered, handles = render_with_proposal_handles(compiled)
    if not handles.canonical_to_handle:
        raise GroundingSmokeError("target source context unexpectedly has no proposal handles")
    for canonical, handle in handles.canonical_to_handle:
        text = handled_rendered.decode("utf-8")
        if canonical in text or handle not in text:
            raise GroundingSmokeError("proposal handle rendering did not replace canonical reference exactly")

    return compiled, cognition, final_evidence, handles


def _prepare_source_cases(source_seal_root: Path, *, profile, policy):
    evidence_root = source_seal_root / "evidence"
    snapshots = _snapshot_rows_from_copy(evidence_root)
    prepared = []
    for tick, actor, action in TARGET_CASES:
        compiled, cognition, evidence, handles = _compile_source_case(
            evidence_root,
            snapshots[tick],
            tick=tick,
            actor=actor,
            action=action,
            profile=profile,
            policy=policy,
        )
        prepared.append(
            {
                "tick": tick,
                "actor": actor,
                "action": action,
                "snapshot": snapshots[tick],
                "compiled": compiled,
                "source_cognition": cognition,
                "source_evidence": evidence,
                "handles": handles,
            }
        )
    return tuple(prepared)


def static_preflight(args) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    head = _git_head()
    if head != args.expected_git_commit:
        raise GroundingSmokeError("grounding smoke repository commit mismatch")
    if not _git_clean():
        raise GroundingSmokeError("grounding smoke requires a clean worktree")
    if args.output_root.exists():
        raise GroundingSmokeError("grounding smoke output root already exists")

    source = _verify_source_seal(args.source_seal_root, args.source_archive)
    freeze_sha, package_count = _runtime_freeze_sha256()
    if freeze_sha != PIP_FREEZE_SHA256 or package_count != RUNTIME_PACKAGE_COUNT:
        raise GroundingSmokeError("canonical runtime freeze drift")

    deployment = verify_static_deployment(
        DeploymentPaths(
            base_model_dir=args.base_model_dir,
            adapter_path=args.adapter_path,
            output_root=args.output_root / "_static_identity_only",
        ),
        expected_git_commit=args.expected_git_commit,
        repository_root=REPOSITORY_ROOT,
    )
    profile = _profile(args.base_model_dir)
    policy = _policy()
    cases = _prepare_source_cases(args.source_seal_root, profile=profile, policy=policy)

    return {
        "status": "STATIC_PREFLIGHT_OK",
        "study_id": STUDY_ID,
        "schema_version": SCHEMA_VERSION,
        "git_commit": head,
        "prereg_commit": PREREG_COMMIT,
        "source": source,
        "deployment": deployment,
        "runtime_pip_freeze_sha256": freeze_sha,
        "runtime_package_count": package_count,
        "targets": [
            {
                "tick": item["tick"],
                "actor": item["actor"],
                "action": item["action"],
                "opportunity_id": item["compiled"].opportunity.opportunity_id.value,
                "snapshot_hash": item["snapshot"].state_hash(),
                "handle_count": len(item["handles"].handles),
                "handles": list(item["handles"].canonical_to_handle),
            }
            for item in cases
        ],
        "action_selector_rerun": False,
        "model_loaded": False,
        "generation": False,
        "simulation_state_commit": False,
        "weight_updates": 0,
        "worktree_clean": True,
    }, cases


def _candidate_dict(candidate) -> dict[str, Any] | None:
    if candidate is None:
        return None
    return {"action_label": candidate.action_label, "payload": candidate.payload_dict()}


def _artifact_ref_dict(reference) -> dict[str, str] | None:
    if reference is None:
        return None
    return {"artifact_id": reference.artifact_id.value, "digest": reference.digest}


def _write_json_once(path: Path, value: Any) -> None:
    if path.exists():
        raise GroundingSmokeError(f"refusing to overwrite grounding smoke evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(canonical_bytes(value) + b"\n")
        stream.flush()
        import os

        os.fsync(stream.fileno())


def execute(args, static: dict[str, Any], cases: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    args.output_root.mkdir(parents=True, exist_ok=False)
    _write_json_once(
        args.output_root / "run_plan.json",
        {
            "study_id": STUDY_ID,
            "git_commit": _git_head(),
            "prereg_commit": PREREG_COMMIT,
            "static_preflight": static,
        },
    )

    environment = ensure_execute_environment()
    profile = _profile(args.base_model_dir)
    policy = _policy()
    store = FileSystemArtifactStore(args.output_root / "cas")
    runtime = PeftTransformersLoader(
        base_model_dir=args.base_model_dir,
        adapter_path=args.adapter_path,
    )(profile)
    provider = C10ProposalHandlePayloadProvider(
        runtime,
        profile=profile,
        generation_policy=policy,
        artifact_store=store,
        generation_seed=GENERATION_SEED,
    )
    gateway = CognitionGateway()

    records = []
    for item in cases:
        compiled = item["compiled"]
        snapshot = item["snapshot"]
        action = item["action"]
        before_hash = snapshot.state_hash()

        attempt = provider.generate_for_action(compiled, action)
        grounding = provider.grounding_for(compiled.opportunity.opportunity_id)
        if grounding.mode != "PROPOSAL_HANDLE_VISIBLE_REFERENCE_DOMAIN":
            raise GroundingSmokeError("target case did not enter proposal-handle mode")
        if grounding.raw_handle_candidate is None or grounding.mapped_candidate is None:
            raise GroundingSmokeError("proposal-handle payload did not produce a mapped candidate")
        raw_payload = grounding.raw_handle_candidate.payload_dict()
        mapped_payload = grounding.mapped_candidate.payload_dict()
        raw_handle = raw_payload.get("proposal_id")
        mapped_id = mapped_payload.get("proposal_id")
        if raw_handle not in grounding.handle_map.handles:
            raise GroundingSmokeError("generated proposal handle is outside frozen visible domain")
        if mapped_id not in grounding.handle_map.canonical_ids:
            raise GroundingSmokeError("resolved proposal id is outside frozen visible domain")
        if attempt.candidate != grounding.mapped_candidate:
            raise GroundingSmokeError("Gateway candidate is not the canonical mapped candidate")

        intent = gateway.bind(attempt.candidate, compiled.opportunity)
        finalized = attempt.finalize(intent, None)
        if finalized.evidence_ref is None or not store.resolve(finalized.evidence_ref):
            raise GroundingSmokeError("final mapped cognition evidence is missing")

        diagnostic_run = SimulationRun(
            run_id=snapshot.run_id,
            lifespan_ticks=Duration(20),
            maturity_delay_ticks=Duration(0),
            refractory_interval_ticks=Duration(0),
            population_capacity=6,
            horizon=Tick(20),
            _snapshot=snapshot,
        )
        validated = LawValidator().validate(
            IntentBatch(tick=snapshot.tick, intents=(intent,)),
            snapshot,
            diagnostic_run,
        )
        trace = provider.trace_for(compiled.opportunity.opportunity_id)
        if snapshot.state_hash() != before_hash:
            raise GroundingSmokeError("grounding smoke mutated source snapshot")

        record = {
            "tick": item["tick"],
            "actor": item["actor"],
            "frozen_action": action,
            "opportunity_id": compiled.opportunity.opportunity_id.value,
            "source_snapshot_hash": before_hash,
            "handle_map": [
                {"canonical_proposal_id": canonical, "handle": handle}
                for canonical, handle in grounding.handle_map.canonical_to_handle
            ],
            "raw_handle_candidate": _candidate_dict(grounding.raw_handle_candidate),
            "mapped_canonical_candidate": _candidate_dict(grounding.mapped_candidate),
            "gateway_intent": {
                "kind": intent.kind.value,
                "proposal_id": getattr(intent.payload, "proposal_id").value,
            },
            "law_validator_admitted_descriptive": len(validated) == 1,
            "evidence_ref": _artifact_ref_dict(finalized.evidence_ref),
            "phase_trace": {
                "prefill_adapter": trace.prefill_adapter,
                "selector_adapter": trace.selector_adapter,
                "phase_boundary_token_aligned": trace.phase_boundary_token_aligned,
                "world_prefill_forward_count": trace.world_prefill_forward_count,
                "selector_prefix_forward_count": trace.selector_prefix_forward_count,
                "selector_continuation_forward_count": trace.selector_continuation_forward_count,
                "world_context_recomputed_after_switch": trace.world_context_recomputed_after_switch,
            },
            "snapshot_unchanged": snapshot.state_hash() == before_hash,
        }
        _write_json_once(
            args.output_root / "cases" / f"tick_{item['tick']:04d}_{item['actor']}.json",
            record,
        )
        records.append(record)
        print(
            "GROUNDING_SMOKE_CASE "
            f"tick={item['tick']} actor={item['actor']} action={action} "
            f"handle={raw_handle} law_admitted={len(validated) == 1}",
            flush=True,
        )

    gates = {
        "G0": static["status"] == "STATIC_PREFLIGHT_OK",
        "G1_source_context_identity": len(cases) == len(TARGET_CASES),
        "G2_handle_mapping": all(
            record["raw_handle_candidate"] is not None
            and record["mapped_canonical_candidate"] is not None
            for record in records
        ),
        "G3_phase_integrity": all(
            record["phase_trace"]["prefill_adapter"] is True
            and record["phase_trace"]["selector_adapter"] is False
            and record["phase_trace"]["phase_boundary_token_aligned"] is True
            and record["phase_trace"]["world_context_recomputed_after_switch"] is False
            for record in records
        ),
        "G4_snapshot_unchanged": all(record["snapshot_unchanged"] for record in records),
    }
    result = {
        "status": "GROUNDING_SMOKE_PASS" if all(gates.values()) else "GROUNDING_SMOKE_INTEGRITY_FAIL",
        "study_id": STUDY_ID,
        "schema_version": SCHEMA_VERSION,
        "git_commit": _git_head(),
        "prereg_commit": PREREG_COMMIT,
        "environment": environment,
        "static_preflight": static,
        "gates": gates,
        "cases": records,
        "law_validator_admitted_descriptive_count": sum(
            bool(record["law_validator_admitted_descriptive"]) for record in records
        ),
        "action_selector_rerun": False,
        "simulation_state_commits": 0,
        "weight_updates": 0,
        "retries": 0,
        "fallbacks": 0,
        "repairs": 0,
    }
    result["result_digest"] = canonical_digest(result)
    _write_json_once(args.output_root / "manifest.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        static, cases = static_preflight(args)
        if args.validate_only:
            print(json.dumps(static, ensure_ascii=False, sort_keys=True))
            return 0
        result = execute(args, static, cases)
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "gates": result["gates"],
                    "law_validator_admitted_descriptive_count": result[
                        "law_validator_admitted_descriptive_count"
                    ],
                    "result_digest": result["result_digest"],
                    "manifest": str(args.output_root / "manifest.json"),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0 if result["status"] == "GROUNDING_SMOKE_PASS" else 2
    except (
        GroundingSmokeError,
        SmokePreflightError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        sqlite3.Error,
        subprocess.CalledProcessError,
    ) as error:
        print(
            json.dumps(
                {"status": "BLOCKED", "error_type": type(error).__name__, "error": str(error)},
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
