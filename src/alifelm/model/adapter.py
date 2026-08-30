"""Storage-independent model adapter and Gateway plumbing."""

from __future__ import annotations

import hashlib
from typing import Protocol

from alifelm.context.gateway import ModelActionCandidate, ModelActionParser
from alifelm.context.orchestration import CompiledContext

from .generation import (
    GenerationPolicy,
    GenerationRequest,
    RawGenerationResult,
    StopHook,
    PrefixAllowedTokensFn,
    generation_identity,
)
from .profile import ModelProfile
from .treatments import I0_STRICT_FREE_GENERATION, InterfaceTreatment


class ModelRuntime(Protocol):
    """The only operation the cognition side needs from a model backend."""

    profile: ModelProfile

    def generate(self, request: GenerationRequest) -> RawGenerationResult: ...


def validate_raw_generation_result(
    request: GenerationRequest,
    result: RawGenerationResult,
    profile: ModelProfile,
    policy: GenerationPolicy,
) -> None:
    """Fail closed when a backend returns evidence for another request.

    A mismatch is an infrastructure-integrity failure.  It is deliberately
    kept separate from parser failures, which represent model output.
    """

    if not isinstance(request, GenerationRequest):
        raise TypeError("request must be a GenerationRequest")
    if not isinstance(result, RawGenerationResult):
        raise TypeError("model runtime must return RawGenerationResult")
    if not isinstance(profile, ModelProfile):
        raise TypeError("profile must be a ModelProfile")
    if not isinstance(policy, GenerationPolicy):
        raise TypeError("policy must be a GenerationPolicy")
    if request.model_profile != profile:
        raise ValueError("request profile does not match configured profile")
    if request.generation_policy != policy:
        raise ValueError("request policy does not match configured policy")
    checks = (
        (result.opportunity_id, request.opportunity_id, "opportunity identity"),
        (result.generation_id, request.generation_id, "generation identity"),
        (result.context_pack_id, request.context_pack_id, "ContextPack identity"),
        (result.context_hash, request.context_hash, "context hash"),
        (result.rendered_input_hash, request.rendered_input_hash, "rendered input"),
        (result.interface_treatment_id, request.interface_treatment_id, "interface treatment identity"),
        (result.interface_treatment_version, request.interface_treatment_version, "interface treatment version"),
        (result.interface_treatment_digest, request.interface_treatment_digest, "interface treatment digest"),
        (result.constraint_policy_id, request.constraint_policy_id, "constraint policy identity"),
        (result.model_profile_id, profile.profile_id, "model profile identity"),
        (result.generation_policy_id, policy.policy_id, "generation policy identity"),
        (result.generation_policy_version, policy.version, "generation policy version"),
        (result.generation_seed_id, request.generation_seed_id, "generation seed identity"),
        (result.generation_seed, request.generation_seed, "generation seed"),
    )
    for actual, expected, label in checks:
        if actual != expected:
            raise ValueError(f"raw result {label} does not match request")


def generation_request_for(
    compiled: CompiledContext,
    profile: ModelProfile,
    policy: GenerationPolicy,
    *,
    generation_seed: int | None = None,
    generator: object | None = None,
    stop_hooks: tuple[StopHook, ...] = (),
    interface_treatment: InterfaceTreatment = I0_STRICT_FREE_GENERATION,
    prefix_allowed_tokens_fn: PrefixAllowedTokensFn | None = None,
) -> GenerationRequest:
    """Bind a compiled ContextPack to an explicit infrastructure request."""

    if not isinstance(compiled, CompiledContext):
        raise TypeError("compiled must be a CompiledContext")
    if not isinstance(profile, ModelProfile):
        raise TypeError("profile must be a ModelProfile")
    if not isinstance(policy, GenerationPolicy):
        raise TypeError("policy must be a GenerationPolicy")
    if not isinstance(interface_treatment, InterfaceTreatment):
        raise TypeError("interface_treatment must be an InterfaceTreatment")
    pack = compiled.context_pack
    if compiled.opportunity.opportunity_id != pack.evidence.opportunity_id:
        raise ValueError("compiled opportunity does not match ContextPack evidence")
    if compiled.opportunity.agent_id != pack.evidence.agent_id:
        raise ValueError("compiled actor does not match ContextPack evidence")
    if pack.infrastructure.model_profile_id != profile.profile_id:
        raise ValueError("ContextPack model profile does not match the request profile")
    if pack.infrastructure.generation_policy_id != policy.policy_id:
        raise ValueError("ContextPack generation policy does not match the request policy")
    rendered_input = interface_treatment.render(compiled.rendered_input)
    rendered_input_hash = hashlib.sha256(rendered_input).hexdigest()
    return GenerationRequest(
        opportunity_id=compiled.opportunity.opportunity_id,
        generation_id=generation_identity(
            context_hash=pack.context_hash,
            profile=profile,
            policy=policy,
            generation_seed_id=pack.infrastructure.generation_seed_id,
            generation_seed=generation_seed,
            rendered_input_hash=rendered_input_hash,
            interface_treatment_id=interface_treatment.treatment_id,
            interface_treatment_version=interface_treatment.version,
            interface_treatment_digest=interface_treatment.digest,
            constraint_policy_id=interface_treatment.constraint_policy_id,
        ),
        context_pack_id=pack.context_pack_id,
        context_hash=pack.context_hash,
        rendered_input_hash=rendered_input_hash,
        rendered_input=rendered_input,
        interface_treatment_id=interface_treatment.treatment_id,
        interface_treatment_version=interface_treatment.version,
        interface_treatment_digest=interface_treatment.digest,
        constraint_policy_id=interface_treatment.constraint_policy_id,
        model_profile=profile,
        generation_policy=policy,
        generation_seed_id=pack.infrastructure.generation_seed_id,
        generation_seed=generation_seed,
        generator=generator,
        stop_hooks=stop_hooks,
        prefix_allowed_tokens_fn=prefix_allowed_tokens_fn,
    )


def parse_raw_generation(
    result: RawGenerationResult,
    parser: ModelActionParser | None = None,
) -> ModelActionCandidate:
    """Parse raw text only; identity binding remains the Cognition Gateway's job."""

    if not isinstance(result, RawGenerationResult):
        raise TypeError("result must be a RawGenerationResult")
    return (parser or ModelActionParser()).parse(result.raw_text)


class ContextModelRuntimeAdapter:
    """Adapt raw-generation runtimes to the existing P4 candidate interface.

    ``infer`` returns only a model candidate.  It never receives a setter or a
    mutable Snapshot, and the Gateway still supplies actor/tick/intent identity.
    """

    def __init__(
        self,
        runtime: ModelRuntime,
        *,
        profile: ModelProfile,
        generation_policy: GenerationPolicy,
        generation_seed: int | None = None,
        generator: object | None = None,
        stop_hooks: tuple[StopHook, ...] = (),
        parser: ModelActionParser | None = None,
    ) -> None:
        if not isinstance(profile, ModelProfile):
            raise TypeError("profile must be a ModelProfile")
        if not isinstance(generation_policy, GenerationPolicy):
            raise TypeError("generation_policy must be a GenerationPolicy")
        if not hasattr(runtime, "generate"):
            raise TypeError("runtime must provide generate(request)")
        self.runtime = runtime
        self.profile = profile
        self.generation_policy = generation_policy
        self.generation_seed = generation_seed
        self.generator = generator
        self.stop_hooks = stop_hooks
        self.parser = parser or ModelActionParser()
        self._raw_results: list[RawGenerationResult] = []

    @property
    def raw_results(self) -> tuple[RawGenerationResult, ...]:
        return tuple(self._raw_results)

    def generate(self, compiled: CompiledContext) -> RawGenerationResult:
        request = generation_request_for(
            compiled,
            self.profile,
            self.generation_policy,
            generation_seed=self.generation_seed,
            generator=self.generator,
            stop_hooks=self.stop_hooks,
        )
        result = self.runtime.generate(request)
        validate_raw_generation_result(
            request, result, self.profile, self.generation_policy
        )
        self._raw_results.append(result)
        return result

    def infer(self, compiled: CompiledContext) -> ModelActionCandidate:
        return parse_raw_generation(self.generate(compiled), self.parser)
