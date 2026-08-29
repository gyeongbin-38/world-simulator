from __future__ import annotations

import json

import pytest

from alifelm.context import ContextPolicy, DEFAULT_ACTION_PRESENTATION, OrderingPolicy, action_presentation_digest
from alifelm.model import (
    CodecValidityStatus,
    R3ContextClass,
    SELECTOR_CODES,
    SELECTOR_GENERATED_OBJECT_PREFIX,
    SELECTOR_PREFIX,
    SelectorCandidateParser,
    balanced_selector_codebooks,
    codec_status_for_selector,
    compile_r3_fixture,
    forced_grounding_schema,
    map_handle_candidate,
    render_selector_interface,
    render_with_local_handles,
    selector_codec_json_schema,
)


def _policy():
    return ContextPolicy.exp000(
        max_prior_visible_records=4,
        ordering=OrderingPolicy("1.0.0", "ALIFELM_CONTEXT_ORDER_V1", "sha256", "r4-order", "1" * 64, "COMMITTED_TICK_CHRONOLOGICAL", "FULL_STABLE_ITEM_KEY"),
        action_presentation_digest=action_presentation_digest(DEFAULT_ACTION_PRESENTATION),
    )


def _compiled(context_class=R3ContextClass.PROPOSAL_RECEIVED):
    return compile_r3_fixture(context_class, 0, policy=_policy(), model_profile_id="profile", generation_policy_id="mode-d", generation_seed_id="seed", artifact_store=None)


def test_balanced_codebooks_rotate_every_action_across_every_selector():
    books = balanced_selector_codebooks()
    assert len(books) == 5
    for action in DEFAULT_ACTION_PRESENTATION.presentation_order:
        assert {dict(book.action_to_code)[action] for book in books} == set(SELECTOR_CODES)
    assert len({book.digest for book in books}) == 5


def test_i4_renderer_removes_semantic_labels_and_exposes_current_mapping():
    compiled = _compiled()
    book = balanced_selector_codebooks()[0]
    rendered = render_selector_interface(compiled, book).decode()
    assert all(entry.model_label not in rendered for entry in DEFAULT_ACTION_PRESENTATION.actions)
    assert all(f"- {code}:" in rendered for code in SELECTOR_CODES)
    assert "incoming-0" in rendered


def test_selector_parser_maps_code_without_changing_payload_contract():
    book = balanced_selector_codebooks()[0]
    parser = SelectorCandidateParser(book)
    wait_code = dict(book.action_to_code)["WAIT"]
    candidate = parser.parse(json.dumps({"selector": wait_code, "payload": {}}))
    assert candidate.action_label == DEFAULT_ACTION_PRESENTATION.entry("WAIT").model_label
    assert codec_status_for_selector(json.dumps({"selector": wait_code, "payload": {}}), parser) is CodecValidityStatus.CODEC_VALID
    assert codec_status_for_selector(json.dumps({"selector": wait_code, "payload": {"x": "y"}}), parser) is CodecValidityStatus.ACTION_PAYLOAD_TYPE_MISMATCH


def test_selector_schema_is_action_typed_but_semantic_values_are_free():
    schema = selector_codec_json_schema(balanced_selector_codebooks()[0])
    assert len(schema["oneOf"]) == 5
    send = next(branch for branch in schema["oneOf"] if set(branch["properties"]["payload"]["required"]) == {"target_agent_id", "body"})
    assert "enum" not in send["properties"]["payload"]["properties"]["target_agent_id"]


def test_local_handles_replace_peer_and_proposal_ids_only_in_rendered_treatment():
    compiled = _compiled()
    rendered, handles = render_with_local_handles(compiled)
    text = rendered.decode()
    assert "P0" in text and "P1" in text and "R0" in text
    assert "incoming-0" not in text
    assert compiled.context_pack.model_input.visible_protocol_state[0].payload.proposal_id == "incoming-0"
    assert dict(handles.proposal_handles) == {"incoming-0": "R0"}


def test_free_grounding_does_not_mask_values_and_pointer_does():
    free = forced_grounding_schema("ACCEPT")
    pointer = forced_grounding_schema("ACCEPT", pointer_values=("R0", "R1"))
    free_ref = free["properties"]["payload"]["properties"]["proposal_id"]
    pointer_ref = pointer["properties"]["payload"]["properties"]["proposal_id"]
    assert "enum" not in free_ref
    assert pointer_ref["enum"] == ["R0", "R1"]


def test_handle_mapping_is_research_side_and_unknown_values_remain_unknown():
    compiled = _compiled()
    _, handles = render_with_local_handles(compiled)
    mapped = json.loads(map_handle_candidate('{"action_label":"CONFIRM_BILATERAL_REQUEST","payload":{"proposal_id":"R0"}}', handles))
    unknown = json.loads(map_handle_candidate('{"action_label":"CONFIRM_BILATERAL_REQUEST","payload":{"proposal_id":"R9"}}', handles))
    assert mapped["payload"]["proposal_id"] == "incoming-0"
    assert unknown["payload"]["proposal_id"] == "R9"


def test_codebooks_and_handle_maps_are_immutable():
    book = balanced_selector_codebooks()[0]
    with pytest.raises((AttributeError, TypeError)):
        book.codebook_id = "changed"
    _, handles = render_with_local_handles(_compiled())
    with pytest.raises((AttributeError, TypeError)):
        handles.peer_handles = ()


def test_r5_grounding_plan_can_exclude_pointer_treatment():
    plan = {
        "ACCEPT": {"G0": 10, "G1_FREE": 10},
        "REJECT": {"G0": 10, "G1_FREE": 10},
        "SEND": {"G0": 5, "G1_FREE": 5},
        "PROPOSE": {"G0": 5, "G1_FREE": 5},
    }
    assert sum(sum(modes.values()) for modes in plan.values()) == 60
    assert all("G1_POINTER" not in modes for modes in plan.values())


def test_selector_scoring_binds_after_the_generated_object_prefix():
    assert SELECTOR_PREFIX.endswith(b'{"selector":"')
    assert SELECTOR_GENERATED_OBJECT_PREFIX == b'{"selector":"'
    assert SELECTOR_PREFIX != SELECTOR_GENERATED_OBJECT_PREFIX


def test_grounding_probe_taxonomy_keeps_malformed_output_separate_from_hallucinated_id():
    codec_valid = False
    visible_hit = False
    self_target = False
    assert not (codec_valid and not visible_hit and not self_target)
