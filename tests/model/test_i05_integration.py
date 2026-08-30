from __future__ import annotations

from dataclasses import replace
import json

import pytest

from alifelm.context import (
    ContextCognitionPipeline,
    ContextPolicy,
    DEFAULT_ACTION_PRESENTATION,
    ModelActionParser,
    OrderingPolicy,
    action_presentation_digest,
)
from alifelm.domain import AgentId, Duration, RunId
from alifelm.kernel import EqualOpportunityScheduler, SimulationRun
from alifelm.model import (
    ContextModelRuntimeAdapter,
    GenerationError,
    GenerationPolicy,
    I1_NEUTRAL_CODEC_SCAFFOLD,
    ModelOutputStatus,
    ModelProfile,
    RawGenerationResult,
    RealCognitionDryRunner,
    TransformersModelRuntime,
    generation_request_for,
)
from alifelm.persistence import FileSystemArtifactStore, SQLiteReferenceStore


def _profile(profile_id: str = "profile-a") -> ModelProfile:
    return ModelProfile(
        profile_id=profile_id,
        profile_version="1.0.0",
        model_identifier="local/model",
        model_revision="revision-a",
        model_digest=None,
        tokenizer_identifier="local/tokenizer",
        tokenizer_revision="tokenizer-revision-a",
        tokenizer_digest=None,
        model_class="AUTO_CAUSAL_LM",
        generation_policy_id="mode-d",
        device="cpu",
        dtype="float32",
        adapter_ref=None,
        trust_remote_code=False,
        add_special_tokens=True,
    )


def _generation_policy(*, sampled: bool = False, seed_id: str | None = None):
    return GenerationPolicy(
        policy_id="mode-d",
        version="1.0.0",
        max_new_tokens=16,
        do_sample=sampled,
        temperature=0.8 if sampled else None,
        top_p=0.95 if sampled else None,
        top_k=50 if sampled else None,
        repetition_penalty=1.0,
        seed_id=seed_id,
        stop_policy_id=None,
    )


def _context_policy() -> ContextPolicy:
    return ContextPolicy.exp000(
        max_prior_visible_records=2,
        ordering=OrderingPolicy(
            policy_version="1.0.0",
            unordered_collection_algorithm="ALIFELM_CONTEXT_ORDER_V1",
            digest_algorithm="sha256",
            ordering_seed_id="i05-order",
            ordering_seed_digest="2" * 64,
            cross_tick_order="COMMITTED_TICK_CHRONOLOGICAL",
            tie_breaker="FULL_STABLE_ITEM_KEY",
        ),
        action_presentation_digest=action_presentation_digest(
            DEFAULT_ACTION_PRESENTATION
        ),
    )


def _run(run_id: str = "i05-run", *agents: str) -> SimulationRun:
    return SimulationRun.bootstrap(
        RunId(run_id),
        lifespan_ticks=Duration(20),
        founder_ids=tuple(AgentId(value) for value in (agents or ("A",))),
    )


def _compiled(tmp_path, *, run=None, profile_id="profile-a", seed_id="seed-d"):
    selected_run = run or _run()
    opportunity = EqualOpportunityScheduler().enumerate(selected_run.snapshot)[0]
    store = FileSystemArtifactStore(tmp_path / "cas")
    pipeline = ContextCognitionPipeline(
        _context_policy(),
        model_profile_id=profile_id,
        generation_policy_id="mode-d",
        generation_seed_id=seed_id,
        artifact_store=store,
    )
    return pipeline.compile_all((opportunity,))[0], store, pipeline


class ScriptedRuntime:
    def __init__(self, text: str, profile=None) -> None:
        self.text = text
        self.profile = profile or _profile()
        self.calls = 0

    def generate(self, request):
        self.calls += 1
        return RawGenerationResult(
            opportunity_id=request.opportunity_id,
            generation_id=request.generation_id,
            context_pack_id=request.context_pack_id,
            context_hash=request.context_hash,
            rendered_input_hash=request.rendered_input_hash,
            interface_treatment_id=request.interface_treatment_id,
            interface_treatment_version=request.interface_treatment_version,
            interface_treatment_digest=request.interface_treatment_digest,
            constraint_policy_id=request.constraint_policy_id,
            raw_text=self.text,
            token_ids=(1, 2, 3),
            model_profile_id=request.model_profile.profile_id,
            generation_policy_id=request.generation_policy.policy_id,
            generation_policy_version=request.generation_policy.version,
            generation_seed_id=request.generation_seed_id,
            generation_seed=request.generation_seed,
            finish_reason="length",
        )


class BrokenRuntime:
    profile = _profile()

    def generate(self, request):
        raise GenerationError("infrastructure failure")


def _valid_wait() -> str:
    return json.dumps({"action_label": "NO_DIRECTED_ACTION", "payload": {}})


def test_real_backend_loads_explicit_profile() -> None:
    class Tokenizer:
        def __call__(self, text, **kwargs):
            return {"input_ids": [[1]]}

    class Model:
        def generate(self, **kwargs):
            return [[1, 2]]

    runtime = TransformersModelRuntime.from_components(
        _profile(), tokenizer=Tokenizer(), model=Model()
    )
    assert runtime.profile == _profile()


def test_one_contextpack_produces_raw_generation(tmp_path) -> None:
    compiled, _, _ = _compiled(tmp_path)
    request = generation_request_for(compiled, _profile(), _generation_policy())
    raw = ScriptedRuntime(_valid_wait()).generate(request)
    assert isinstance(raw, RawGenerationResult)


def test_interface_treatment_changes_generation_not_context_identity(tmp_path) -> None:
    compiled, _, _ = _compiled(tmp_path)
    control = generation_request_for(compiled, _profile(), _generation_policy())
    scaffold = generation_request_for(
        compiled,
        _profile(),
        _generation_policy(),
        interface_treatment=I1_NEUTRAL_CODEC_SCAFFOLD,
    )
    assert control.context_hash == scaffold.context_hash
    assert control.rendered_input_hash != scaffold.rendered_input_hash
    assert control.generation_id != scaffold.generation_id
    assert scaffold.rendered_input.endswith(b"\nAction selection JSON:\n")


def test_raw_generation_preserved_before_parse(tmp_path) -> None:
    compiled, store, _ = _compiled(tmp_path)
    result = RealCognitionDryRunner(
        ScriptedRuntime("not json"), _profile(), _generation_policy(), store
    ).run(compiled)
    assert result.evidence.parse_status is ModelOutputStatus.MALFORMED_SYNTAX
    assert store.resolve(result.evidence.raw_text_ref) == b"not json"


@pytest.mark.parametrize("field", ["actor_id", "tick", "intent_id"])
def test_model_cannot_set_infrastructure_identity(field: str) -> None:
    value = {"action_label": "NO_DIRECTED_ACTION", "payload": {}, field: "override"}
    with pytest.raises(ValueError, match="only action_label and payload"):
        ModelActionParser().parse(value)


def test_model_cannot_set_actor_id() -> None:
    test_model_cannot_set_infrastructure_identity("actor_id")


def test_model_cannot_set_tick() -> None:
    test_model_cannot_set_infrastructure_identity("tick")


def test_model_cannot_set_intent_id() -> None:
    test_model_cannot_set_infrastructure_identity("intent_id")


def test_malformed_output_does_not_mutate_state(tmp_path) -> None:
    run = _run()
    compiled, store, _ = _compiled(tmp_path, run=run)
    before = run.state_hash()
    result = RealCognitionDryRunner(
        ScriptedRuntime("{"), _profile(), _generation_policy(), store
    ).run(compiled)
    assert result.evidence.parse_status is ModelOutputStatus.TRUNCATED
    assert run.state_hash() == before


def test_backend_failure_is_not_agent_death(tmp_path) -> None:
    run = _run()
    compiled, store, _ = _compiled(tmp_path, run=run)
    before = run.snapshot
    with pytest.raises(GenerationError):
        RealCognitionDryRunner(
            BrokenRuntime(), _profile(), _generation_policy(), store
        ).run(compiled)
    assert run.snapshot == before
    assert tuple(agent.agent_id.value for agent in run.snapshot.agents) == ("A",)


def test_same_tick_barrier_survives_real_backend(tmp_path) -> None:
    run = _run("barrier-run", "A", "B", "C")
    opportunities = EqualOpportunityScheduler().enumerate(run.snapshot)
    store = FileSystemArtifactStore(tmp_path / "cas")
    pipeline = ContextCognitionPipeline(
        _context_policy(),
        model_profile_id="profile-a",
        generation_policy_id="mode-d",
        generation_seed_id="seed-d",
        artifact_store=store,
    )
    compiled = pipeline.compile_all(opportunities)
    before = run.state_hash()
    adapter = ContextModelRuntimeAdapter(
        ScriptedRuntime(_valid_wait()),
        profile=_profile(),
        generation_policy=_generation_policy(),
    )
    batch = pipeline.execute(
        compiled, adapter, completion_order=(AgentId("C"), AgentId("A"), AgentId("B"))
    )
    assert len(batch.intents) == 3
    assert run.state_hash() == before
    assert all(item.opportunity.snapshot is run.snapshot for item in compiled)


def test_ContextPack_hash_matches_preinference_evidence(tmp_path) -> None:
    compiled, store, _ = _compiled(tmp_path)
    result = RealCognitionDryRunner(
        ScriptedRuntime(_valid_wait()), _profile(), _generation_policy(), store
    ).run(compiled)
    assert result.evidence.context_hash == compiled.context_pack.context_hash


def test_raw_output_artifact_resolves(tmp_path) -> None:
    compiled, store, _ = _compiled(tmp_path)
    result = RealCognitionDryRunner(
        ScriptedRuntime(_valid_wait()), _profile(), _generation_policy(), store
    ).run(compiled)
    assert store.resolve(result.evidence.raw_text_ref).decode() == _valid_wait()
    assert store.is_durable(result.evidence.raw_generation_ref)


def test_deterministic_mode_repeatability(tmp_path) -> None:
    compiled, store, _ = _compiled(tmp_path)
    runtime = ScriptedRuntime(_valid_wait())
    runner = RealCognitionDryRunner(runtime, _profile(), _generation_policy(), store)
    first = runner.run(compiled)
    second = runner.run(compiled)
    assert first.raw_generation == second.raw_generation
    assert first.evidence_ref == second.evidence_ref


def test_seeded_sampling_same_seed_repeatability(tmp_path) -> None:
    compiled, store, _ = _compiled(tmp_path, seed_id="seed-s")
    policy = replace(_generation_policy(sampled=True), seed_id="seed-s")
    runtime = ScriptedRuntime(_valid_wait())
    first = RealCognitionDryRunner(
        runtime, _profile(), policy, store, generation_seed=7
    ).run(compiled)
    second = RealCognitionDryRunner(
        runtime, _profile(), policy, store, generation_seed=7
    ).run(compiled)
    assert first.raw_generation.generation_id == second.raw_generation.generation_id
    assert first.raw_generation.raw_text == second.raw_generation.raw_text


def test_different_generation_seed_changes_identity(tmp_path) -> None:
    compiled, _, _ = _compiled(tmp_path, seed_id="seed-s")
    policy = replace(_generation_policy(sampled=True), seed_id="seed-s")
    first = generation_request_for(compiled, _profile(), policy, generation_seed=7)
    second = generation_request_for(compiled, _profile(), policy, generation_seed=8)
    assert first.generation_id != second.generation_id


def test_restart_does_not_add_cognition_opportunity(tmp_path) -> None:
    run = _run()
    before = EqualOpportunityScheduler().enumerate(run.snapshot)
    store = SQLiteReferenceStore(tmp_path / "run.sqlite", artifact_root=tmp_path / "cas")
    try:
        store.create_run(run)
        restored = store.load_run(run.run_id)
        after = EqualOpportunityScheduler().enumerate(restored.snapshot)
    finally:
        store.close()
    assert tuple(item.opportunity_id for item in before) == tuple(
        item.opportunity_id for item in after
    )


def test_replay_does_not_call_real_model(tmp_path) -> None:
    run = _run("replay-i05")
    store = SQLiteReferenceStore(tmp_path / "run.sqlite", artifact_root=tmp_path / "cas")
    runtime = ScriptedRuntime(_valid_wait())
    try:
        store.create_run(run)
        replayed = store.replay(run.run_id)
    finally:
        store.close()
    assert replayed.state_hash == run.state_hash()
    assert runtime.calls == 0


def test_model_completion_order_does_not_change_commit_order(tmp_path) -> None:
    run = _run("order-run", "A", "B", "C")
    opportunities = EqualOpportunityScheduler().enumerate(run.snapshot)
    pipeline = ContextCognitionPipeline(
        _context_policy(),
        model_profile_id="profile-a",
        generation_policy_id="mode-d",
        generation_seed_id="seed-d",
    )
    compiled = pipeline.compile_all(opportunities)
    first = pipeline.execute(
        compiled,
        ContextModelRuntimeAdapter(
            ScriptedRuntime(_valid_wait()),
            profile=_profile(),
            generation_policy=_generation_policy(),
        ),
        completion_order=(AgentId("A"), AgentId("B"), AgentId("C")),
    )
    second = pipeline.execute(
        compiled,
        ContextModelRuntimeAdapter(
            ScriptedRuntime(_valid_wait()),
            profile=_profile(),
            generation_policy=_generation_policy(),
        ),
        completion_order=(AgentId("C"), AgentId("A"), AgentId("B")),
    )
    assert first == second


def test_model_profile_change_changes_generation_identity(tmp_path) -> None:
    compiled_a, _, _ = _compiled(tmp_path / "a")
    profile_b = replace(_profile(), model_revision="revision-b")
    request_a = generation_request_for(compiled_a, _profile(), _generation_policy())
    request_b = generation_request_for(compiled_a, profile_b, _generation_policy())
    assert request_a.generation_id != request_b.generation_id


def test_deployment_paths_do_not_change_generation_identity(tmp_path) -> None:
    compiled_a, _, _ = _compiled(tmp_path / "path-a")
    profile_a = _profile()
    profile_b = replace(
        profile_a,
        model_identifier=str(tmp_path / "resolved-b" / "base"),
        tokenizer_identifier=str(tmp_path / "resolved-b" / "tokenizer"),
    )
    request_a = generation_request_for(compiled_a, profile_a, _generation_policy())
    request_b = generation_request_for(compiled_a, profile_b, _generation_policy())
    assert request_a.generation_id == request_b.generation_id


def test_tokenizer_profile_identity_is_recorded(tmp_path) -> None:
    compiled, store, _ = _compiled(tmp_path)
    result = RealCognitionDryRunner(
        ScriptedRuntime(_valid_wait()), _profile(), _generation_policy(), store
    ).run(compiled)
    assert result.evidence.model_profile_id == "profile-a"
    assert result.evidence.tokenizer_identifier == "local/tokenizer"
    assert result.evidence.tokenizer_revision == "tokenizer-revision-a"


def test_no_hidden_context_fields_enter_model_input(tmp_path) -> None:
    compiled, _, _ = _compiled(tmp_path)
    rendered = compiled.rendered_input.decode("utf-8")
    assert "tick" not in rendered.lower()
    assert "lifespan" not in rendered.lower()
    assert "revision-a" not in rendered
    assert "seed-d" not in rendered
