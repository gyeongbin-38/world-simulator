"""Storage-neutral durable boundaries for the I-03 reference adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

from alifelm.domain import ArtifactRef, DomainEvent, RunId, StateVersion, Tick
from alifelm.kernel import CommitRequest, CommitResult, SimulationRun, Snapshot


class PersistenceError(RuntimeError):
    """Base error for a durable adapter failure."""


class ArtifactMissingError(PersistenceError):
    """A required ArtifactRef does not resolve to bytes."""


class ArtifactIntegrityError(PersistenceError):
    """Artifact bytes do not match their content identity."""


class UnsupportedSchemaError(PersistenceError):
    """A database was created by a newer unsupported schema."""


class ReplayCorruptionError(PersistenceError):
    """Durable replay inputs do not form a verifiable commit chain."""


class FaultInjected(RuntimeError):
    """Deterministic test fault at a named recovery point."""


class FaultInjector(Protocol):
    def check(self, point: str) -> None:
        """Raise at a configured point or return."""


@dataclass(frozen=True, slots=True)
class OutboxRecord:
    outbox_id: str
    commit_id: str
    commit_seq: int
    record_type: str
    event_id: str | None
    status: str = "PENDING"
    attempt_count: int = 0
    payload_artifact_ref: ArtifactRef | None = None


@dataclass(frozen=True, slots=True)
class DurableCommitRecord:
    commit_id: str
    commit_seq: int
    run_id: RunId
    tick: Tick
    state_version_before: StateVersion
    state_version_after: StateVersion
    previous_state_hash: str
    resulting_state_hash: str
    transition_digest: str
    snapshot: Snapshot
    events: tuple[DomainEvent, ...]
    artifact_refs: tuple[ArtifactRef, ...]
    outbox_ids: tuple[str, ...]

    @property
    def commit_status(self) -> str:
        return "COMMITTED"

    @property
    def event_ordinals(self) -> tuple[int, ...]:
        return tuple(event.commit_order for event in self.events)


@dataclass(frozen=True, slots=True)
class DurableCommitResult:
    """CommitResult-compatible durable response plus commit identity."""

    commit_id: str
    commit_seq: int | None
    result: CommitResult

    @property
    def committed(self) -> bool:
        return self.result.committed

    @property
    def snapshot(self) -> Snapshot:
        return self.result.snapshot

    @property
    def events(self) -> tuple[DomainEvent, ...]:
        return self.result.events

    @property
    def error(self):
        return self.result.error

    @property
    def capacity_censored(self) -> bool:
        return self.result.capacity_censored


@dataclass(frozen=True, slots=True)
class ReplayResult:
    run_id: RunId
    snapshot: Snapshot
    verified_commit_ids: tuple[str, ...]

    @property
    def state_hash(self) -> str:
        return self.snapshot.state_hash()


class ArtifactStore(Protocol):
    def put_bytes(
        self,
        data: bytes,
        *,
        media_type: str = "application/octet-stream",
        contract_id: str = "raw-bytes",
        fault_injector: FaultInjector | None = None,
    ) -> ArtifactRef:
        """Durably finalize and return a content-addressed reference."""

    def resolve(self, reference: ArtifactRef) -> bytes:
        """Return verified immutable bytes for a reference."""

    def is_durable(self, reference: ArtifactRef) -> bool:
        """Return whether a reference resolves and verifies."""

    def list_orphans(self, referenced: Iterable[ArtifactRef] = ()) -> tuple[ArtifactRef, ...]:
        """Find durable CAS content that is not in the supplied reference set."""


class DurableRunStore(Protocol):
    def create_run(self, run: SimulationRun) -> None:
        """Durably create the initial run boundary."""

    def load_run(self, run_id: RunId) -> SimulationRun:
        """Load the current materialized run boundary."""

    def snapshot_at(self, run_id: RunId, state_version: StateVersion) -> Snapshot:
        """Read a committed snapshot/checkpoint by version."""


class DurableCommitStore(Protocol):
    def commit(
        self,
        run: SimulationRun,
        request: CommitRequest,
        *,
        artifact_refs: tuple[ArtifactRef, ...] = (),
        fault_injector: FaultInjector | None = None,
    ) -> DurableCommitResult:
        """Apply one logical commit or return its exact existing result."""

    def lookup_commit(self, commit_id: str) -> DurableCommitRecord | None:
        """Resolve an idempotency identity without mutating state."""

    def iter_commits(self, run_id: RunId) -> tuple[DurableCommitRecord, ...]:
        """Read committed boundaries in their durable per-run order."""


class ReplayReader(Protocol):
    def replay(
        self,
        run_id: RunId,
        *,
        target_state_version: StateVersion | None = None,
        fault_injector: FaultInjector | None = None,
    ) -> ReplayResult:
        """Verify/reconstruct committed boundaries without model inference."""
