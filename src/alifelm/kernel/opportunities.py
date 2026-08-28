"""Deterministic cognition opportunities for one immutable snapshot."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

from alifelm.domain import (
    AgentId,
    MessageRecord,
    OpportunityId,
    ProposalState,
    ReproductionProposal,
    RunId,
    Tick,
    is_active,
)

from .state import Snapshot


@dataclass(frozen=True, slots=True)
class CognitionFixture:
    """Small immutable fake-runtime fixture, not the ARC-300 Context Fabric."""

    tick: Tick
    agent_id: AgentId
    visible_agent_ids: tuple[AgentId, ...]
    messages: tuple[MessageRecord, ...]
    proposals: tuple[ReproductionProposal, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.tick, Tick):
            raise TypeError("fixture tick must be a Tick")
        if not isinstance(self.agent_id, AgentId):
            raise TypeError("fixture agent_id must be an AgentId")
        if not isinstance(self.visible_agent_ids, tuple) or any(
            not isinstance(agent_id, AgentId) for agent_id in self.visible_agent_ids
        ):
            raise TypeError("visible_agent_ids must be a tuple of AgentId values")
        if tuple(self.visible_agent_ids) != tuple(sorted(self.visible_agent_ids, key=str)):
            raise ValueError("visible_agent_ids must use canonical ID ordering")
        if len(set(self.visible_agent_ids)) != len(self.visible_agent_ids):
            raise ValueError("visible_agent_ids must be unique")
        if self.agent_id not in self.visible_agent_ids:
            raise ValueError("the opportunity actor must be visible to itself")
        if not isinstance(self.messages, tuple) or any(
            not isinstance(message, MessageRecord) for message in self.messages
        ):
            raise TypeError("messages must be a tuple of MessageRecord values")
        if any(message.recipient_id != self.agent_id for message in self.messages):
            raise ValueError("a fixture may contain only the actor's messages")
        if any(message.available_tick > self.tick for message in self.messages):
            raise ValueError("a fixture cannot contain a not-yet-available message")
        if not isinstance(self.proposals, tuple) or any(
            not isinstance(proposal, ReproductionProposal)
            for proposal in self.proposals
        ):
            raise TypeError("proposals must be a tuple of ReproductionProposal values")
        if any(
            proposal.target_id != self.agent_id
            or proposal.state is not ProposalState.PENDING
            or not proposal.visible_at(self.tick)
            for proposal in self.proposals
        ):
            raise ValueError("a fixture may contain only visible pending target proposals")

    @property
    def active_agent_ids(self) -> tuple[AgentId, ...]:
        """Compatibility name for the bounded active-agent directory."""

        return self.visible_agent_ids


@dataclass(frozen=True, slots=True)
class CognitionOpportunity:
    """Exactly one opportunity for one active agent in one snapshot."""

    opportunity_id: OpportunityId
    run_id: RunId
    tick: Tick
    agent_id: AgentId
    snapshot: Snapshot
    fixture: CognitionFixture

    def __post_init__(self) -> None:
        if not isinstance(self.opportunity_id, OpportunityId):
            raise TypeError("opportunity_id must be an OpportunityId")
        if self.run_id != self.snapshot.run_id:
            raise ValueError("opportunity run_id must match its snapshot")
        if self.tick != self.snapshot.tick:
            raise ValueError("opportunity tick must match its snapshot")
        if self.agent_id != self.fixture.agent_id or self.tick != self.fixture.tick:
            raise ValueError("opportunity and fixture identity must match")
        if self.snapshot.agent(self.agent_id) is None:
            raise ValueError("opportunity actor must be present in the snapshot")


class EqualOpportunityScheduler:
    """Enumerate one stable opportunity per active agent in canonical order."""

    def enumerate(self, snapshot: Snapshot) -> tuple[CognitionOpportunity, ...]:
        active_agents = tuple(
            sorted(
                (
                    agent
                    for agent in snapshot.agents
                    if is_active(agent, snapshot.tick)
                ),
                key=lambda agent: str(agent.agent_id),
            )
        )
        visible_agent_ids = tuple(agent.agent_id for agent in active_agents)
        opportunities: list[CognitionOpportunity] = []
        for agent in active_agents:
            fixture = CognitionFixture(
                tick=snapshot.tick,
                agent_id=agent.agent_id,
                visible_agent_ids=visible_agent_ids,
                messages=snapshot.messages_for(agent.agent_id),
                proposals=snapshot.pending_proposals_for(agent.agent_id),
            )
            opportunities.append(
                CognitionOpportunity(
                    opportunity_id=_opportunity_id(
                        snapshot.run_id, snapshot.tick, agent.agent_id
                    ),
                    run_id=snapshot.run_id,
                    tick=snapshot.tick,
                    agent_id=agent.agent_id,
                    snapshot=snapshot,
                    fixture=fixture,
                )
            )
        return tuple(opportunities)


def _opportunity_id(run_id: RunId, tick: Tick, agent_id: AgentId) -> OpportunityId:
    value = f"{run_id.value}|{int(tick)}|{agent_id.value}"
    return OpportunityId(hashlib.sha256(value.encode("utf-8")).hexdigest())
