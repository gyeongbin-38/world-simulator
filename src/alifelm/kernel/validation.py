"""Pure intent validation against one immutable snapshot."""

from __future__ import annotations

from alifelm.domain import (
    AcceptAction,
    ActionKind,
    ActionIntent,
    AgentState,
    ProposeAction,
    ProposalState,
    RejectAction,
    SendAction,
    StateVersion,
    can_reproduce,
)

from .run import SimulationRun
from .state import Snapshot


class LawValidator:
    """Keep only intents permitted by the current canonical snapshot."""

    def validate(
        self,
        batch,
        snapshot: Snapshot,
        run: SimulationRun,
    ):
        if batch.tick != snapshot.tick:
            raise ValueError("intent batch and snapshot ticks must match")
        if snapshot.run_id != run.run_id:
            raise ValueError("snapshot and run must belong to the same run")
        validated = []
        for intent in sorted(batch.intents, key=lambda item: str(item.actor_id)):
            actor = snapshot.agent(intent.actor_id)
            if actor is None or not actor.is_active(snapshot.tick):
                continue
            if intent.tick != snapshot.tick:
                continue
            if self._is_valid(intent, actor, snapshot):
                validated.append(
                    _validated(intent, snapshot.state_version)
                )
        return tuple(validated)

    def _is_valid(self, intent: ActionIntent, actor: AgentState, snapshot: Snapshot) -> bool:
        if intent.kind is ActionKind.WAIT:
            return True
        if intent.kind is ActionKind.SEND:
            assert isinstance(intent.payload, SendAction)
            target = snapshot.agent(intent.payload.target_agent_id)
            return (
                target is not None
                and target.agent_id != actor.agent_id
                and target.is_active(snapshot.tick)
            )
        if intent.kind is ActionKind.PROPOSE:
            assert isinstance(intent.payload, ProposeAction)
            target = snapshot.agent(intent.payload.target_agent_id)
            return target is not None and can_reproduce(actor, snapshot.tick) and can_reproduce(
                target, snapshot.tick
            )
        if intent.kind is ActionKind.ACCEPT:
            assert isinstance(intent.payload, AcceptAction)
            proposal = _proposal(snapshot, intent.payload.proposal_id)
            if proposal is None or proposal.state is not ProposalState.PENDING:
                return False
            proposer = snapshot.agent(proposal.proposer_id)
            return (
                proposal.target_id == actor.agent_id
                and proposal.visible_at(snapshot.tick)
                and proposer is not None
                and can_reproduce(actor, snapshot.tick)
                and can_reproduce(proposer, snapshot.tick)
            )
        if intent.kind is ActionKind.REJECT:
            assert isinstance(intent.payload, RejectAction)
            proposal = _proposal(snapshot, intent.payload.proposal_id)
            return bool(
                proposal is not None
                and proposal.state is ProposalState.PENDING
                and proposal.target_id == actor.agent_id
                and proposal.visible_at(snapshot.tick)
            )
        return False


def _proposal(snapshot: Snapshot, proposal_id):
    return next(
        (proposal for proposal in snapshot.proposals if proposal.proposal_id == proposal_id),
        None,
    )


def _validated(intent: ActionIntent, state_version: StateVersion):
    from alifelm.domain import ValidatedIntent

    return ValidatedIntent(intent=intent, validated_state_version=state_version)
