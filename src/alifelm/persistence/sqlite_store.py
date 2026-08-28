"""SQLite reference adapter for durable materialized state and commit history."""

from __future__ import annotations

from pathlib import Path
import hashlib
import json
import sqlite3
from threading import RLock
from typing import Iterable

from alifelm.domain import (
    ArtifactId,
    ArtifactRef,
    Duration,
    RunId,
    StateVersion,
    Tick,
)
from alifelm.kernel import (
    CommitError,
    CommitRequest,
    CommitResult,
    InMemoryCommitCoordinator,
    RunStatus,
    SimulationRun,
    Snapshot,
)
from alifelm.domain import DomainEvent

from .contracts import (
    ArtifactStore,
    DurableCommitRecord,
    DurableCommitResult,
    FaultInjector,
    PersistenceError,
    ReplayCorruptionError,
)
from .migrations import configure_connection, migrate
from .serialization import (
    agent_from_dict,
    agent_to_dict,
    artifact_ref_to_dict,
    canonical_json,
    event_from_dict,
    message_from_dict,
    message_to_dict,
    proposal_from_dict,
    proposal_to_dict,
    snapshot_from_dict,
    snapshot_to_dict,
    transition_digest,
)


class SQLiteDurableRunStore:
    """Own SQLite connection/migrations and materialized current state reads."""

    def __init__(
        self,
        db_path: Path | str,
        *,
        fault_injector: FaultInjector | None = None,
    ) -> None:
        self.db_path = None if str(db_path) == ":memory:" else Path(db_path).resolve()
        if self.db_path is not None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(
            ":memory:" if self.db_path is None else str(self.db_path),
            check_same_thread=False,
        )
        try:
            configure_connection(self._connection)
            migrate(self._connection, fault_injector=fault_injector)
        except Exception:
            self._connection.close()
            raise
        self._lock = RLock()

    @property
    def connection(self) -> sqlite3.Connection:
        """Expose the connection only to the paired reference commit adapter."""

        return self._connection

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def create_run(self, run: SimulationRun) -> None:
        with self._lock:
            existing = self._connection.execute(
                "SELECT run_id FROM runs WHERE run_id = ?", (run.run_id.value,)
            ).fetchone()
            if existing is not None:
                loaded = self.load_run(run.run_id)
                if loaded.state_hash() != run.state_hash() or not _same_config(loaded, run):
                    raise PersistenceError("run identity already exists with different content")
                return

            committed = False
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                self._connection.execute(
                    """
                    INSERT INTO runs (
                        run_id, lifespan_ticks, maturity_delay_ticks,
                        refractory_interval_ticks, population_capacity, horizon,
                        status, current_tick, current_state_version, current_state_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run.run_id.value,
                        int(run.lifespan_ticks),
                        int(run.maturity_delay_ticks),
                        int(run.refractory_interval_ticks),
                        run.population_capacity,
                        None if run.horizon is None else int(run.horizon),
                        run.snapshot.status.value,
                        int(run.snapshot.tick),
                        int(run.snapshot.state_version),
                        run.state_hash(),
                    ),
                )
                self._insert_snapshot(run.snapshot, commit_id=None)
                self._replace_current_tables(run.snapshot)
                self._connection.commit()
                committed = True
            except Exception:
                if not committed:
                    self._connection.rollback()
                raise

    def load_run(self, run_id: RunId) -> SimulationRun:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id.value,)
            ).fetchone()
            if row is None:
                raise PersistenceError(f"run does not exist: {run_id}")
            snapshot = self._read_snapshot(run_id, StateVersion(row["current_state_version"]))
            if (
                snapshot.tick != row["current_tick"]
                or snapshot.state_version != row["current_state_version"]
                or snapshot.state_hash() != row["current_state_hash"]
            ):
                raise ReplayCorruptionError("runs metadata and current snapshot disagree")
            self._verify_materialized_projection(snapshot)
            return SimulationRun(
                run_id=run_id,
                lifespan_ticks=Duration(row["lifespan_ticks"]),
                maturity_delay_ticks=Duration(row["maturity_delay_ticks"]),
                refractory_interval_ticks=Duration(row["refractory_interval_ticks"]),
                _snapshot=snapshot,
                population_capacity=row["population_capacity"],
                horizon=(None if row["horizon"] is None else Tick(row["horizon"])),
            )

    def snapshot_at(self, run_id: RunId, state_version: StateVersion) -> Snapshot:
        with self._lock:
            return self._read_snapshot(run_id, state_version)

    def _read_snapshot(self, run_id: RunId, state_version: StateVersion) -> Snapshot:
        row = self._connection.execute(
            "SELECT state_hash, snapshot_json FROM snapshots WHERE run_id = ? AND state_version = ?",
            (run_id.value, int(state_version)),
        ).fetchone()
        if row is None:
            raise PersistenceError(
                f"snapshot does not exist: run={run_id.value}, version={int(state_version)}"
            )
        try:
            snapshot = snapshot_from_dict(json.loads(row["snapshot_json"]))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ReplayCorruptionError("snapshot JSON is invalid") from exc
        if snapshot.run_id != run_id or snapshot.state_version != state_version:
            raise ReplayCorruptionError("snapshot identity does not match its durable key")
        if snapshot.state_hash() != row["state_hash"]:
            raise ReplayCorruptionError("snapshot hash does not match its durable record")
        return snapshot

    def _insert_snapshot(self, snapshot: Snapshot, *, commit_id: str | None) -> None:
        self._connection.execute(
            """
            INSERT INTO snapshots (
                run_id, state_version, tick, state_hash, commit_id, snapshot_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot.run_id.value,
                int(snapshot.state_version),
                int(snapshot.tick),
                snapshot.state_hash(),
                commit_id,
                canonical_json(snapshot_to_dict(snapshot)),
            ),
        )

    def _replace_current_tables(self, snapshot: Snapshot) -> None:
        run_id = snapshot.run_id.value
        for table in ("agents_current", "messages_current", "proposals_current"):
            self._connection.execute(f"DELETE FROM {table} WHERE run_id = ?", (run_id,))
        self._connection.executemany(
            """
            INSERT INTO agents_current (
                run_id, agent_id, birth_tick, first_active_tick, lifespan_ticks,
                maturity_delay_ticks, state, refractory_until_tick
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    agent.agent_id.value,
                    int(agent.birth_tick),
                    int(agent.first_active_tick),
                    int(agent.lifespan_ticks),
                    int(agent.maturity_delay_ticks),
                    agent.state.value,
                    None
                    if agent.refractory_until_tick is None
                    else int(agent.refractory_until_tick),
                )
                for agent in snapshot.agents
            ],
        )
        self._connection.executemany(
            """
            INSERT INTO messages_current (
                run_id, message_id, sender_id, recipient_id, body,
                committed_tick, available_tick
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    message.message_id.value,
                    message.sender_id.value,
                    message.recipient_id.value,
                    message.body,
                    int(message.committed_tick),
                    int(message.available_tick),
                )
                for message in snapshot.messages
            ],
        )
        self._connection.executemany(
            """
            INSERT INTO proposals_current (
                run_id, proposal_id, proposer_id, target_id, created_tick,
                state, expires_at_tick
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    proposal.proposal_id.value,
                    proposal.proposer_id.value,
                    proposal.target_id.value,
                    int(proposal.created_tick),
                    proposal.state.value,
                    None
                    if proposal.expires_at_tick is None
                    else int(proposal.expires_at_tick),
                )
                for proposal in snapshot.proposals
            ],
        )

    def _verify_materialized_projection(self, snapshot: Snapshot) -> None:
        run_id = snapshot.run_id.value
        agents = tuple(
            agent_from_dict(
                {
                    "agent_id": row["agent_id"],
                    "birth_tick": row["birth_tick"],
                    "first_active_tick": row["first_active_tick"],
                    "lifespan_ticks": row["lifespan_ticks"],
                    "maturity_delay_ticks": row["maturity_delay_ticks"],
                    "state": row["state"],
                    "refractory_until_tick": row["refractory_until_tick"],
                }
            )
            for row in self._connection.execute(
                "SELECT * FROM agents_current WHERE run_id = ? ORDER BY agent_id", (run_id,)
            )
        )
        messages = tuple(
            message_from_dict(
                {
                    "message_id": row["message_id"],
                    "sender_id": row["sender_id"],
                    "recipient_id": row["recipient_id"],
                    "body": row["body"],
                    "committed_tick": row["committed_tick"],
                    "available_tick": row["available_tick"],
                }
            )
            for row in self._connection.execute(
                "SELECT * FROM messages_current WHERE run_id = ? ORDER BY message_id", (run_id,)
            )
        )
        proposals = tuple(
            proposal_from_dict(
                {
                    "proposal_id": row["proposal_id"],
                    "proposer_id": row["proposer_id"],
                    "target_id": row["target_id"],
                    "created_tick": row["created_tick"],
                    "state": row["state"],
                    "expires_at_tick": row["expires_at_tick"],
                }
            )
            for row in self._connection.execute(
                "SELECT * FROM proposals_current WHERE run_id = ? ORDER BY proposal_id", (run_id,)
            )
        )
        if agents != snapshot.agents or messages != snapshot.messages or proposals != snapshot.proposals:
            raise ReplayCorruptionError("materialized state tables disagree with snapshot checkpoint")


class SQLiteDurableCommitStore:
    """Durable commit coordinator preserving the in-memory transition semantics."""

    def __init__(
        self,
        run_store: SQLiteDurableRunStore,
        *,
        artifact_store: ArtifactStore | None = None,
    ) -> None:
        self.run_store = run_store
        self.artifact_store = artifact_store
        self._lock = run_store._lock

    def lookup_commit(self, commit_id: str) -> DurableCommitRecord | None:
        with self._lock:
            return self._read_commit(commit_id)

    def iter_commits(self, run_id: RunId) -> tuple[DurableCommitRecord, ...]:
        with self._lock:
            rows = self.run_store.connection.execute(
                "SELECT commit_id FROM commits WHERE run_id = ? ORDER BY commit_seq",
                (run_id.value,),
            ).fetchall()
            records = tuple(
                self._read_commit(row["commit_id"]) for row in rows
            )
            return tuple(record for record in records if record is not None)

    def commit(
        self,
        run: SimulationRun,
        request: CommitRequest,
        *,
        artifact_refs: tuple[ArtifactRef, ...] = (),
        fault_injector: FaultInjector | None = None,
    ) -> DurableCommitResult:
        digest = transition_digest(request, artifact_refs)
        candidate_id = _commit_id(request, run.snapshot.state_hash(), digest)
        if request.run_id != run.run_id:
            return _durable_failure(candidate_id, run.snapshot, CommitError.RUN_ID_MISMATCH)

        with self._lock:
            try:
                prior = self.run_store._read_snapshot(
                    request.run_id, request.expected_state_version
                )
            except ReplayCorruptionError:
                raise
            except PersistenceError:
                prior = run.snapshot
            previous_hash = prior.state_hash()
            candidate_id = _commit_id(request, previous_hash, digest)
            existing = self._read_commit(candidate_id)
            if existing is not None:
                if (
                    existing.state_version_before != request.expected_state_version
                    or existing.previous_state_hash != previous_hash
                    or existing.transition_digest != digest
                ):
                    raise PersistenceError("commit identity resolves to different immutable content")
                self._sync_run_if_needed(run, existing.snapshot)
                return _durable_success(existing)

            current_row = self.run_store.connection.execute(
                "SELECT * FROM runs WHERE run_id = ?", (request.run_id.value,)
            ).fetchone()
            if current_row is None:
                return _durable_failure(candidate_id, run.snapshot, CommitError.RUN_ID_MISMATCH)
            if current_row["status"] != RunStatus.RUNNING.value:
                return _durable_failure(candidate_id, run.snapshot, CommitError.RUN_NOT_RUNNING)
            if (
                current_row["current_state_version"] != int(request.expected_state_version)
                or current_row["current_state_hash"] != previous_hash
            ):
                return _durable_failure(
                    candidate_id, run.snapshot, CommitError.STATE_VERSION_MISMATCH
                )
            if not _same_config_values(current_row, run):
                raise PersistenceError("caller run configuration differs from durable run")

            planned_run = SimulationRun(
                run_id=run.run_id,
                lifespan_ticks=run.lifespan_ticks,
                maturity_delay_ticks=run.maturity_delay_ticks,
                refractory_interval_ticks=run.refractory_interval_ticks,
                _snapshot=prior,
                population_capacity=run.population_capacity,
                horizon=run.horizon,
            )
            in_memory_result = InMemoryCommitCoordinator().commit(planned_run, request)
            if not in_memory_result.committed:
                return DurableCommitResult(candidate_id, None, in_memory_result)

            all_artifact_refs = _unique_artifact_refs(
                artifact_refs,
                *(event.artifact_refs for event in in_memory_result.events),
            )
            self._verify_artifacts(all_artifact_refs)
            if fault_injector is not None:
                fault_injector.check("F5_BEFORE_COMMIT")

            commit_seq = int(in_memory_result.snapshot.state_version)
            outbox_rows = _outbox_rows(candidate_id, commit_seq, in_memory_result.events)
            committed = False
            try:
                self.run_store.connection.execute("BEGIN IMMEDIATE")
                if fault_injector is not None:
                    fault_injector.check("F6_TRANSACTION_BEGIN")
                self.run_store._replace_current_tables(in_memory_result.snapshot)
                self.run_store.connection.execute(
                    """
                    UPDATE runs
                    SET status = ?, current_tick = ?, current_state_version = ?, current_state_hash = ?
                    WHERE run_id = ?
                    """,
                    (
                        in_memory_result.snapshot.status.value,
                        int(in_memory_result.snapshot.tick),
                        int(in_memory_result.snapshot.state_version),
                        in_memory_result.snapshot.state_hash(),
                        run.run_id.value,
                    ),
                )
                self.run_store._insert_snapshot(
                    in_memory_result.snapshot, commit_id=candidate_id
                )
                if fault_injector is not None:
                    fault_injector.check("F7_AFTER_STATE_WRITE")

                self.run_store.connection.execute(
                    """
                    INSERT INTO commits (
                        commit_id, run_id, commit_seq, tick, state_version_before,
                        state_version_after, previous_state_hash, resulting_state_hash,
                        transition_digest, commit_status, resulting_snapshot_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'COMMITTED', ?)
                    """,
                    (
                        candidate_id,
                        run.run_id.value,
                        commit_seq,
                        int(request.tick),
                        int(request.expected_state_version),
                        int(in_memory_result.snapshot.state_version),
                        previous_hash,
                        in_memory_result.snapshot.state_hash(),
                        digest,
                        canonical_json(snapshot_to_dict(in_memory_result.snapshot)),
                    ),
                )
                for ordinal, event in enumerate(in_memory_result.events):
                    self.run_store.connection.execute(
                        """
                        INSERT INTO commit_events (
                            commit_id, event_ordinal, event_id, event_type,
                            commit_tick, commit_order, artifact_refs_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            candidate_id,
                            ordinal,
                            event.event_id.value,
                            event.event_type,
                            int(event.commit_tick),
                            event.commit_order,
                            canonical_json(
                                [artifact_ref_to_dict(ref) for ref in event.artifact_refs]
                            ),
                        ),
                    )
                for reference in all_artifact_refs:
                    self.run_store.connection.execute(
                        "INSERT INTO commit_artifacts (commit_id, artifact_id, digest) VALUES (?, ?, ?)",
                        (candidate_id, reference.artifact_id.value, reference.digest),
                    )
                for outbox in outbox_rows:
                    self.run_store.connection.execute(
                        """
                        INSERT INTO outbox (
                            outbox_id, commit_id, commit_seq, record_type, event_id,
                            status, attempt_count, payload_artifact_ref_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            outbox.outbox_id,
                            outbox.commit_id,
                            outbox.commit_seq,
                            outbox.record_type,
                            outbox.event_id,
                            outbox.status,
                            outbox.attempt_count,
                            None
                            if outbox.payload_artifact_ref is None
                            else canonical_json(
                                artifact_ref_to_dict(outbox.payload_artifact_ref)
                            ),
                        ),
                    )
                if fault_injector is not None:
                    fault_injector.check("F8_BEFORE_COMMIT")
                self.run_store.connection.commit()
                committed = True
            except Exception:
                if not committed:
                    self.run_store.connection.rollback()
                raise

            if fault_injector is not None:
                fault_injector.check("F9_AFTER_COMMIT_BEFORE_ACK")
                fault_injector.check("F10_BEFORE_PUBLICATION")
            run._publish_snapshot(
                in_memory_result.snapshot,
                request.expected_state_version,
            )
            return DurableCommitResult(candidate_id, commit_seq, in_memory_result)

    def _verify_artifacts(self, references: tuple[ArtifactRef, ...]) -> None:
        if not references:
            return
        if self.artifact_store is None:
            raise PersistenceError("required ArtifactRefs need an ArtifactStore")
        for reference in references:
            self.artifact_store.resolve(reference)

    def _read_commit(self, commit_id: str) -> DurableCommitRecord | None:
        row = self.run_store.connection.execute(
            "SELECT * FROM commits WHERE commit_id = ?", (commit_id,)
        ).fetchone()
        if row is None:
            return None
        try:
            snapshot = snapshot_from_dict(json.loads(row["resulting_snapshot_json"]))
            event_rows = self.run_store.connection.execute(
                """
                SELECT * FROM commit_events
                WHERE commit_id = ? ORDER BY event_ordinal
                """,
                (commit_id,),
            ).fetchall()
            events = tuple(
                event_from_dict(
                    {
                        "event_id": event_row["event_id"],
                        "event_type": event_row["event_type"],
                        "commit_tick": event_row["commit_tick"],
                        "commit_order": event_row["commit_order"],
                        "artifact_refs": json.loads(event_row["artifact_refs_json"]),
                    }
                )
                for event_row in event_rows
            )
            artifact_rows = self.run_store.connection.execute(
                "SELECT artifact_id, digest FROM commit_artifacts WHERE commit_id = ? ORDER BY artifact_id",
                (commit_id,),
            ).fetchall()
            artifacts = tuple(
                ArtifactRef(ArtifactId(row["artifact_id"]), row["digest"])
                for row in artifact_rows
            )
            if artifacts:
                self._verify_artifacts(artifacts)
            outbox_rows = self.run_store.connection.execute(
                "SELECT * FROM outbox WHERE commit_id = ? ORDER BY outbox_id",
                (commit_id,),
            ).fetchall()
            outbox_ids = tuple(row["outbox_id"] for row in outbox_rows)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ReplayCorruptionError("durable commit payload is invalid") from exc
        if (
            snapshot.run_id.value != row["run_id"]
            or row["commit_status"] != "COMMITTED"
            or row["state_version_after"] != row["state_version_before"] + 1
            or snapshot.state_version != row["state_version_after"]
            or snapshot.tick != Tick(row["tick"] + 1)
            or snapshot.state_hash() != row["resulting_state_hash"]
        ):
            raise ReplayCorruptionError("durable commit metadata disagrees with its snapshot")
        try:
            previous_snapshot = self.run_store._read_snapshot(
                RunId(row["run_id"]), StateVersion(row["state_version_before"])
            )
        except PersistenceError as exc:
            raise ReplayCorruptionError("durable commit previous boundary is missing") from exc
        if previous_snapshot.state_hash() != row["previous_state_hash"]:
            raise ReplayCorruptionError("durable commit previous state hash is invalid")
        if any(
            event.commit_tick != Tick(row["tick"])
            or event.commit_order != ordinal
            for ordinal, event in enumerate(events)
        ):
            raise ReplayCorruptionError("durable commit event ordering is invalid")
        if events and tuple(event.event_id.value for event in events) != tuple(
            event.event_id.value for event in snapshot.events[-len(events):]
        ):
            raise ReplayCorruptionError("durable commit events disagree with its snapshot")
        artifact_set = {(reference.artifact_id.value, reference.digest) for reference in artifacts}
        event_artifacts = {
            (reference.artifact_id.value, reference.digest)
            for event in events
            for reference in event.artifact_refs
        }
        if not event_artifacts.issubset(artifact_set):
            raise ReplayCorruptionError("event references are absent from commit artifacts")
        expected_outbox_ids = {
            _outbox_id(commit_id, event.event_id.value) for event in events
        }
        expected_outbox_ids.add(_outbox_id(commit_id, "snapshot-publication"))
        if set(outbox_ids) != expected_outbox_ids:
            raise ReplayCorruptionError("durable outbox does not cover the committed boundary")
        for outbox_row in outbox_rows:
            if (
                outbox_row["commit_seq"] != row["commit_seq"]
                or outbox_row["status"] != "PENDING"
                or outbox_row["attempt_count"] != 0
            ):
                raise ReplayCorruptionError("durable outbox metadata is invalid")
        return DurableCommitRecord(
            commit_id=row["commit_id"],
            commit_seq=row["commit_seq"],
            run_id=RunId(row["run_id"]),
            tick=Tick(row["tick"]),
            state_version_before=StateVersion(row["state_version_before"]),
            state_version_after=StateVersion(row["state_version_after"]),
            previous_state_hash=row["previous_state_hash"],
            resulting_state_hash=row["resulting_state_hash"],
            transition_digest=row["transition_digest"],
            snapshot=snapshot,
            events=events,
            artifact_refs=artifacts,
            outbox_ids=outbox_ids,
        )

    def _sync_run_if_needed(self, run: SimulationRun, snapshot: Snapshot) -> None:
        if run.snapshot.state_version == snapshot.state_version:
            if run.snapshot.state_hash() != snapshot.state_hash():
                raise PersistenceError("in-memory run disagrees with existing durable commit")
            return
        if run.snapshot.state_version < snapshot.state_version:
            run._publish_snapshot(snapshot, run.snapshot.state_version)


def _same_config(left: SimulationRun, right: SimulationRun) -> bool:
    return (
        left.lifespan_ticks == right.lifespan_ticks
        and left.maturity_delay_ticks == right.maturity_delay_ticks
        and left.refractory_interval_ticks == right.refractory_interval_ticks
        and left.population_capacity == right.population_capacity
        and left.horizon == right.horizon
    )


def _same_config_values(row: sqlite3.Row, run: SimulationRun) -> bool:
    return (
        row["lifespan_ticks"] == int(run.lifespan_ticks)
        and row["maturity_delay_ticks"] == int(run.maturity_delay_ticks)
        and row["refractory_interval_ticks"] == int(run.refractory_interval_ticks)
        and row["population_capacity"] == run.population_capacity
        and row["horizon"] == (None if run.horizon is None else int(run.horizon))
    )


def _commit_id(request: CommitRequest, previous_hash: str, digest: str) -> str:
    material = (
        f"commit|{request.run_id.value}|{int(request.tick)}|"
        f"{int(request.expected_state_version)}|{previous_hash}|{digest}"
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _outbox_rows(commit_id: str, commit_seq: int, events: tuple[DomainEvent, ...]):
    from .contracts import OutboxRecord

    rows = [
        OutboxRecord(
            outbox_id=_outbox_id(commit_id, event.event_id.value),
            commit_id=commit_id,
            commit_seq=commit_seq,
            record_type="DOMAIN_EVENT",
            event_id=event.event_id.value,
        )
        for event in events
    ]
    rows.append(
        OutboxRecord(
            outbox_id=_outbox_id(commit_id, "snapshot-publication"),
            commit_id=commit_id,
            commit_seq=commit_seq,
            record_type="SNAPSHOT_PUBLICATION",
            event_id=None,
        )
    )
    return tuple(rows)


def _outbox_id(commit_id: str, key: str) -> str:
    return hashlib.sha256(f"outbox|{commit_id}|{key}".encode("utf-8")).hexdigest()


def _unique_artifact_refs(
    first: tuple[ArtifactRef, ...],
    *groups: Iterable[ArtifactRef],
) -> tuple[ArtifactRef, ...]:
    values = {reference.artifact_id.value: reference for reference in first}
    for group in groups:
        for reference in group:
            existing = values.get(reference.artifact_id.value)
            if existing is not None and existing.digest != reference.digest:
                raise PersistenceError("one artifact identity has multiple digests")
            values[reference.artifact_id.value] = reference
    return tuple(values[key] for key in sorted(values))


def _durable_success(record: DurableCommitRecord) -> DurableCommitResult:
    result = CommitResult(
        committed=True,
        snapshot=record.snapshot,
        events=record.events,
        capacity_censored=record.snapshot.status is RunStatus.CENSORED,
    )
    return DurableCommitResult(record.commit_id, record.commit_seq, result)


def _durable_failure(commit_id: str, snapshot: Snapshot, error: CommitError) -> DurableCommitResult:
    return DurableCommitResult(
        commit_id,
        None,
        CommitResult(committed=False, snapshot=snapshot, events=(), error=error),
    )
