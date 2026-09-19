#!/usr/bin/env python3
"""EXP-000 durability/restart/replay soak harness.

Drives the admitted LIVE EXP-000 stack (deterministic kernel, context pipeline,
SQLite durable store, CAS artifacts, replay reader) with a deterministic
hash-driven policy runtime. The soak measures infrastructure behavior only:
restart after every committed boundary, crash injection at every commit-path
fault point, full replay reconstruction, and repeated-recovery idempotency.
It introduces no new causal variable and performs no model reseeding,
fallback, repair, or action masking.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from alifelm.context import (  # noqa: E402
    ContextCognitionPipeline,
    ContextPolicy,
    DEFAULT_ACTION_PRESENTATION,
    OrderingPolicy,
    VisibleRecordCategory,
    action_presentation_digest,
)
from alifelm.domain import RunId, StateVersion  # noqa: E402
from alifelm.kernel import RunStatus  # noqa: E402
from alifelm.live import LiveExperimentConfig, LiveExperimentController  # noqa: E402
from alifelm.persistence import (  # noqa: E402
    FaultInjected,
    SQLiteReferenceStore,
)

STUDY_ID = "WORLD_EXP000_SOAK_V1"
SCHEMA_VERSION = "1.0.0"
SOAK_SEED_ID = "exp000-soak-policy-seed-v1"

FAULT_POINTS = (
    "F5_BEFORE_COMMIT",
    "F6_TRANSACTION_BEGIN",
    "F7_AFTER_STATE_WRITE",
    "F8_BEFORE_COMMIT",
    "F9_AFTER_COMMIT_BEFORE_ACK",
    "F10_BEFORE_PUBLICATION",
)
# Faults before the database commit leave the durable boundary at S_t;
# faults after it leave the durable boundary at S_(t+1) (ack lost).
PRE_COMMIT_POINTS = frozenset(FAULT_POINTS[:4])


class SoakError(RuntimeError):
    """Fail-closed soak contract error."""


class SoakPolicyRuntime:
    """Deterministic hash-driven candidate runtime.

    Decisions depend only on (run_id, tick, actor, visible state), so a
    trajectory is identical across process restarts. The shared ``calls``
    list records every invocation for the no-recall audit.
    """

    def __init__(self, run_id: str, calls: list[tuple[int, str, str]]) -> None:
        self.run_id = run_id
        self.calls = calls

    def infer(self, compiled):
        opportunity = compiled.opportunity
        tick = int(opportunity.tick)
        actor = opportunity.agent_id.value
        model_input = compiled.context_pack.model_input
        incoming = tuple(
            record
            for record in model_input.visible_protocol_state
            if record.category is VisibleRecordCategory.INCOMING_PROPOSAL
        )
        peers = tuple(entry.agent_id.value for entry in model_input.peer_directory)
        roll = int.from_bytes(
            hashlib.sha256(
                f"{SOAK_SEED_ID}|{self.run_id}|{tick}|{actor}".encode("utf-8")
            ).digest()[:8],
            "big",
        )
        if incoming:
            proposal_id = incoming[roll % len(incoming)].payload.proposal_id
            if roll % 10 < 6:
                label, payload = "CONFIRM_BILATERAL_REQUEST", {"proposal_id": proposal_id}
            else:
                label, payload = "DECLINE_BILATERAL_REQUEST", {"proposal_id": proposal_id}
        elif peers:
            target = peers[(roll // 10) % len(peers)]
            bucket = roll % 10
            if bucket < 3:
                label, payload = "DIRECT_TEXT", {
                    "target_agent_id": target,
                    "body": f"soak-{tick}-{actor}",
                }
            elif bucket < 6:
                label, payload = "OPEN_BILATERAL_REQUEST", {"target_agent_id": target}
            else:
                label, payload = "NO_DIRECTED_ACTION", {}
        else:
            label, payload = "NO_DIRECTED_ACTION", {}
        self.calls.append((tick, actor, label))
        return {"action_label": label, "payload": payload}


class _ArmOnce:
    """FaultInjector raising once at the armed point."""

    def __init__(self, point: str) -> None:
        self.point = point
        self.fired = False

    def check(self, point: str) -> None:
        if not self.fired and point == self.point:
            self.fired = True
            raise FaultInjected(f"soak fault at {point}")


def _policy() -> ContextPolicy:
    return ContextPolicy.exp000(
        max_prior_visible_records=8,
        ordering=OrderingPolicy(
            policy_version="1.0.0",
            unordered_collection_algorithm="ALIFELM_CONTEXT_ORDER_V1",
            digest_algorithm="sha256",
            ordering_seed_id="exp000-soak-order",
            ordering_seed_digest="4" * 64,
            cross_tick_order="COMMITTED_TICK_CHRONOLOGICAL",
            tie_breaker="FULL_STABLE_ITEM_KEY",
        ),
        action_presentation_digest=action_presentation_digest(DEFAULT_ACTION_PRESENTATION),
    )


def _pipeline(store: SQLiteReferenceStore) -> ContextCognitionPipeline:
    return ContextCognitionPipeline(
        _policy(),
        model_profile_id="exp000-soak-policy-runtime",
        generation_policy_id="exp000-soak-policy",
        generation_seed_id=SOAK_SEED_ID,
        artifact_store=store.artifact_store,
    )


def soak_config(run_id: str, horizon_ticks: int = 48) -> LiveExperimentConfig:
    return LiveExperimentConfig(
        run_id=run_id,
        founders=("SOAK_F0", "SOAK_F1", "SOAK_F2", "SOAK_F3"),
        lifespan_ticks=30,
        maturity_delay_ticks=0,
        refractory_interval_ticks=4,
        population_capacity=18,
        horizon_ticks=horizon_ticks,
    )


def _event_types(result) -> list[str]:
    return [event.event_type for event in result.commit_result.events]


def _run_one_tick(controller: LiveExperimentController, fault_point: str | None = None):
    if controller.run.status is not RunStatus.RUNNING:
        raise SoakError(f"run is not RUNNING: {controller.run.status.value}")
    injector = _ArmOnce(fault_point) if fault_point is not None else None
    result = controller.kernel.run_tick(fault_injector=injector)
    if injector is not None and not injector.fired:
        raise SoakError(f"armed fault point never reached: {fault_point}")
    if not result.commit_result.committed:
        raise SoakError(f"tick did not commit: {result.commit_result.error}")
    return result


def _durable_series(store: SQLiteReferenceStore, run_id: str) -> list[dict[str, Any]]:
    """Authoritative boundary series rebuilt from the durable commit chain."""

    rid = RunId(run_id)
    initial = store.run_store.snapshot_at(rid, StateVersion(0))
    series = [
        {
            "tick": int(initial.tick),
            "state_version": int(initial.state_version),
            "state_hash": initial.state_hash(),
            "event_types": [],
            "population": len(initial.agents),
        }
    ]
    for record in store.commit_store.iter_commits(rid):
        series.append(
            {
                "tick": int(record.snapshot.tick),
                "state_version": int(record.state_version_after),
                "state_hash": record.resulting_state_hash,
                "event_types": [event.event_type for event in record.events],
                "population": len(record.snapshot.agents),
            }
        )
    return series


def _trajectory(
    root: Path,
    config: LiveExperimentConfig,
    *,
    restart_every: int | None = None,
    fault_point: str | None = None,
    fault_tick: int | None = None,
    fault_recovery: str = "inprocess",
    horizon: int | None = None,
) -> dict[str, Any]:
    """Execute one soak trajectory; return durable series and audits."""

    calls: list[tuple[int, str, str]] = []
    resumes: list[dict[str, Any]] = []
    fault_record: dict[str, Any] | None = None
    db_path = root / "world.sqlite"
    cas_root = root / "cas"
    limit = horizon if horizon is not None else (config.horizon_ticks or 0)
    run_id = config.run_id

    store = SQLiteReferenceStore(db_path, artifact_root=cas_root)
    controller = LiveExperimentController.create(
        config,
        runtime=SoakPolicyRuntime(run_id, calls),
        context_pipeline=_pipeline(store),
        store=store,
    )
    boundary_count = 0
    last_committed_hash = controller.run.state_hash()
    try:
        while controller.run.status is RunStatus.RUNNING and boundary_count < limit:
            current_tick = int(controller.run.snapshot.tick)
            armed = fault_point if fault_tick == current_tick else None
            try:
                result = _run_one_tick(controller, fault_point=armed)
            except FaultInjected:
                fault_record = _probe_durable(
                    db_path, cas_root, run_id, point=armed, mode=fault_recovery
                )
                if fault_recovery == "restart":
                    store.close()
                    store = SQLiteReferenceStore(db_path, artifact_root=cas_root)
                    controller = LiveExperimentController.resume(
                        run_id,
                        runtime=SoakPolicyRuntime(run_id, calls),
                        context_pipeline=_pipeline(store),
                        store=store,
                    )
                    resumes.append(
                        {
                            "after_fault": True,
                            "loaded_tick": int(controller.run.snapshot.tick),
                            "loaded_hash": controller.run.state_hash(),
                        }
                    )
                # inprocess: same controller; the durable committer resolves
                # either a fresh commit (rolled back) or the existing one.
                result = _run_one_tick(controller)
            boundary_count += 1
            last_committed_hash = result.commit_result.snapshot.state_hash()
            if restart_every is not None and boundary_count % restart_every == 0:
                expected = last_committed_hash
                store.close()
                store = SQLiteReferenceStore(db_path, artifact_root=cas_root)
                controller = LiveExperimentController.resume(
                    run_id,
                    runtime=SoakPolicyRuntime(run_id, calls),
                    context_pipeline=_pipeline(store),
                    store=store,
                )
                loaded = controller.run.state_hash()
                resumes.append(
                    {
                        "after_fault": False,
                        "loaded_tick": int(controller.run.snapshot.tick),
                        "expected_hash": expected,
                        "loaded_hash": loaded,
                        "hash_match": loaded == expected,
                    }
                )
        final_status = controller.run.status.value
        final_hash = controller.run.state_hash()
        final_tick = int(controller.run.snapshot.tick)
        series = _durable_series(store, run_id)
    finally:
        store.close()

    # Replay verification over the whole durable history.
    replay_store = SQLiteReferenceStore(db_path, artifact_root=cas_root)
    try:
        replay = replay_store.replay(RunId(run_id))
        commit_count = len(replay_store.commit_store.iter_commits(RunId(run_id)))
    finally:
        replay_store.close()

    return {
        "series": series,
        "resumes": resumes,
        "fault": fault_record,
        "calls": calls,
        "final_status": final_status,
        "final_state_hash": final_hash,
        "final_tick": final_tick,
        "replay_verified_commits": len(replay.verified_commit_ids),
        "replay_final_hash": replay.state_hash,
        "durable_commit_count": commit_count,
    }


def _probe_durable(
    db_path: Path, cas_root: Path, run_id: str, *, point: str | None, mode: str
) -> dict[str, Any]:
    """Inspect the durable boundary immediately after a fault."""

    probe = SQLiteReferenceStore(db_path, artifact_root=cas_root)
    try:
        durable = probe.load_run(RunId(run_id))
        return {
            "point": point,
            "mode": mode,
            "durable_tick_after_fault": int(durable.snapshot.tick),
            "durable_hash_after_fault": durable.state_hash(),
            "commit_count_after_fault": len(probe.commit_store.iter_commits(RunId(run_id))),
        }
    finally:
        probe.close()


def _compare_series(
    baseline: list[dict[str, Any]], other: list[dict[str, Any]], label: str
) -> dict[str, Any]:
    mismatches = [
        {"index": index, "baseline": a["state_hash"], label: b["state_hash"]}
        for index, (a, b) in enumerate(zip(baseline, other))
        if a["tick"] != b["tick"] or a["state_hash"] != b["state_hash"]
    ]
    event_mismatch = any(
        a["event_types"] != b["event_types"] for a, b in zip(baseline, other)
    )
    return {
        "label": label,
        "boundaries_compared": min(len(baseline), len(other)),
        "lengths_match": len(baseline) == len(other),
        "hash_mismatches": mismatches,
        "event_mismatch": event_mismatch,
        "identical": not mismatches
        and not event_mismatch
        and len(baseline) == len(other),
    }


def _call_audit(calls: list[tuple[int, str, str]]) -> dict[str, Any]:
    seen: dict[tuple[int, str], int] = {}
    for tick, actor, _label in calls:
        key = (tick, actor)
        seen[key] = seen.get(key, 0) + 1
    duplicates = [
        {"tick": tick, "actor": actor, "count": count}
        for (tick, actor), count in sorted(seen.items())
        if count > 1
    ]
    return {
        "total_inferences": len(calls),
        "unique_tick_actor": len(seen),
        "duplicate_cognition_calls": duplicates,
        "no_recall": not duplicates,
    }


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _write_json_once(path: Path, value: Any) -> None:
    if path.exists():
        raise SoakError(f"refusing to overwrite sealed evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(_canonical_bytes(value) + b"\n")
        stream.flush()
        import os

        os.fsync(stream.fileno())


def execute(output_root: Path, *, horizon: int = 48, fault_tick: int = 12) -> dict[str, Any]:
    if output_root.exists():
        raise SoakError(f"soak evidence root already exists: {output_root}")
    config = soak_config(STUDY_ID + "_R1", horizon_ticks=horizon)

    baseline = _trajectory(output_root / "baseline", config, horizon=horizon)
    restart = _trajectory(
        output_root / "restart", config, restart_every=1, horizon=horizon
    )
    comparison = _compare_series(baseline["series"], restart["series"], "restart")

    fault_results = []
    for mode in ("inprocess", "restart"):
        for point in FAULT_POINTS:
            sub = _trajectory(
                output_root / f"fault-{point.lower().replace('_', '-')}-{mode}",
                config,
                fault_point=point,
                fault_tick=fault_tick,
                fault_recovery=mode,
                horizon=horizon,
            )
            expected_tick = fault_tick if point in PRE_COMMIT_POINTS else fault_tick + 1
            fault_results.append(
                {
                    "point": point,
                    "mode": mode,
                    "durable_tick_after_fault": sub["fault"]["durable_tick_after_fault"],
                    "expected_durable_tick": expected_tick,
                    "boundary_correct": sub["fault"]["durable_tick_after_fault"]
                    == expected_tick,
                    "commit_count_after_fault": sub["fault"]["commit_count_after_fault"],
                    "final_hash_matches_baseline": sub["final_state_hash"]
                    == baseline["final_state_hash"],
                    "series_identical": _compare_series(
                        baseline["series"], sub["series"], f"{point}:{mode}"
                    )["identical"],
                    "final_status": sub["final_status"],
                    "replay_verified_commits": sub["replay_verified_commits"],
                }
            )

    audits = {
        "baseline_calls": _call_audit(baseline["calls"]),
        "restart_calls": _call_audit(restart["calls"]),
    }
    # Post-fault re-cognition is permitted on the pre-raw-output retry path;
    # the no-recall audit therefore applies to the uninterrupted baseline and
    # the every-tick restart sweep, not to the fault sweep.
    event_tally: dict[str, int] = {}
    for item in baseline["series"]:
        for event_type in item["event_types"]:
            event_tally[event_type] = event_tally.get(event_type, 0) + 1
    # COMPLETED and CENSORED are both explicit terminal outcomes under
    # SEQ-250; either one is a legal soak endpoint.
    checks = {
        "baseline_terminal": baseline["final_status"] in {"COMPLETED", "CENSORED"},
        "baseline_replay_all_commits": baseline["replay_verified_commits"]
        == baseline["durable_commit_count"]
        and baseline["durable_commit_count"] > 0,
        "baseline_replay_final_hash": baseline["replay_final_hash"]
        == baseline["final_state_hash"],
        "restart_trajectory_identical": comparison["identical"],
        "restart_replay_final_hash": restart["replay_final_hash"]
        == baseline["replay_final_hash"],
        "restart_resume_hashes_match": all(
            item["hash_match"] for item in restart["resumes"]
        ),
        "fault_boundaries_correct": all(item["boundary_correct"] for item in fault_results),
        "fault_series_identical": all(item["series_identical"] for item in fault_results),
        "no_recall_baseline": audits["baseline_calls"]["no_recall"],
        "no_recall_restart": audits["restart_calls"]["no_recall"],
    }
    result = {
        "status": "SOAK_COMPLETE" if all(checks.values()) else "SOAK_INTEGRITY_FAIL",
        "study_id": STUDY_ID,
        "schema_version": SCHEMA_VERSION,
        "run_id": config.run_id,
        "config": {
            "founders": list(config.founders),
            "horizon_ticks": config.horizon_ticks,
            "lifespan_ticks": config.lifespan_ticks,
            "maturity_delay_ticks": config.maturity_delay_ticks,
            "refractory_interval_ticks": config.refractory_interval_ticks,
            "population_capacity": config.population_capacity,
        },
        "fault_tick": fault_tick,
        "checks": checks,
        "trajectory_comparison": comparison,
        "fault_sweep": fault_results,
        "call_audits": audits,
        "baseline": {
            "final_tick": baseline["final_tick"],
            "final_status": baseline["final_status"],
            "final_state_hash": baseline["final_state_hash"],
            "durable_commit_count": baseline["durable_commit_count"],
            "replay_verified_commits": baseline["replay_verified_commits"],
            "event_tally": event_tally,
        },
        "restart": {
            "final_state_hash": restart["final_state_hash"],
            "durable_commit_count": restart["durable_commit_count"],
            "resumes": len(restart["resumes"]),
        },
        "boundary_hashes": [
            {key: item[key] for key in ("tick", "state_version", "state_hash", "event_types")}
            for item in baseline["series"]
        ],
    }
    result["result_digest"] = _digest(result)
    _write_json_once(output_root / "soak-manifest.json", result)
    _write_json_once(
        output_root / "boundary-hashes.json", {"records": result["boundary_hashes"]}
    )
    return result


def audit(output_root: Path) -> dict[str, Any]:
    manifest_path = output_root / "soak-manifest.json"
    if not manifest_path.is_file():
        raise SoakError("soak manifest missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = _digest({key: value for key, value in manifest.items() if key != "result_digest"})
    db = output_root / "baseline" / "world.sqlite"
    cas = output_root / "baseline" / "cas"
    store = SQLiteReferenceStore(db, artifact_root=cas)
    try:
        replay = store.replay(RunId(manifest["run_id"]))
        commits = len(store.commit_store.iter_commits(RunId(manifest["run_id"])))
    finally:
        store.close()
    checks = {
        "manifest_digest_matches": digest == manifest["result_digest"],
        "status_complete": manifest["status"] == "SOAK_COMPLETE",
        "replay_final_hash": replay.state_hash == manifest["baseline"]["final_state_hash"],
        "commit_count_matches": commits == manifest["baseline"]["durable_commit_count"],
        "all_checks_true": all(manifest["checks"].values()),
    }
    return {"audit": "PASS" if all(checks.values()) else "FAIL", "checks": checks}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--audit", action="store_true")
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--horizon", type=int, default=48)
    parser.add_argument("--fault-tick", type=int, default=12)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.audit:
            report = audit(args.output_root)
            print(json.dumps(report, ensure_ascii=False, sort_keys=True))
            return 0 if report["audit"] == "PASS" else 2
        result = execute(args.output_root, horizon=args.horizon, fault_tick=args.fault_tick)
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "checks": result["checks"],
                    "result_digest": result["result_digest"],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0 if result["status"] == "SOAK_COMPLETE" else 2
    except (SoakError, OSError, RuntimeError, TypeError, ValueError) as error:
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
