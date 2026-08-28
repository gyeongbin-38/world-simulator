"""Positive, agent-scoped visibility projection for EXP-000."""

from __future__ import annotations

from dataclasses import dataclass

from alifelm.domain import AgentId, ProposalState, Tick, is_active
from alifelm.kernel.state import Snapshot

from .types import (
    ContextPolicy,
    DeliveredMessagePayload,
    IncomingProposalPayload,
    OutgoingProposalPayload,
    PeerDirectoryEntry,
    SentMessagePayload,
    SourceBinding,
    SourceKind,
    VisibleRecord,
    VisibleRecordCategory,
)


@dataclass(frozen=True, slots=True)
class ProjectedPeer:
    model_value: PeerDirectoryEntry
    source: SourceBinding


@dataclass(frozen=True, slots=True)
class ProjectedRecord:
    """A safe model projection paired with non-rendered source evidence."""

    model_value: VisibleRecord
    source: SourceBinding
    first_visible_tick: Tick

    def __post_init__(self) -> None:
        if not isinstance(self.model_value, VisibleRecord):
            raise TypeError("model_value must be a VisibleRecord")
        if not isinstance(self.source, SourceBinding):
            raise TypeError("source must be a SourceBinding")
        if not isinstance(self.first_visible_tick, Tick):
            raise TypeError("first_visible_tick must be a Tick")


@dataclass(frozen=True, slots=True)
class VisibilityProjectionResult:
    """Safe projections and researcher-only source bindings for one actor."""

    agent_id: AgentId
    bound_tick: Tick
    age: int
    self_source: SourceBinding
    active_peers: tuple[ProjectedPeer, ...]
    delivered_messages: tuple[ProjectedRecord, ...]
    own_sent_messages: tuple[ProjectedRecord, ...]
    incoming_pending_proposals: tuple[ProjectedRecord, ...]
    outgoing_pending_proposals: tuple[ProjectedRecord, ...]

    @property
    def active_peer_ids(self) -> tuple[AgentId, ...]:
        return tuple(peer.model_value.agent_id for peer in self.active_peers)


class VisibilityProjection:
    """Pure positive projection from one immutable committed snapshot.

    Raw AgentState, MessageRecord, ReproductionProposal, event streams, and
    uncommitted protocol objects are never placed in the result. Hidden source
    metadata needed for traceability is represented only by SourceBinding and
    never copied into ModelInput.
    """

    @staticmethod
    def project(
        snapshot: Snapshot,
        agent_id: AgentId,
        policy: ContextPolicy,
    ) -> VisibilityProjectionResult:
        if not isinstance(snapshot, Snapshot):
            raise TypeError("snapshot must be a Snapshot")
        if not isinstance(agent_id, AgentId):
            raise TypeError("agent_id must be an AgentId")
        if not isinstance(policy, ContextPolicy):
            raise TypeError("policy must be a ContextPolicy")

        agent = snapshot.agent(agent_id)
        if agent is None:
            raise ValueError("context actor must be present in the bound snapshot")
        if not is_active(agent, snapshot.tick):
            raise ValueError("context actor must be active at the bound snapshot")

        def state_source(source_id: str, commit_tick: Tick | None = None) -> SourceBinding:
            return SourceBinding(
                source_kind=SourceKind.STATE,
                source_id=source_id,
                source_state_version=snapshot.state_version,
                commit_id=None,
                commit_tick=commit_tick,
                commit_order=None,
                artifact_refs=(),
            )

        active_peers = tuple(
            ProjectedPeer(
                model_value=PeerDirectoryEntry(other.agent_id),
                source=state_source(other.agent_id.value),
            )
            for other in snapshot.agents
            if other.agent_id != agent_id and is_active(other, snapshot.tick)
        )

        delivered_messages = tuple(
            ProjectedRecord(
                model_value=VisibleRecord(
                    category=VisibleRecordCategory.DELIVERED_MESSAGE,
                    payload=DeliveredMessagePayload(message.sender_id, message.body),
                ),
                source=state_source(message.message_id.value, message.committed_tick),
                first_visible_tick=message.available_tick,
            )
            for message in snapshot.messages
            if message.recipient_id == agent_id
            and message.available_tick <= snapshot.tick
            and message.committed_tick < snapshot.tick
        )
        own_sent_messages = tuple(
            ProjectedRecord(
                model_value=VisibleRecord(
                    category=VisibleRecordCategory.SENT_MESSAGE,
                    payload=SentMessagePayload(message.recipient_id, message.body),
                ),
                source=state_source(message.message_id.value, message.committed_tick),
                first_visible_tick=Tick(message.committed_tick + 1),
            )
            for message in snapshot.messages
            if message.sender_id == agent_id and message.committed_tick < snapshot.tick
        )

        visible_proposals = tuple(
            proposal
            for proposal in snapshot.proposals
            if proposal.visible_at(snapshot.tick)
            and proposal.state is ProposalState.PENDING
            and (proposal.proposer_id == agent_id or proposal.target_id == agent_id)
        )
        incoming_pending_proposals = tuple(
            ProjectedRecord(
                model_value=VisibleRecord(
                    category=VisibleRecordCategory.INCOMING_PROPOSAL,
                    payload=IncomingProposalPayload(
                        proposal.proposal_id.value, proposal.proposer_id
                    ),
                ),
                source=state_source(proposal.proposal_id.value, proposal.created_tick),
                first_visible_tick=Tick(proposal.created_tick + 1),
            )
            for proposal in visible_proposals
            if proposal.target_id == agent_id
        )
        outgoing_pending_proposals = tuple(
            ProjectedRecord(
                model_value=VisibleRecord(
                    category=VisibleRecordCategory.OUTGOING_PROPOSAL,
                    payload=OutgoingProposalPayload(
                        proposal.proposal_id.value, proposal.target_id
                    ),
                ),
                source=state_source(proposal.proposal_id.value, proposal.created_tick),
                first_visible_tick=Tick(proposal.created_tick + 1),
            )
            for proposal in visible_proposals
            if proposal.proposer_id == agent_id
        )

        return VisibilityProjectionResult(
            agent_id=agent_id,
            bound_tick=snapshot.tick,
            age=int(snapshot.tick - agent.first_active_tick),
            self_source=state_source(agent_id.value),
            active_peers=active_peers,
            delivered_messages=delivered_messages,
            own_sent_messages=own_sent_messages,
            incoming_pending_proposals=incoming_pending_proposals,
            outgoing_pending_proposals=outgoing_pending_proposals,
        )


def project_visibility(
    snapshot: Snapshot,
    agent_id: AgentId,
    policy: ContextPolicy,
) -> VisibilityProjectionResult:
    return VisibilityProjection.project(snapshot, agent_id, policy)

