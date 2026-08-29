from __future__ import annotations

import json

import pytest

from alifelm.context import (
    ContextPolicy,
    DEFAULT_ACTION_PRESENTATION,
    OrderingPolicy,
    action_presentation_digest,
)
from alifelm.model import (
    ACTION_SCORE_TREATMENT_ID,
    ACTION_SCORE_TREATMENT_VERSION,
    ActionLabelScoreResult,
    I3_BRANCH_ORDERS,
    R3ContextClass,
    action_label_score_bytes,
    compile_r3_fixture,
    forced_action_codec_json_schema,
    i3_branch_order_treatment,
    i3_forced_branch_treatment,
    rank_action_label_scores,
    typed_action_codec_json_schema,
)
from alifelm.persistence import FileSystemArtifactStore


def _policy() -> ContextPolicy:
    return ContextPolicy.exp000(
        max_prior_visible_records=4,
        ordering=OrderingPolicy(
            policy_version="1.0.0",
            unordered_collection_algorithm="ALIFELM_CONTEXT_ORDER_V1",
            digest_algorithm="sha256",
            ordering_seed_id="i05r3-test-order",
            ordering_seed_digest="2" * 64,
            cross_tick_order="COMMITTED_TICK_CHRONOLOGICAL",
            tie_breaker="FULL_STABLE_ITEM_KEY",
        ),
        action_presentation_digest=action_presentation_digest(
            DEFAULT_ACTION_PRESENTATION
        ),
    )


@pytest.mark.parametrize(
    ("context_class", "expected"),
    [
        (R3ContextClass.QUIET, (0, 0, 0)),
        (R3ContextClass.MESSAGE_RECEIVED, (1, 0, 0)),
        (R3ContextClass.PROPOSAL_RECEIVED, (0, 1, 0)),
        (R3ContextClass.OWN_PROPOSAL_PENDING, (0, 1, 0)),
        (R3ContextClass.RECENT_INTERACTION, (0, 0, 1)),
    ],
)
def test_r3_fixture_changes_only_committed_visible_state(
    tmp_path, context_class: R3ContextClass, expected: tuple[int, int, int]
) -> None:
    compiled = compile_r3_fixture(
        context_class,
        3,
        policy=_policy(),
        model_profile_id="profile-r3",
        generation_policy_id="mode-d",
        generation_seed_id="seed-r3",
        artifact_store=FileSystemArtifactStore(tmp_path / "cas"),
    )
    model_input = compiled.context_pack.model_input
    observed = (
        len(model_input.newly_delivered),
        len(model_input.visible_protocol_state),
        len(model_input.prior_history),
    )
    assert observed == expected
    assert len(model_input.peer_directory) == 2
    assert compiled.opportunity.snapshot.state_hash() == (
        compiled.context_pack.evidence.bound_state_hash
    )


def test_r3_fixture_adds_no_behavior_directive(tmp_path) -> None:
    rendered = compile_r3_fixture(
        R3ContextClass.MESSAGE_RECEIVED,
        2,
        policy=_policy(),
        model_profile_id="profile-r3",
        generation_policy_id="mode-d",
        generation_seed_id="seed-r3",
        artifact_store=FileSystemArtifactStore(tmp_path / "cas"),
    ).rendered_input.decode("utf-8")
    assert "signal-2" in rendered
    assert "you should" not in rendered.lower()
    assert "choose appropriately" not in rendered.lower()
    assert "best action" not in rendered.lower()


def test_branch_order_treatments_change_identity_not_branch_semantics() -> None:
    digests = set()
    expected_labels = {
        entry.model_label for entry in DEFAULT_ACTION_PRESENTATION.actions
    }
    for index, order in enumerate(I3_BRANCH_ORDERS):
        treatment = i3_branch_order_treatment(index)
        schema = typed_action_codec_json_schema(action_order=order)
        observed = [
            branch["properties"]["action_label"]["const"]
            for branch in schema["oneOf"]
        ]
        assert observed == [
            DEFAULT_ACTION_PRESENTATION.entry(action).model_label for action in order
        ]
        assert set(observed) == expected_labels
        digests.add(treatment.digest)
    assert len(digests) == 4


@pytest.mark.parametrize("action", ("SEND", "PROPOSE", "ACCEPT", "REJECT"))
def test_forced_branch_constrains_shape_not_semantic_values(action: str) -> None:
    schema = forced_action_codec_json_schema(action)
    entry = DEFAULT_ACTION_PRESENTATION.entry(action)
    assert schema["properties"]["action_label"]["const"] == entry.model_label
    payload = schema["properties"]["payload"]
    assert tuple(payload["required"]) == entry.payload_fields
    assert "enum" not in json.dumps(payload)
    assert i3_forced_branch_treatment(action).treatment_id.endswith(
        f"{action.lower()}-payload"
    )


def test_action_score_ranking_uses_full_sequence_total() -> None:
    ranked = rank_action_label_scores(
        (
            ("A", (1,), -2.0),
            ("B", (2, 3), -1.0),
            ("C", (4,), -3.0),
            ("D", (5,), -4.0),
            ("E", (6,), -5.0),
        )
    )
    assert [score.model_label for score in ranked] == ["B", "A", "C", "D", "E"]
    assert ranked[0].mean_log_probability == -0.5


def test_action_score_artifact_is_deterministic_and_researcher_only() -> None:
    scores = rank_action_label_scores(
        tuple(
            (entry.model_label, (index,), -float(index))
            for index, entry in enumerate(DEFAULT_ACTION_PRESENTATION.actions, 1)
        )
    )
    result = ActionLabelScoreResult(
        context_hash="a" * 64,
        context_pack_ref="b" * 64,
        rendered_input_hash="c" * 64,
        rendered_input_ref="d" * 64,
        model_profile_id="profile-r3",
        model_revision="revision-r3",
        treatment_id=ACTION_SCORE_TREATMENT_ID,
        treatment_version=ACTION_SCORE_TREATMENT_VERSION,
        score_prefix_hash="e" * 64,
        scores=scores,
        shared_token_prefixes=(),
    )
    first = action_label_score_bytes(result)
    assert first == action_label_score_bytes(result)
    document = json.loads(first)
    assert document["context_pack_ref"] == "b" * 64
    assert document["rendered_input_ref"] == "d" * 64
    assert "action_intent" not in document
