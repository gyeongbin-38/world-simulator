"""In-memory atomic commit boundary for the deterministic vertical slice."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
import hashlib

from alifelm.domain import (
    AgentId,
    AgentState,
    ConflictReason,
    DomainEvent,
    EventId,
    LifecycleState,
    ProposalState,
    RunId,
    StateVersion,
    Tick,
    can_reproduce,
    is_active,
    should_die_after_tick,
)

from .run import SimulationRun
from .state import RunStatus, Snapshot
from .transitions import (
    BirthConflictTransition,
    BirthTransition,
    MessageTransition,
    NaturalDeathTransition,
    ProposalCreatedTransition,
    ProposalRejectedTransition,
    TransitionFragment,
    TransitionKind,
)


class CommitError(StrEnum):
    RUN_NOT_RUNNING = "RUN_NOT_RUNNING"
    RUN_ID_MISMATCH = "RUN_ID_MISMATCH"
    TICK_MISMATCH = "TICK_MISMATCH"
    STATE_VERSION_MISMATCH = "STATE_VERSION_MISMATCH"
    INVALID_TRANSITION = "INVALID_TRANSITION"


@dataclass(frozen=True, slots=True)
class CommitRequest:
    run_id: RunId
    tick: Tick
    expected_state_version: StateVersion
    fragments: tuple[TransitionFragment, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, RunId):
            raise TypeError("run_id must be a RunId")
        if not isinstance(self.tick, Tick):
            raise TypeError("tick must be a Tick")
        if not isinstance(self.expected_state_version, StateVersion):
            raise TypeError("expected_state_version must be a StateVersion")
        if not isinstance(self.fragments, tuple) or any(
            not isinstance(fragment, TransitionFragment) for fragment in self.fragments
        ):
            raise TypeError("fragments must be a tuple of TransitionFragment values")


@dataclass(frozen=True, slots=True)
class CommitResult:
    committed: bool
    snapshot: Snapshot
    events: tuple[DomainEvent, ...]
    error: CommitError | None = None
    capacity_censored: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.committed, bool):
            raise TypeError("committed must be a bool")
        if not isinstance(self.snapshot, Snapshot):
            raise TypeError("snapshot must be a Snapshot")
        if not isinstance(self.events, tuple) or any(
            not isinstance(event, DomainEvent) for event in self.events
        ):
            raise TypeError("events must be a tuple of DomainEvent values")
        if self.committed and self.error is not None:
            raise ValueError("a committed result cannot carry an error")
        if not self.committed and self.capacity_censored:
            raise ValueError("a failed result cannot be capacity censored")


class _InvalidTransition(Exception):
    pass


class InMemoryCommitCoordinator:
    """The only I-02 component allowed to publish a next canonical snapshot."""

    def commit(
        self,
        run: SimulationRun,
        request: CommitRequest,
        *,
        artifact_refs: tuple = (),
        fault_injector=None,
    ) -> CommitResult:
        # The optional hook is an infrastructure-test seam.  It does not add
        # a simulation transition or alter the canonical I-02 semantics.
        if fault_injector is not None:
            fault_injector.check("F5_BEFORE_COMMIT")
        prior = run.snapshot
        if prior.status is not RunStatus.RUNNING:
            return _failure(prior, CommitError.RUN_NOT_RUNNING)
        if request.run_id != run.run_id:
            return _failure(prior, CommitError.RUN_ID_MISMATCH)
        if request.tick != prior.tick:
            return _failure(prior, CommitError.TICK_MISMATCH)
        if request.expected_state_version != prior.state_version:
            return _failure(prior, CommitError.STATE_VERSION_MISMATCH)

        try:
            fragments = _canonical_fragments(request.fragments)
            self._validate_fragments(run, prior, request.tick, fragments)
            if _would_exceed_capacity(run, prior, fragments):
                result = self._censor_for_capacity(run, prior, request.tick)
            else:
                result = self._apply(run, prior, request.tick, fragments)
        except _InvalidTransition:
            return _failure(prior, CommitError.INVALID_TRANSITION)

        run._publish_snapshot(result.snapshot, request.expected_state_version)
        return result

    def _validate_fragments(
        self,
        run: SimulationRun,
        snapshot: Snapshot,
        tick: Tick,
        fragments: tuple[TransitionFragment, ...],
    ) -> None:
        fragment_ids = [fragment.fragment_id for fragment in fragments]
        if len(set(fragment_ids)) != len(fragment_ids):
            raise _InvalidTransition

        created_proposals: set = set()
        rejected_proposals: set = set()
        born_proposals: set = set()
        death_agents: set[AgentId] = set()
        birth_parent_ids: set[AgentId] = set()
        birth_child_ids: set[AgentId] = set()
        current_proposals = {proposal.proposal_id: proposal for proposal in snapshot.proposals}
        current_agents = {agent.agent_id: agent for agent in snapshot.agents}

        for fragment in fragments:
            if fragment.tick != tick:
                raise _InvalidTransition
            payload = fragment.payload
            if fragment.kind is TransitionKind.MESSAGE:
                assert isinstance(payload, MessageTransition)
                message = payload.message
                if message.committed_tick != tick or message.message_id in {
                    existing.message_id for existing in snapshot.messages
                }:
                    raise _InvalidTransition
                if (
                    not _active(current_agents.get(message.sender_id), tick)
                    or not _active(current_agents.get(message.recipient_id), tick)
                ):
                    raise _InvalidTransition
            elif fragment.kind is TransitionKind.PROPOSAL_CREATED:
                assert isinstance(payload, ProposalCreatedTransition)
                proposal = payload.proposal
                if (
                    proposal.created_tick != tick
                    or proposal.state is not ProposalState.PENDING
                    or proposal.proposal_id in current_proposals
                    or proposal.proposal_id in created_proposals
                ):
                    raise _InvalidTransition
                proposer = current_agents.get(proposal.proposer_id)
                target = current_agents.get(proposal.target_id)
                if (
                    not _active(proposer, tick)
                    or not _active(target, tick)
                    or not _reproductive(proposer, tick)
                    or not _reproductive(target, tick)
                ):
                    raise _InvalidTransition
                created_proposals.add(proposal.proposal_id)
            elif fragment.kind is TransitionKind.PROPOSAL_REJECTED:
                assert isinstance(payload, ProposalRejectedTransition)
                proposal = current_proposals.get(payload.proposal_id)
                if (
                    proposal is None
                    or proposal.state is not ProposalState.PENDING
                    or not proposal.visible_at(tick)
                    or proposal.target_id != payload.actor_id
                    or not _active(current_agents.get(payload.actor_id), tick)
                    or payload.proposal_id in rejected_proposals
                ):
                    raise _InvalidTransition
                rejected_proposals.add(payload.proposal_id)
            elif fragment.kind is TransitionKind.BIRTH_CONFLICT_REJECTED:
                assert isinstance(payload, BirthConflictTransition)
                proposal = current_proposals.get(payload.proposal_id)
                if (
                    proposal is None
                    or proposal.state is not ProposalState.PENDING
                    or not proposal.visible_at(tick)
                    or payload.reason is not ConflictReason.MULTI_BIRTH_BOUNDARY_CONFLICT
                    or payload.proposal_id in born_proposals
                ):
                    raise _InvalidTransition
                if not _reproductive(current_agents.get(proposal.proposer_id), tick) or not _reproductive(
                    current_agents.get(proposal.target_id), tick
                ):
                    raise _InvalidTransition
                # This is candidate rejection only.  The proposal remains PENDING.
                born_proposals.add(payload.proposal_id)
            elif fragment.kind is TransitionKind.BIRTH:
                assert isinstance(payload, BirthTransition)
                proposal = current_proposals.get(payload.proposal_id)
                if proposal is None or proposal.state is not ProposalState.PENDING:
                    raise _InvalidTransition
                if (
                    proposal.proposer_id,
                    proposal.target_id,
                ) != payload.parent_ids:
                    raise _InvalidTransition
                if not proposal.visible_at(tick):
                    raise _InvalidTransition
                if payload.child.birth_tick != tick or payload.child.first_active_tick != Tick(tick + 1):
                    raise _InvalidTransition
                if (
                    payload.child.lifespan_ticks != run.lifespan_ticks
                    or payload.child.maturity_delay_ticks != run.maturity_delay_ticks
                    or payload.child.state is not LifecycleState.ALIVE
                    or payload.child.agent_id in current_agents
                    or payload.child.agent_id in birth_child_ids
                ):
                    raise _InvalidTransition
                if not all(
                    _active(current_agents.get(parent_id), tick)
                    for parent_id in payload.parent_ids
                ):
                    raise _InvalidTransition
                if not all(
                    _reproductive(current_agents.get(parent_id), tick)
                    for parent_id in payload.parent_ids
                ):
                    raise _InvalidTransition
                if any(parent_id in birth_parent_ids for parent_id in payload.parent_ids):
                    # No winner is selected when a parent participates in two births.
                    raise _InvalidTransition
                if payload.proposal_id in born_proposals:
                    raise _InvalidTransition
                if payload.refractory_until_tick < tick:
                    raise _InvalidTransition
                born_proposals.add(payload.proposal_id)
                birth_parent_ids.update(payload.parent_ids)
                birth_child_ids.add(payload.child.agent_id)
            elif fragment.kind is TransitionKind.NATURAL_DEATH:
                assert isinstance(payload, NaturalDeathTransition)
                agent = current_agents.get(payload.agent_id)
                if (
                    agent is None
                    or payload.agent_id in death_agents
                    or not should_die_after_tick(agent, tick)
                ):
                    raise _InvalidTransition
                death_agents.add(payload.agent_id)
            else:
                raise _InvalidTransition

    def _censor_for_capacity(
        self, run: SimulationRun, prior: Snapshot, tick: Tick
    ) -> CommitResult:
        event = _event(
            run.run_id,
            tick,
            "RunCensoredCapacity",
            "capacity",
            0,
        )
        snapshot = Snapshot(
            run_id=prior.run_id,
            tick=Tick(tick + 1),
            state_version=StateVersion(prior.state_version + 1),
            agents=prior.agents,
            messages=prior.messages,
            proposals=prior.proposals,
            events=prior.events + (event,),
            status=RunStatus.CENSORED,
        )
        return CommitResult(
            committed=True,
            snapshot=snapshot,
            events=(event,),
            capacity_censored=True,
        )

    def _apply(
        self,
        run: SimulationRun,
        prior: Snapshot,
        tick: Tick,
        fragments: tuple[TransitionFragment, ...],
    ) -> CommitResult:
        agents = {agent.agent_id: agent for agent in prior.agents}
        messages = {message.message_id: message for message in prior.messages}
        proposals = {proposal.proposal_id: proposal for proposal in prior.proposals}
        events: list[DomainEvent] = []

        for fragment in fragments:
            payload = fragment.payload
            if fragment.kind is TransitionKind.MESSAGE:
                assert isinstance(payload, MessageTransition)
                messages[payload.message.message_id] = payload.message
                events.append(_event(run.run_id, tick, "MessageCommitted", fragment.fragment_id.value, len(events)))
            elif fragment.kind is TransitionKind.PROPOSAL_CREATED:
                assert isinstance(payload, ProposalCreatedTransition)
                proposals[payload.proposal.proposal_id] = payload.proposal
                events.append(_event(run.run_id, tick, "ReproductionProposalCreated", fragment.fragment_id.value, len(events)))
            elif fragment.kind is TransitionKind.PROPOSAL_REJECTED:
                assert isinstance(payload, ProposalRejectedTransition)
                proposal = proposals[payload.proposal_id]
                proposals[payload.proposal_id] = replace(proposal, state=ProposalState.REJECTED)
                events.append(_event(run.run_id, tick, "ReproductionProposalRejected", fragment.fragment_id.value, len(events)))
            elif fragment.kind is TransitionKind.BIRTH_CONFLICT_REJECTED:
                assert isinstance(payload, BirthConflictTransition)
                events.append(
                    _event(
                        run.run_id,
                        tick,
                        "BirthCandidateRejected:MULTI_BIRTH_BOUNDARY_CONFLICT",
                        fragment.fragment_id.value,
                        len(events),
                    )
                )
            elif fragment.kind is TransitionKind.BIRTH:
                assert isinstance(payload, BirthTransition)
                proposal = proposals[payload.proposal_id]
                proposals[payload.proposal_id] = replace(proposal, state=ProposalState.ACCEPTED)
                agents[payload.child.agent_id] = payload.child
                for parent_id in payload.parent_ids:
                    parent = agents.get(parent_id)
                    if parent is not None:
                        agents[parent_id] = replace(
                            parent,
                            refractory_until_tick=payload.refractory_until_tick,
                        )
                events.append(_event(run.run_id, tick, "ReproductionProposalAccepted", fragment.fragment_id.value, len(events)))
                events.append(_event(run.run_id, tick, "AgentBorn", payload.child.agent_id.value, len(events)))
            elif fragment.kind is TransitionKind.NATURAL_DEATH:
                assert isinstance(payload, NaturalDeathTransition)
                agents.pop(payload.agent_id, None)
                events.append(_event(run.run_id, tick, "AgentDied", payload.agent_id.value, len(events)))

        next_tick = Tick(tick + 1)
        alive_ids = set(agents)
        for proposal_id, proposal in sorted(proposals.items(), key=lambda item: item[0].value):
            if proposal.state is not ProposalState.PENDING:
                continue
            if proposal.proposer_id not in alive_ids or proposal.target_id not in alive_ids:
                proposals[proposal_id] = replace(proposal, state=ProposalState.INVALIDATED)
                events.append(_event(run.run_id, tick, "ReproductionProposalInvalidated", proposal_id.value, len(events)))
            elif proposal.expires_at_tick is not None and proposal.expires_at_tick <= next_tick:
                proposals[proposal_id] = replace(proposal, state=ProposalState.EXPIRED)
                events.append(_event(run.run_id, tick, "ReproductionProposalExpired", proposal_id.value, len(events)))

        ordered_events = tuple(
            replace(event, commit_order=index)
            for index, event in enumerate(events)
        )
        status = (
            RunStatus.COMPLETED
            if run.horizon is not None and next_tick >= run.horizon
            else RunStatus.RUNNING
        )
        snapshot = Snapshot(
            run_id=prior.run_id,
            tick=next_tick,
            state_version=StateVersion(prior.state_version + 1),
            agents=tuple(sorted(agents.values(), key=lambda agent: str(agent.agent_id))),
            messages=tuple(sorted(messages.values(), key=lambda message: str(message.message_id))),
            proposals=tuple(sorted(proposals.values(), key=lambda proposal: str(proposal.proposal_id))),
            events=prior.events + ordered_events,
            status=status,
        )
        return CommitResult(committed=True, snapshot=snapshot, events=ordered_events)


def _canonical_fragments(
    fragments: tuple[TransitionFragment, ...],
) -> tuple[TransitionFragment, ...]:
    priority = {
        TransitionKind.MESSAGE: 10,
        TransitionKind.PROPOSAL_CREATED: 20,
        TransitionKind.PROPOSAL_REJECTED: 30,
        TransitionKind.BIRTH_CONFLICT_REJECTED: 40,
        TransitionKind.BIRTH: 50,
        TransitionKind.NATURAL_DEATH: 60,
    }
    return tuple(sorted(fragments, key=lambda item: (priority[item.kind], item.fragment_id.value)))


def _would_exceed_capacity(
    run: SimulationRun,
    snapshot: Snapshot,
    fragments: tuple[TransitionFragment, ...],
) -> bool:
    if run.population_capacity is None:
        return False
    births = sum(fragment.kind is TransitionKind.BIRTH for fragment in fragments)
    deaths = sum(fragment.kind is TransitionKind.NATURAL_DEATH for fragment in fragments)
    return len(snapshot.agents) - deaths + births > run.population_capacity


def _event(run_id: RunId, tick: Tick, event_type: str, key: str, order: int) -> DomainEvent:
    material = f"{run_id.value}|{int(tick)}|{event_type}|{key}"
    event_id = EventId(hashlib.sha256(material.encode("utf-8")).hexdigest())
    return DomainEvent(
        event_id=event_id,
        event_type=event_type,
        commit_tick=tick,
        commit_order=order,
    )


def _failure(snapshot: Snapshot, error: CommitError) -> CommitResult:
    return CommitResult(committed=False, snapshot=snapshot, events=(), error=error)


def _active(agent: AgentState | None, tick: Tick) -> bool:
    return agent is not None and is_active(agent, tick)


def _reproductive(agent: AgentState | None, tick: Tick) -> bool:
    return agent is not None and can_reproduce(agent, tick)
