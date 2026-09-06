from __future__ import annotations

from dataclasses import dataclass

import pytest

from alifelm.context import CognitionAttempt, CompiledContext, ModelActionCandidate
from alifelm.domain import AgentId, Duration, OpportunityId, RunId
from alifelm.kernel import EqualOpportunityScheduler, SimulationRun
from alifelm.model.evidence import ModelOutputStatus, RejectedModelOutput
from alifelm.model.score_selected_runtime import ScoreSelectedCandidateRuntime


ACTIONS = ("WAIT", "SEND", "PROPOSE", "ACCEPT", "REJECT")


def _compiled(agent: str = "A") -> CompiledContext:
    run = SimulationRun.bootstrap(
        RunId("EXP000_CPU_COMPOSE"),
        lifespan_ticks=Duration(20),
        founder_ids=(AgentId("A"), AgentId("B")),
    )
    opportunities = EqualOpportunityScheduler().enumerate(run.snapshot)
    opportunity = next(item for item in opportunities if item.agent_id == AgentId(agent))
    return CompiledContext(
        opportunity=opportunity,
        context_pack=object(),
        rendered_input=b"cpu-only",
        artifact_ref=None,
    )


@dataclass
class Scores:
    values: dict[str, float]
    calls: int = 0

    def mean_scores(self, compiled):
        self.calls += 1
        return dict(self.values)


class Payloads:
    def __init__(self, *, candidate=None, rejection=None):
        self.candidate = candidate
        self.rejection = rejection
        self.calls: list[tuple[str, str]] = []

    def generate_for_action(self, compiled, selected_action):
        self.calls.append((compiled.opportunity.agent_id.value, selected_action))
        return CognitionAttempt(
            opportunity_id=compiled.opportunity.opportunity_id,
            candidate=self.candidate,
            evidence_ref=None,
            parse_status=(
                ModelOutputStatus.VALID
                if self.candidate is not None
                else ModelOutputStatus.INVALID_PAYLOAD
            ),
            generation_id="payload-generation",
            rejection=self.rejection,
        )


class AnySelectedPayload:
    """Return a contract-shaped candidate for whichever action was selected."""

    def generate_for_action(self, compiled, selected_action):
        candidates = {
            "SEND": ModelActionCandidate(
                "DIRECT_TEXT",
                (("body", "hello"), ("target_agent_id", "B")),
            ),
            "PROPOSE": ModelActionCandidate(
                "OPEN_BILATERAL_REQUEST",
                (("target_agent_id", "B"),),
            ),
            "ACCEPT": ModelActionCandidate(
                "CONFIRM_BILATERAL_REQUEST",
                (("proposal_id", "PENDING"),),
            ),
            "REJECT": ModelActionCandidate(
                "DECLINE_BILATERAL_REQUEST",
                (("proposal_id", "PENDING"),),
            ),
        }
        return CognitionAttempt(
            opportunity_id=compiled.opportunity.opportunity_id,
            candidate=candidates[selected_action],
            evidence_ref=None,
            parse_status=ModelOutputStatus.VALID,
            generation_id="payload-generation",
        )


def _dominant(action: str) -> dict[str, float]:
    return {name: (1000.0 if name == action else -1000.0) for name in ACTIONS}


def test_wait_selection_skips_payload_generation() -> None:
    scores = Scores(_dominant("WAIT"))
    payloads = Payloads()
    runtime = ScoreSelectedCandidateRuntime(scores, payloads)

    attempt = runtime.infer(_compiled())

    assert attempt.candidate == ModelActionCandidate("NO_DIRECTED_ACTION", ())
    assert payloads.calls == []
    assert scores.calls == 1
    assert runtime.decision_for(attempt.opportunity_id).selected_action == "WAIT"


def test_selected_send_is_immutable_and_payload_only_fills_send() -> None:
    scores = Scores(_dominant("SEND"))
    candidate = ModelActionCandidate(
        "DIRECT_TEXT",
        (("body", "hello"), ("target_agent_id", "B")),
    )
    payloads = Payloads(candidate=candidate)
    runtime = ScoreSelectedCandidateRuntime(scores, payloads)

    attempt = runtime.infer(_compiled())

    assert runtime.decision_for(attempt.opportunity_id).selected_action == "SEND"
    assert payloads.calls == [("A", "SEND")]
    assert attempt.candidate == candidate


def test_payload_stage_cannot_reselect_another_action() -> None:
    scores = Scores(_dominant("SEND"))
    wrong = ModelActionCandidate("NO_DIRECTED_ACTION", ())
    runtime = ScoreSelectedCandidateRuntime(scores, Payloads(candidate=wrong))

    attempt = runtime.infer(_compiled())

    assert attempt.candidate is None
    assert attempt.parse_status is ModelOutputStatus.DOMAIN_REJECTED
    assert isinstance(attempt.rejection, RejectedModelOutput)
    assert attempt.rejection.error_type == "SelectedActionMismatch"


def test_payload_field_shape_change_is_rejected_not_rewritten() -> None:
    scores = Scores(_dominant("SEND"))
    wrong_shape = ModelActionCandidate("DIRECT_TEXT", (("target_agent_id", "B"),))
    runtime = ScoreSelectedCandidateRuntime(scores, Payloads(candidate=wrong_shape))

    attempt = runtime.infer(_compiled())

    assert attempt.candidate is None
    assert attempt.parse_status is ModelOutputStatus.DOMAIN_REJECTED
    assert attempt.rejection is not None


def test_typed_payload_rejection_is_preserved_without_fallback() -> None:
    scores = Scores(_dominant("ACCEPT"))
    rejection = RejectedModelOutput(
        generation_id="payload-generation",
        status=ModelOutputStatus.INVALID_PAYLOAD,
        error_type="BadProposal",
        error_message="no proposal payload",
    )
    runtime = ScoreSelectedCandidateRuntime(
        scores,
        Payloads(candidate=None, rejection=rejection),
    )

    attempt = runtime.infer(_compiled())

    assert runtime.decision_for(attempt.opportunity_id).selected_action == "ACCEPT"
    assert attempt.candidate is None
    assert attempt.rejection == rejection
    assert attempt.parse_status is ModelOutputStatus.INVALID_PAYLOAD


def test_no_legality_mask_rewrites_selected_accept_without_visible_proposal() -> None:
    scores = Scores(_dominant("ACCEPT"))
    candidate = ModelActionCandidate(
        "CONFIRM_BILATERAL_REQUEST",
        (("proposal_id", "NONEXISTENT"),),
    )
    payloads = Payloads(candidate=candidate)
    runtime = ScoreSelectedCandidateRuntime(scores, payloads)

    attempt = runtime.infer(_compiled())

    assert runtime.decision_for(attempt.opportunity_id).selected_action == "ACCEPT"
    assert payloads.calls == [("A", "ACCEPT")]
    assert attempt.candidate == candidate


def test_duplicate_opportunity_fails_closed_instead_of_retrying() -> None:
    scores = Scores(_dominant("WAIT"))
    runtime = ScoreSelectedCandidateRuntime(scores, Payloads())
    compiled = _compiled()

    runtime.infer(compiled)
    with pytest.raises(RuntimeError, match="no-retry"):
        runtime.infer(compiled)

    assert scores.calls == 1


def test_completion_order_does_not_change_per_opportunity_decision() -> None:
    values = {
        "WAIT": -0.2,
        "SEND": -0.3,
        "PROPOSE": -1.0,
        "ACCEPT": -1.1,
        "REJECT": -2.0,
    }
    a = _compiled("A")
    b = _compiled("B")

    forward = ScoreSelectedCandidateRuntime(Scores(values), AnySelectedPayload())
    reverse = ScoreSelectedCandidateRuntime(Scores(values), AnySelectedPayload())

    for compiled in (a, b):
        forward.infer(compiled)
    for compiled in (b, a):
        reverse.infer(compiled)

    for compiled in (a, b):
        oid = compiled.opportunity.opportunity_id
        assert forward.decision_for(oid) == reverse.decision_for(oid)


def test_payload_attempt_must_match_opportunity_identity() -> None:
    class WrongOpportunityPayload:
        def generate_for_action(self, compiled, selected_action):
            return CognitionAttempt(
                opportunity_id=OpportunityId("0" * 64),
                candidate=ModelActionCandidate(
                    "DIRECT_TEXT",
                    (("body", "hello"), ("target_agent_id", "B")),
                ),
                evidence_ref=None,
                parse_status=ModelOutputStatus.VALID,
            )

    runtime = ScoreSelectedCandidateRuntime(
        Scores(_dominant("SEND")),
        WrongOpportunityPayload(),
    )

    with pytest.raises(ValueError, match="opportunity identity"):
        runtime.infer(_compiled())


def test_payload_provider_must_return_cognition_attempt() -> None:
    class BadPayload:
        def generate_for_action(self, compiled, selected_action):
            return {"action_label": "DIRECT_TEXT", "payload": {}}

    runtime = ScoreSelectedCandidateRuntime(Scores(_dominant("SEND")), BadPayload())

    with pytest.raises(TypeError, match="CognitionAttempt"):
        runtime.infer(_compiled())
