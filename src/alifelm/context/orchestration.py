"""P3/P4 context compilation barrier and fake candidate-runtime integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from alifelm.domain import AgentId, ArtifactRef, IntentBatch
from alifelm.kernel.opportunities import CognitionOpportunity

from .compile import ContextCompiler
from .gateway import CognitionGateway, ModelActionCandidate
from .render import render_model_input_bytes
from .serialization import serialize_context_pack
from .types import ContextPack, ContextPolicy


class ContextArtifactStore(Protocol):
    def put_bytes(
        self,
        data: bytes,
        *,
        media_type: str = "application/octet-stream",
        contract_id: str = "raw-bytes",
        fault_injector=None,
    ) -> ArtifactRef: ...

    def resolve(self, reference: ArtifactRef) -> bytes: ...


@dataclass(frozen=True, slots=True)
class CompiledContext:
    opportunity: CognitionOpportunity
    context_pack: ContextPack
    rendered_input: bytes
    artifact_ref: ArtifactRef | None


class CandidateModelRuntime(Protocol):
    def infer(
        self, compiled: CompiledContext
    ) -> ModelActionCandidate | Mapping[str, Any] | str | bytes: ...


@dataclass(frozen=True, slots=True)
class ContextCognitionResult:
    compiled_contexts: tuple[CompiledContext, ...]
    intent_batch: IntentBatch

    @property
    def artifact_refs(self) -> tuple[ArtifactRef, ...]:
        return tuple(
            item.artifact_ref
            for item in self.compiled_contexts
            if item.artifact_ref is not None
        )


class ContextCognitionPipeline:
    """Compile every pack before executing any cognition opportunity."""

    def __init__(
        self,
        policy: ContextPolicy,
        *,
        model_profile_id: str,
        generation_policy_id: str,
        generation_seed_id: str,
        compiler: ContextCompiler | None = None,
        gateway: CognitionGateway | None = None,
        artifact_store: ContextArtifactStore | None = None,
    ) -> None:
        self.policy = policy
        self.model_profile_id = model_profile_id
        self.generation_policy_id = generation_policy_id
        self.generation_seed_id = generation_seed_id
        self.compiler = compiler or ContextCompiler()
        self.gateway = gateway or CognitionGateway()
        self.artifact_store = artifact_store

    def compile_all(
        self, opportunities: tuple[CognitionOpportunity, ...]
    ) -> tuple[CompiledContext, ...]:
        if not isinstance(opportunities, tuple) or any(
            not isinstance(item, CognitionOpportunity) for item in opportunities
        ):
            raise TypeError("opportunities must contain CognitionOpportunity values")
        compiled: list[CompiledContext] = []
        for opportunity in opportunities:
            pack = self.compiler.compile(
                opportunity,
                self.policy,
                model_profile_id=self.model_profile_id,
                generation_policy_id=self.generation_policy_id,
                generation_seed_id=self.generation_seed_id,
            )
            packed_bytes = serialize_context_pack(pack)
            reference = None
            if self.artifact_store is not None:
                reference = self.artifact_store.put_bytes(
                    packed_bytes,
                    media_type="application/json",
                    contract_id="context-pack-1.0.0",
                )
                if self.artifact_store.resolve(reference) != packed_bytes:
                    raise ValueError("ContextPack CAS roundtrip changed bytes")
            compiled.append(
                CompiledContext(
                    opportunity=opportunity,
                    context_pack=pack,
                    rendered_input=render_model_input_bytes(pack.model_input),
                    artifact_ref=reference,
                )
            )
        return tuple(compiled)

    def execute(
        self,
        compiled: tuple[CompiledContext, ...],
        runtime: CandidateModelRuntime,
        completion_order: tuple[AgentId, ...] | None = None,
    ) -> IntentBatch:
        by_agent = {item.opportunity.agent_id: item for item in compiled}
        if len(by_agent) != len(compiled):
            raise ValueError("compiled contexts must contain one item per actor")
        if completion_order is None:
            execution = compiled
        else:
            if len(completion_order) != len(by_agent) or set(completion_order) != set(by_agent):
                raise ValueError("completion_order must contain each compiled actor once")
            execution = tuple(by_agent[agent_id] for agent_id in completion_order)

        intents = tuple(
            self.gateway.bind(runtime.infer(item), item.opportunity)
            for item in execution
        )
        tick_set = {item.opportunity.tick for item in compiled}
        if len(tick_set) != 1:
            raise ValueError("compiled contexts must belong to one tick")
        tick = next(iter(tick_set))
        return IntentBatch(
            tick=tick,
            intents=tuple(sorted(intents, key=lambda intent: intent.actor_id.value)),
        )

    def run(
        self,
        opportunities: tuple[CognitionOpportunity, ...],
        runtime: CandidateModelRuntime,
        completion_order: tuple[AgentId, ...] | None = None,
    ) -> ContextCognitionResult:
        compiled = self.compile_all(opportunities)
        return ContextCognitionResult(
            compiled_contexts=compiled,
            intent_batch=self.execute(compiled, runtime, completion_order),
        )

