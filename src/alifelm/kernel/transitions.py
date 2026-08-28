"""Non-authoritative transition fragments staged before one commit boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from alifelm.domain import (
    AgentId,
    AgentState,
    ConflictReason,
    FragmentId,
    MessageRecord,
    ProposalId,
    ReproductionProposal,
    Tick,
)


class TransitionKind(StrEnum):
    MESSAGE = "MESSAGE"
    PROPOSAL_CREATED = "PROPOSAL_CREATED"
    PROPOSAL_REJECTED = "PROPOSAL_REJECTED"
    BIRTH_CONFLICT_REJECTED = "BIRTH_CONFLICT_REJECTED"
    BIRTH = "BIRTH"
    NATURAL_DEATH = "NATURAL_DEATH"


@dataclass(frozen=True, slots=True)
class MessageTransition:
    message: MessageRecord


@dataclass(frozen=True, slots=True)
class ProposalCreatedTransition:
    proposal: ReproductionProposal


@dataclass(frozen=True, slots=True)
class ProposalRejectedTransition:
    proposal_id: ProposalId
    actor_id: AgentId


@dataclass(frozen=True, slots=True)
class BirthTransition:
    proposal_id: ProposalId
    child: AgentState
    parent_ids: tuple[AgentId, AgentId]
    refractory_until_tick: Tick


@dataclass(frozen=True, slots=True)
class BirthConflictTransition:
    """A rejected candidate classification that leaves its proposal pending."""

    proposal_id: ProposalId
    reason: ConflictReason


@dataclass(frozen=True, slots=True)
class NaturalDeathTransition:
    agent_id: AgentId


TransitionPayload = (
    MessageTransition
    | ProposalCreatedTransition
    | ProposalRejectedTransition
    | BirthTransition
    | BirthConflictTransition
    | NaturalDeathTransition
)


@dataclass(frozen=True, slots=True)
class TransitionFragment:
    fragment_id: FragmentId
    tick: Tick
    kind: TransitionKind
    payload: TransitionPayload

    def __post_init__(self) -> None:
        if not isinstance(self.fragment_id, FragmentId):
            raise TypeError("fragment_id must be a FragmentId")
        if not isinstance(self.tick, Tick):
            raise TypeError("tick must be a Tick")
        if not isinstance(self.kind, TransitionKind):
            raise TypeError("kind must be a TransitionKind")
        expected = {
            TransitionKind.MESSAGE: MessageTransition,
            TransitionKind.PROPOSAL_CREATED: ProposalCreatedTransition,
            TransitionKind.PROPOSAL_REJECTED: ProposalRejectedTransition,
            TransitionKind.BIRTH: BirthTransition,
            TransitionKind.BIRTH_CONFLICT_REJECTED: BirthConflictTransition,
            TransitionKind.NATURAL_DEATH: NaturalDeathTransition,
        }
        if not isinstance(self.payload, expected[self.kind]):
            raise TypeError(f"{self.kind} requires {expected[self.kind].__name__}")
