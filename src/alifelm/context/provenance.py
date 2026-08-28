"""Executable validation of ContextPack model-item provenance."""

from __future__ import annotations

from alifelm.kernel.state import Snapshot

from .types import ContextPack, ProjectionKind


def expected_model_paths(pack: ContextPack) -> tuple[str, ...]:
    model = pack.model_input
    paths = ["/model_input/stable_prefix", "/model_input/current_self"]
    paths.extend(
        f"/model_input/peer_directory/{index}"
        for index in range(len(model.peer_directory))
    )
    paths.extend(
        f"/model_input/newly_delivered/{index}"
        for index in range(len(model.newly_delivered))
    )
    paths.extend(
        f"/model_input/visible_protocol_state/{index}"
        for index in range(len(model.visible_protocol_state))
    )
    paths.extend(
        f"/model_input/prior_history/{index}"
        for index in range(len(model.prior_history))
    )
    return tuple(paths)


def validate_context_provenance(pack: ContextPack, snapshot: Snapshot) -> None:
    if not isinstance(pack, ContextPack):
        raise TypeError("pack must be a ContextPack")
    if not isinstance(snapshot, Snapshot):
        raise TypeError("snapshot must be a Snapshot")
    if pack.evidence.run_id != snapshot.run_id:
        raise ValueError("ContextPack provenance belongs to another run")
    if pack.evidence.bound_tick != int(snapshot.tick):
        raise ValueError("ContextPack provenance binds another tick")
    if pack.evidence.bound_state_version != int(snapshot.state_version):
        raise ValueError("ContextPack provenance binds another state version")
    if pack.evidence.bound_state_hash != snapshot.state_hash():
        raise ValueError("ContextPack provenance binds another state hash")

    expected = expected_model_paths(pack)
    actual = tuple(item.model_path for item in pack.evidence.provenance)
    if actual != expected or len(set(actual)) != len(actual):
        raise ValueError("every model-visible item must have one ordered provenance entry")

    agent_ids = {agent.agent_id.value for agent in snapshot.agents}
    message_ids = {message.message_id.value for message in snapshot.messages}
    proposal_ids = {proposal.proposal_id.value for proposal in snapshot.proposals}
    event_ids = {event.event_id.value for event in snapshot.events}
    for item in pack.evidence.provenance:
        if item.source_state_version > int(snapshot.state_version):
            raise ValueError("provenance cannot reference a future state version")
        if item.projection_kind is ProjectionKind.STABLE_PREFIX:
            if item.source_id != pack.evidence.action_presentation_policy_id:
                raise ValueError("stable prefix provenance is not version-pinned")
        elif item.projection_kind in (
            ProjectionKind.SELF_STATE,
            ProjectionKind.PEER_DIRECTORY_ENTRY,
        ):
            if item.source_id not in agent_ids:
                raise ValueError("agent projection source does not resolve")
        elif item.projection_kind in (
            ProjectionKind.DELIVERED_MESSAGE,
            ProjectionKind.SENT_MESSAGE,
        ):
            if item.source_id not in message_ids:
                raise ValueError("message projection source does not resolve")
        elif item.projection_kind in (
            ProjectionKind.INCOMING_PROPOSAL,
            ProjectionKind.OUTGOING_PROPOSAL,
        ):
            if item.source_id not in proposal_ids:
                raise ValueError("proposal projection source does not resolve")
        elif item.projection_kind is ProjectionKind.PROTOCOL_RESOLUTION:
            if (
                item.source_id not in proposal_ids
                and item.source_id not in event_ids
                and not item.artifact_refs
            ):
                raise ValueError("resolution projection source does not resolve")

