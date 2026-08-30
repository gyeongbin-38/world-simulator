"""P3/P4 context compilation barrier and candidate-runtime integration."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Callable, Mapping, Protocol

from alifelm.domain import ActionIntent, AgentId, ArtifactRef, IntentBatch, OpportunityId
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
    ) -> (
        "CognitionAttempt"
        | ModelActionCandidate
        | Mapping[str, Any]
        | str
        | bytes
    ): ...


@dataclass(frozen=True, slots=True)
class CognitionAttempt:
    """One P4 outcome: a candidate or a typed rejection, never an implicit WAIT.

    ``evidence_finalizer`` is an infrastructure-only callback supplied by a
    live runtime.  It is excluded from equality/repr and never enters
    canonical state; it lets the pipeline bind identity exactly once before
    writing the final evidence artifact.
    """

    opportunity_id: OpportunityId
    candidate: ModelActionCandidate | None
    evidence_ref: ArtifactRef | None
    parse_status: object
    generation_id: str = ""
    rejection: object | None = None
    evidence_finalizer: Callable[[ActionIntent | None, object | None], ArtifactRef] | None = field(
        default=None, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if not isinstance(self.opportunity_id, OpportunityId):
            raise TypeError("attempt opportunity_id must be an OpportunityId")
        if isinstance(self.parse_status, str):
            if not self.parse_status:
                raise ValueError("attempt parse_status must be non-empty")
        elif not isinstance(getattr(self.parse_status, "value", None), str):
            raise TypeError("attempt parse_status must be a status string or enum")
        if not isinstance(self.generation_id, str):
            raise TypeError("attempt generation_id must be a string")
        if self.candidate is not None and not isinstance(
            self.candidate, ModelActionCandidate
        ):
            raise TypeError("attempt candidate must be a ModelActionCandidate or None")
        if self.evidence_ref is not None and not isinstance(self.evidence_ref, ArtifactRef):
            raise TypeError("attempt evidence_ref must be an ArtifactRef or None")
        if self.evidence_finalizer is not None and not callable(self.evidence_finalizer):
            raise TypeError("attempt evidence_finalizer must be callable or None")

    def finalize(
        self,
        action_intent: ActionIntent | None,
        rejection: object | None,
    ) -> "CognitionAttempt":
        reference = self.evidence_ref
        if self.evidence_finalizer is not None:
            reference = self.evidence_finalizer(action_intent, rejection)
            if not isinstance(reference, ArtifactRef):
                raise TypeError("evidence finalizer must return an ArtifactRef")
        return replace(self, evidence_ref=reference, rejection=rejection or self.rejection)


@dataclass(frozen=True, slots=True)
class ContextCognitionResult:
    compiled_contexts: tuple[CompiledContext, ...]
    attempts: tuple[CognitionAttempt, ...]
    intent_batch: IntentBatch

    @property
    def artifact_refs(self) -> tuple[ArtifactRef, ...]:
        refs = {
            item.artifact_ref
            for item in self.compiled_contexts
            if item.artifact_ref is not None
        }
        refs.update(
            attempt.evidence_ref
            for attempt in self.attempts
            if attempt.evidence_ref is not None
        )
        return tuple(
            sorted(refs, key=lambda ref: (ref.artifact_id.value, ref.digest))
        )

    @property
    def rejections(self) -> tuple[CognitionAttempt, ...]:
        return tuple(item for item in self.attempts if item.rejection is not None)


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

    def _execute(
        self,
        compiled: tuple[CompiledContext, ...],
        runtime: CandidateModelRuntime,
        completion_order: tuple[AgentId, ...] | None = None,
    ) -> tuple[tuple[CognitionAttempt, ...], IntentBatch]:
        by_agent = {item.opportunity.agent_id: item for item in compiled}
        if len(by_agent) != len(compiled):
            raise ValueError("compiled contexts must contain one item per actor")
        if completion_order is None:
            execution = compiled
        else:
            if len(completion_order) != len(by_agent) or set(completion_order) != set(by_agent):
                raise ValueError("completion_order must contain each compiled actor once")
            execution = tuple(by_agent[agent_id] for agent_id in completion_order)

        attempts: list[CognitionAttempt] = []
        intents: list[ActionIntent] = []
        for item in execution:
            outcome = runtime.infer(item)
            if isinstance(outcome, CognitionAttempt):
                if outcome.opportunity_id != item.opportunity.opportunity_id:
                    raise ValueError("cognition attempt opportunity identity does not match")
                attempt = outcome
            else:
                # Backward-compatible fake runtimes remain candidates.  They
                # are normalized to the same attempt shape without evidence.
                candidate = self.gateway.parser.parse(outcome)
                attempt = CognitionAttempt(
                    opportunity_id=item.opportunity.opportunity_id,
                    candidate=candidate,
                    evidence_ref=None,
                    parse_status="VALID",
                )

            if attempt.candidate is None:
                if attempt.rejection is None:
                    raise ValueError("a rejected cognition attempt requires rejection evidence")
                attempts.append(attempt.finalize(None, attempt.rejection))
                continue

            try:
                intent = self.gateway.bind(attempt.candidate, item.opportunity)
            except (TypeError, ValueError) as error:
                # Gateway/domain rejection is model-output failure, not an
                # infrastructure mismatch.  Import lazily to avoid making
                # the context package depend on model package initialization.
                from alifelm.model.evidence import ModelOutputStatus, RejectedModelOutput

                rejection = RejectedModelOutput(
                    generation_id=attempt.generation_id or "gateway-rejection",
                    status=ModelOutputStatus.DOMAIN_REJECTED,
                    error_type=type(error).__name__,
                    error_message=str(error),
                )
                attempts.append(
                    replace(
                        attempt.finalize(None, rejection),
                        candidate=None,
                        parse_status=ModelOutputStatus.DOMAIN_REJECTED,
                    )
                )
                continue
            attempts.append(attempt.finalize(intent, None))
            intents.append(intent)

        tick_set = {item.opportunity.tick for item in compiled}
        if len(tick_set) != 1:
            raise ValueError("compiled contexts must belong to one tick")
        tick = next(iter(tick_set))
        attempt_values = tuple(
            sorted(attempts, key=lambda attempt: attempt.opportunity_id.value)
        )
        return attempt_values, IntentBatch(
            tick=tick,
            intents=tuple(sorted(intents, key=lambda intent: intent.actor_id.value)),
        )

    def execute(
        self,
        compiled: tuple[CompiledContext, ...],
        runtime: CandidateModelRuntime,
        completion_order: tuple[AgentId, ...] | None = None,
    ) -> IntentBatch:
        """Execute P4 while retaining the legacy return type for callers."""

        _, intent_batch = self._execute(compiled, runtime, completion_order)
        return intent_batch

    def run(
        self,
        opportunities: tuple[CognitionOpportunity, ...],
        runtime: CandidateModelRuntime,
        completion_order: tuple[AgentId, ...] | None = None,
    ) -> ContextCognitionResult:
        compiled = self.compile_all(opportunities)
        attempts, intent_batch = self._execute(compiled, runtime, completion_order)
        return ContextCognitionResult(
            compiled_contexts=compiled,
            attempts=attempts,
            intent_batch=intent_batch,
        )
