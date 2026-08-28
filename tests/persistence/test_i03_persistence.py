from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import textwrap
import time

import pytest

from alifelm.domain import (
    AcceptAction,
    ActionIntent,
    ActionKind,
    AgentId,
    ArtifactId,
    ArtifactRef,
    Duration,
    IntentId,
    ProposeAction,
    RunId,
    SendAction,
    StateVersion,
    Tick,
    WaitAction,
)
from alifelm.kernel import (
    CommitError,
    DeterministicKernel,
    FakeDeterministicModelRuntime,
    InMemoryCommitCoordinator,
    SimulationRun,
)
from alifelm.persistence import (
    ArtifactIntegrityError,
    ArtifactMissingError,
    FileSystemArtifactStore,
    FaultInjected,
    PersistenceError,
    SQLiteDurableRunStore,
    SQLiteReferenceStore,
    UnsupportedSchemaError,
)
from alifelm.persistence.migrations import configure_connection, migrate


class RaiseAt:
    def __init__(self, point: str) -> None:
        self.point = point

    def check(self, point: str) -> None:
        if point == self.point:
            raise FaultInjected(point)


def make_run(
    *founders: str,
    lifespan: int = 10,
    maturity: int = 0,
    refractory: int = 0,
    capacity: int | None = None,
) -> SimulationRun:
    return SimulationRun.bootstrap(
        RunId("run-1"),
        lifespan_ticks=Duration(lifespan),
        maturity_delay_ticks=Duration(maturity),
        refractory_interval_ticks=Duration(refractory),
        founder_ids=tuple(AgentId(founder) for founder in founders),
        population_capacity=capacity,
    )


def intent(name: str, actor: str, tick: int, kind: ActionKind, payload) -> ActionIntent:
    return ActionIntent(
        intent_id=IntentId(name),
        actor_id=AgentId(actor),
        tick=Tick(tick),
        kind=kind,
        payload=payload,
    )


def wait(name: str, actor: str, tick: int) -> ActionIntent:
    return intent(name, actor, tick, ActionKind.WAIT, WaitAction())


def clone_run(run: SimulationRun) -> SimulationRun:
    return SimulationRun(
        run_id=run.run_id,
        lifespan_ticks=run.lifespan_ticks,
        maturity_delay_ticks=run.maturity_delay_ticks,
        refractory_interval_ticks=run.refractory_interval_ticks,
        _snapshot=run.snapshot,
        population_capacity=run.population_capacity,
        horizon=run.horizon,
    )


def staged_request(
    run: SimulationRun,
    script: dict[tuple[Tick, AgentId], ActionIntent],
    *,
    completion_order: tuple[AgentId, ...] | None = None,
):
    staged = clone_run(run)
    result = DeterministicKernel(
        staged,
        FakeDeterministicModelRuntime(script),
        committer=InMemoryCommitCoordinator(),
    ).run_tick(completion_order=completion_order)
    return result.commit_request


def durable_store(tmp_path: Path) -> SQLiteReferenceStore:
    return SQLiteReferenceStore(
        tmp_path / "run.sqlite",
        artifact_root=tmp_path / "cas",
    )


def durable_send_request(run: SimulationRun, body: str = "hello"):
    return staged_request(
        run,
        {
            (Tick(0), AgentId("A")): intent(
                "send-0", "A", 0, ActionKind.SEND, SendAction(AgentId("B"), body)
            )
        },
    )


def commit_one_send(store: SQLiteReferenceStore, run: SimulationRun, body: str = "hello"):
    request = durable_send_request(run, body)
    return request, store.commit_store.commit(run, request)


def assert_initial_boundary(store: SQLiteReferenceStore, run: SimulationRun) -> None:
    loaded = store.load_run(run.run_id)
    assert loaded.snapshot == run.snapshot
    assert loaded.state_hash() == run.state_hash()
    assert store.commit_store.iter_commits(run.run_id) == ()


@pytest.mark.parametrize(
    "point",
    [
        "F1_COGNITION_START",
        "F2_INFERENCE",
        "F3_RAW_OUTPUT_BEFORE_PARSE",
        "F4_AFTER_VALIDATION_INPUT",
    ],
)
def test_precommit_cognition_faults_leave_prior_boundary_unchanged(
    tmp_path: Path, point: str
) -> None:
    store = durable_store(tmp_path)
    try:
        run = make_run("A", "B")
        store.create_run(run)
        kernel = DeterministicKernel(
            run,
            FakeDeterministicModelRuntime(),
            committer=store.commit_store,
        )
        with pytest.raises(FaultInjected):
            kernel.run_tick(fault_injector=RaiseAt(point))
        assert_initial_boundary(store, run)
    finally:
        store.close()


def test_crash_before_commit_preserves_prior_state(tmp_path: Path) -> None:
    store = durable_store(tmp_path)
    try:
        run = make_run("A", "B")
        store.create_run(run)
        request = durable_send_request(run)
        with pytest.raises(FaultInjected):
            store.commit_store.commit(run, request, fault_injector=RaiseAt("F5_BEFORE_COMMIT"))
        assert_initial_boundary(store, run)
    finally:
        store.close()


@pytest.mark.parametrize("point", ["F6_TRANSACTION_BEGIN", "F7_AFTER_STATE_WRITE", "F8_BEFORE_COMMIT"])
def test_crash_during_transaction_has_no_partial_transition(tmp_path: Path, point: str) -> None:
    store = durable_store(tmp_path)
    try:
        run = make_run("A", "B")
        store.create_run(run)
        request = durable_send_request(run)
        with pytest.raises(FaultInjected):
            store.commit_store.commit(run, request, fault_injector=RaiseAt(point))
        assert_initial_boundary(store, run)
        assert store.run_store.connection.execute("SELECT COUNT(*) FROM commit_events").fetchone()[0] == 0
        assert store.run_store.connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 0
    finally:
        store.close()


def test_committed_state_never_lacks_required_event(tmp_path: Path) -> None:
    store = durable_store(tmp_path)
    try:
        run = make_run("A", "B")
        store.create_run(run)
        _, result = commit_one_send(store, run)
        assert result.committed
        record = store.commit_store.lookup_commit(result.commit_id)
        assert record is not None
        assert record.events
        assert store.run_store.connection.execute(
            "SELECT COUNT(*) FROM commit_events WHERE commit_id = ?", (result.commit_id,)
        ).fetchone()[0] == len(record.events)
        assert store.run_store.connection.execute(
            "SELECT COUNT(*) FROM outbox WHERE commit_id = ? AND record_type = 'DOMAIN_EVENT'",
            (result.commit_id,),
        ).fetchone()[0] == len(record.events)
    finally:
        store.close()


def test_committed_event_never_claims_uncommitted_state(tmp_path: Path) -> None:
    store = durable_store(tmp_path)
    try:
        run = make_run("A", "B")
        store.create_run(run)
        _, result = commit_one_send(store, run)
        record = store.commit_store.lookup_commit(result.commit_id)
        assert record is not None
        loaded = store.load_run(run.run_id)
        assert loaded.snapshot == record.snapshot
        assert loaded.state_hash() == record.resulting_state_hash
        assert all(event in loaded.snapshot.events for event in record.events)
    finally:
        store.close()


def test_retry_same_commit_is_idempotent(tmp_path: Path) -> None:
    store = durable_store(tmp_path)
    try:
        run = make_run("A", "B")
        store.create_run(run)
        request = durable_send_request(run)
        first = store.commit_store.commit(run, request)
        second = store.commit_store.commit(run, request)
        assert first.commit_id == second.commit_id
        assert first.snapshot == second.snapshot
        assert first.events == second.events
        assert len(store.commit_store.iter_commits(run.run_id)) == 1
        assert run.snapshot.state_version == StateVersion(1)
    finally:
        store.close()


def test_duplicate_commit_does_not_duplicate_birth(tmp_path: Path) -> None:
    store = durable_store(tmp_path)
    try:
        run = make_run("A", "B")
        store.create_run(run)
        proposal_request = staged_request(
            run,
            {(Tick(0), AgentId("A")): intent("proposal", "A", 0, ActionKind.PROPOSE, ProposeAction(AgentId("B")))},
        )
        first = store.commit_store.commit(run, proposal_request)
        assert first.committed
        proposal_id = run.snapshot.proposals[0].proposal_id
        accept_request = staged_request(
            run,
            {(Tick(1), AgentId("B")): intent("accept", "B", 1, ActionKind.ACCEPT, AcceptAction(proposal_id))},
        )
        first_birth = store.commit_store.commit(run, accept_request)
        retry = store.commit_store.commit(run, accept_request)
        assert first_birth.snapshot == retry.snapshot
        assert sum(event.event_type == "AgentBorn" for event in retry.events) == 1
        assert len([agent for agent in run.snapshot.agents if agent.birth_tick == Tick(1)]) == 1
        assert len(store.commit_store.iter_commits(run.run_id)) == 2
    finally:
        store.close()


def test_duplicate_commit_does_not_duplicate_message(tmp_path: Path) -> None:
    store = durable_store(tmp_path)
    try:
        run = make_run("A", "B")
        store.create_run(run)
        request = durable_send_request(run)
        first = store.commit_store.commit(run, request)
        retry = store.commit_store.commit(run, request)
        assert first.snapshot.messages == retry.snapshot.messages
        assert len(retry.snapshot.messages) == 1
        assert len(store.commit_store.iter_commits(run.run_id)) == 1
    finally:
        store.close()


def test_duplicate_commit_does_not_duplicate_proposal(tmp_path: Path) -> None:
    store = durable_store(tmp_path)
    try:
        run = make_run("A", "B")
        store.create_run(run)
        request = staged_request(
            run,
            {(Tick(0), AgentId("A")): intent("proposal", "A", 0, ActionKind.PROPOSE, ProposeAction(AgentId("B")))},
        )
        first = store.commit_store.commit(run, request)
        retry = store.commit_store.commit(run, request)
        assert first.snapshot.proposals == retry.snapshot.proposals
        assert len(retry.snapshot.proposals) == 1
        assert len(store.commit_store.iter_commits(run.run_id)) == 1
    finally:
        store.close()


def test_committed_artifact_ref_always_resolves(tmp_path: Path) -> None:
    store = durable_store(tmp_path)
    try:
        run = make_run("A", "B")
        store.create_run(run)
        reference = store.artifact_store.put_bytes(b"raw evidence", contract_id="raw-output")
        request = durable_send_request(run)
        result = store.commit_store.commit(run, request, artifact_refs=(reference,))
        assert result.committed
        record = store.commit_store.lookup_commit(result.commit_id)
        assert record is not None
        assert record.artifact_refs == (reference,)
        assert store.artifact_store.resolve(reference) == b"raw evidence"
    finally:
        store.close()


def test_orphan_artifact_does_not_become_canonical(tmp_path: Path) -> None:
    store = durable_store(tmp_path)
    try:
        run = make_run("A", "B")
        store.create_run(run)
        orphan = store.artifact_store.put_bytes(b"orphan")
        assert store.commit_store.iter_commits(run.run_id) == ()
        assert store.load_run(run.run_id).snapshot == run.snapshot
        assert store.artifact_store.list_orphans() == (orphan,)
    finally:
        store.close()


def test_restart_after_unknown_commit_result_detects_existing_commit(tmp_path: Path) -> None:
    db_path = tmp_path / "run.sqlite"
    cas_path = tmp_path / "cas"
    child_code = textwrap.dedent(
        f"""
        import os
        from alifelm.domain import ActionKind, AgentId, Duration, IntentId, RunId, SendAction, Tick, ActionIntent
        from alifelm.kernel import DeterministicKernel, FakeDeterministicModelRuntime, SimulationRun
        from alifelm.persistence import SQLiteReferenceStore
        class Crash:
            def check(self, point):
                if point == 'F9_AFTER_COMMIT_BEFORE_ACK':
                    os._exit(37)
        store = SQLiteReferenceStore(r'{db_path}', artifact_root=r'{cas_path}')
        run = SimulationRun.bootstrap(RunId('run-1'), lifespan_ticks=Duration(10), founder_ids=(AgentId('A'), AgentId('B')))
        store.create_run(run)
        intent = ActionIntent(IntentId('send-0'), AgentId('A'), Tick(0), ActionKind.SEND, SendAction(AgentId('B'), 'hello'))
        staged = SimulationRun.bootstrap(RunId('run-1'), lifespan_ticks=Duration(10), founder_ids=(AgentId('A'), AgentId('B')))
        staged_result = DeterministicKernel(staged, FakeDeterministicModelRuntime({{(Tick(0), AgentId('A')): intent}})).run_tick()
        store.commit_store.commit(run, staged_result.commit_request, fault_injector=Crash())
        """
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parents[2] / "src") + os.pathsep + env.get("PYTHONPATH", "")
    completed = subprocess.run(
        [sys.executable, "-c", child_code],
        cwd=Path(__file__).parents[2],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 37, completed.stderr

    store = SQLiteReferenceStore(db_path, artifact_root=cas_path)
    try:
        recovered = store.load_run(RunId("run-1"))
        assert recovered.snapshot.state_version == StateVersion(1)
        retry_request = durable_send_request(make_run("A", "B"))
        retry = store.commit_store.commit(recovered, retry_request)
        assert retry.committed
        assert retry.commit_id == store.commit_store.iter_commits(RunId("run-1"))[0].commit_id
        assert len(store.commit_store.iter_commits(RunId("run-1"))) == 1
    finally:
        store.close()


def test_replay_reconstructs_identical_state_hash(tmp_path: Path) -> None:
    store = durable_store(tmp_path)
    try:
        run = make_run("A", "B")
        store.create_run(run)
        commit_one_send(store, run)
        replayed = store.replay(run.run_id)
        assert replayed.snapshot == run.snapshot
        assert replayed.state_hash == run.state_hash()
    finally:
        store.close()


def test_replay_does_not_call_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = durable_store(tmp_path)
    try:
        run = make_run("A", "B")
        store.create_run(run)
        commit_one_send(store, run)

        monkeypatch.setattr(
            FakeDeterministicModelRuntime,
            "infer",
            lambda _self, _opportunity: (_ for _ in ()).throw(
                AssertionError("replay invoked model inference")
            ),
        )
        result = store.replay(run.run_id)
        assert result.state_hash == run.state_hash()
    finally:
        store.close()


def test_wall_clock_pause_does_not_advance_simulation_tick(tmp_path: Path) -> None:
    store = durable_store(tmp_path)
    try:
        run = make_run("A", "B")
        store.create_run(run)
        time.sleep(0.01)
        assert store.load_run(run.run_id).snapshot.tick == Tick(0)
        assert store.load_run(run.run_id).snapshot.state_version == StateVersion(0)
    finally:
        store.close()


def test_crash_does_not_kill_agents(tmp_path: Path) -> None:
    store = durable_store(tmp_path)
    try:
        run = make_run("A", "B")
        store.create_run(run)
        request = durable_send_request(run)
        with pytest.raises(FaultInjected):
            store.commit_store.commit(run, request, fault_injector=RaiseAt("F8_BEFORE_COMMIT"))
        recovered = store.load_run(run.run_id)
        assert {agent.agent_id for agent in recovered.snapshot.agents} == {AgentId("A"), AgentId("B")}
        assert recovered.snapshot.tick == Tick(0)
    finally:
        store.close()


def test_repeated_recovery_is_idempotent(tmp_path: Path) -> None:
    store = durable_store(tmp_path)
    try:
        run = make_run("A", "B")
        store.create_run(run)
        request = durable_send_request(run)
        with pytest.raises(FaultInjected):
            store.commit_store.commit(run, request, fault_injector=RaiseAt("F10_BEFORE_PUBLICATION"))
        recovered_one = store.load_run(run.run_id)
        recovered_two = store.load_run(run.run_id)
        assert recovered_one.state_hash() == recovered_two.state_hash()
        assert len(store.commit_store.iter_commits(run.run_id)) == 1
        retry = store.commit_store.commit(recovered_two, request)
        assert retry.committed
        assert len(store.commit_store.iter_commits(run.run_id)) == 1
    finally:
        store.close()


def test_corrupted_artifact_hash_is_rejected(tmp_path: Path) -> None:
    cas = FileSystemArtifactStore(tmp_path / "cas")
    reference = cas.put_bytes(b"original")
    path = cas.root / reference.digest[:2] / reference.digest
    path.write_bytes(b"tampered")
    with pytest.raises(ArtifactIntegrityError):
        cas.resolve(reference)


@pytest.mark.parametrize(
    "point",
    [
        "F11_ARTIFACT_WRITE",
        "F11_HASH_VERIFICATION",
        "F11_BEFORE_FINALIZATION",
        "F11_AFTER_FINALIZATION",
    ],
)
def test_artifact_fault_points_never_create_an_invalid_reference(
    tmp_path: Path, point: str
) -> None:
    cas = FileSystemArtifactStore(tmp_path / "cas")
    with pytest.raises(FaultInjected):
        cas.put_bytes(b"faulted", fault_injector=RaiseAt(point))
    digest = hashlib.sha256(b"faulted").hexdigest()
    path = cas.root / digest[:2] / digest
    if point == "F11_AFTER_FINALIZATION":
        assert path.is_file()
        assert cas.resolve(ArtifactRef(ArtifactId(f"artifact-{digest}"), digest)) == b"faulted"
    else:
        assert not path.exists()


def test_expected_state_version_conflict_rolls_back(tmp_path: Path) -> None:
    store = durable_store(tmp_path)
    try:
        run = make_run("A", "B")
        store.create_run(run)
        old_request = durable_send_request(run, "first")
        store.commit_store.commit(run, old_request)
        conflicting_request = durable_send_request(make_run("A", "B"), "second")
        result = store.commit_store.commit(run, conflicting_request)
        assert not result.committed
        assert result.error is CommitError.STATE_VERSION_MISMATCH
        assert len(store.commit_store.iter_commits(run.run_id)) == 1
        assert store.load_run(run.run_id).snapshot.state_version == StateVersion(1)
    finally:
        store.close()


def test_failed_migration_does_not_partially_upgrade(tmp_path: Path) -> None:
    db_path = tmp_path / "migration.sqlite"
    connection = sqlite3.connect(db_path)
    try:
        configure_connection(connection)
        with pytest.raises(FaultInjected):
            migrate(connection, fault_injector=RaiseAt("MIGRATION_0001"))
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        assert tables == []
    finally:
        connection.close()
    store = SQLiteDurableRunStore(db_path)
    store.close()


def test_newer_schema_is_not_opened_by_older_code(tmp_path: Path) -> None:
    db_path = tmp_path / "newer.sqlite"
    connection = sqlite3.connect(db_path)
    connection.execute(
        "CREATE TABLE schema_meta (schema_id INTEGER PRIMARY KEY, schema_version INTEGER NOT NULL, migration_id TEXT NOT NULL)"
    )
    connection.execute(
        "INSERT INTO schema_meta VALUES (1, 999, 'future')"
    )
    connection.commit()
    connection.close()
    with pytest.raises(UnsupportedSchemaError):
        SQLiteDurableRunStore(db_path)


def test_reopening_database_preserves_commit_sequence(tmp_path: Path) -> None:
    db_path = tmp_path / "run.sqlite"
    cas_path = tmp_path / "cas"
    store = SQLiteReferenceStore(db_path, artifact_root=cas_path)
    run = make_run("A", "B")
    store.create_run(run)
    commit_one_send(store, run)
    store.close()
    reopened = SQLiteReferenceStore(db_path, artifact_root=cas_path)
    try:
        loaded = reopened.load_run(run.run_id)
        request = staged_request(loaded, {})
        result = reopened.commit_store.commit(loaded, request)
        assert result.committed
        assert [record.commit_seq for record in reopened.commit_store.iter_commits(run.run_id)] == [1, 2]
    finally:
        reopened.close()


def test_wal_checkpoint_behavior_does_not_change_canonical_hash(tmp_path: Path) -> None:
    store = durable_store(tmp_path)
    try:
        run = make_run("A", "B")
        store.create_run(run)
        commit_one_send(store, run)
        before = store.load_run(run.run_id).state_hash()
        store.run_store.connection.execute("PRAGMA wal_checkpoint(FULL)")
        after = store.load_run(run.run_id).state_hash()
        assert before == after == run.state_hash()
    finally:
        store.close()


def test_replay_twice_produces_identical_result(tmp_path: Path) -> None:
    store = durable_store(tmp_path)
    try:
        run = make_run("A", "B")
        store.create_run(run)
        commit_one_send(store, run)
        first = store.replay(run.run_id)
        second = store.replay(run.run_id)
        assert first.snapshot == second.snapshot
        assert first.verified_commit_ids == second.verified_commit_ids
    finally:
        store.close()


def test_replay_fault_can_restart_without_mutation(tmp_path: Path) -> None:
    store = durable_store(tmp_path)
    try:
        run = make_run("A", "B")
        store.create_run(run)
        commit_one_send(store, run)
        with pytest.raises(FaultInjected):
            store.replay(run.run_id, fault_injector=RaiseAt("F12_REPLAY"))
        again = store.replay(run.run_id)
        assert again.state_hash == run.state_hash()
    finally:
        store.close()


def test_required_artifact_is_checked_before_commit(tmp_path: Path) -> None:
    store = durable_store(tmp_path)
    try:
        run = make_run("A", "B")
        store.create_run(run)
        digest = hashlib.sha256(b"missing").hexdigest()
        reference = ArtifactRef(ArtifactId("artifact-missing"), digest)
        with pytest.raises(ArtifactMissingError):
            store.commit_store.commit(run, durable_send_request(run), artifact_refs=(reference,))
        assert_initial_boundary(store, run)
    finally:
        store.close()
