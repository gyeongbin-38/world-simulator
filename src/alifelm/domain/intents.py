"""Non-authoritative model proposal contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .identifiers import AgentId, IntentId, ProposalId
from .values import StateVersion, Tick


class ActionKind(StrEnum):
    SEND = "SEND"
    PROPOSE = "PROPOSE"
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    WAIT = "WAIT"


@dataclass(frozen=True, slots=True)
class SendAction:
    target_agent_id: AgentId
    body: str

    def __post_init__(self) -> None:
        if not isinstance(self.target_agent_id, AgentId):
            raise TypeError("target_agent_id must be an AgentId")
        if not isinstance(self.body, str):
            raise TypeError("message body must be a string")


@dataclass(frozen=True, slots=True)
class ProposeAction:
    target_agent_id: AgentId

    def __post_init__(self) -> None:
        if not isinstance(self.target_agent_id, AgentId):
            raise TypeError("target_agent_id must be an AgentId")


@dataclass(frozen=True, slots=True)
class AcceptAction:
    proposal_id: ProposalId

    def __post_init__(self) -> None:
        if not isinstance(self.proposal_id, ProposalId):
            raise TypeError("proposal_id must be a ProposalId")


@dataclass(frozen=True, slots=True)
class RejectAction:
    proposal_id: ProposalId

    def __post_init__(self) -> None:
        if not isinstance(self.proposal_id, ProposalId):
            raise TypeError("proposal_id must be a ProposalId")


@dataclass(frozen=True, slots=True)
class WaitAction:
    pass


ActionPayload = SendAction | ProposeAction | AcceptAction | RejectAction | WaitAction


@dataclass(frozen=True, slots=True)
class ActionIntent:
    """One primary action proposal for one agent opportunity."""

    intent_id: IntentId
    actor_id: AgentId
    tick: Tick
    kind: ActionKind
    payload: ActionPayload

    def __post_init__(self) -> None:
        if not isinstance(self.intent_id, IntentId):
            raise TypeError("intent_id must be an IntentId")
        if not isinstance(self.actor_id, AgentId):
            raise TypeError("actor_id must be an AgentId")
        if not isinstance(self.tick, Tick):
            raise TypeError("tick must be a Tick")
        if not isinstance(self.kind, ActionKind):
            raise TypeError("kind must be an ActionKind")
        expected: dict[ActionKind, type[ActionPayload]] = {
            ActionKind.SEND: SendAction,
            ActionKind.PROPOSE: ProposeAction,
            ActionKind.ACCEPT: AcceptAction,
            ActionKind.REJECT: RejectAction,
            ActionKind.WAIT: WaitAction,
        }
        if not isinstance(self.payload, expected[self.kind]):
            raise TypeError(f"{self.kind} requires {expected[self.kind].__name__}")
        if self.kind is ActionKind.PROPOSE:
            assert isinstance(self.payload, ProposeAction)
            if self.payload.target_agent_id == self.actor_id:
                raise ValueError("an agent cannot propose reproduction with itself")


@dataclass(frozen=True, slots=True)
class ValidatedIntent:
    """A valid intent evaluated against one immutable snapshot version."""

    intent: ActionIntent
    validated_state_version: StateVersion

    def __post_init__(self) -> None:
        if not isinstance(self.intent, ActionIntent):
            raise TypeError("intent must be an ActionIntent")
        if not isinstance(self.validated_state_version, StateVersion):
            raise TypeError("validated_state_version must be a StateVersion")


@dataclass(frozen=True, slots=True)
class IntentBatch:
    """Closed same-tick proposals, with at most one primary outcome per actor."""

    tick: Tick
    intents: tuple[ActionIntent, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.tick, Tick):
            raise TypeError("tick must be a Tick")
        intent_ids = [intent.intent_id for intent in self.intents]
        actor_ids = [intent.actor_id for intent in self.intents]
        if any(intent.tick != self.tick for intent in self.intents):
            raise ValueError("all intents in a batch must use the batch tick")
        if len(set(intent_ids)) != len(intent_ids):
            raise ValueError("an intent identity may occur only once in a batch")
        if len(set(actor_ids)) != len(actor_ids):
            raise ValueError("a cognition opportunity yields at most one primary intent")
