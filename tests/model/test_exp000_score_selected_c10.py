from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

import pytest

from alifelm.context import CompiledContext, ModelActionCandidate
from alifelm.domain import AgentId, ArtifactId, ArtifactRef, Duration, RunId
from alifelm.kernel import EqualOpportunityScheduler, SimulationRun
from alifelm.model.evidence import ModelOutputStatus
from alifelm.model.generation import GenerationPolicy
from alifelm.model.profile import ModelProfile
from alifelm.model.score_selected_c10 import (
    C10ConditionalPayloadProvider,
    C10MeanBranchScoreProvider,
    build_c10_score_selected_runtime,
)


ACTIONS = ("WAIT", "SEND", "PROPOSE", "ACCEPT", "REJECT")


def _compiled(agent: str = "A") -> CompiledContext:
    run = SimulationRun.bootstrap(
        RunId("EXP000_C10_CPU"),
        lifespan_ticks=Duration(20),
        founder_ids=(AgentId("A"), AgentId("B")),
    )
    opportunity = next(
        item
        for item in EqualOpportunityScheduler().enumerate(run.snapshot)
        if item.agent_id == AgentId(agent)
    )
    return CompiledContext(
        opportunity=opportunity,
        context_pack=object(),
        rendered_input=b"WORLD-CONTEXT",
        artifact_ref=None,
    )


def _profile() -> ModelProfile:
    return ModelProfile(
        profile_id="EXP000_C10_PROFILE",
        profile_version="1.0.0",
        model_identifier="local/test",
        model_revision="rev",
        model_digest="1" * 64,
        tokenizer_identifier="local/test",
        tokenizer_revision="rev",
        tokenizer_digest="2" * 64,
        model_class="AUTO_CAUSAL_LM",
        generation_policy_id="EXP000_C10_POLICY",
        device="cpu",
        dtype="bfloat16",
        adapter_ref=ArtifactRef(ArtifactId("adapter"), "3" * 64),
        trust_remote_code=False,
        add_special_tokens=True,
    )


def _policy() -> GenerationPolicy:
    return GenerationPolicy(
        policy_id="EXP000_C10_POLICY",
        version="1.0.0",
        max_new_tokens=128,
        do_sample=False,
        temperature=None,
        top_p=None,
        top_k=None,
        repetition_penalty=1.0,
        seed_id="EXP000_C10_SEED",
        stop_policy_id=None,
    )


class _Store:
    def put_bytes(self, data, **kwargs):
        del kwargs
        return ArtifactRef(ArtifactId("artifact"), "4" * 64)

    def resolve(self, reference):
        del reference
        return b""


class _Runtime:
    def __init__(self, profile):
        self.profile = profile
        self.model = object()
        self.tokenizer = object()

    def generate(self, request):
        raise AssertionError("CPU contract test must not call a real generator")


def _probe(values=None, *, prefill=True, selector=False):
    values = values or {name: float(index) for index, name in enumerate(ACTIONS)}
    return SimpleNamespace(
        prefill_adapter=prefill,
        selector_adapter=selector,
        branch_scores=tuple(SimpleNamespace(internal_action=name) for name in ACTIONS),
        mean_scores=lambda: dict(values),
    )


def _trace():
    return SimpleNamespace(
        prefill_adapter=True,
        selector_adapter=False,
        phase_boundary_token_aligned=True,
        world_prefill_forward_count=1,
        world_context_recomputed_after_switch=False,
    )


def test_c10_score_provider_uses_exact_i3_boundary_and_c10_flags(monkeypatch) -> None:
    import alifelm.model.score_selected_c10 as module

    seen = {}

    def fake_score(runtime, *, rendered_input, prefill_adapter, selector_adapter):
        seen.update(
            runtime=runtime,
            rendered_input=rendered_input,
            prefill=prefill_adapter,
            selector=selector_adapter,
        )
        return _probe()

    monkeypatch.setattr(module, "score_i3_decision_boundary", fake_score)
    runtime = _Runtime(_profile())
    provider = C10MeanBranchScoreProvider(runtime)
    compiled = _compiled()

    scores = provider.mean_scores(compiled)

    assert tuple(scores) == ACTIONS
    assert seen["runtime"] is runtime
    assert seen["prefill"] is True
    assert seen["selector"] is False
    assert seen["rendered_input"].endswith(b"\nAction selection JSON:\n")
    assert provider.probe_for(compiled.opportunity.opportunity_id).mean_scores() == scores


def test_c10_score_provider_fails_closed_on_non_c10_probe(monkeypatch) -> None:
    import alifelm.model.score_selected_c10 as module

    monkeypatch.setattr(
        module,
        "score_i3_decision_boundary",
        lambda *args, **kwargs: _probe(prefill=False, selector=False),
    )
    provider = C10MeanBranchScoreProvider(_Runtime(_profile()))

    with pytest.raises(RuntimeError, match="non-C10"):
        provider.mean_scores(_compiled())


def test_c10_score_provider_rejects_duplicate_opportunity(monkeypatch) -> None:
    import alifelm.model.score_selected_c10 as module

    monkeypatch.setattr(module, "score_i3_decision_boundary", lambda *a, **k: _probe())
    provider = C10MeanBranchScoreProvider(_Runtime(_profile()))
    compiled = _compiled()
    provider.mean_scores(compiled)

    with pytest.raises(RuntimeError, match="no-retry"):
        provider.mean_scores(compiled)


def _patch_payload_path(monkeypatch, *, candidate):
    import alifelm.model.score_selected_c10 as module

    seen = {}

    class FakePhaseRuntime:
        def __init__(self, runtime, *, prefill_adapter, selector_adapter):
            self.runtime = runtime
            self.profile = runtime.profile
            self.prefill_adapter = prefill_adapter
            self.selector_adapter = selector_adapter
            self.last_trace = None

        def generate(self, request):
            raise AssertionError("prepare_cognition_evidence is patched in CPU tests")

    def fake_constraint(tokenizer, *, schema):
        seen["tokenizer"] = tokenizer
        seen["schema"] = schema
        return "CONSTRAINT"

    def fake_prepare(compiled, phase_runtime, profile, policy, store, **kwargs):
        seen["compiled"] = compiled
        seen["phase_runtime"] = phase_runtime
        seen["profile"] = profile
        seen["policy"] = policy
        seen["store"] = store
        seen["kwargs"] = kwargs
        phase_runtime.last_trace = _trace()
        return SimpleNamespace(
            candidate=candidate,
            parse_status=ModelOutputStatus.VALID,
            raw_generation=SimpleNamespace(generation_id="c10-payload-generation"),
            rejection=None,
        )

    def fake_finalize(preparation, profile, policy, store, **kwargs):
        del preparation, profile, policy, store
        seen["finalize_kwargs"] = kwargs
        return ArtifactRef(ArtifactId("final-evidence"), "5" * 64)

    monkeypatch.setattr(module, "PhaseSwitchedGenerationRuntime", FakePhaseRuntime)
    monkeypatch.setattr(module, "build_transformers_constraint", fake_constraint)
    monkeypatch.setattr(module, "prepare_cognition_evidence", fake_prepare)
    monkeypatch.setattr(module, "finalize_cognition_evidence", fake_finalize)
    return seen


def test_c10_payload_provider_forces_only_selected_send_branch(monkeypatch) -> None:
    candidate = ModelActionCandidate(
        "DIRECT_TEXT",
        (("body", "hello"), ("target_agent_id", "B")),
    )
    seen = _patch_payload_path(monkeypatch, candidate=candidate)
    profile = _profile()
    runtime = _Runtime(profile)
    provider = C10ConditionalPayloadProvider(
        runtime,
        profile=profile,
        generation_policy=_policy(),
        artifact_store=_Store(),
        generation_seed=123,
    )
    compiled = _compiled()

    attempt = provider.generate_for_action(compiled, "SEND")

    assert provider.phase_runtime.prefill_adapter is True
    assert provider.phase_runtime.selector_adapter is False
    assert attempt.candidate == candidate
    assert seen["schema"]["properties"]["action_label"]["const"] == "DIRECT_TEXT"
    treatment = seen["kwargs"]["interface_treatment"]
    assert treatment.treatment_id == "i05r3-forced-send-payload"
    assert seen["kwargs"]["prefix_allowed_tokens_fn"] == "CONSTRAINT"
    assert seen["kwargs"]["generation_seed"] == 123
    assert provider.trace_for(compiled.opportunity.opportunity_id).prefill_adapter is True
    ref = attempt.evidence_finalizer(None, None)
    assert ref.digest == "5" * 64


def test_c10_payload_provider_never_handles_wait(monkeypatch) -> None:
    _patch_payload_path(monkeypatch, candidate=None)
    profile = _profile()
    provider = C10ConditionalPayloadProvider(
        _Runtime(profile),
        profile=profile,
        generation_policy=_policy(),
        artifact_store=_Store(),
        generation_seed=None,
    )

    with pytest.raises(ValueError, match="WAIT has no"):
        provider.generate_for_action(_compiled(), "WAIT")


def test_c10_payload_provider_rejects_duplicate_generation(monkeypatch) -> None:
    candidate = ModelActionCandidate(
        "DIRECT_TEXT",
        (("body", "hello"), ("target_agent_id", "B")),
    )
    _patch_payload_path(monkeypatch, candidate=candidate)
    profile = _profile()
    provider = C10ConditionalPayloadProvider(
        _Runtime(profile),
        profile=profile,
        generation_policy=_policy(),
        artifact_store=_Store(),
        generation_seed=None,
    )
    compiled = _compiled()
    provider.generate_for_action(compiled, "SEND")

    with pytest.raises(RuntimeError, match="no-retry"):
        provider.generate_for_action(compiled, "SEND")


def test_full_c10_composition_selects_then_generates_only_that_payload(monkeypatch) -> None:
    import alifelm.model.score_selected_c10 as module

    dominant_send = {name: (-1000.0 if name != "SEND" else 1000.0) for name in ACTIONS}
    monkeypatch.setattr(
        module,
        "score_i3_decision_boundary",
        lambda *args, **kwargs: _probe(dominant_send),
    )
    candidate = ModelActionCandidate(
        "DIRECT_TEXT",
        (("body", "hello"), ("target_agent_id", "B")),
    )
    _patch_payload_path(monkeypatch, candidate=candidate)
    profile = _profile()
    runtime = _Runtime(profile)
    composed = build_c10_score_selected_runtime(
        runtime,
        profile=profile,
        generation_policy=_policy(),
        artifact_store=_Store(),
        generation_seed=123,
    )
    compiled = _compiled()

    attempt = composed.infer(compiled)

    decision = composed.decision_for(compiled.opportunity.opportunity_id)
    assert decision.selected_action == "SEND"
    assert attempt.candidate == candidate
    assert composed.score_provider.probe_for(compiled.opportunity.opportunity_id)
    assert composed.payload_provider.trace_for(compiled.opportunity.opportunity_id)
