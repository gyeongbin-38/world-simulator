import pytest

from alifelm.domain import (
    AcceptAction,
    ActionIntent,
    ActionKind,
    AgentId,
    IntentBatch,
    IntentId,
    ProposalId,
    ProposeAction,
    SendAction,
    Tick,
    WaitAction,
)


def intent(kind: ActionKind, payload: object, *, name: str = "intent-1", actor: str = "agent-1") -> ActionIntent:
    return ActionIntent(IntentId(name), AgentId(actor), Tick(2), kind, payload)  # type: ignore[arg-type]


def test_baseline_action_vocabulary_is_explicit() -> None:
    assert tuple(ActionKind) == (
        ActionKind.SEND,
        ActionKind.PROPOSE,
        ActionKind.ACCEPT,
        ActionKind.REJECT,
        ActionKind.WAIT,
    )


def test_model_output_is_a_proposal_with_discriminated_payload() -> None:
    proposed = intent(ActionKind.SEND, SendAction(AgentId("agent-2"), "hello"))
    assert proposed.kind is ActionKind.SEND
    assert proposed.actor_id == AgentId("agent-1")

    with pytest.raises(TypeError):
        intent(ActionKind.WAIT, AcceptAction(ProposalId("proposal-1")))


def test_self_reproduction_is_invalid() -> None:
    with pytest.raises(ValueError):
        intent(ActionKind.PROPOSE, ProposeAction(AgentId("agent-1")))


def test_intent_batch_has_one_primary_outcome_per_actor_and_tick() -> None:
    first = intent(ActionKind.WAIT, WaitAction())
    assert IntentBatch(Tick(2), (first,)).intents == (first,)

    with pytest.raises(ValueError):
        IntentBatch(Tick(2), (first, intent(ActionKind.WAIT, WaitAction(), name="intent-2")))

    with pytest.raises(ValueError):
        IntentBatch(Tick(2), (first, intent(ActionKind.WAIT, WaitAction(), name="intent-1", actor="agent-2")))
