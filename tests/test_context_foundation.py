from dataclasses import FrozenInstanceError, fields
import json
from pathlib import Path

import pytest

from alifelm.context import (
    ActionPresentation,
    ContextEvidence,
    ContextPack,
    ContextPolicy,
    DEFAULT_ACTION_PRESENTATION,
    InfrastructureMetadata,
    ModelInput,
    OrderingPolicy,
    PersonalVisibleHistory,
    VisibleRecordCounts,
    VisibilityProjection,
    build_model_input,
    render_model_input,
)
from alifelm.domain import (
    AgentId,
    AgentState,
    Duration,
    LifecycleState,
    MessageId,
    MessageRecord,
    OpportunityId,
    ProposalId,
    ProposalState,
    ReproductionProposal,
    RunId,
    StateVersion,
    Tick,
)
from alifelm.kernel import Snapshot


def _policy(max_records: int = 8) -> ContextPolicy:
    return ContextPolicy.exp000(
        max_prior_visible_records=max_records,
        ordering=OrderingPolicy(
            policy_version="1.0.0",
            unordered_collection_algorithm="ALIFELM_CONTEXT_ORDER_V1",
            digest_algorithm="sha256",
            ordering_seed_id="fixture-order-seed",
            ordering_seed_digest="a" * 64,
            cross_tick_order="COMMITTED_TICK_CHRONOLOGICAL",
            tie_breaker="FULL_STABLE_ITEM_KEY",
        ),
        action_presentation_digest="b" * 64,
    )


def _agent(
    value: str,
    *,
    first_active_tick: int = 0,
    lifespan_ticks: int = 20,
) -> AgentState:
    return AgentState(
        agent_id=AgentId(value),
        birth_tick=Tick(0 if first_active_tick == 0 else first_active_tick - 1),
        first_active_tick=Tick(first_active_tick),
        lifespan_ticks=Duration(lifespan_ticks),
        maturity_delay_ticks=Duration(0),
        state=LifecycleState.ALIVE,
    )


def _message(
    value: str,
    sender: str,
    recipient: str,
    *,
    committed_tick: int = 0,
) -> MessageRecord:
    return MessageRecord(
        message_id=MessageId(value),
        sender_id=AgentId(sender),
        recipient_id=AgentId(recipient),
        body=f"body-{value}",
        committed_tick=Tick(committed_tick),
        available_tick=Tick(committed_tick + 1),
    )


def _snapshot(
    *,
    tick: int,
    agents: tuple[AgentState, ...],
    messages: tuple[MessageRecord, ...] = (),
    proposals: tuple[ReproductionProposal, ...] = (),
) -> Snapshot:
    return Snapshot(
        run_id=RunId("run-context"),
        tick=Tick(tick),
        state_version=StateVersion(tick),
        agents=tuple(sorted(agents, key=lambda agent: str(agent.agent_id))),
        messages=messages,
        proposals=proposals,
        events=(),
    )


def _model_input(snapshot: Snapshot, agent_id: str, policy: ContextPolicy | None = None) -> ModelInput:
    selected_policy = policy or _policy()
    projection = VisibilityProjection.project(snapshot, AgentId(agent_id), selected_policy)
    history = PersonalVisibleHistory.select(projection, selected_policy)
    return build_model_input(projection, selected_policy, history)


def test_peer_private_history_hidden() -> None:
    snapshot = _snapshot(
        tick=1,
        agents=(_agent("A"), _agent("B"), _agent("C")),
        messages=(_message("private", "B", "C"),),
    )

    model_input = _model_input(snapshot, "A")

    assert model_input.newly_delivered == ()
    assert model_input.prior_history == ()
    assert "body-private" not in render_model_input(model_input)


def test_hidden_lineage_never_enters_model_input() -> None:
    model_input = _model_input(_snapshot(tick=1, agents=(_agent("A"),)), "A")

    assert not hasattr(model_input.current_self, "lineage")
    assert "lineage" not in render_model_input(model_input).lower()


def test_hidden_birth_seq_never_enters_model_input() -> None:
    model_input = _model_input(_snapshot(tick=1, agents=(_agent("A"),)), "A")

    assert not hasattr(model_input.current_self, "agent_birth_seq")
    assert "birth_seq" not in render_model_input(model_input).lower()


def test_researcher_labels_never_enter_model_input() -> None:
    model_input = _model_input(_snapshot(tick=1, agents=(_agent("A"),)), "A")

    assert "researcher" not in render_model_input(model_input).lower()
    assert "label" not in render_model_input(model_input).lower()


def test_own_delivered_message_is_visible() -> None:
    snapshot = _snapshot(
        tick=1,
        agents=(_agent("A"), _agent("B")),
        messages=(_message("to-a", "B", "A"),),
    )

    model_input = _model_input(snapshot, "A")

    assert len(model_input.newly_delivered) == 1
    assert model_input.newly_delivered[0].payload.sender_id == AgentId("B")
    assert "body-to-a" in render_model_input(model_input)


def test_unrelated_directed_message_is_hidden() -> None:
    snapshot = _snapshot(
        tick=1,
        agents=(_agent("A"), _agent("B"), _agent("C")),
        messages=(_message("not-a", "B", "C"),),
    )

    model_input = _model_input(snapshot, "A")

    assert model_input.newly_delivered == ()
    assert model_input.prior_history == ()


def test_proposal_visible_only_to_participants() -> None:
    proposal = ReproductionProposal(
        proposal_id=ProposalId("proposal-ab"),
        proposer_id=AgentId("A"),
        target_id=AgentId("B"),
        created_tick=Tick(0),
        state=ProposalState.PENDING,
    )
    snapshot = _snapshot(
        tick=1,
        agents=(_agent("A"), _agent("B"), _agent("C")),
        proposals=(proposal,),
    )

    a_input = _model_input(snapshot, "A")
    b_input = _model_input(snapshot, "B")
    c_input = _model_input(snapshot, "C")

    assert len(a_input.visible_protocol_state) == 1
    assert len(b_input.visible_protocol_state) == 1
    assert c_input.visible_protocol_state == ()


def test_newborn_has_no_parent_history() -> None:
    snapshot = _snapshot(
        tick=1,
        agents=(_agent("A"), _agent("B"), _agent("child", first_active_tick=1)),
        messages=(_message("parent-record", "A", "B"),),
    )

    child_input = _model_input(snapshot, "child")

    assert child_input.prior_history == ()
    assert child_input.newly_delivered == ()


def test_sprite_identity_is_hidden() -> None:
    model_input = _model_input(_snapshot(tick=1, agents=(_agent("A"),)), "A")

    assert "sprite" not in render_model_input(model_input).lower()


def test_exp000_has_no_model_written_semantic_memory() -> None:
    policy = _policy()
    model_input = _model_input(
        _snapshot(tick=1, agents=(_agent("A"),)), "A", policy
    )

    assert policy.recall.mode == "DISABLED"
    assert policy.recall.agent_triggered is False
    assert policy.recall.semantic_retrieval is False
    assert policy.history.model_written_semantic_memory is False
    assert policy.history.lossy_summarization is False
    assert "diary" not in render_model_input(model_input).lower()


def test_current_tick_is_not_rendered() -> None:
    model_input = _model_input(_snapshot(tick=7, agents=(_agent("A"),)), "A")

    assert "tick" not in render_model_input(model_input).lower()


def test_natural_death_tick_is_not_rendered() -> None:
    model_input = _model_input(
        _snapshot(tick=3, agents=(_agent("A", lifespan_ticks=5),)), "A"
    )

    rendered = render_model_input(model_input).lower()
    assert "natural_death" not in rendered
    assert "lifespan" not in rendered


def test_context_pack_is_immutable() -> None:
    model_input = _model_input(_snapshot(tick=1, agents=(_agent("A"),)), "A")
    evidence = ContextEvidence(
        run_id=RunId("run-context"),
        opportunity_id=OpportunityId("opportunity-a"),
        agent_id=AgentId("A"),
        bound_tick=1,
        bound_state_version=1,
        bound_state_hash="c" * 64,
        context_policy_id="exp000-context",
        context_policy_version="1.0.0",
        context_policy_digest="d" * 64,
        visibility_policy_version="1.0.0",
        ordering_policy_version="1.0.0",
        ordering_seed_id="fixture-order-seed",
        ordering_seed_digest="a" * 64,
        action_presentation_policy_id="exp000-neutral-actions",
        action_presentation_version="1.0.0",
        action_presentation_digest="b" * 64,
        provenance=(),
        artifact_refs=(),
    )
    pack = ContextPack(
        context_pack_id="context-pack-a",
        schema_version="1.0.0",
        context_hash="e" * 64,
        model_input=model_input,
        evidence=evidence,
        infrastructure=InfrastructureMetadata(
            model_profile_id="fixture-model",
            generation_policy_id="fixture-generation",
            generation_seed_id="fixture-generation-seed",
            visible_record_counts=VisibleRecordCounts(
                peers=0, newly_delivered=0, visible_protocol_state=0, prior_history=0
            ),
            tokenizer_profile_id=None,
            rendered_input_token_count=None,
            cache_telemetry=None,
        ),
    )

    with pytest.raises(FrozenInstanceError):
        pack.context_hash = "f" * 64  # type: ignore[misc]
    assert isinstance(pack.model_input.peer_directory, tuple)


def test_history_uses_semantic_record_limit() -> None:
    messages = tuple(
        _message(f"m{tick}", "A", "B", committed_tick=tick) for tick in range(3)
    )
    policy = _policy(max_records=2)
    snapshot = _snapshot(tick=3, agents=(_agent("A"), _agent("B")), messages=messages)

    projection = VisibilityProjection.project(snapshot, AgentId("A"), policy)
    history = PersonalVisibleHistory.select(projection, policy)

    assert [record.source_id for record in history] == ["m1", "m2"]
    assert [int(record.committed_tick) for record in history] == [1, 2]


def test_context_machine_contract_top_level_field_parity(repository_root: Path) -> None:
    policy_schema = json.loads(
        (repository_root / "specs/contracts/context-policy.schema.json").read_text(
            encoding="utf-8"
        )
    )
    pack_schema = json.loads(
        (repository_root / "specs/contracts/context-pack.schema.json").read_text(
            encoding="utf-8"
        )
    )
    action_schema = json.loads(
        (repository_root / "specs/contracts/action-presentation.schema.json").read_text(
            encoding="utf-8"
        )
    )

    assert set(policy_schema["properties"]) == {
        field.name for field in fields(ContextPolicy)
    }
    assert set(pack_schema["properties"]) == {field.name for field in fields(ContextPack)}
    assert set(action_schema["properties"]) == {
        field.name for field in fields(ActionPresentation)
    }


def test_action_presentation_is_the_only_exact_model_action_reference() -> None:
    assert DEFAULT_ACTION_PRESENTATION.presentation_order == (
        "WAIT",
        "SEND",
        "PROPOSE",
        "ACCEPT",
        "REJECT",
    )
    assert DEFAULT_ACTION_PRESENTATION.entry("WAIT").model_label == "NO_DIRECTED_ACTION"
    assert "survive" not in " ".join(
        entry.description.lower() for entry in DEFAULT_ACTION_PRESENTATION.actions
    )
