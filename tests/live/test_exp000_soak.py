"""Bounded soak tests for the durable EXP-000 live path.

These exercise the same invariants as the full soak harness in
``tools/world_exp000_soak.py`` at a reduced horizon: restart after every
committed boundary, crash injection at every commit-path fault point,
replay reconstruction, and no re-cognition of committed ticks.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import world_exp000_soak as soak


HORIZON = 8
FAULT_TICK = 3


def _config(run_id: str = "exp000-soak-test-run"):
    return soak.LiveExperimentConfig(
        run_id=run_id,
        founders=("T0", "T1", "T2"),
        lifespan_ticks=7,
        maturity_delay_ticks=0,
        refractory_interval_ticks=2,
        population_capacity=8,
        horizon_ticks=HORIZON,
    )


@pytest.fixture(scope="module")
def baseline(tmp_path_factory) -> dict:
    root = tmp_path_factory.mktemp("soak-baseline")
    return soak._trajectory(root / "baseline", _config(), horizon=HORIZON)


@pytest.fixture(scope="module")
def restart(tmp_path_factory) -> dict:
    root = tmp_path_factory.mktemp("soak-restart")
    return soak._trajectory(
        root / "restart", _config(), restart_every=1, horizon=HORIZON
    )


def test_baseline_completes_and_replays(baseline: dict) -> None:
    assert baseline["final_status"] == "COMPLETED"
    assert baseline["final_tick"] == HORIZON
    assert baseline["durable_commit_count"] == HORIZON
    assert baseline["replay_verified_commits"] == HORIZON
    assert baseline["replay_final_hash"] == baseline["final_state_hash"]
    # The scripted cohort must produce non-trivial dynamics.
    event_types = {et for item in baseline["series"] for et in item["event_types"]}
    assert "AgentBorn" in event_types
    assert "AgentDied" in event_types
    assert "MessageCommitted" in event_types


def test_restart_every_tick_preserves_trajectory(baseline: dict, restart: dict) -> None:
    comparison = soak._compare_series(baseline["series"], restart["series"], "restart")
    assert comparison["lengths_match"]
    assert comparison["identical"], comparison["hash_mismatches"]
    assert restart["replay_final_hash"] == baseline["replay_final_hash"]
    assert all(item["hash_match"] for item in restart["resumes"])
    assert len(restart["resumes"]) == HORIZON


def test_no_recall_of_committed_ticks(baseline: dict, restart: dict) -> None:
    assert soak._call_audit(baseline["calls"])["no_recall"]
    assert soak._call_audit(restart["calls"])["no_recall"]


@pytest.mark.parametrize("mode", ("inprocess", "restart"))
@pytest.mark.parametrize("point", soak.FAULT_POINTS)
def test_fault_recovery_preserves_trajectory(
    tmp_path: Path, baseline: dict, point: str, mode: str
) -> None:
    sub = soak._trajectory(
        tmp_path / f"{point}-{mode}",
        _config(),
        fault_point=point,
        fault_tick=FAULT_TICK,
        fault_recovery=mode,
        horizon=HORIZON,
    )
    expected_tick = FAULT_TICK if point in soak.PRE_COMMIT_POINTS else FAULT_TICK + 1
    assert sub["fault"]["durable_tick_after_fault"] == expected_tick
    assert sub["final_state_hash"] == baseline["final_state_hash"]
    comparison = soak._compare_series(baseline["series"], sub["series"], f"{point}:{mode}")
    assert comparison["identical"]
    assert sub["replay_verified_commits"] == sub["durable_commit_count"]


def test_repeated_resume_is_idempotent(tmp_path: Path, baseline: dict) -> None:
    db = tmp_path / "run.sqlite"
    cas = tmp_path / "cas"
    config = _config()
    calls: list[tuple[int, str, str]] = []
    store = soak.SQLiteReferenceStore(db, artifact_root=cas)
    try:
        controller = soak.LiveExperimentController.create(
            config,
            runtime=soak.SoakPolicyRuntime(config.run_id, calls),
            context_pipeline=soak._pipeline(store),
            store=store,
        )
        controller.run_until_stop(max_ticks=3)
        mid_hash = controller.run.state_hash()
    finally:
        store.close()
    for _ in range(2):
        store = soak.SQLiteReferenceStore(db, artifact_root=cas)
        try:
            resumed = soak.LiveExperimentController.resume(
                config.run_id,
                runtime=soak.SoakPolicyRuntime(config.run_id, calls),
                context_pipeline=soak._pipeline(store),
                store=store,
            )
            assert resumed.run.state_hash() == mid_hash
            assert int(resumed.run.snapshot.tick) == 3
        finally:
            store.close()
