from __future__ import annotations

from dataclasses import fields
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from alifelm.context import ContextCognitionPipeline, ContextPolicy, OrderingPolicy
from alifelm.domain import AgentId, Duration, RunId, Tick
from alifelm.kernel import EqualOpportunityScheduler, SimulationRun
from alifelm.model import (
    ContextModelRuntimeAdapter,
    GenerationPolicy,
    GenerationRequest,
    ModelLoadError,
    ModelProfile,
    RawGenerationResult,
    TransformersModelRuntime,
    generation_request_for,
)
from alifelm.context import (
    DEFAULT_ACTION_PRESENTATION,
    action_presentation_digest,
)


def profile() -> ModelProfile:
    return ModelProfile(
        profile_id="model-profile",
        profile_version="1.0.0",
        model_identifier="local/model",
        model_revision=None,
        model_digest=None,
        tokenizer_identifier="local/tokenizer",
        tokenizer_revision=None,
        tokenizer_digest=None,
        model_class="AUTO_CAUSAL_LM",
        generation_policy_id="generation-policy",
        device="cpu",
        dtype="auto",
        adapter_ref=None,
        trust_remote_code=False,
        add_special_tokens=True,
    )


def generation_policy() -> GenerationPolicy:
    return GenerationPolicy(
        policy_id="generation-policy",
        version="1.0.0",
        max_new_tokens=12,
        do_sample=False,
        temperature=None,
        top_p=None,
        top_k=None,
        repetition_penalty=1.0,
        seed_id=None,
        stop_policy_id=None,
    )


def policy() -> ContextPolicy:
    return ContextPolicy.exp000(
        max_prior_visible_records=4,
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
    )


def compiled_context():
    run = SimulationRun.bootstrap(
        RunId("model-run"),
        lifespan_ticks=Duration(20),
        founder_ids=(AgentId("A"),),
    )
    opportunity = EqualOpportunityScheduler().enumerate(run.snapshot)[0]
    pipeline = ContextCognitionPipeline(
        policy(),
        model_profile_id="model-profile",
        generation_policy_id="generation-policy",
        generation_seed_id="generation-seed",
    )
    return pipeline.compile_all((opportunity,))[0]


class ScriptedRawRuntime:
    def __init__(self, raw_text: str) -> None:
        self.raw_text = raw_text
        self.requests: list[GenerationRequest] = []

    def generate(self, request: GenerationRequest) -> RawGenerationResult:
        self.requests.append(request)
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
            raw_text=self.raw_text,
            token_ids=(17, 18),
            model_profile_id=request.model_profile.profile_id,
            generation_policy_id=request.generation_policy.policy_id,
            generation_policy_version=request.generation_policy.version,
            generation_seed_id=request.generation_seed_id,
            generation_seed=request.generation_seed,
            finish_reason=None,
        )


def wait_text() -> str:
    return json.dumps({"action_label": "NO_DIRECTED_ACTION", "payload": {}})


def test_model_profile_and_generation_contracts_are_frozen() -> None:
    assert profile().profile_id == "model-profile"
    assert generation_policy().max_new_tokens == 12
    with pytest.raises(ValueError):
        ModelProfile(
            profile_id="model-profile",
            profile_version="1.0.0",
            model_identifier="local/model",
            model_revision=None,
            model_digest="not-a-digest",
            tokenizer_identifier="local/tokenizer",
            tokenizer_revision=None,
            tokenizer_digest=None,
            model_class="AUTO_CAUSAL_LM",
            generation_policy_id="generation-policy",
            device="cpu",
            dtype="auto",
            adapter_ref=None,
            trust_remote_code=False,
            add_special_tokens=True,
        )


def test_new_machine_contracts_match_frozen_python_types(repository_root: Path) -> None:
    for python_type, schema_name in (
        (ModelProfile, "model-profile.schema.json"),
        (GenerationPolicy, "generation-policy.schema.json"),
        (RawGenerationResult, "raw-generation-result.schema.json"),
    ):
        schema = json.loads(
            (repository_root / "specs" / "contracts" / schema_name).read_text(
                encoding="utf-8"
            )
        )
        assert set(schema["properties"]) == {field.name for field in fields(python_type)}
        assert set(schema["required"]) == set(schema["properties"])
        assert python_type.__dataclass_params__.frozen


def test_backend_loads_an_injectable_explicit_profile() -> None:
    calls: dict[str, dict] = {}

    class FakeTokenizer:
        @classmethod
        def from_pretrained(cls, identifier, **kwargs):
            calls["tokenizer"] = {"identifier": identifier, **kwargs}
            return cls()

    class FakeModel:
        def __init__(self) -> None:
            self.device = None
            self.evaluated = False

        @classmethod
        def from_pretrained(cls, identifier, **kwargs):
            calls["model"] = {"identifier": identifier, **kwargs}
            model = cls()
            calls["instance"] = {"model": model}
            return model

        def to(self, device):
            self.device = device
            return self

        def eval(self):
            self.evaluated = True
            return self

    fake_transformers = SimpleNamespace(
        AutoTokenizer=FakeTokenizer,
        AutoModelForCausalLM=FakeModel,
    )
    fake_torch = SimpleNamespace()
    runtime = TransformersModelRuntime.load(
        profile(), torch_module=fake_torch, transformers_module=fake_transformers
    )

    assert runtime.profile == profile()
    assert calls["tokenizer"] == {
        "identifier": "local/tokenizer",
        "trust_remote_code": False,
    }
    assert calls["model"] == {
        "identifier": "local/model",
        "trust_remote_code": False,
        "torch_dtype": "auto",
    }
    assert calls["instance"]["model"].device == "cpu"
    assert calls["instance"]["model"].evaluated is True


class FakeTensor:
    def __init__(self, values):
        self.values = values

    @property
    def shape(self):
        if self.values and isinstance(self.values[0], list):
            return (len(self.values), len(self.values[0]))
        return (len(self.values),)

    def to(self, device):
        return self

    def __getitem__(self, item):
        return self.values[item]

    def tolist(self):
        return self.values


class FakeTokenizerForGeneration:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, text, **kwargs):
        self.calls.append((text, kwargs))
        return {"input_ids": FakeTensor([[101, 102]])}

    def decode(self, token_ids, **kwargs):
        self.calls.append(("decode", {"token_ids": token_ids, **kwargs}))
        return wait_text()


class FakeModelForGeneration:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return FakeTensor([[101, 102, 201, 202]])


class FakeGenerator:
    def __init__(self, *, device) -> None:
        self.device = device
        self.seed = None

    def manual_seed(self, seed):
        self.seed = seed
        return self


class FakeForkRng:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


def test_one_rendered_context_produces_raw_generation_before_parsing() -> None:
    compiled = compiled_context()
    tokenizer = FakeTokenizerForGeneration()
    model = FakeModelForGeneration()
    runtime = TransformersModelRuntime.from_components(
        profile(), tokenizer=tokenizer, model=model
    )
    request = generation_request_for(compiled, profile(), generation_policy())
    result = runtime.generate(request)

    assert isinstance(result, RawGenerationResult)
    assert result.raw_text == wait_text()
    assert result.token_ids == (201, 202)
    assert result.context_hash == compiled.context_pack.context_hash
    assert model.calls[0]["max_new_tokens"] == 12
    assert model.calls[0]["do_sample"] is False
    assert "actor_id" not in model.calls[0]
    assert "tick" not in model.calls[0]


def test_generation_policy_controls_optional_generation_arguments() -> None:
    compiled = compiled_context()
    tokenizer = FakeTokenizerForGeneration()
    model = FakeModelForGeneration()
    runtime = TransformersModelRuntime.from_components(
        profile(), tokenizer=tokenizer, model=model
    )
    configured = GenerationPolicy(
        policy_id="generation-policy",
        version="1.0.0",
        max_new_tokens=9,
        do_sample=True,
        temperature=0.7,
        top_p=0.9,
        top_k=40,
        repetition_penalty=1.0,
        seed_id=None,
        stop_policy_id=None,
    )
    seeded = []
    fake_torch = SimpleNamespace(
        random=SimpleNamespace(fork_rng=lambda **kwargs: FakeForkRng()),
        manual_seed=lambda seed: seeded.append(seed),
    )
    runtime = TransformersModelRuntime.from_components(
        profile(), tokenizer=tokenizer, model=model, torch_module=fake_torch
    )
    request = generation_request_for(
        compiled, profile(), configured, generation_seed=123
    )
    runtime.generate(request)
    call = model.calls[0]
    assert call["max_new_tokens"] == 9
    assert call["do_sample"] is True
    assert call["repetition_penalty"] == 1.0
    assert call["temperature"] == 0.7
    assert call["top_p"] == 0.9
    assert call["top_k"] == 40
    assert "generator" not in call
    assert seeded == [123]


def test_raw_result_is_preserved_and_gateway_binds_identity() -> None:
    compiled = compiled_context()
    raw_runtime = ScriptedRawRuntime(wait_text())
    adapter = ContextModelRuntimeAdapter(
        raw_runtime, profile=profile(), generation_policy=generation_policy()
    )
    raw = adapter.generate(compiled)
    candidate = adapter.infer(compiled)

    assert raw.raw_text == wait_text()
    assert adapter.raw_results[0] == raw
    assert len(adapter.raw_results) == 2
    assert candidate.action_label == "NO_DIRECTED_ACTION"
    pipeline = ContextCognitionPipeline(
        policy(),
        model_profile_id="model-profile",
        generation_policy_id="generation-policy",
        generation_seed_id="generation-seed",
    )
    intent = pipeline.gateway.bind(candidate, compiled.opportunity)
    assert intent.actor_id == compiled.opportunity.agent_id
    assert intent.tick == compiled.opportunity.tick


def test_adapter_fits_existing_context_pipeline_without_writing_state() -> None:
    compiled = compiled_context()
    adapter = ContextModelRuntimeAdapter(
        ScriptedRawRuntime(wait_text()),
        profile=profile(),
        generation_policy=generation_policy(),
    )
    pipeline = ContextCognitionPipeline(
        policy(),
        model_profile_id="model-profile",
        generation_policy_id="generation-policy",
        generation_seed_id="generation-seed",
    )
    batch = pipeline.execute((compiled,), adapter)

    assert len(batch.intents) == 1
    assert batch.intents[0].actor_id == compiled.opportunity.agent_id
    assert batch.intents[0].tick == compiled.opportunity.tick


def test_parser_cannot_override_actor_or_tick_and_bad_output_does_not_mutate_snapshot() -> None:
    compiled = compiled_context()
    before = compiled.opportunity.snapshot.state_hash()
    malicious = json.dumps(
        {
            "action_label": "NO_DIRECTED_ACTION",
            "payload": {},
            "actor_id": "B",
            "tick": 999,
        }
    )
    adapter = ContextModelRuntimeAdapter(
        ScriptedRawRuntime(malicious),
        profile=profile(),
        generation_policy=generation_policy(),
    )
    with pytest.raises(ValueError, match="only action_label and payload"):
        adapter.infer(compiled)
    assert compiled.opportunity.snapshot.state_hash() == before


def test_adapter_cannot_write_snapshot() -> None:
    adapter = ContextModelRuntimeAdapter(
        ScriptedRawRuntime(wait_text()),
        profile=profile(),
        generation_policy=generation_policy(),
    )
    assert not any(name.startswith("publish") for name in dir(adapter))
    assert not hasattr(adapter, "snapshot")


def test_load_failure_is_an_infrastructure_error_not_agent_death() -> None:
    with pytest.raises(ModelLoadError, match="failed to load model profile"):
        TransformersModelRuntime.load(
            profile(), torch_module=object(), transformers_module=object()
        )


def test_request_requires_context_profile_and_policy_identity_match() -> None:
    compiled = compiled_context()
    mismatched_profile = ModelProfile(
        profile_id="other-profile",
        profile_version="1.0.0",
        model_identifier="local/model",
        model_revision=None,
        model_digest=None,
        tokenizer_identifier="local/tokenizer",
        tokenizer_revision=None,
        tokenizer_digest=None,
        model_class="AUTO_CAUSAL_LM",
        generation_policy_id="generation-policy",
        device="cpu",
        dtype="auto",
        adapter_ref=None,
        trust_remote_code=False,
        add_special_tokens=True,
    )
    with pytest.raises(ValueError, match="model profile"):
        generation_request_for(compiled, mismatched_profile, generation_policy())
