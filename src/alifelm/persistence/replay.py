"""Verification-oriented replay over durable checkpoints and commit history."""

from __future__ import annotations

from alifelm.domain import RunId, StateVersion, Tick

from .contracts import (
    ArtifactStore,
    DurableCommitRecord,
    FaultInjector,
    ReplayCorruptionError,
    ReplayResult,
)
from .sqlite_store import SQLiteDurableCommitStore, SQLiteDurableRunStore


class SQLiteReplayReader:
    """Reconstruct and verify a run without invoking model inference.

    The reference store is intentionally not event-sourced: every durable commit
    contains a materialized resulting snapshot. Replay verifies that checkpoint
    chain, event suffix, ordering, and hashes agree before returning the result.
    """

    def __init__(
        self,
        run_store: SQLiteDurableRunStore,
        commit_store: SQLiteDurableCommitStore,
        artifact_store: ArtifactStore | None = None,
    ) -> None:
        self.run_store = run_store
        self.commit_store = commit_store
        self.artifact_store = artifact_store

    def replay(
        self,
        run_id: RunId,
        *,
        target_state_version: StateVersion | None = None,
        fault_injector: FaultInjector | None = None,
    ) -> ReplayResult:
        target = target_state_version
        initial = self.run_store.snapshot_at(run_id, StateVersion(0))
        if target is not None and target < initial.state_version:
            raise ReplayCorruptionError("replay target precedes the initial boundary")

        current = initial
        verified: list[str] = []
        if target is not None and target == current.state_version:
            return ReplayResult(run_id, current, ())

        expected_seq = 1
        for record in self.commit_store.iter_commits(run_id):
            if fault_injector is not None:
                fault_injector.check("F12_REPLAY")
            self._verify_record(record, current, expected_seq)
            if self.artifact_store is not None:
                for reference in record.artifact_refs:
                    self.artifact_store.resolve(reference)
            current = record.snapshot
            verified.append(record.commit_id)
            expected_seq += 1
            if target is not None and current.state_version == target:
                return ReplayResult(run_id, current, tuple(verified))
            if target is not None and current.state_version > target:
                raise ReplayCorruptionError("replay crossed its requested state version")

        if target is not None and current.state_version != target:
            raise ReplayCorruptionError("requested replay boundary is not committed")
        return ReplayResult(run_id, current, tuple(verified))

    def _verify_record(
        self,
        record: DurableCommitRecord,
        prior,
        expected_seq: int,
    ) -> None:
        if record.commit_seq != expected_seq:
            raise ReplayCorruptionError("commit sequence is not contiguous")
        if record.run_id != prior.run_id:
            raise ReplayCorruptionError("commit belongs to another run")
        if record.state_version_before != prior.state_version:
            raise ReplayCorruptionError("commit does not begin at the prior state version")
        if record.previous_state_hash != prior.state_hash():
            raise ReplayCorruptionError("commit previous state hash does not match prior snapshot")
        if record.state_version_after != StateVersion(record.state_version_before + 1):
            raise ReplayCorruptionError("commit advances state version by more than one")
        if record.state_version_after != record.snapshot.state_version:
            raise ReplayCorruptionError("commit and resulting snapshot versions disagree")
        if record.snapshot.tick != Tick(record.tick + 1):
            raise ReplayCorruptionError("commit and resulting snapshot ticks disagree")
        if record.snapshot.state_hash() != record.resulting_state_hash:
            raise ReplayCorruptionError("resulting snapshot hash is invalid")
        if record.snapshot.events[: len(prior.events)] != prior.events:
            raise ReplayCorruptionError("snapshot event history is not append-only")
        event_suffix = record.snapshot.events[len(prior.events) :]
        if event_suffix != record.events:
            raise ReplayCorruptionError("commit event records do not match snapshot event suffix")
