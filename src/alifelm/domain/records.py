"""State/event/artifact/protocol category contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .identifiers import AgentId, ArtifactId, EventId, MessageId
from .values import Tick


class RecordKind(StrEnum):
    STATE = "STATE"
    EVENT = "EVENT"
    ARTIFACT = "ARTIFACT"
    PROTOCOL = "PROTOCOL"


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """A stable reference to immutable evidence or payload bytes."""

    artifact_id: ArtifactId
    digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.artifact_id, ArtifactId):
            raise TypeError("artifact_id must be an ArtifactId")
        if not isinstance(self.digest, str) or not self.digest:
            raise ValueError("an artifact reference requires a non-empty digest")


@dataclass(frozen=True, slots=True)
class MessageRecord:
    """Committed directed message visible from its next snapshot onward."""

    message_id: MessageId
    sender_id: AgentId
    recipient_id: AgentId
    body: str
    committed_tick: Tick
    available_tick: Tick

    def __post_init__(self) -> None:
        if not isinstance(self.message_id, MessageId):
            raise TypeError("message_id must be a MessageId")
        if not isinstance(self.sender_id, AgentId):
            raise TypeError("sender_id must be an AgentId")
        if not isinstance(self.recipient_id, AgentId):
            raise TypeError("recipient_id must be an AgentId")
        if not isinstance(self.body, str):
            raise TypeError("message body must be a string")
        if not isinstance(self.committed_tick, Tick):
            raise TypeError("committed_tick must be a Tick")
        if not isinstance(self.available_tick, Tick):
            raise TypeError("available_tick must be a Tick")
        if self.available_tick != self.committed_tick + 1:
            raise ValueError("a message becomes available exactly one tick after commit")


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Immutable historical fact with explicit committed ordering metadata."""

    event_id: EventId
    event_type: str
    commit_tick: Tick
    commit_order: int
    artifact_refs: tuple[ArtifactRef, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, EventId):
            raise TypeError("event_id must be an EventId")
        if not isinstance(self.commit_tick, Tick):
            raise TypeError("commit_tick must be a Tick")
        if not self.event_type or not isinstance(self.event_type, str):
            raise ValueError("event_type must be a non-empty string")
        if isinstance(self.commit_order, bool) or not isinstance(self.commit_order, int):
            raise TypeError("commit_order must be an integer")
        if self.commit_order < 0:
            raise ValueError("commit_order cannot be negative")
        if not isinstance(self.artifact_refs, tuple) or any(
            not isinstance(ref, ArtifactRef) for ref in self.artifact_refs
        ):
            raise TypeError("artifact_refs must be a tuple of ArtifactRef values")
