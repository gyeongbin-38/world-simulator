"""Real-runtime composition for the preregistered EXP-000 C10 score selector.

This module is the GPU-bound adapter between the already-admitted generic
``ScoreSelectedCandidateRuntime`` and the existing P2 phase-scoring/generation
machinery.  It does not change the selector rule, temperature, action order,
legality semantics, Gateway authority, or commit authority.

C10 remains exactly:

* WORLD prefill under FA-v1;
* action scoring / continuation under BASE.

The score stage measures the five frozen I3 mean branch log probabilities.
After the generic selector fixes one action, the payload stage runs one forced
I3 branch for that action only.  It may fill payload values but cannot select a
different action.  No retry, fallback, repair, legality mask, or action bonus
is implemented here.
"""

from __future__ import annotations

from typing import Any, Mapping

from alifelm.context import CognitionAttempt, CompiledContext, ModelActionParser
from alifelm.domain import OpportunityId
from alifelm.persistence import ArtifactStore

from .evidence import (
    ModelOutputStatus,
    finalize_cognition_evidence,
    prepare_cognition_evidence,
)
from .generation import GenerationPolicy
from .p2_d1_boundary import (
    D1_ACTION_ORDER,
    D1BoundaryProbeResult,
    score_i3_decision_boundary,
)
from .phase_generation import PhaseGenerationTrace, PhaseSwitchedGenerationRuntime
from .profile import ModelProfile
from .score_selected_runtime import ScoreSelectedCandidateRuntime
from .treatments import (
    I3_CONDITIONAL_TYPED_CODEC,
    build_transformers_constraint,
    forced_action_codec_json_schema,
    i3_forced_branch_treatment,
)


C10_PREFILL_ADAPTER = True
C10_SELECTOR_ADAPTER = False


class C10MeanBranchScoreProvider:
    """Measure one immutable C10 D1-style score vector per opportunity."""

    def __init__(self, runtime: Any) -> None:
        if not hasattr(runtime, "model") or not hasattr(runtime, "tokenizer"):
            raise TypeError("runtime must provide model and tokenizer for C10 scoring")
        self.runtime = runtime
        self._probes: dict[OpportunityId, D1BoundaryProbeResult] = {}

    def probe_for(self, opportunity_id: OpportunityId) -> D1BoundaryProbeResult:
        if not isinstance(opportunity_id, OpportunityId):
            raise TypeError("opportunity_id must be an OpportunityId")
        try:
            return self._probes[opportunity_id]
        except KeyError as error:
            raise KeyError("no C10 score probe exists for this opportunity") from error

    def mean_scores(self, compiled: CompiledContext) -> Mapping[str, float]:
        if not isinstance(compiled, CompiledContext):
            raise TypeError("compiled must be a CompiledContext")
        opportunity_id = compiled.opportunity.opportunity_id
        if opportunity_id in self._probes:
            raise RuntimeError("duplicate C10 score probe would violate V1 no-retry policy")

        snapshot_hash = compiled.opportunity.snapshot.state_hash()
        rendered = I3_CONDITIONAL_TYPED_CODEC.render(compiled.rendered_input)
        probe = score_i3_decision_boundary(
            self.runtime,
            rendered_input=rendered,
            prefill_adapter=C10_PREFILL_ADAPTER,
            selector_adapter=C10_SELECTOR_ADAPTER,
        )
        if (
            probe.prefill_adapter is not C10_PREFILL_ADAPTER
            or probe.selector_adapter is not C10_SELECTOR_ADAPTER
        ):
            raise RuntimeError("C10 score probe returned a non-C10 phase identity")
        if tuple(score.internal_action for score in probe.branch_scores) != D1_ACTION_ORDER:
            raise RuntimeError("C10 score probe action order differs from frozen D1 order")
        if compiled.opportunity.snapshot.state_hash() != snapshot_hash:
            raise AssertionError("C10 score probe mutated its bound Snapshot")

        self._probes[opportunity_id] = probe
        return probe.mean_scores()


class C10ConditionalPayloadProvider:
    """Generate only the payload branch for one already-selected non-WAIT action."""

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
        if not isinstance(profile, ModelProfile):
            raise TypeError("profile must be a ModelProfile")
        if not isinstance(generation_policy, GenerationPolicy):
            raise TypeError("generation_policy must be a GenerationPolicy")
        if getattr(runtime, "profile", profile) != profile:
            raise ValueError("runtime profile does not match C10 payload profile")
        if not hasattr(artifact_store, "put_bytes") or not hasattr(artifact_store, "resolve"):
            raise TypeError("artifact_store must provide put_bytes and resolve")

        self.runtime = runtime
        self.profile = profile
        self.generation_policy = generation_policy
        self.artifact_store = artifact_store
        self.generation_seed = generation_seed
        self.parser = parser or ModelActionParser()
        self.phase_runtime = PhaseSwitchedGenerationRuntime(
            runtime,
            prefill_adapter=C10_PREFILL_ADAPTER,
            selector_adapter=C10_SELECTOR_ADAPTER,
        )
        self._traces: dict[OpportunityId, PhaseGenerationTrace] = {}

    def trace_for(self, opportunity_id: OpportunityId) -> PhaseGenerationTrace:
        if not isinstance(opportunity_id, OpportunityId):
            raise TypeError("opportunity_id must be an OpportunityId")
        try:
            return self._traces[opportunity_id]
        except KeyError as error:
            raise KeyError("no C10 payload trace exists for this opportunity") from error

    def generate_for_action(
        self,
        compiled: CompiledContext,
        selected_action: str,
    ) -> CognitionAttempt:
        if not isinstance(compiled, CompiledContext):
            raise TypeError("compiled must be a CompiledContext")
        if selected_action not in D1_ACTION_ORDER:
            raise ValueError("selected_action is outside the frozen action order")
        if selected_action == "WAIT":
            raise ValueError("WAIT has no conditional payload generation stage")

        opportunity_id = compiled.opportunity.opportunity_id
        if opportunity_id in self._traces:
            raise RuntimeError("duplicate C10 payload generation would violate V1 no-retry policy")

        snapshot_hash = compiled.opportunity.snapshot.state_hash()
        treatment = i3_forced_branch_treatment(selected_action)
        constraint = build_transformers_constraint(
            self.runtime.tokenizer,
            schema=forced_action_codec_json_schema(selected_action),
        )
        preparation = prepare_cognition_evidence(
            compiled,
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
            raise RuntimeError("C10 payload generation completed without a phase trace")
        if (
            trace.prefill_adapter is not C10_PREFILL_ADAPTER
            or trace.selector_adapter is not C10_SELECTOR_ADAPTER
            or not trace.phase_boundary_token_aligned
            or trace.world_prefill_forward_count != 1
            or trace.world_context_recomputed_after_switch
        ):
            raise RuntimeError("C10 payload generation phase integrity failed")
        if compiled.opportunity.snapshot.state_hash() != snapshot_hash:
            raise AssertionError("C10 payload generation mutated its bound Snapshot")
        self._traces[opportunity_id] = trace

        def finalize(action_intent, rejection):
            return finalize_cognition_evidence(
                preparation,
                self.profile,
                self.generation_policy,
                self.artifact_store,
                action_intent=action_intent,
                rejection=rejection,
            )

        return CognitionAttempt(
            opportunity_id=opportunity_id,
            candidate=preparation.candidate,
            evidence_ref=None,
            parse_status=preparation.parse_status,
            generation_id=preparation.raw_generation.generation_id,
            rejection=preparation.rejection,
            evidence_finalizer=finalize,
        )


def build_c10_score_selected_runtime(
    runtime: Any,
    *,
    profile: ModelProfile,
    generation_policy: GenerationPolicy,
    artifact_store: ArtifactStore,
    generation_seed: int | None,
    parser: ModelActionParser | None = None,
) -> ScoreSelectedCandidateRuntime:
    """Compose the frozen C10 scorer and forced-payload provider for LIVE P4."""

    score_provider = C10MeanBranchScoreProvider(runtime)
    payload_provider = C10ConditionalPayloadProvider(
        runtime,
        profile=profile,
        generation_policy=generation_policy,
        artifact_store=artifact_store,
        generation_seed=generation_seed,
        parser=parser,
    )
    return ScoreSelectedCandidateRuntime(score_provider, payload_provider)


__all__ = [
    "C10_PREFILL_ADAPTER",
    "C10_SELECTOR_ADAPTER",
    "C10ConditionalPayloadProvider",
    "C10MeanBranchScoreProvider",
    "build_c10_score_selected_runtime",
]
