"""I-03 storage-neutral persistence boundaries and reference adapters."""

from __future__ import annotations

from pathlib import Path

from alifelm.domain import RunId, StateVersion

from .cas import FileSystemArtifactStore
from .contracts import (
    ArtifactIntegrityError,
    ArtifactMissingError,
    ArtifactStore,
    DurableCommitRecord,
    DurableCommitResult,
    DurableCommitStore,
    DurableRunStore,
    FaultInjected,
    FaultInjector,
    OutboxRecord,
    PersistenceError,
    ReplayCorruptionError,
    ReplayReader,
    ReplayResult,
    UnsupportedSchemaError,
)
from .replay import SQLiteReplayReader
from .sqlite_store import SQLiteDurableCommitStore, SQLiteDurableRunStore


class SQLiteReferenceStore:
    """Convenience composition of the SQLite and filesystem reference adapters."""

    def __init__(self, db_path: Path | str, *, artifact_root: Path | str | None = None) -> None:
        self.run_store = SQLiteDurableRunStore(db_path)
        if artifact_root is None:
            if str(db_path) == ":memory:":
                artifact_root = Path.cwd() / ".alifelm-cas-memory"
            else:
                artifact_root = Path(db_path).with_suffix(".cas")
        self.artifact_store = FileSystemArtifactStore(artifact_root)
        self.commit_store = SQLiteDurableCommitStore(
            self.run_store,
            artifact_store=self.artifact_store,
        )
        self.replay_reader = SQLiteReplayReader(
            self.run_store,
            self.commit_store,
            self.artifact_store,
        )

    def create_run(self, run) -> None:
        self.run_store.create_run(run)

    def load_run(self, run_id: RunId):
        return self.run_store.load_run(run_id)

    def snapshot_at(self, run_id: RunId, state_version: StateVersion):
        return self.run_store.snapshot_at(run_id, state_version)

    def commit(self, run, request, **kwargs) -> DurableCommitResult:
        return self.commit_store.commit(run, request, **kwargs)

    def replay(self, run_id: RunId, **kwargs) -> ReplayResult:
        return self.replay_reader.replay(run_id, **kwargs)

    def close(self) -> None:
        self.run_store.close()


SQLiteDurableStore = SQLiteReferenceStore


__all__ = [
    "ArtifactIntegrityError",
    "ArtifactMissingError",
    "ArtifactStore",
    "DurableCommitRecord",
    "DurableCommitResult",
    "DurableCommitStore",
    "DurableRunStore",
    "FaultInjected",
    "FaultInjector",
    "FileSystemArtifactStore",
    "OutboxRecord",
    "PersistenceError",
    "ReplayCorruptionError",
    "ReplayReader",
    "ReplayResult",
    "SQLiteDurableCommitStore",
    "SQLiteDurableRunStore",
    "SQLiteReferenceStore",
    "SQLiteDurableStore",
    "SQLiteReplayReader",
    "UnsupportedSchemaError",
]
