"""Proposal-reference grounding for the preregistered EXP-000 V1 intervention.

The score/action-selection path is unchanged.  Only an already-selected
ACCEPT/REJECT payload may see context-local proposal handles.  Handles are
research/interface values only; the CognitionGateway always receives the
resolved canonical proposal identifier.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from alifelm.context import (
    CognitionAttempt,
    CompiledContext,
    DEFAULT_ACTION_PRESENTATION,
    DeliveredMessagePayload,
    IncomingProposalPayload,
    ModelActionCandidate,
    ModelActionParser,
    ModelInput,
    OutgoingProposalPayload,
    ProtocolResolutionPayload,
    SentMessagePayload,
    VisibleRecord,
    render_model_input_bytes,
)
from alifelm.domain import OpportunityId
from alifelm.persistence import ArtifactStore

from .evidence import (
    ModelOutputStatus,
    RejectedModelOutput,
    finalize_cognition_evidence,
    prepare_cognition_evidence,
)
from .generation import GenerationPolicy
from .motor_diagnostics import forced_grounding_schema
from .phase_generation import PhaseGenerationTrace, PhaseSwitchedGenerationRuntime
from .profile import ModelProfile
from .score_selected_c10 import (
    C10_PREFILL_ADAPTER,
    C10_SELECTOR_ADAPTER,
    C10ConditionalPayloadProvider,
    C10MeanBranchScoreProvider,
)
from .score_selected_runtime import ScoreSelectedCandidateRuntime
from .treatments import (
    I3_CONDITIONAL_TYPED_CODEC,
    InterfaceMode,
    InterfaceTreatment,
    build_transformers_constraint,
)


PROPOSAL_HANDLE_GROUNDING_VERSION = "1.0.0"
PROPOSAL_HANDLE_ACTIONS = frozenset(("ACCEPT", "REJECT"))


@dataclass(frozen=True, slots=True)
class ProposalHandleMap:
    """Deterministic canonical proposal-id -> local handle mapping."""

    canonical_to_handle: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        canonical = [item[0] for item in self.canonical_to_handle]
        handles = [item[1] for item in self.canonical_to_handle]
        if any(not isinstance(value, str) or not value for value in canonical + handles):
            raise ValueError("proposal handle map values must be non-empty strings")
        if len(set(canonical)) != len(canonical) or len(set(handles)) != len(handles):
            raise ValueError("proposal handle map must be one-to-one")
        expected = [f"R{index}" for index in range(len(handles))]
        if handles != expected:
            raise ValueError("proposal handles must use deterministic R0..Rn ordering")

    @property
    def handle_to_canonical(self) -> dict[str, str]:
        return {handle: canonical for canonical, handle in self.canonical_to_handle}

    @property
    def handles(self) -> tuple[str, ...]:
        return tuple(handle for _, handle in self.canonical_to_handle)

    @property
    def canonical_ids(self) -> tuple[str, ...]:
        return tuple(canonical for canonical, _ in self.canonical_to_handle)


@dataclass(frozen=True, slots=True)
class ProposalGroundingRecord:
    opportunity_id: OpportunityId
    selected_action: str
    mode: str
    handle_map: ProposalHandleMap
    raw_handle_candidate: ModelActionCandidate | None
    mapped_candidate: ModelActionCandidate | None
    treatment_id: str | None


def _proposal_ids(model_input: ModelInput) -> tuple[str, ...]:
    values: list[str] = []
    for records in (
        model_input.newly_delivered,
        model_input.visible_protocol_state,
        model_input.prior_history,
    ):
        for record in records:
            proposal_id = getattr(record.payload, "proposal_id", None)
            if proposal_id is not None:
                value = str(proposal_id)
                if value not in values:
                    values.append(value)
    return tuple(values)


def proposal_handle_map(compiled: CompiledContext) -> ProposalHandleMap:
    if not isinstance(compiled, CompiledContext):
        raise TypeError("compiled must be a CompiledContext")
    ids = _proposal_ids(compiled.context_pack.model_input)
    return ProposalHandleMap(tuple((value, f"R{index}") for index, value in enumerate(ids)))


def _alias_record(record: VisibleRecord, proposal_aliases: dict[str, str]) -> VisibleRecord:
    payload = record.payload
    if isinstance(payload, (DeliveredMessagePayload, SentMessagePayload)):
        return record
    if isinstance(payload, IncomingProposalPayload):
        aliased = IncomingProposalPayload(
            proposal_aliases[str(payload.proposal_id)],
            payload.proposer_id,
        )
    elif isinstance(payload, OutgoingProposalPayload):
        aliased = OutgoingProposalPayload(
            proposal_aliases[str(payload.proposal_id)],
            payload.target_id,
        )
    elif isinstance(payload, ProtocolResolutionPayload):
        aliased = ProtocolResolutionPayload(
            proposal_aliases[str(payload.proposal_id)],
            payload.counterparty_id,
            payload.result,
        )
    else:  # pragma: no cover - VisibleRecord guards the payload union.
        raise TypeError("unsupported visible record payload")
    return VisibleRecord(record.category, aliased)


def render_with_proposal_handles(
    compiled: CompiledContext,
) -> tuple[bytes, ProposalHandleMap]:
    """Alias proposal IDs only; agent IDs and canonical ContextPack stay unchanged."""

    if not isinstance(compiled, CompiledContext):
        raise TypeError("compiled must be a CompiledContext")
    handles = proposal_handle_map(compiled)
    if not handles.canonical_to_handle:
        return compiled.rendered_input, handles

    source = compiled.context_pack.model_input
    aliases = dict(handles.canonical_to_handle)
    aliased = ModelInput(
        stable_prefix=source.stable_prefix,
        current_self=source.current_self,
        peer_directory=source.peer_directory,
        newly_delivered=tuple(_alias_record(item, aliases) for item in source.newly_delivered),
        visible_protocol_state=tuple(
            _alias_record(item, aliases) for item in source.visible_protocol_state
        ),
        prior_history=tuple(_alias_record(item, aliases) for item in source.prior_history),
    )
    return render_model_input_bytes(aliased), handles


def proposal_handle_treatment(internal_action: str) -> InterfaceTreatment:
    if internal_action not in PROPOSAL_HANDLE_ACTIONS:
        raise ValueError("proposal handle treatment is only defined for ACCEPT/REJECT")
    return InterfaceTreatment(
        treatment_id=f"exp000-proposal-handle-{internal_action.lower()}-v1",
        version=PROPOSAL_HANDLE_GROUNDING_VERSION,
        mode=InterfaceMode.I3,
        completion_suffix=I3_CONDITIONAL_TYPED_CODEC.completion_suffix,
        constraint_policy_id=(
            f"exp000-proposal-handle-{internal_action.lower()}-visible-reference-domain-v1"
        ),
    )


def resolve_proposal_handle_candidate(
    candidate: ModelActionCandidate,
    handles: ProposalHandleMap,
) -> ModelActionCandidate:
    """Resolve one generated local proposal handle to its canonical identifier."""

    if not isinstance(candidate, ModelActionCandidate):
        raise TypeError("candidate must be a ModelActionCandidate")
    payload = candidate.payload_dict()
    if set(payload) != {"proposal_id"}:
        raise ValueError("proposal handle candidate must contain only proposal_id")
    handle = payload["proposal_id"]
    try:
        canonical = handles.handle_to_canonical[handle]
    except KeyError as error:
        raise ValueError("generated proposal handle is outside the visible reference domain") from error
    return ModelActionCandidate(candidate.action_label, (("proposal_id", canonical),))


class C10ProposalHandlePayloadProvider:
    """C10 payload provider with proposal-only local handles for ACCEPT/REJECT."""

    def __init__(
        self,
        runtime: Any,
        *,
        profile: ModelProfile,
        generation_policy: GenerationPolicy,
        artifact_store: ArtifactStore,
        generation_seed: int | None,
        parser: ModelActionParser | None = None,
    ) -> None:
        if not hasattr(runtime, "generate") or not hasattr(runtime, "tokenizer"):
            raise TypeError("runtime must provide generate and tokenizer")
        self.runtime = runtime
        self.profile = profile
        self.generation_policy = generation_policy
        self.artifact_store = artifact_store
        self.generation_seed = generation_seed
        self.parser = parser or ModelActionParser()
        self.baseline = C10ConditionalPayloadProvider(
            runtime,
            profile=profile,
            generation_policy=generation_policy,
            artifact_store=artifact_store,
            generation_seed=generation_seed,
            parser=self.parser,
        )
        self.phase_runtime = PhaseSwitchedGenerationRuntime(
            runtime,
            prefill_adapter=C10_PREFILL_ADAPTER,
            selector_adapter=C10_SELECTOR_ADAPTER,
        )
        self._traces: dict[OpportunityId, PhaseGenerationTrace] = {}
        self._grounding: dict[OpportunityId, ProposalGroundingRecord] = {}

    def trace_for(self, opportunity_id: OpportunityId) -> PhaseGenerationTrace:
        if opportunity_id in self._traces:
            return self._traces[opportunity_id]
        return self.baseline.trace_for(opportunity_id)

    def grounding_for(self, opportunity_id: OpportunityId) -> ProposalGroundingRecord:
        if not isinstance(opportunity_id, OpportunityId):
            raise TypeError("opportunity_id must be an OpportunityId")
        try:
            return self._grounding[opportunity_id]
        except KeyError as error:
            raise KeyError("no proposal-grounding record exists for this opportunity") from error

    def generate_for_action(
        self,
        compiled: CompiledContext,
        selected_action: str,
    ) -> CognitionAttempt:
        if not isinstance(compiled, CompiledContext):
            raise TypeError("compiled must be a CompiledContext")
        opportunity_id = compiled.opportunity.opportunity_id
        if opportunity_id in self._grounding:
            raise RuntimeError("duplicate grounding attempt would violate no-retry policy")

        if selected_action not in PROPOSAL_HANDLE_ACTIONS:
            return self.baseline.generate_for_action(compiled, selected_action)

        rendered, handles = render_with_proposal_handles(compiled)
        if not handles.canonical_to_handle:
            self._grounding[opportunity_id] = ProposalGroundingRecord(
                opportunity_id,
                selected_action,
                "BASELINE_NO_VISIBLE_PROPOSAL_REFERENCE",
                handles,
                None,
                None,
                None,
            )
            return self.baseline.generate_for_action(compiled, selected_action)

        snapshot_hash = compiled.opportunity.snapshot.state_hash()
        treatment = proposal_handle_treatment(selected_action)
        constraint = build_transformers_constraint(
            self.runtime.tokenizer,
            schema=forced_grounding_schema(
                selected_action,
                pointer_values=handles.handles,
            ),
        )
        treated_compiled = replace(compiled, rendered_input=rendered)
        preparation = prepare_cognition_evidence(
            treated_compiled,
            self.phase_runtime,
            self.profile,
            self.generation_policy,
            self.artifact_store,
            generation_seed=self.generation_seed,
            parser=self.parser,
            interface_treatment=treatment,
            prefix_allowed_tokens_fn=constraint,
        )
        trace = self.phase_runtime.last_trace
        if trace is None:
            raise RuntimeError("proposal-handle payload generation completed without trace")
        if (
            trace.prefill_adapter is not C10_PREFILL_ADAPTER
            or trace.selector_adapter is not C10_SELECTOR_ADAPTER
            or not trace.phase_boundary_token_aligned
            or trace.world_prefill_forward_count != 1
            or trace.world_context_recomputed_after_switch
        ):
            raise RuntimeError("proposal-handle C10 phase integrity failed")
        if compiled.opportunity.snapshot.state_hash() != snapshot_hash:
            raise AssertionError("proposal-handle generation mutated its bound Snapshot")
        self._traces[opportunity_id] = trace

        raw_candidate = preparation.candidate
        mapped_candidate = raw_candidate
        effective_status = preparation.parse_status
        effective_rejection = preparation.rejection
        expected_label = DEFAULT_ACTION_PRESENTATION.entry(selected_action).model_label
        if (
            raw_candidate is not None
            and raw_candidate.action_label == expected_label
            and set(raw_candidate.payload_dict()) == {"proposal_id"}
        ):
            try:
                mapped_candidate = resolve_proposal_handle_candidate(raw_candidate, handles)
            except (TypeError, ValueError) as error:
                mapped_candidate = None
                effective_status = ModelOutputStatus.DOMAIN_REJECTED
                effective_rejection = RejectedModelOutput(
                    generation_id=preparation.raw_generation.generation_id,
                    status=ModelOutputStatus.DOMAIN_REJECTED,
                    error_type="ProposalHandleResolutionError",
                    error_message=str(error),
                )

        canonical_preparation = replace(
            preparation,
            candidate=mapped_candidate,
            parse_status=effective_status,
            rejection=effective_rejection,
        )
        self._grounding[opportunity_id] = ProposalGroundingRecord(
            opportunity_id,
            selected_action,
            "PROPOSAL_HANDLE_VISIBLE_REFERENCE_DOMAIN",
            handles,
            raw_candidate,
            mapped_candidate,
            treatment.treatment_id,
        )

        def finalize(action_intent, rejection):
            return finalize_cognition_evidence(
                canonical_preparation,
                self.profile,
                self.generation_policy,
                self.artifact_store,
                action_intent=action_intent,
                rejection=rejection,
            )

        return CognitionAttempt(
            opportunity_id=opportunity_id,
            candidate=mapped_candidate,
            evidence_ref=None,
            parse_status=effective_status,
            generation_id=preparation.raw_generation.generation_id,
            rejection=effective_rejection,
            evidence_finalizer=finalize,
        )


def build_c10_score_selected_proposal_handle_runtime(
    runtime: Any,
    *,
    profile: ModelProfile,
    generation_policy: GenerationPolicy,
    artifact_store: ArtifactStore,
    generation_seed: int | None,
    parser: ModelActionParser | None = None,
) -> ScoreSelectedCandidateRuntime:
    """Compose unchanged C10 scores with proposal-handle payload grounding."""

    score_provider = C10MeanBranchScoreProvider(runtime)
    payload_provider = C10ProposalHandlePayloadProvider(
        runtime,
        profile=profile,
        generation_policy=generation_policy,
        artifact_store=artifact_store,
        generation_seed=generation_seed,
        parser=parser,
    )
    return ScoreSelectedCandidateRuntime(score_provider, payload_provider)


__all__ = [
    "PROPOSAL_HANDLE_ACTIONS",
    "PROPOSAL_HANDLE_GROUNDING_VERSION",
    "ProposalGroundingRecord",
    "ProposalHandleMap",
    "C10ProposalHandlePayloadProvider",
    "build_c10_score_selected_proposal_handle_runtime",
    "proposal_handle_map",
    "proposal_handle_treatment",
    "render_with_proposal_handles",
    "resolve_proposal_handle_candidate",
]
