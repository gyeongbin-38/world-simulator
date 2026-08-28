"""Deterministic JSON serialization for durable I-03 records."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from alifelm.domain import (
    AcceptAction,
    ActionIntent,
    ActionKind,
    AgentId,
    AgentState,
    ArtifactId,
    ArtifactRef,
    Duration,
    DomainEvent,
    EventId,
    LifecycleState,
    MessageId,
    MessageRecord,
    ProposalId,
    ProposalState,
    ProposeAction,
    RejectAction,
    ReproductionProposal,
    SendAction,
    StateVersion,
    Tick,
    WaitAction,
)
from alifelm.kernel import (
    CommitRequest,
    RunStatus,
    Snapshot,
    TransitionFragment,
    TransitionKind,
)
from alifelm.kernel.transitions import (
    BirthConflictTransition,
    BirthTransition,
    MessageTransition,
    NaturalDeathTransition,
    ProposalCreatedTransition,
    ProposalRejectedTransition,
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def artifact_ref_to_dict(reference: ArtifactRef) -> dict[str, str]:
    return {"artifact_id": reference.artifact_id.value, "digest": reference.digest}


def artifact_ref_from_dict(value: dict[str, Any]) -> ArtifactRef:
    return ArtifactRef(ArtifactId(value["artifact_id"]), value["digest"])


def agent_to_dict(agent: AgentState) -> dict[str, Any]:
    return {
        "agent_id": agent.agent_id.value,
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


def agent_from_dict(value: dict[str, Any]) -> AgentState:
    refractory = value["refractory_until_tick"]
    return AgentState(
        agent_id=AgentId(value["agent_id"]),
        birth_tick=Tick(value["birth_tick"]),
        first_active_tick=Tick(value["first_active_tick"]),
        lifespan_ticks=Duration(value["lifespan_ticks"]),
        maturity_delay_ticks=Duration(value["maturity_delay_ticks"]),
        state=LifecycleState(value["state"]),
        refractory_until_tick=Tick(refractory) if refractory is not None else None,
    )


def message_to_dict(message: MessageRecord) -> dict[str, Any]:
    return {
        "message_id": message.message_id.value,
        "sender_id": message.sender_id.value,
        "recipient_id": message.recipient_id.value,
        "body": message.body,
        "committed_tick": int(message.committed_tick),
        "available_tick": int(message.available_tick),
    }


def message_from_dict(value: dict[str, Any]) -> MessageRecord:
    return MessageRecord(
        message_id=MessageId(value["message_id"]),
        sender_id=AgentId(value["sender_id"]),
        recipient_id=AgentId(value["recipient_id"]),
        body=value["body"],
        committed_tick=Tick(value["committed_tick"]),
        available_tick=Tick(value["available_tick"]),
    )


def proposal_to_dict(proposal: ReproductionProposal) -> dict[str, Any]:
    return {
        "proposal_id": proposal.proposal_id.value,
        "proposer_id": proposal.proposer_id.value,
        "target_id": proposal.target_id.value,
        "created_tick": int(proposal.created_tick),
        "state": proposal.state.value,
        "expires_at_tick": (
            int(proposal.expires_at_tick)
            if proposal.expires_at_tick is not None
            else None
        ),
    }


def proposal_from_dict(value: dict[str, Any]) -> ReproductionProposal:
    expires = value["expires_at_tick"]
    return ReproductionProposal(
        proposal_id=ProposalId(value["proposal_id"]),
        proposer_id=AgentId(value["proposer_id"]),
        target_id=AgentId(value["target_id"]),
        created_tick=Tick(value["created_tick"]),
        state=ProposalState(value["state"]),
        expires_at_tick=Tick(expires) if expires is not None else None,
    )


def event_to_dict(event: DomainEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id.value,
        "event_type": event.event_type,
        "commit_tick": int(event.commit_tick),
        "commit_order": event.commit_order,
        "artifact_refs": [artifact_ref_to_dict(ref) for ref in event.artifact_refs],
    }


def event_from_dict(value: dict[str, Any]) -> DomainEvent:
    return DomainEvent(
        event_id=EventId(value["event_id"]),
        event_type=value["event_type"],
        commit_tick=Tick(value["commit_tick"]),
        commit_order=value["commit_order"],
        artifact_refs=tuple(
            artifact_ref_from_dict(ref) for ref in value["artifact_refs"]
        ),
    )


def snapshot_to_dict(snapshot: Snapshot) -> dict[str, Any]:
    return {
        "run_id": snapshot.run_id.value,
        "tick": int(snapshot.tick),
        "state_version": int(snapshot.state_version),
        "agents": [agent_to_dict(agent) for agent in snapshot.agents],
        "messages": [message_to_dict(message) for message in snapshot.messages],
        "proposals": [proposal_to_dict(proposal) for proposal in snapshot.proposals],
        "events": [event_to_dict(event) for event in snapshot.events],
        "status": snapshot.status.value,
    }


def snapshot_from_dict(value: dict[str, Any]) -> Snapshot:
    from alifelm.domain import RunId

    return Snapshot(
        run_id=RunId(value["run_id"]),
        tick=Tick(value["tick"]),
        state_version=StateVersion(value["state_version"]),
        agents=tuple(agent_from_dict(agent) for agent in value["agents"]),
        messages=tuple(message_from_dict(message) for message in value["messages"]),
        proposals=tuple(proposal_from_dict(proposal) for proposal in value["proposals"]),
        events=tuple(event_from_dict(event) for event in value["events"]),
        status=RunStatus(value["status"]),
    )


def _action_to_dict(intent: ActionIntent) -> dict[str, Any]:
    payload: dict[str, Any]
    if intent.kind is ActionKind.SEND:
        assert isinstance(intent.payload, SendAction)
        payload = {"target_agent_id": intent.payload.target_agent_id.value, "body": intent.payload.body}
    elif intent.kind is ActionKind.PROPOSE:
        assert isinstance(intent.payload, ProposeAction)
        payload = {"target_agent_id": intent.payload.target_agent_id.value}
    elif intent.kind in (ActionKind.ACCEPT, ActionKind.REJECT):
        assert isinstance(intent.payload, (AcceptAction, RejectAction))
        payload = {"proposal_id": intent.payload.proposal_id.value}
    else:
        assert isinstance(intent.payload, WaitAction)
        payload = {}
    return {
        "intent_id": intent.intent_id.value,
        "actor_id": intent.actor_id.value,
        "tick": int(intent.tick),
        "kind": intent.kind.value,
        "payload": payload,
    }


def fragment_to_dict(fragment: TransitionFragment) -> dict[str, Any]:
    payload = fragment.payload
    if isinstance(payload, MessageTransition):
        value = {"message": message_to_dict(payload.message)}
    elif isinstance(payload, ProposalCreatedTransition):
        value = {"proposal": proposal_to_dict(payload.proposal)}
    elif isinstance(payload, ProposalRejectedTransition):
        value = {
            "proposal_id": payload.proposal_id.value,
            "actor_id": payload.actor_id.value,
        }
    elif isinstance(payload, BirthConflictTransition):
        value = {"proposal_id": payload.proposal_id.value, "reason": payload.reason.value}
    elif isinstance(payload, BirthTransition):
        value = {
            "proposal_id": payload.proposal_id.value,
            "child": agent_to_dict(payload.child),
            "parent_ids": [parent.value for parent in payload.parent_ids],
            "refractory_until_tick": int(payload.refractory_until_tick),
        }
    else:
        assert isinstance(payload, NaturalDeathTransition)
        value = {"agent_id": payload.agent_id.value}
    return {
        "fragment_id": fragment.fragment_id.value,
        "tick": int(fragment.tick),
        "kind": fragment.kind.value,
        "payload": value,
    }


def commit_request_to_dict(
    request: CommitRequest,
    artifact_refs: tuple[ArtifactRef, ...] = (),
) -> dict[str, Any]:
    return {
        "run_id": request.run_id.value,
        "tick": int(request.tick),
        "expected_state_version": int(request.expected_state_version),
        "fragments": [
            fragment_to_dict(fragment)
            for fragment in sorted(
                request.fragments,
                key=lambda fragment: (fragment.kind.value, fragment.fragment_id.value),
            )
        ],
        "artifact_refs": [
            artifact_ref_to_dict(reference)
            for reference in sorted(artifact_refs, key=lambda ref: (ref.artifact_id.value, ref.digest))
        ],
    }


def transition_digest(
    request: CommitRequest,
    artifact_refs: tuple[ArtifactRef, ...] = (),
) -> str:
    return digest_value(commit_request_to_dict(request, artifact_refs))
