"""CPU-testable EXP-000 two-stage score-selected cognition runtime.

This module composes the preregistered V1 score selector with a conditional
payload stage.  It does not implement transformer scoring itself and therefore
can be admitted on CPU before any new GPU forward.

The selector owns the action label.  The payload stage may only fill the
payload for that already-selected action.  A mismatching label/shape is a typed
rejection, never a re-selection or fallback WAIT.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Mapping, Protocol

from alifelm.context import (
    CognitionAttempt,
    CompiledContext,
    DEFAULT_ACTION_PRESENTATION,
    ModelActionCandidate,
)
from alifelm.domain import OpportunityId

from .evidence import ModelOutputStatus, RejectedModelOutput
from .score_selector import ScoreSelectorDecision, select_score_action


class MeanBranchScoreProvider(Protocol):
    """Provide the five frozen D1/I3 mean branch scores for one context."""

    def mean_scores(self, compiled: CompiledContext) -> Mapping[str, float]: ...


class ConditionalPayloadProvider(Protocol):
    """Generate evidence/candidate for one action that was selected already."""

    def generate_for_action(
        self,
        compiled: CompiledContext,
        selected_action: str,
    ) -> CognitionAttempt: ...


class ScoreSelectedCandidateRuntime:
    """Compose score selection and payload generation without action rewrite.

    V1 is intentionally single-attempt.  Calling ``infer`` twice for the same
    cognition opportunity fails closed rather than becoming an implicit retry.
    Decisions are retained only as research-side runtime evidence keyed by
    immutable opportunity identity; they are not canonical simulation state.
    """

    def __init__(
        self,
        score_provider: MeanBranchScoreProvider,
        payload_provider: ConditionalPayloadProvider,
    ) -> None:
        if not hasattr(score_provider, "mean_scores"):
            raise TypeError("score_provider must provide mean_scores(compiled)")
        if not hasattr(payload_provider, "generate_for_action"):
            raise TypeError("payload_provider must provide generate_for_action(compiled, action)")
        self.score_provider = score_provider
        self.payload_provider = payload_provider
        self._decisions: dict[OpportunityId, ScoreSelectorDecision] = {}

    def decision_for(self, opportunity_id: OpportunityId) -> ScoreSelectorDecision:
        if not isinstance(opportunity_id, OpportunityId):
            raise TypeError("opportunity_id must be an OpportunityId")
        try:
            return self._decisions[opportunity_id]
        except KeyError as error:
            raise KeyError("no score-selector decision exists for this opportunity") from error

    def infer(self, compiled: CompiledContext) -> CognitionAttempt:
        if not isinstance(compiled, CompiledContext):
            raise TypeError("compiled must be a CompiledContext")
        opportunity = compiled.opportunity
        if opportunity.opportunity_id in self._decisions:
            raise RuntimeError("duplicate cognition opportunity would violate V1 no-retry policy")

        scores = self.score_provider.mean_scores(compiled)
        decision = select_score_action(
            scores,
            run_id=opportunity.run_id,
            tick=opportunity.tick,
            opportunity_id=opportunity.opportunity_id,
            agent_id=opportunity.agent_id,
        )
        self._decisions[opportunity.opportunity_id] = decision

        entry = DEFAULT_ACTION_PRESENTATION.entry(decision.selected_action)
        if decision.selected_action == "WAIT":
            # WAIT has no payload stage.  The selected label itself is the full
            # model-facing candidate under the frozen action presentation.
            return CognitionAttempt(
                opportunity_id=opportunity.opportunity_id,
                candidate=ModelActionCandidate(entry.model_label, ()),
                evidence_ref=None,
                parse_status=ModelOutputStatus.VALID,
                generation_id=f"score-selector-{decision.seed_digest}",
            )

        attempt = self.payload_provider.generate_for_action(
            compiled,
            decision.selected_action,
        )
        if not isinstance(attempt, CognitionAttempt):
            raise TypeError("payload provider must return CognitionAttempt")
        if attempt.opportunity_id != opportunity.opportunity_id:
            raise ValueError("payload attempt opportunity identity does not match selection")
        if attempt.candidate is None:
            if attempt.rejection is None:
                raise ValueError("payload rejection requires typed rejection evidence")
            return attempt

        candidate = attempt.candidate
        actual_fields = {name for name, _ in candidate.payload}
        expected_fields = set(entry.payload_fields)
        if candidate.action_label == entry.model_label and actual_fields == expected_fields:
            return attempt

        rejection = RejectedModelOutput(
            generation_id=attempt.generation_id or f"score-selector-{decision.seed_digest}",
            status=ModelOutputStatus.DOMAIN_REJECTED,
            error_type="SelectedActionMismatch",
            error_message=(
                "conditional payload stage changed the preregistered selected action "
                "or payload field shape"
            ),
        )
        return replace(
            attempt,
            candidate=None,
            parse_status=ModelOutputStatus.DOMAIN_REJECTED,
            rejection=rejection,
        )


__all__ = [
    "ConditionalPayloadProvider",
    "MeanBranchScoreProvider",
    "ScoreSelectedCandidateRuntime",
]
