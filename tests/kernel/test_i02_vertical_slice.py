from __future__ import annotations

from alifelm.domain import (
    AcceptAction,
    ActionIntent,
    ActionKind,
    AgentId,
    Duration,
    IntentId,
    ProposalId,
    ProposeAction,
    RunId,
    SendAction,
    StateVersion,
    Tick,
    WaitAction,
)
from alifelm.kernel import (
    CommitRequest,
    DeterministicKernel,
    FakeDeterministicModelRuntime,
    InMemoryCommitCoordinator,
    RunStatus,
    SimulationRun,
)


def make_run(
    *founders: str,
    lifespan: int = 10,
    maturity: int = 0,
    refractory: int = 0,
    capacity: int | None = None,
) -> SimulationRun:
    return SimulationRun.bootstrap(
        RunId("run-1"),
        lifespan_ticks=Duration(lifespan),
        maturity_delay_ticks=Duration(maturity),
        refractory_interval_ticks=Duration(refractory),
        founder_ids=tuple(AgentId(founder) for founder in founders),
        population_capacity=capacity,
    )


def make_intent(
    name: str,
    actor: str,
    tick: int,
    kind: ActionKind,
    payload,
) -> ActionIntent:
    return ActionIntent(
        intent_id=IntentId(name),
        actor_id=AgentId(actor),
        tick=Tick(tick),
        kind=kind,
        payload=payload,
    )


def wait(name: str, actor: str, tick: int) -> ActionIntent:
    return make_intent(name, actor, tick, ActionKind.WAIT, WaitAction())


def run_with(run: SimulationRun, script: dict[tuple[Tick, AgentId], ActionIntent]):
    kernel = DeterministicKernel(run, FakeDeterministicModelRuntime(script))
    return kernel, kernel.run_tick()


def create_proposal(run: SimulationRun, proposer: str = "A", target: str = "B"):
    kernel, _ = run_with(
        run,
        {
            (Tick(0), AgentId(proposer)): make_intent(
                "proposal-0", proposer, 0, ActionKind.PROPOSE, ProposeAction(AgentId(target))
            )
        },
    )
    return kernel, run.snapshot.proposals[0].proposal_id


def accept_proposal(kernel: DeterministicKernel, proposal_id: ProposalId, actor: str = "B"):
    kernel.runtime = FakeDeterministicModelRuntime(
        {
            (Tick(1), AgentId(actor)): make_intent(
                "accept-1", actor, 1, ActionKind.ACCEPT, AcceptAction(proposal_id)
            )
        }
    )
    return kernel.run_tick()


def test_same_tick_message_isolation() -> None:
    run = make_run("A", "B")
    _, result = run_with(
        run,
        {
            (Tick(0), AgentId("A")): make_intent(
                "send-0", "A", 0, ActionKind.SEND, SendAction(AgentId("B"), "hello")
            )
        },
    )

    recipient_opportunity = next(
        opportunity for opportunity in result.opportunities if opportunity.agent_id == AgentId("B")
    )
    assert recipient_opportunity.fixture.messages == ()
    assert result.snapshot_before.messages == ()


def test_message_visible_next_tick() -> None:
    run = make_run("A", "B")
    kernel, _ = run_with(
        run,
        {
            (Tick(0), AgentId("A")): make_intent(
                "send-0", "A", 0, ActionKind.SEND, SendAction(AgentId("B"), "hello")
            )
        },
    )
    next_result = kernel.run_tick()
    recipient_opportunity = next(
        opportunity for opportunity in next_result.opportunities if opportunity.agent_id == AgentId("B")
    )
    assert tuple(message.body for message in recipient_opportunity.fixture.messages) == ("hello",)
    assert next_result.snapshot_before.tick == Tick(1)


def test_newborn_not_active_same_tick() -> None:
    run = make_run("A", "B")
    kernel, proposal_id = create_proposal(run)
    result = accept_proposal(kernel, proposal_id)

    child = next(agent for agent in run.snapshot.agents if agent.agent_id not in {AgentId("A"), AgentId("B")})
    assert child.birth_tick == Tick(1)
    assert child.first_active_tick == Tick(2)
    assert child.agent_id not in {opportunity.agent_id for opportunity in result.opportunities}


def test_newborn_active_next_tick() -> None:
    run = make_run("A", "B")
    kernel, proposal_id = create_proposal(run)
    accept_proposal(kernel, proposal_id)
    result = kernel.run_tick()

    child = next(agent for agent in run.snapshot.agents if agent.agent_id not in {AgentId("A"), AgentId("B")})
    assert child.agent_id in {opportunity.agent_id for opportunity in result.opportunities}


def test_maturity_only_gates_reproduction() -> None:
    run = make_run("A", "B", maturity=2)
    _, result = run_with(
        run,
        {
            (Tick(0), AgentId("A")): make_intent(
                "send-0", "A", 0, ActionKind.SEND, SendAction(AgentId("B"), "still-active")
            )
        },
    )
    assert result.commit_result.committed
    assert tuple(message.sender_id for message in run.snapshot.messages) == (AgentId("A"),)
    assert run.snapshot.proposals == ()


def test_refractory_only_gates_reproduction() -> None:
    run = make_run("A", "B", "C", refractory=3)
    kernel, proposal_id = create_proposal(run)
    accept_proposal(kernel, proposal_id)
    kernel.runtime = FakeDeterministicModelRuntime(
        {
            (Tick(2), AgentId("A")): make_intent(
                "send-2", "A", 2, ActionKind.SEND, SendAction(AgentId("C"), "refractory-does-not-block-send")
            ),
            (Tick(2), AgentId("B")): wait("wait-2", "B", 2),
        }
    )
    result = kernel.run_tick()

    assert result.commit_result.committed
    assert any(message.body == "refractory-does-not-block-send" for message in run.snapshot.messages)
    assert run.snapshot.agent(AgentId("A")).refractory_until_tick == Tick(4)


def test_final_tick_send_survives_sender_death() -> None:
    run = make_run("A", "B", lifespan=1)
    _, result = run_with(
        run,
        {
            (Tick(0), AgentId("A")): make_intent(
                "final-send", "A", 0, ActionKind.SEND, SendAction(AgentId("B"), "last")
            )
        },
    )
    assert AgentId("A") not in {agent.agent_id for agent in run.snapshot.agents}
    assert run.snapshot.messages[0].sender_id == AgentId("A")
    assert any(event.event_type == "AgentDied" for event in result.commit_result.events)


def test_successful_birth_can_coexist_with_parent_natural_death() -> None:
    run = make_run("A", "B", lifespan=2)
    kernel, proposal_id = create_proposal(run)
    result = accept_proposal(kernel, proposal_id)

    agents = {agent.agent_id: agent for agent in run.snapshot.agents}
    child_ids = set(agents) - {AgentId("A"), AgentId("B")}
    assert len(child_ids) == 1
    assert AgentId("A") not in agents and AgentId("B") not in agents
    assert any(event.event_type == "AgentBorn" for event in result.commit_result.events)
    assert sum(event.event_type == "AgentDied" for event in result.commit_result.events) == 2


def _make_two_proposals_at_same_boundary():
    run = make_run("A", "B", "C")
    kernel, first_id = create_proposal(run, target="B")
    kernel.runtime = FakeDeterministicModelRuntime(
        {
            (Tick(1), AgentId("A")): make_intent(
                "proposal-1", "A", 1, ActionKind.PROPOSE, ProposeAction(AgentId("C"))
            )
        }
    )
    kernel.run_tick()
    second_id = next(
        proposal.proposal_id
        for proposal in run.snapshot.proposals
        if proposal.proposal_id != first_id
    )
    kernel.runtime = FakeDeterministicModelRuntime(
        {
            (Tick(2), AgentId("B")): make_intent(
                "accept-b", "B", 2, ActionKind.ACCEPT, AcceptAction(first_id)
            ),
            (Tick(2), AgentId("C")): make_intent(
                "accept-c", "C", 2, ActionKind.ACCEPT, AcceptAction(second_id)
            ),
        }
    )
    return run, kernel, first_id, second_id


def test_multi_birth_conflict_rejects_all() -> None:
    run, kernel, first_id, second_id = _make_two_proposals_at_same_boundary()
    result = kernel.run_tick()

    assert not any(agent.birth_tick == Tick(2) for agent in run.snapshot.agents)
    rejected = [
        event
        for event in result.commit_result.events
        if event.event_type == "BirthCandidateRejected:MULTI_BIRTH_BOUNDARY_CONFLICT"
    ]
    assert len(rejected) == 2
    assert {proposal.proposal_id for proposal in run.snapshot.proposals} == {first_id, second_id}


def test_conflicted_proposals_remain_pending() -> None:
    run, kernel, first_id, second_id = _make_two_proposals_at_same_boundary()
    kernel.run_tick()
    states = {proposal.proposal_id: proposal.state for proposal in run.snapshot.proposals}
    assert states[first_id].value == "PENDING"
    assert states[second_id].value == "PENDING"


def test_failed_acceptance_does_not_commit_accepted_state() -> None:
    run = make_run("A", "B")
    kernel, proposal_id = create_proposal(run)
    kernel.runtime = FakeDeterministicModelRuntime(
        {
            (Tick(1), AgentId("B")): make_intent(
                "bad-accept", "B", 1, ActionKind.ACCEPT, AcceptAction(ProposalId("missing"))
            )
        }
    )
    result = kernel.run_tick()

    assert all(item.intent.kind is not ActionKind.ACCEPT for item in result.validated_intents)
    proposal = next(proposal for proposal in run.snapshot.proposals if proposal.proposal_id == proposal_id)
    assert proposal.state.value == "PENDING"
    assert not any(event.event_type == "ReproductionProposalAccepted" for event in run.snapshot.events)


def _permutation_result(order: tuple[str, ...]):
    run = make_run("A", "B", "C")
    kernel = DeterministicKernel(
        run,
        FakeDeterministicModelRuntime(
            {
                (Tick(0), AgentId("A")): make_intent(
                    "a-send", "A", 0, ActionKind.SEND, SendAction(AgentId("B"), "a")
                ),
                (Tick(0), AgentId("B")): make_intent(
                    "b-send", "B", 0, ActionKind.SEND, SendAction(AgentId("C"), "b")
                ),
                (Tick(0), AgentId("C")): wait("c-wait", "C", 0),
            }
        ),
    )
    result = kernel.run_tick(tuple(AgentId(agent) for agent in order))
    return run.snapshot.state_hash(), tuple(
        (event.event_type, event.event_id.value, event.commit_order)
        for event in result.commit_result.events
    )


def test_inference_completion_order_does_not_change_state() -> None:
    outputs = {
        _permutation_result(order)[0]
        for order in (("A", "B", "C"), ("C", "A", "B"), ("B", "C", "A"))
    }
    assert len(outputs) == 1


def test_inference_completion_order_does_not_change_events() -> None:
    outputs = {
        _permutation_result(order)[1]
        for order in (("A", "B", "C"), ("C", "A", "B"), ("B", "C", "A"))
    }
    assert len(outputs) == 1


def test_same_inputs_produce_same_state_hash() -> None:
    assert _permutation_result(("A", "B", "C"))[0] == _permutation_result(("A", "B", "C"))[0]


def test_capacity_condition_is_not_agent_death() -> None:
    run = make_run("A", "B", capacity=2)
    kernel, proposal_id = create_proposal(run)
    result = accept_proposal(kernel, proposal_id)

    assert result.commit_result.capacity_censored
    assert run.status is RunStatus.CENSORED
    assert {agent.agent_id for agent in run.snapshot.agents} == {AgentId("A"), AgentId("B")}
    assert not any(event.event_type == "AgentDied" for event in run.snapshot.events)


def test_commit_failure_leaves_prior_snapshot_unchanged() -> None:
    run = make_run("A")
    prior = run.snapshot
    result = run_with_commit_failure(run)

    assert not result.committed
    assert result.snapshot is prior
    assert run.snapshot is prior
    assert run.snapshot.state_hash() == prior.state_hash()


def run_with_commit_failure(run: SimulationRun):
    return InMemoryCommitCoordinator().commit(
        run,
        CommitRequest(
            run_id=run.run_id,
            tick=run.snapshot.tick,
            expected_state_version=StateVersion(99),
            fragments=(),
        ),
    )


def test_proposal_created_is_not_visible_same_tick() -> None:
    run = make_run("A", "B")
    _, result = run_with(
        run,
        {
            (Tick(0), AgentId("A")): make_intent(
                "proposal-0", "A", 0, ActionKind.PROPOSE, ProposeAction(AgentId("B"))
            ),
            (Tick(0), AgentId("B")): make_intent(
                "accept-too-soon", "B", 0, ActionKind.ACCEPT, AcceptAction(ProposalId("missing"))
            ),
        },
    )
    assert result.validated_intents[0].intent.kind is ActionKind.PROPOSE
    assert all(proposal.state.value == "PENDING" for proposal in run.snapshot.proposals)
