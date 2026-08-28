"""Immutable canonical snapshots for the in-memory run."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json

from alifelm.domain import (
    AgentState,
    LifecycleState,
    MessageRecord,
    ProposalState,
    ReproductionProposal,
    RunId,
    StateVersion,
    Tick,
    validate_fixed_global_lifespan,
)
from alifelm.domain.records import DomainEvent


class RunStatus(StrEnum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CENSORED = "CENSORED"


@dataclass(frozen=True, slots=True)
class Snapshot:
    """The immutable ``S_t`` / ``S_(t+1)`` value exchanged by kernel phases."""

    run_id: RunId
    tick: Tick
    state_version: StateVersion
    agents: tuple[AgentState, ...]
    messages: tuple[MessageRecord, ...]
    proposals: tuple[ReproductionProposal, ...]
    events: tuple[DomainEvent, ...]
    status: RunStatus = RunStatus.RUNNING

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, RunId):
            raise TypeError("run_id must be a RunId")
        if not isinstance(self.tick, Tick):
            raise TypeError("tick must be a Tick")
        if not isinstance(self.state_version, StateVersion):
            raise TypeError("state_version must be a StateVersion")
        if not isinstance(self.status, RunStatus):
            raise TypeError("status must be a RunStatus")
        if not isinstance(self.agents, tuple) or any(
            not isinstance(agent, AgentState) for agent in self.agents
        ):
            raise TypeError("agents must be a tuple of AgentState values")
        if any(agent.state is not LifecycleState.ALIVE for agent in self.agents):
            raise ValueError("dead agents are removed from the next canonical snapshot")
        agent_ids = [agent.agent_id for agent in self.agents]
        if len(set(agent_ids)) != len(agent_ids):
            raise ValueError("agent IDs must be unique in a snapshot")
        if tuple(agent_ids) != tuple(sorted(agent_ids, key=str)):
            raise ValueError("agents must use canonical ID ordering")
        validate_fixed_global_lifespan(self.agents)

        if not isinstance(self.messages, tuple) or any(
            not isinstance(message, MessageRecord) for message in self.messages
        ):
            raise TypeError("messages must be a tuple of MessageRecord values")
        message_ids = [message.message_id for message in self.messages]
        if len(set(message_ids)) != len(message_ids):
            raise ValueError("message IDs must be unique in a snapshot")
        if any(message.available_tick > self.tick for message in self.messages):
            raise ValueError("a snapshot cannot contain a message before its availability tick")

        if not isinstance(self.proposals, tuple) or any(
            not isinstance(proposal, ReproductionProposal)
            for proposal in self.proposals
        ):
            raise TypeError("proposals must be a tuple of ReproductionProposal values")
        proposal_ids = [proposal.proposal_id for proposal in self.proposals]
        if len(set(proposal_ids)) != len(proposal_ids):
            raise ValueError("proposal IDs must be unique in a snapshot")
        if any(proposal.created_tick >= self.tick for proposal in self.proposals):
            raise ValueError("a proposal is visible in the snapshot only after its commit tick")

        if not isinstance(self.events, tuple) or any(
            not isinstance(event, DomainEvent) for event in self.events
        ):
            raise TypeError("events must be a tuple of DomainEvent values")
        event_ids = [event.event_id for event in self.events]
        if len(set(event_ids)) != len(event_ids):
            raise ValueError("event IDs must be unique in a snapshot")
        if any(event.commit_tick >= self.tick for event in self.events):
            raise ValueError("a snapshot cannot publish an event from its open tick")
        event_order = [(event.commit_tick, event.commit_order) for event in self.events]
        if event_order != sorted(event_order):
            raise ValueError("events must use committed causal ordering")

    def agent(self, agent_id):
        return next((agent for agent in self.agents if agent.agent_id == agent_id), None)

    def messages_for(self, recipient_id):
        return tuple(
            message for message in self.messages if message.recipient_id == recipient_id
        )

    def pending_proposals_for(self, target_id):
        return tuple(
            proposal
            for proposal in self.proposals
            if proposal.target_id == target_id
            and proposal.state is ProposalState.PENDING
            and proposal.visible_at(self.tick)
        )

    def state_hash(self) -> str:
        """Hash canonical values in stable order, excluding object identity."""

        value = {
            "run_id": str(self.run_id),
            "tick": int(self.tick),
            "state_version": int(self.state_version),
            "status": self.status.value,
            "agents": [
                {
                    "agent_id": str(agent.agent_id),
                    "birth_tick": int(agent.birth_tick),
                    "first_active_tick": int(agent.first_active_tick),
                    "lifespan_ticks": int(agent.lifespan_ticks),
                    "maturity_delay_ticks": int(agent.maturity_delay_ticks),
                    "state": agent.state.value,
                    "refractory_until_tick": (
                        int(agent.refractory_until_tick)
                        if agent.refractory_until_tick is not None
                        else None
                    ),
                }
                for agent in sorted(self.agents, key=lambda item: item.agent_id.value)
            ],
            "messages": [
                {
                    "message_id": str(message.message_id),
                    "sender_id": str(message.sender_id),
                    "recipient_id": str(message.recipient_id),
                    "body": message.body,
                    "committed_tick": int(message.committed_tick),
                    "available_tick": int(message.available_tick),
                }
                for message in sorted(
                    self.messages, key=lambda item: item.message_id.value
                )
            ],
            "proposals": [
                {
                    "proposal_id": str(proposal.proposal_id),
                    "proposer_id": str(proposal.proposer_id),
                    "target_id": str(proposal.target_id),
                    "created_tick": int(proposal.created_tick),
                    "state": proposal.state.value,
                    "expires_at_tick": (
                        int(proposal.expires_at_tick)
                        if proposal.expires_at_tick is not None
                        else None
                    ),
                }
                for proposal in sorted(
                    self.proposals, key=lambda item: item.proposal_id.value
                )
            ],
            "events": [
                {
                    "event_id": str(event.event_id),
                    "event_type": event.event_type,
                    "commit_tick": int(event.commit_tick),
                    "commit_order": event.commit_order,
                    "artifact_refs": [
                        {"artifact_id": str(ref.artifact_id), "digest": ref.digest}
                        for ref in event.artifact_refs
                    ],
                }
                for event in sorted(
                    self.events,
                    key=lambda item: (
                        int(item.commit_tick), item.commit_order, item.event_id.value
                    ),
                )
            ],
        }
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
