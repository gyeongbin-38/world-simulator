"""Storage-independent model adapter and Gateway plumbing."""

from __future__ import annotations

from typing import Protocol

from alifelm.context.gateway import ModelActionCandidate, ModelActionParser
from alifelm.context.orchestration import CompiledContext

from .generation import GenerationPolicy, GenerationRequest, RawGenerationResult, StopHook
from .profile import ModelProfile


class ModelRuntime(Protocol):
    """The only operation the cognition side needs from a model backend."""

    profile: ModelProfile

    def generate(self, request: GenerationRequest) -> RawGenerationResult: ...


def generation_request_for(
    compiled: CompiledContext,
    profile: ModelProfile,
    policy: GenerationPolicy,
    *,
    generation_seed: int | None = None,
    generator: object | None = None,
    stop_hooks: tuple[StopHook, ...] = (),
) -> GenerationRequest:
    """Bind a compiled ContextPack to an explicit infrastructure request."""

    if not isinstance(compiled, CompiledContext):
        raise TypeError("compiled must be a CompiledContext")
    if not isinstance(profile, ModelProfile):
        raise TypeError("profile must be a ModelProfile")
    if not isinstance(policy, GenerationPolicy):
        raise TypeError("policy must be a GenerationPolicy")
    pack = compiled.context_pack
    if compiled.opportunity.opportunity_id != pack.evidence.opportunity_id:
        raise ValueError("compiled opportunity does not match ContextPack evidence")
    if compiled.opportunity.agent_id != pack.evidence.agent_id:
        raise ValueError("compiled actor does not match ContextPack evidence")
    if pack.infrastructure.model_profile_id != profile.profile_id:
        raise ValueError("ContextPack model profile does not match the request profile")
    if pack.infrastructure.generation_policy_id != policy.policy_id:
        raise ValueError("ContextPack generation policy does not match the request policy")
    return GenerationRequest(
        opportunity_id=compiled.opportunity.opportunity_id,
        context_pack_id=pack.context_pack_id,
        context_hash=pack.context_hash,
        rendered_input=compiled.rendered_input,
        model_profile=profile,
        generation_policy=policy,
        generation_seed_id=pack.infrastructure.generation_seed_id,
        generation_seed=generation_seed,
        generator=generator,
        stop_hooks=stop_hooks,
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
        if not isinstance(result, RawGenerationResult):
            raise TypeError("model runtime must return RawGenerationResult")
        if result.opportunity_id != request.opportunity_id:
            raise ValueError("raw result opportunity identity does not match request")
        if result.context_pack_id != request.context_pack_id:
            raise ValueError("raw result ContextPack identity does not match request")
        if result.context_hash != request.context_hash:
            raise ValueError("raw result context hash does not match request")
        if result.model_profile_id != self.profile.profile_id:
            raise ValueError("raw result model profile does not match request")
        if result.generation_policy_id != self.generation_policy.policy_id:
            raise ValueError("raw result generation policy does not match request")
        if result.generation_policy_version != self.generation_policy.version:
            raise ValueError("raw result generation policy version does not match request")
        if result.generation_seed_id != request.generation_seed_id:
            raise ValueError("raw result generation seed identity does not match request")
        self._raw_results.append(result)
        return result

    def infer(self, compiled: CompiledContext) -> ModelActionCandidate:
        return parse_raw_generation(self.generate(compiled), self.parser)
