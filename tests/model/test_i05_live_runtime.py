from __future__ import annotations

import json
from pathlib import Path

import pytest

from alifelm.context import (
    ContextCognitionPipeline,
    ContextPolicy,
    DEFAULT_ACTION_PRESENTATION,
    ModelActionParser,
    OrderingPolicy,
    action_presentation_digest,
)
from alifelm.domain import AgentId, ArtifactId, ArtifactRef, Duration, RunId
from alifelm.kernel import DeterministicKernel, EqualOpportunityScheduler, SimulationRun
from alifelm.model import (
    GenerationPolicy,
    LiveCandidateRuntime,
    LiveRuntimeIdentity,
    ModelOutputStatus,
    ModelProfile,
    RawGenerationResult,
    RejectedModelOutput,
)
from alifelm.persistence import FileSystemArtifactStore


BASE_DIGEST = "36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f"
ADAPTER_DIGEST = "46917511362243be67e0783ddb7411a96f26613c1083bc4f95117d910d0998ec"
BASE_REVISION = "48d788eca847d4d7548f375ad03d3c9312f6139e"
TOKENIZER_DIGEST = "c448b9e69576a2af5fccdb905c4d6c9f6c0d06509b15d2459a3bc92bb33d42ff"


def _profile() -> ModelProfile:
    return ModelProfile(
        profile_id="world-v0-fa-v1",
        profile_version="1.0.0",
        model_identifier="local/olmo",
        model_revision=BASE_REVISION,
        model_digest=BASE_DIGEST,
        tokenizer_identifier="local/olmo-tokenizer",
        tokenizer_revision=BASE_REVISION,
        tokenizer_digest=TOKENIZER_DIGEST,
        model_class="AUTO_CAUSAL_LM",
        generation_policy_id="world-v0-greedy",
        device="cpu",
        dtype="float32",
        adapter_ref=ArtifactRef(ArtifactId("fa-v1"), ADAPTER_DIGEST),
        trust_remote_code=False,
        add_special_tokens=True,
    )


def _policy() -> GenerationPolicy:
    return GenerationPolicy(
        policy_id="world-v0-greedy",
        version="1.0.0",
        max_new_tokens=32,
        do_sample=False,
        temperature=None,
        top_p=None,
        top_k=None,
        repetition_penalty=1.0,
        seed_id="world-seed",
        stop_policy_id=None,
    )


def _identity() -> LiveRuntimeIdentity:
    return LiveRuntimeIdentity(
        base_model_repo="allenai/OLMo-2-0425-1B-Instruct",
        base_model_revision=BASE_REVISION,
        base_checkpoint_sha256=BASE_DIGEST,
        tokenizer_revision=BASE_REVISION,
        tokenizer_digest=TOKENIZER_DIGEST,
        adapter_sha256=ADAPTER_DIGEST,
    )


def _context_policy() -> ContextPolicy:
    return ContextPolicy.exp000(
        max_prior_visible_records=2,
        ordering=OrderingPolicy(
            policy_version="1.0.0",
            unordered_collection_algorithm="ALIFELM_CONTEXT_ORDER_V1",
            digest_algorithm="sha256",
            ordering_seed_id="world-order",
            ordering_seed_digest="2" * 64,
            cross_tick_order="COMMITTED_TICK_CHRONOLOGICAL",
            tie_breaker="FULL_STABLE_ITEM_KEY",
        ),
        action_presentation_digest=action_presentation_digest(
            DEFAULT_ACTION_PRESENTATION
        ),
    )


def _run(run_id: str = "world-run", *agents: str) -> SimulationRun:
    return SimulationRun.bootstrap(
        RunId(run_id),
        lifespan_ticks=Duration(20),
        founder_ids=tuple(AgentId(value) for value in (agents or ("A",))),
    )


def _pipeline(store: FileSystemArtifactStore) -> ContextCognitionPipeline:
    return ContextCognitionPipeline(
        _context_policy(),
        model_profile_id=_profile().profile_id,
        generation_policy_id=_policy().policy_id,
        generation_seed_id="world-seed",
        artifact_store=store,
    )


def _raw(request, text: str) -> RawGenerationResult:
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
        raw_text=text,
        token_ids=(1, 2),
        model_profile_id=request.model_profile.profile_id,
        generation_policy_id=request.generation_policy.policy_id,
        generation_policy_version=request.generation_policy.version,
        generation_seed_id=request.generation_seed_id,
        generation_seed=request.generation_seed,
        finish_reason="completed",
    )


class ScriptedBackend:
    def __init__(self, profile: ModelProfile, texts: dict[str, str], *, mutate: str | None = None):
        self.profile = profile
        self.texts = texts
        self.mutate = mutate
        self.calls: list[str] = []

    def generate(self, request):
        self.calls.append(request.opportunity_id.value)
        result = _raw(request, self.texts.get(request.opportunity_id.value, _wait()))
        if self.mutate == "context_hash":
            return RawGenerationResult(
                opportunity_id=result.opportunity_id,
                generation_id=result.generation_id,
                context_pack_id=result.context_pack_id,
                context_hash="f" * 64,
                rendered_input_hash=result.rendered_input_hash,
                interface_treatment_id=result.interface_treatment_id,
                interface_treatment_version=result.interface_treatment_version,
                interface_treatment_digest=result.interface_treatment_digest,
                constraint_policy_id=result.constraint_policy_id,
                raw_text=result.raw_text,
                token_ids=result.token_ids,
                model_profile_id=result.model_profile_id,
                generation_policy_id=result.generation_policy_id,
                generation_policy_version=result.generation_policy_version,
                generation_seed_id=result.generation_seed_id,
                generation_seed=result.generation_seed,
                finish_reason=result.finish_reason,
            )
        return result


def _wait() -> str:
    return json.dumps({"action_label": "NO_DIRECTED_ACTION", "payload": {}})


def _send(target: str, body: str = "hello") -> str:
    return json.dumps(
        {
            "action_label": "DIRECT_TEXT",
            "payload": {"body": body, "target_agent_id": target},
        }
    )


def _live(
    store: FileSystemArtifactStore,
    backend: ScriptedBackend,
    *,
    parser: ModelActionParser | None = None,
) -> LiveCandidateRuntime:
    return LiveCandidateRuntime(
        backend,
        profile=_profile(),
        generation_policy=_policy(),
        artifact_store=store,
        identity=_identity(),
        parser=parser,
    )


def _scripts_for(run: SimulationRun, values: dict[str, str]) -> dict[str, str]:
    return {
        opportunity.opportunity_id.value: values.get(str(opportunity.agent_id), _wait())
        for opportunity in EqualOpportunityScheduler().enumerate(run.snapshot)
    }


def test_live_runtime_load_once_and_identity_is_startup_bound(tmp_path: Path) -> None:
    run = _run("load-once", "A", "B", "C")
    store = FileSystemArtifactStore(tmp_path / "cas")
    counts = {"base": 0, "tokenizer": 0, "adapter": 0}

    def loader(profile):
        del profile
        counts["base"] += 1
        counts["tokenizer"] += 1
        counts["adapter"] += 1
        return ScriptedBackend(_profile(), _scripts_for(run, {}))

    runtime = LiveCandidateRuntime.from_loader(
        loader,
        profile=_profile(),
        generation_policy=_policy(),
        artifact_store=store,
        identity=_identity(),
    )
    compiled = _pipeline(store).compile_all(
        EqualOpportunityScheduler().enumerate(run.snapshot)
    )
    for item in compiled:
        runtime.infer(item)
    assert counts == {"base": 1, "tokenizer": 1, "adapter": 1}


def test_live_runtime_forces_loaded_model_to_immutable_eval_mode(tmp_path: Path) -> None:
    class Parameter:
        requires_grad = True

        def requires_grad_(self, value):
            self.requires_grad = value
            return self

    class Model:
        training = True

        def __init__(self):
            self.parameters_seen = [Parameter(), Parameter()]

        def eval(self):
            self.training = False
            return self

        def parameters(self):
            return iter(self.parameters_seen)

    class Backend(ScriptedBackend):
        def __init__(self):
            super().__init__(_profile(), {})
            self.model = Model()

    backend = Backend()
    _live(FileSystemArtifactStore(tmp_path / "cas"), backend)
    assert backend.model.training is False
    assert all(parameter.requires_grad is False for parameter in backend.model.parameters_seen)


def test_live_runtime_rejects_wrong_startup_adapter_digest(tmp_path: Path) -> None:
    profile = _profile()
    wrong = _identity()
    wrong = LiveRuntimeIdentity(
        wrong.base_model_repo,
        wrong.base_model_revision,
        wrong.base_checkpoint_sha256,
        wrong.tokenizer_revision,
        wrong.tokenizer_digest,
        "b" * 64,
    )
    with pytest.raises(Exception, match="adapter digest"):
        LiveCandidateRuntime(
            ScriptedBackend(profile, {}),
            profile=profile,
            generation_policy=_policy(),
            artifact_store=FileSystemArtifactStore(tmp_path / "cas-2"),
            identity=wrong,
        )


def test_live_runtime_rejects_wrong_startup_tokenizer_digest(tmp_path: Path) -> None:
    profile = _profile()
    identity = _identity()
    wrong = LiveRuntimeIdentity(
        identity.base_model_repo,
        identity.base_model_revision,
        identity.base_checkpoint_sha256,
        identity.tokenizer_revision,
        "c" * 64,
        identity.adapter_sha256,
    )
    with pytest.raises(Exception, match="tokenizer digest"):
        LiveCandidateRuntime(
            ScriptedBackend(profile, {}),
            profile=profile,
            generation_policy=_policy(),
            artifact_store=FileSystemArtifactStore(tmp_path / "cas-tokenizer"),
            identity=wrong,
        )


def test_live_runtime_rejects_wrong_startup_tokenizer_revision(tmp_path: Path) -> None:
    profile = _profile()
    identity = _identity()
    wrong = LiveRuntimeIdentity(
        identity.base_model_repo,
        identity.base_model_revision,
        identity.base_checkpoint_sha256,
        "revision-other",
        identity.tokenizer_digest,
        identity.adapter_sha256,
    )
    with pytest.raises(Exception, match="tokenizer revision"):
        LiveCandidateRuntime(
            ScriptedBackend(profile, {}),
            profile=profile,
            generation_policy=_policy(),
            artifact_store=FileSystemArtifactStore(tmp_path / "cas-tokenizer-revision"),
            identity=wrong,
        )


def test_live_runtime_accepts_local_paths_by_digest_not_path_name(tmp_path: Path) -> None:
    profile = _profile()
    path_profile = ModelProfile(
        profile_id=profile.profile_id,
        profile_version=profile.profile_version,
        model_identifier=str(tmp_path / "resolved-base"),
        model_revision=profile.model_revision,
        model_digest=profile.model_digest,
        tokenizer_identifier=str(tmp_path / "resolved-tokenizer"),
        tokenizer_revision=profile.tokenizer_revision,
        tokenizer_digest=profile.tokenizer_digest,
        model_class=profile.model_class,
        generation_policy_id=profile.generation_policy_id,
        device=profile.device,
        dtype=profile.dtype,
        adapter_ref=profile.adapter_ref,
        trust_remote_code=profile.trust_remote_code,
        add_special_tokens=profile.add_special_tokens,
    )
    runtime = ScriptedBackend(path_profile, {})
    LiveCandidateRuntime(
        runtime,
        profile=path_profile,
        generation_policy=_policy(),
        artifact_store=FileSystemArtifactStore(tmp_path / "cas-local"),
        identity=_identity(),
    )


def test_live_runtime_rejects_hub_source_identifier_mismatch(tmp_path: Path) -> None:
    profile = _profile()
    source_profile = ModelProfile(
        profile_id=profile.profile_id,
        profile_version=profile.profile_version,
        model_identifier="other-org/model",
        model_revision=profile.model_revision,
        model_digest=profile.model_digest,
        tokenizer_identifier=profile.tokenizer_identifier,
        tokenizer_revision=profile.tokenizer_revision,
        tokenizer_digest=profile.tokenizer_digest,
        model_class=profile.model_class,
        generation_policy_id=profile.generation_policy_id,
        device=profile.device,
        dtype=profile.dtype,
        adapter_ref=profile.adapter_ref,
        trust_remote_code=profile.trust_remote_code,
        add_special_tokens=profile.add_special_tokens,
    )
    with pytest.raises(Exception, match="source identifier"):
        LiveCandidateRuntime(
            ScriptedBackend(source_profile, {}),
            profile=source_profile,
            generation_policy=_policy(),
            artifact_store=FileSystemArtifactStore(tmp_path / "cas-source"),
            identity=_identity(),
        )
def test_raw_identity_mismatch_is_infrastructure_failure(tmp_path: Path) -> None:
    run = _run("identity-failure")
    store = FileSystemArtifactStore(tmp_path / "cas")
    compiled = _pipeline(store).compile_all(
        EqualOpportunityScheduler().enumerate(run.snapshot)
    )
    backend = ScriptedBackend(_profile(), {}, mutate="context_hash")
    runtime = _live(store, backend)
    with pytest.raises(ValueError, match="raw result context hash"):
        runtime.infer(compiled[0])
    assert not list(store.list_orphans()) or all(
        store.resolve(reference) != b"{}" for reference in store.list_orphans()
    )


def test_malformed_attempt_is_durable_and_never_wait_or_retry(tmp_path: Path) -> None:
    run = _run("mixed", "A", "B", "C")
    store = FileSystemArtifactStore(tmp_path / "cas")
    pipeline = _pipeline(store)
    opportunities = EqualOpportunityScheduler().enumerate(run.snapshot)
    values = {"A": _send("B"), "B": "{", "C": _wait()}
    backend = ScriptedBackend(_profile(), _scripts_for(run, values))
    result = pipeline.run(opportunities, _live(store, backend))

    assert len(result.attempts) == 3
    rejected = next(item for item in result.attempts if str(item.opportunity_id) == str(opportunities[1].opportunity_id))
    assert rejected.candidate is None
    assert rejected.parse_status is ModelOutputStatus.TRUNCATED
    assert rejected.rejection is not None
    assert rejected.rejection.status is ModelOutputStatus.TRUNCATED
    assert rejected.evidence_ref is not None and store.is_durable(rejected.evidence_ref)
    evidence = json.loads(store.resolve(rejected.evidence_ref))
    assert store.is_durable(
        ArtifactRef(
            ArtifactId(evidence["raw_text_ref"]["artifact_id"]),
            evidence["raw_text_ref"]["digest"],
        )
    )
    assert store.is_durable(
        ArtifactRef(
            ArtifactId(evidence["raw_generation_ref"]["artifact_id"]),
            evidence["raw_generation_ref"]["digest"],
        )
    )
    assert len(result.intent_batch.intents) == 2
    assert all(str(intent.actor_id) != "B" for intent in result.intent_batch.intents)
    assert len(backend.calls) == 3


def test_cas_failure_aborts_before_parse(tmp_path: Path) -> None:
    class FailingStore(FileSystemArtifactStore):
        def put_bytes(self, data: bytes, **kwargs):
            if kwargs.get("contract_id") == "raw-model-text-1.0.0":
                raise OSError("raw CAS unavailable")
            return super().put_bytes(data, **kwargs)

    class CountingParser(ModelActionParser):
        calls = 0

        def parse(self, value):
            self.calls += 1
            return super().parse(value)

    run = _run("cas-failure")
    store = FailingStore(tmp_path / "cas")
    compiled = _pipeline(store).compile_all(
        EqualOpportunityScheduler().enumerate(run.snapshot)
    )
    parser = CountingParser()
    with pytest.raises(OSError, match="raw CAS unavailable"):
        _live(store, ScriptedBackend(_profile(), {}), parser=parser).infer(compiled[0])
    assert parser.calls == 0


def test_rendered_model_input_has_no_hidden_opportunity_or_snapshot_authority(tmp_path: Path) -> None:
    run = _run("visibility", "A", "B")
    opportunity = EqualOpportunityScheduler().enumerate(run.snapshot)[0]
    compiled = _pipeline(FileSystemArtifactStore(tmp_path / "cas")).compile_all((opportunity,))[0]
    rendered = compiled.rendered_input.decode("utf-8")
    assert str(opportunity.opportunity_id) not in rendered
    assert run.snapshot.state_hash() not in rendered
    assert "lineage" not in rendered.lower()
    assert "private" not in rendered.lower()
    assert "commit_id" not in rendered.lower()


@pytest.mark.parametrize(
    "completion_order",
    [
        ("A", "B", "C"),
        ("C", "B", "A"),
        ("B", "C", "A"),
    ],
)
def test_completion_order_produces_same_live_tick(tmp_path: Path, completion_order: tuple[str, ...]) -> None:
    run = _run("completion-order", "A", "B", "C")
    store = FileSystemArtifactStore(tmp_path / "cas")
    opportunities = EqualOpportunityScheduler().enumerate(run.snapshot)
    backend = ScriptedBackend(
        _profile(),
        _scripts_for(run, {"A": _send("B"), "B": _wait(), "C": _wait()}),
    )
    pipeline = _pipeline(store)
    result = DeterministicKernel(
        run,
        _live(store, backend),
        context_pipeline=pipeline,
    ).run_tick(completion_order=tuple(AgentId(item) for item in completion_order))
    assert tuple(item.context_hash for item in result.context_packs) == tuple(
        item.context_pack.context_hash for item in pipeline.compile_all(opportunities)
    )
    assert all(item.generation_id for item in result.cognition_attempts)
    assert tuple(str(intent.actor_id) for intent in result.intent_batch.intents) == ("A", "B", "C")[: len(result.intent_batch.intents)]
    assert result.commit_result.committed


def test_three_completion_orders_have_identical_canonical_results(tmp_path: Path) -> None:
    snapshots = []
    fragments = []
    attempt_views = []
    context_views = []
    intent_views = []
    for index, completion_order in enumerate(
        (("A", "B", "C"), ("C", "B", "A"), ("B", "C", "A"))
    ):
        run = _run("same-order", "A", "B", "C")
        store = FileSystemArtifactStore(tmp_path / f"cas-{index}")
        backend = ScriptedBackend(
            _profile(),
            _scripts_for(run, {"A": _send("B"), "B": _wait(), "C": _wait()}),
        )
        result = DeterministicKernel(
            run,
            _live(store, backend),
            context_pipeline=_pipeline(store),
        ).run_tick(completion_order=tuple(AgentId(item) for item in completion_order))
        snapshots.append(result.commit_result.snapshot)
        fragments.append(result.fragments)
        context_views.append(tuple(item.context_hash for item in result.context_packs))
        intent_views.append(result.intent_batch)
        attempt_views.append(
            tuple(
                (str(item.opportunity_id), item.generation_id, item.parse_status, item.candidate)
                for item in result.cognition_attempts
            )
        )
    assert snapshots[0] == snapshots[1] == snapshots[2]
    assert fragments[0] == fragments[1] == fragments[2]
    assert context_views[0] == context_views[1] == context_views[2]
    assert intent_views[0] == intent_views[1] == intent_views[2]
    assert attempt_views[0] == attempt_views[1] == attempt_views[2]


def test_headless_live_vertical_slice_keeps_raw_text_out_of_canonical_state(tmp_path: Path) -> None:
    run = _run("headless", "A", "B", "C")
    store = FileSystemArtifactStore(tmp_path / "cas")
    backend = ScriptedBackend(
        _profile(),
        _scripts_for(run, {"A": _send("B"), "B": "RAW_ONLY_EVIDENCE", "C": _wait()}),
    )
    result = DeterministicKernel(
        run,
        _live(store, backend),
        context_pipeline=_pipeline(store),
    ).run_tick()
    assert result.commit_result.committed
    assert len(result.cognition_attempts) == 3
    assert len(result.intent_batch.intents) == 2
    assert any(item.rejection is not None for item in result.cognition_attempts)
    assert all(
        item.evidence_ref is not None and store.is_durable(item.evidence_ref)
        for item in result.cognition_attempts
    )
    assert "RAW_ONLY_EVIDENCE" not in repr(result.commit_result.snapshot)
    assert any(str(message.body) == "hello" for message in result.commit_result.snapshot.messages)
