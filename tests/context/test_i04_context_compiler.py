from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
import hashlib
import itertools
import json

import pytest

from alifelm.context import (
    ActionPresentationEntry,
    CognitionGateway,
    ContextCompiler,
    ContextCognitionPipeline,
    ContextPolicy,
    DEFAULT_ACTION_PRESENTATION,
    ModelActionParser,
    NeutralOrdering,
    OrderingBinding,
    OrderingPolicy,
    PersonalVisibleHistory,
    VisibilityProjection,
    action_presentation_digest,
    action_presentation_to_dict,
    build_model_input,
    canonical_bytes,
    context_pack_to_dict,
    deserialize_context_pack,
    render_model_input,
    render_model_input_bytes,
    serialize_context_pack,
    validate_context_provenance,
)
from alifelm.domain import (
    ActionIntent,
    ActionKind,
    AgentId,
    AgentState,
    ArtifactId,
    ArtifactRef,
    Duration,
    IntentId,
    MessageId,
    MessageRecord,
    OpportunityId,
    ProposalId,
    ProposalState,
    ReproductionProposal,
    RunId,
    SendAction,
    StateVersion,
    Tick,
)
from alifelm.kernel import (
    DeterministicKernel,
    EqualOpportunityScheduler,
    SimulationRun,
    Snapshot,
)
from alifelm.persistence import FileSystemArtifactStore, SQLiteReferenceStore
from alifelm.persistence.serialization import snapshot_from_dict, snapshot_to_dict


def policy(max_records: int = 8, *, version: str = "1.0.0") -> ContextPolicy:
    return ContextPolicy.exp000(
        max_prior_visible_records=max_records,
        ordering=OrderingPolicy(
            policy_version="1.0.0",
            unordered_collection_algorithm="ALIFELM_CONTEXT_ORDER_V1",
            digest_algorithm="sha256",
            ordering_seed_id="context-order-seed",
            ordering_seed_digest="a" * 64,
            cross_tick_order="COMMITTED_TICK_CHRONOLOGICAL",
            tie_breaker="FULL_STABLE_ITEM_KEY",
        ),
        action_presentation_digest=action_presentation_digest(
            DEFAULT_ACTION_PRESENTATION
        ),
        version=version,
    )


def agent(
    value: str,
    *,
    first_active_tick: int = 0,
    lifespan: int = 100,
) -> AgentState:
    return AgentState(
        agent_id=AgentId(value),
        birth_tick=Tick(0 if first_active_tick == 0 else first_active_tick - 1),
        first_active_tick=Tick(first_active_tick),
        lifespan_ticks=Duration(lifespan),
        maturity_delay_ticks=Duration(0),
    )


def message(
    value: str,
    sender: str,
    recipient: str,
    body: str,
    committed_tick: int,
) -> MessageRecord:
    return MessageRecord(
        message_id=MessageId(value),
        sender_id=AgentId(sender),
        recipient_id=AgentId(recipient),
        body=body,
        committed_tick=Tick(committed_tick),
        available_tick=Tick(committed_tick + 1),
    )


def proposal(value: str, proposer: str, target: str, created_tick: int) -> ReproductionProposal:
    return ReproductionProposal(
        proposal_id=ProposalId(value),
        proposer_id=AgentId(proposer),
        target_id=AgentId(target),
        created_tick=Tick(created_tick),
        state=ProposalState.PENDING,
    )


def snapshot(
    *,
    tick: int = 1,
    agents: tuple[AgentState, ...] | None = None,
    messages: tuple[MessageRecord, ...] = (),
    proposals: tuple[ReproductionProposal, ...] = (),
    run_id: str = "context-run",
) -> Snapshot:
    values = agents or (agent("A"), agent("B"), agent("C"))
    return Snapshot(
        run_id=RunId(run_id),
        tick=Tick(tick),
        state_version=StateVersion(tick),
        agents=tuple(sorted(values, key=lambda item: item.agent_id.value)),
        messages=messages,
        proposals=proposals,
        events=(),
    )


def opportunity(bound: Snapshot, actor: str):
    return next(
        item
        for item in EqualOpportunityScheduler().enumerate(bound)
        if item.agent_id == AgentId(actor)
    )


def compile_pack(
    bound: Snapshot,
    actor: str = "A",
    selected_policy: ContextPolicy | None = None,
    *,
    source_artifact_refs: tuple[ArtifactRef, ...] = (),
):
    return ContextCompiler().compile(
        opportunity(bound, actor),
        selected_policy or policy(),
        model_profile_id="fixture-model",
        generation_policy_id="fixture-generation",
        generation_seed_id="fixture-generation-seed",
        source_artifact_refs=source_artifact_refs,
    )


class CandidateRuntime:
    def __init__(self, outputs=None):
        self.outputs = outputs or {}
        self.calls: list[AgentId] = []

    def infer(self, compiled):
        self.calls.append(compiled.opportunity.agent_id)
        return self.outputs.get(
            compiled.opportunity.agent_id,
            {"action_label": "NO_DIRECTED_ACTION", "payload": {}},
        )


def make_run(*ids: str) -> SimulationRun:
    return SimulationRun.bootstrap(
        RunId("context-kernel-run"),
        lifespan_ticks=Duration(100),
        founder_ids=tuple(AgentId(value) for value in ids),
    )


def pipeline(artifact_store=None) -> ContextCognitionPipeline:
    return ContextCognitionPipeline(
        policy(),
        model_profile_id="fixture-model",
        generation_policy_id="fixture-generation",
        generation_seed_id="fixture-generation-seed",
        artifact_store=artifact_store,
    )


def model_structure(pack) -> str:
    return json.dumps(
        context_pack_to_dict(pack)["model_input"], ensure_ascii=False, sort_keys=True
    )


def test_peer_private_history_never_leaks() -> None:
    bound = snapshot(
        messages=(message("private", "B", "C", "SECRET_PRIVATE_MESSAGE", 0),)
    )
    pack = compile_pack(bound, "A")
    assert "SECRET_PRIVATE_MESSAGE" not in model_structure(pack)
    assert "SECRET_PRIVATE_MESSAGE" not in render_model_input(pack.model_input)


def test_hidden_lineage_never_leaks() -> None:
    ref = ArtifactRef(ArtifactId("SECRET_PARENT_X"), "1" * 64)
    pack = compile_pack(snapshot(), source_artifact_refs=(ref,))
    assert "SECRET_PARENT_X" not in model_structure(pack)
    assert "SECRET_PARENT_X" not in render_model_input(pack.model_input)


def test_hidden_birth_seq_never_leaks() -> None:
    pack = compile_pack(snapshot())
    structured = context_pack_to_dict(pack)["model_input"]
    assert "agent_birth_seq" not in json.dumps(structured, sort_keys=True)
    assert "birth_tick" not in json.dumps(structured, sort_keys=True)


def test_researcher_labels_never_leak() -> None:
    pack = ContextCompiler().compile(
        opportunity(snapshot(), "A"),
        policy(),
        model_profile_id="SECRET_RESEARCH_LABEL",
        generation_policy_id="fixture-generation",
        generation_seed_id="fixture-generation-seed",
    )
    assert "SECRET_RESEARCH_LABEL" not in model_structure(pack)
    assert "SECRET_RESEARCH_LABEL" not in render_model_input(pack.model_input)


def test_same_tick_peer_output_never_leaks() -> None:
    run = make_run("A", "B")
    runtime = CandidateRuntime(
        {
            AgentId("A"): {
                "action_label": "DIRECT_TEXT",
                "payload": {
                    "target_agent_id": "B",
                    "body": "SAME_TICK_SECRET",
                },
            }
        }
    )
    result = DeterministicKernel(
        run, runtime, context_pipeline=pipeline()
    ).run_tick((AgentId("A"), AgentId("B")))
    b_pack = next(
        pack for pack in result.context_packs if pack.evidence.agent_id == AgentId("B")
    )
    assert "SAME_TICK_SECRET" not in model_structure(b_pack)


def test_uncommitted_intent_never_leaks() -> None:
    uncommitted = ActionIntent(
        IntentId("uncommitted"),
        AgentId("B"),
        Tick(1),
        ActionKind.SEND,
        SendAction(AgentId("A"), "UNCOMMITTED_SECRET"),
    )
    assert uncommitted.payload.body == "UNCOMMITTED_SECRET"
    pack = compile_pack(snapshot(), "A")
    assert "UNCOMMITTED_SECRET" not in model_structure(pack)


def test_newborn_has_no_parent_history() -> None:
    bound = snapshot(
        agents=(agent("A"), agent("B"), agent("child", first_active_tick=1)),
        messages=(message("parent-message", "A", "B", "PARENT_HISTORY", 0),),
    )
    pack = compile_pack(bound, "child")
    assert pack.model_input.prior_history == ()
    assert "PARENT_HISTORY" not in model_structure(pack)


def test_own_delivered_message_is_visible() -> None:
    pack = compile_pack(
        snapshot(messages=(message("to-a", "B", "A", "VISIBLE_TO_A", 0),)),
        "A",
    )
    assert "VISIBLE_TO_A" in model_structure(pack)


def test_other_agents_directed_message_is_hidden() -> None:
    pack = compile_pack(
        snapshot(messages=(message("to-c", "B", "C", "ONLY_FOR_C", 0),)),
        "A",
    )
    assert "ONLY_FOR_C" not in model_structure(pack)


def test_proposal_visible_only_to_allowed_participant() -> None:
    bound = snapshot(proposals=(proposal("p-ab", "A", "B", 0),))
    a = compile_pack(bound, "A")
    b = compile_pack(bound, "B")
    c = compile_pack(bound, "C")
    assert "p-ab" in model_structure(a)
    assert "p-ab" in model_structure(b)
    assert "p-ab" not in model_structure(c)


def test_identical_inputs_produce_identical_context_hash() -> None:
    bound = snapshot(messages=(message("to-a", "B", "A", "same", 0),))
    first = compile_pack(bound)
    second = compile_pack(bound)
    assert first == second
    assert serialize_context_pack(first) == serialize_context_pack(second)


def test_storage_query_order_does_not_change_context() -> None:
    records = (
        message("m-a", "B", "A", "one", 0),
        message("m-b", "C", "A", "two", 0),
        message("m-c", "A", "B", "three", 0),
    )
    proposals = (proposal("p-a", "A", "B", 0), proposal("p-b", "C", "A", 0))
    baseline = compile_pack(snapshot(messages=records, proposals=proposals))
    for message_order in itertools.permutations(records):
        permuted = compile_pack(
            snapshot(messages=message_order, proposals=tuple(reversed(proposals)))
        )
        assert permuted.model_input == baseline.model_input
        assert permuted.context_hash == baseline.context_hash


def test_inference_completion_order_does_not_change_context() -> None:
    outputs = []
    for order in (("A", "B", "C"), ("C", "A", "B"), ("B", "C", "A")):
        run = make_run("A", "B", "C")
        result = DeterministicKernel(
            run, CandidateRuntime(), context_pipeline=pipeline()
        ).run_tick(tuple(AgentId(value) for value in order))
        outputs.append(
            tuple(
                (pack.evidence.agent_id.value, pack.context_hash)
                for pack in result.context_packs
            )
        )
    assert outputs[0] == outputs[1] == outputs[2]


def test_neutral_peer_order_has_no_low_id_priority() -> None:
    selected_first: set[str] = set()
    values = ("A", "B", "C", "D")
    for index in range(24):
        ordering = NeutralOrdering(
            policy().ordering,
            OrderingBinding(
                RunId("neutral-run"), OpportunityId(f"opportunity-{index}"), Tick(index)
            ),
        )
        result = ordering.order(
            values, category="peer_directory", stable_key=lambda value: f"agent|{value}"
        )
        selected_first.add(result[0])
    assert len(selected_first) > 1
    assert selected_first != {"A"}


def test_context_contains_only_traceable_committed_sources() -> None:
    bound = snapshot(
        messages=(message("m-a", "B", "A", "visible", 0),),
        proposals=(proposal("p-a", "A", "B", 0),),
    )
    pack = compile_pack(bound)
    validate_context_provenance(pack, bound)
    assert len(pack.evidence.provenance) == (
        2
        + len(pack.model_input.peer_directory)
        + len(pack.model_input.newly_delivered)
        + len(pack.model_input.visible_protocol_state)
        + len(pack.model_input.prior_history)
    )


def test_sprite_identity_not_visible_in_EXP000() -> None:
    pack = ContextCompiler().compile(
        opportunity(snapshot(), "A"),
        policy(),
        model_profile_id="fixture-model",
        generation_policy_id="SECRET_SPRITE",
        generation_seed_id="fixture-generation-seed",
    )
    assert "SECRET_SPRITE" not in model_structure(pack)


def test_no_model_written_semantic_memory_in_baseline() -> None:
    selected = policy()
    assert selected.recall.mode == "DISABLED"
    assert selected.recall.semantic_retrieval is False
    assert selected.history.lossy_summarization is False
    assert selected.history.model_written_semantic_memory is False
    assert "diary" not in render_model_input(compile_pack(snapshot()).model_input).lower()


def test_action_presentation_is_version_pinned() -> None:
    changed = replace(
        DEFAULT_ACTION_PRESENTATION.actions[0], description="invented synonym"
    )
    with pytest.raises(ValueError):
        replace(
            DEFAULT_ACTION_PRESENTATION,
            actions=(changed, *DEFAULT_ACTION_PRESENTATION.actions[1:]),
        )


def test_policy_change_changes_context_identity() -> None:
    bound = snapshot()
    assert compile_pack(bound, selected_policy=policy(1)).context_hash != compile_pack(
        bound, selected_policy=policy(2)
    ).context_hash


def test_restart_reload_produces_identical_context(tmp_path) -> None:
    run = make_run("A", "B")
    before = ContextCompiler().compile(
        EqualOpportunityScheduler().enumerate(run.snapshot)[0],
        policy(),
        model_profile_id="fixture-model",
        generation_policy_id="fixture-generation",
        generation_seed_id="fixture-generation-seed",
    )
    store = SQLiteReferenceStore(
        tmp_path / "reload.sqlite", artifact_root=tmp_path / "cas"
    )
    try:
        store.create_run(run)
        reloaded = store.load_run(run.run_id)
        after = ContextCompiler().compile(
            EqualOpportunityScheduler().enumerate(reloaded.snapshot)[0],
            policy(),
            model_profile_id="fixture-model",
            generation_policy_id="fixture-generation",
            generation_seed_id="fixture-generation-seed",
        )
        assert after == before
        assert serialize_context_pack(after) == serialize_context_pack(before)
    finally:
        store.close()


def test_current_tick_not_rendered_to_model() -> None:
    rendered = render_model_input(compile_pack(snapshot(tick=7)).model_input).lower()
    assert "tick" not in rendered
    assert "bound_tick" not in rendered


def test_natural_death_tick_not_rendered() -> None:
    bound = snapshot(
        tick=1,
        agents=(agent("A", lifespan=987654321), agent("B", lifespan=987654321)),
    )
    rendered = render_model_input(compile_pack(bound).model_input).lower()
    assert "natural_death" not in rendered
    assert "lifespan" not in rendered
    assert "987654321" not in rendered


def test_model_output_cannot_override_actor_id() -> None:
    with pytest.raises(ValueError):
        CognitionGateway().bind(
            {"action_label": "NO_DIRECTED_ACTION", "payload": {}, "actor_id": "B"},
            opportunity(snapshot(), "A"),
        )


def test_model_output_cannot_override_tick() -> None:
    with pytest.raises(ValueError):
        CognitionGateway().bind(
            {"action_label": "NO_DIRECTED_ACTION", "payload": {}, "tick": 999},
            opportunity(snapshot(), "A"),
        )


def test_gateway_binds_identity_from_opportunity() -> None:
    bound_opportunity = opportunity(snapshot(tick=3), "A")
    intent = CognitionGateway().bind(
        {
            "action_label": "DIRECT_TEXT",
            "payload": {"body": "hello", "target_agent_id": "B"},
        },
        bound_opportunity,
    )
    assert intent.actor_id == bound_opportunity.agent_id
    assert intent.tick == bound_opportunity.tick
    assert intent.intent_id == CognitionGateway().bind(
        {
            "payload": {"target_agent_id": "B", "body": "hello"},
            "action_label": "DIRECT_TEXT",
        },
        bound_opportunity,
    ).intent_id


def test_same_boundary_seeded_order_reproducible() -> None:
    records = (
        message("m-a", "B", "A", "one", 0),
        message("m-b", "C", "A", "two", 0),
    )
    first = compile_pack(snapshot(messages=records))
    second = compile_pack(snapshot(messages=tuple(reversed(records))))
    assert first.model_input.newly_delivered == second.model_input.newly_delivered
    assert first.context_hash == second.context_hash


def test_peer_source_enumeration_order_does_not_change_context_structure() -> None:
    bound = snapshot()
    selected = policy()
    actor_opportunity = opportunity(bound, "A")
    projected = VisibilityProjection.project(bound, AgentId("A"), selected)
    ordering = NeutralOrdering(
        selected.ordering,
        OrderingBinding(
            bound.run_id, actor_opportunity.opportunity_id, bound.tick
        ),
    )
    first = build_model_input(projected, selected, ordering=ordering)
    reversed_projection = replace(
        projected, active_peers=tuple(reversed(projected.active_peers))
    )
    second = build_model_input(reversed_projection, selected, ordering=ordering)
    assert first == second


def test_dict_insertion_order_does_not_change_hash() -> None:
    first = {"a": 1, "b": {"x": 2, "y": 3}}
    second = {"b": {"y": 3, "x": 2}, "a": 1}
    first_hash = hashlib.sha256(canonical_bytes(first)).hexdigest()
    second_hash = hashlib.sha256(canonical_bytes(second)).hexdigest()
    assert first_hash == second_hash


def test_DB_row_order_does_not_change_hash() -> None:
    bound = snapshot(
        messages=(
            message("m-a", "B", "A", "one", 0),
            message("m-b", "C", "A", "two", 0),
        ),
        proposals=(proposal("p-a", "A", "B", 0), proposal("p-b", "C", "A", 0)),
    )
    raw = snapshot_to_dict(bound)
    raw["messages"].reverse()
    raw["proposals"].reverse()
    row_reloaded = snapshot_from_dict(raw)
    assert bound.state_hash() == row_reloaded.state_hash()
    assert compile_pack(bound).context_hash == compile_pack(row_reloaded).context_hash


def test_ContextPack_immutable() -> None:
    pack = compile_pack(snapshot())
    with pytest.raises(FrozenInstanceError):
        pack.context_hash = "f" * 64  # type: ignore[misc]


def test_ContextPack_CAS_roundtrip_preserves_hash(tmp_path) -> None:
    pack = compile_pack(snapshot())
    data = serialize_context_pack(pack)
    cas = FileSystemArtifactStore(tmp_path / "cas")
    reference = cas.put_bytes(
        data, media_type="application/json", contract_id="context-pack-1.0.0"
    )
    reloaded = deserialize_context_pack(cas.resolve(reference))
    assert reloaded == pack
    assert reloaded.context_hash == pack.context_hash


def test_context_artifacts_are_durable_commit_evidence(tmp_path) -> None:
    store = SQLiteReferenceStore(
        tmp_path / "context.sqlite", artifact_root=tmp_path / "cas"
    )
    try:
        run = make_run("A", "B")
        store.create_run(run)
        context_pipeline = pipeline(store.artifact_store)
        class AssertP3Barrier(CandidateRuntime):
            def infer(self, compiled):
                assert len(store.artifact_store.list_orphans()) == 2
                return super().infer(compiled)

        result = DeterministicKernel(
            run,
            AssertP3Barrier(),
            committer=store.commit_store,
            context_pipeline=context_pipeline,
        ).run_tick()
        assert len(result.context_artifact_refs) == 2
        assert all(
            store.artifact_store.resolve(reference)
            for reference in result.context_artifact_refs
        )
        commits = store.commit_store.iter_commits(run.run_id)
        assert commits[0].artifact_refs == tuple(
            sorted(
                result.context_artifact_refs,
                key=lambda ref: (ref.artifact_id.value, ref.digest),
            )
        )
    finally:
        store.close()


def test_renderer_byte_deterministic() -> None:
    model_input = compile_pack(snapshot()).model_input
    assert render_model_input_bytes(model_input) == render_model_input_bytes(model_input)
    assert render_model_input_bytes(model_input) == render_model_input(model_input).encode(
        "utf-8"
    )


def test_ContextCompiler_does_not_mutate_Snapshot() -> None:
    bound = snapshot(messages=(message("m-a", "B", "A", "visible", 0),))
    before_hash = bound.state_hash()
    before_value = snapshot_to_dict(bound)
    compile_pack(bound)
    assert bound.state_hash() == before_hash
    assert snapshot_to_dict(bound) == before_value


def test_history_uses_semantic_record_limit_only() -> None:
    records = tuple(
        message(f"m-{index}", "A", "B", f"body-{index}", index)
        for index in range(3)
    )
    bound = snapshot(tick=3, messages=records)
    selected_policy = policy(2)
    projected = VisibilityProjection.project(bound, AgentId("A"), selected_policy)
    order = NeutralOrdering(
        selected_policy.ordering,
        OrderingBinding(
            bound.run_id, opportunity(bound, "A").opportunity_id, bound.tick
        ),
    )
    history = PersonalVisibleHistory.select(
        projected, selected_policy, ordering=order
    )
    assert [record.source_id for record in history] == ["m-1", "m-2"]
    assert not hasattr(selected_policy.history, "token_budget")


def test_adversarial_hidden_sentinels_absent_from_model_representations() -> None:
    private = message(
        "private", "B", "C", "SECRET_PRIVATE_MESSAGE", 0
    )
    hidden_refs = (
        ArtifactRef(ArtifactId("SECRET_PARENT_X"), "1" * 64),
        ArtifactRef(ArtifactId("SECRET_SEED_ABC"), "2" * 64),
    )
    pack = ContextCompiler().compile(
        opportunity(
            snapshot(
                agents=(
                    agent("A", lifespan=987654321),
                    agent("B", lifespan=987654321),
                    agent("C", lifespan=987654321),
                ),
                messages=(private,),
            ),
            "A",
        ),
        policy(),
        model_profile_id="SECRET_RESEARCH_LABEL",
        generation_policy_id="SECRET_SPRITE",
        generation_seed_id="SECRET_SEED_ABC",
        source_artifact_refs=hidden_refs,
    )
    structured = context_pack_to_dict(pack)["model_input"]
    structured_text = json.dumps(structured, ensure_ascii=False, sort_keys=True)
    rendered = render_model_input(pack.model_input)
    for sentinel in (
        "SECRET_PARENT_X",
        "SECRET_PRIVATE_MESSAGE",
        "SECRET_RESEARCH_LABEL",
        "SECRET_SPRITE",
        "SECRET_SEED_ABC",
        "987654321",
    ):
        assert sentinel not in structured_text
        assert sentinel not in rendered
    hidden_keys = {
        "current_tick",
        "natural_death_tick",
        "lifespan_ticks",
        "agent_birth_seq",
        "lineage",
        "seed",
        "researcher_label",
        "sprite",
        "intent_id",
        "actor_id",
    }

    def keys(value):
        if isinstance(value, dict):
            return set(value).union(*(keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(item) for item in value)) if value else set()
        return set()

    assert not hidden_keys.intersection(keys(structured))


def test_parser_rejects_duplicate_or_hidden_identity_fields() -> None:
    parser = ModelActionParser()
    with pytest.raises(ValueError):
        parser.parse(
            '{"action_label":"NO_DIRECTED_ACTION","action_label":"DIRECT_TEXT","payload":{}}'
        )
    with pytest.raises(ValueError):
        parser.parse(
            {"action_label": "NO_DIRECTED_ACTION", "payload": {}, "intent_id": "x"}
        )


def test_runtime_context_contracts_match_machine_contracts(repository_root) -> None:
    contracts = repository_root / "specs" / "contracts"
    action_schema = json.loads(
        (contracts / "action-presentation.schema.json").read_text(encoding="utf-8")
    )
    runtime_action = action_presentation_to_dict(DEFAULT_ACTION_PRESENTATION)
    for name, definition in action_schema["properties"].items():
        if "const" in definition:
            assert runtime_action[name] == definition["const"]
    action_definitions = action_schema["properties"]["actions"]["properties"]
    for action_name, definition in action_definitions.items():
        for field_name, field_definition in definition["properties"].items():
            assert runtime_action["actions"][action_name][field_name] == field_definition["const"]

    policy_schema = json.loads(
        (contracts / "context-policy.schema.json").read_text(encoding="utf-8")
    )
    runtime_policy = policy()
    assert set(policy_schema["properties"]) == {
        field.name for field in fields(runtime_policy)
    }
    for section in (
        "visibility",
        "history",
        "ordering",
        "recall",
        "canonicalization",
        "action_presentation",
    ):
        assert set(policy_schema["properties"][section]["properties"]) == {
            field.name for field in fields(getattr(runtime_policy, section))
        }
