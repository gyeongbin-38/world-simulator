from __future__ import annotations

import pytest

from alifelm.context import DEFAULT_ACTION_PRESENTATION, ModelActionCandidate
from alifelm.model.proposal_handle_grounding import (
    PROPOSAL_HANDLE_ACTIONS,
    ProposalHandleMap,
    proposal_handle_map,
    proposal_handle_treatment,
    render_with_proposal_handles,
    resolve_proposal_handle_candidate,
)
from alifelm.model.r3_fixtures import R3ContextClass, compile_r3_fixture
from alifelm.model.treatments import I3_CONDITIONAL_TYPED_CODEC
from alifelm.model.world_v0_smoke import build_context_policy


def _compiled(context_class: R3ContextClass, case_index: int = 4000):
    return compile_r3_fixture(
        context_class,
        case_index,
        policy=build_context_policy(),
        model_profile_id="proposal-handle-test-model",
        generation_policy_id="proposal-handle-test-policy",
        generation_seed_id="proposal-handle-test-seed",
        artifact_store=None,
    )


def test_quiet_context_has_no_proposal_handles_and_rendering_is_unchanged() -> None:
    compiled = _compiled(R3ContextClass.QUIET)

    rendered, handles = render_with_proposal_handles(compiled)

    assert handles == ProposalHandleMap(())
    assert rendered == compiled.rendered_input


def test_incoming_proposal_is_aliased_but_agent_ids_are_not() -> None:
    compiled = _compiled(R3ContextClass.PROPOSAL_RECEIVED)
    canonical = "incoming-4000"

    rendered, handles = render_with_proposal_handles(compiled)
    text = rendered.decode("utf-8")

    assert handles.canonical_to_handle == ((canonical, "R0"),)
    assert canonical not in text
    assert "request R0 from B" in text
    assert "- B" in text
    assert "- C" in text


def test_outgoing_proposal_is_aliased_without_changing_counterparty() -> None:
    compiled = _compiled(R3ContextClass.OWN_PROPOSAL_PENDING)
    canonical = "outgoing-4000"

    rendered, handles = render_with_proposal_handles(compiled)
    text = rendered.decode("utf-8")

    assert handles.canonical_to_handle == ((canonical, "R0"),)
    assert canonical not in text
    assert "request R0 to B" in text
    assert "- B" in text


def test_handle_map_uses_strict_deterministic_r_sequence() -> None:
    assert ProposalHandleMap((("a", "R0"), ("b", "R1"))).handles == ("R0", "R1")

    with pytest.raises(ValueError, match="R0..Rn"):
        ProposalHandleMap((("a", "R1"),))


def test_proposal_handle_treatment_is_accept_reject_only_and_keeps_i3_boundary() -> None:
    assert PROPOSAL_HANDLE_ACTIONS == frozenset(("ACCEPT", "REJECT"))

    treatment = proposal_handle_treatment("ACCEPT")
    assert treatment.completion_suffix == I3_CONDITIONAL_TYPED_CODEC.completion_suffix
    assert treatment.treatment_id == "exp000-proposal-handle-accept-v1"
    assert "visible-reference-domain" in treatment.constraint_policy_id

    with pytest.raises(ValueError, match="ACCEPT/REJECT"):
        proposal_handle_treatment("SEND")


def test_resolve_proposal_handle_candidate_maps_only_the_reference() -> None:
    handles = ProposalHandleMap((("canonical-proposal", "R0"),))
    label = DEFAULT_ACTION_PRESENTATION.entry("ACCEPT").model_label
    raw = ModelActionCandidate(label, (("proposal_id", "R0"),))

    mapped = resolve_proposal_handle_candidate(raw, handles)

    assert mapped.action_label == label
    assert mapped.payload_dict() == {"proposal_id": "canonical-proposal"}


def test_resolve_unknown_handle_fails_closed() -> None:
    handles = ProposalHandleMap((("canonical-proposal", "R0"),))
    label = DEFAULT_ACTION_PRESENTATION.entry("REJECT").model_label
    raw = ModelActionCandidate(label, (("proposal_id", "R9"),))

    with pytest.raises(ValueError, match="outside the visible reference domain"):
        resolve_proposal_handle_candidate(raw, handles)


def test_proposal_handle_map_is_derived_from_model_visible_records_only() -> None:
    incoming = _compiled(R3ContextClass.PROPOSAL_RECEIVED, 4012)
    quiet = _compiled(R3ContextClass.QUIET, 4012)

    assert proposal_handle_map(incoming).canonical_ids == ("incoming-4012",)
    assert proposal_handle_map(quiet).canonical_ids == ()
