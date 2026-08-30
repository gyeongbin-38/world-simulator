from __future__ import annotations

import json

import pytest

from alifelm.model.foundation_eval import (
    FOUNDATION_ANSWER_PREFIX,
    FOUNDATION_EVALUATOR_ID,
    FOUNDATION_RANKING_METRIC,
    CandidateSequenceScore,
    FoundationSerializationEvaluation,
    FoundationScalarEvaluation,
    evaluate_foundation_serialization_text,
    foundation_evaluation_bytes,
    foundation_scoring_prompt,
    rank_candidate_sequence_scores,
)


def test_rank_candidate_sequence_scores_uses_mean_token_log_probability() -> None:
    ranked = rank_candidate_sequence_scores(
        (
            ("SHORT", (1,), -0.60),
            ("LONGER", (2, 3), -1.00),
            ("WORST", (4,), -2.00),
        )
    )
    assert [score.candidate for score in ranked] == ["LONGER", "SHORT", "WORST"]
    assert ranked[0].mean_log_probability == -0.5
    assert ranked[0].total_log_probability == -1.0


def test_rank_candidate_sequence_scores_has_stable_lexical_tie_break() -> None:
    ranked = rank_candidate_sequence_scores(
        (
            ("B", (1,), -0.5),
            ("A", (2,), -0.5),
        )
    )
    assert [score.candidate for score in ranked] == ["A", "B"]


def test_foundation_scoring_prompt_has_one_canonical_answer_boundary() -> None:
    assert foundation_scoring_prompt("facts\nquestion  \n") == (
        b"facts\nquestion" + FOUNDATION_ANSWER_PREFIX
    )


def _serialization_record(expected: str) -> dict[str, str]:
    return {
        "example_id": "F0-TEST-000001",
        "semantic_family": "ALREADY_SELECTED_ACTION_SERIALIZATION",
        "ground_truth": expected,
    }


@pytest.mark.parametrize(
    "raw",
    (
        '{"action_label":"DIRECT_TEXT","payload":{"target_agent_id":"P7"}}',
        '{"action_label":"NOT_A_LABEL","payload":{}}',
        '{"payload":{"target_agent_id":"P7","body":"hello"}}',
        '["DIRECT_TEXT"]',
        "not-json",
    ),
)
def test_serialization_evaluator_rejects_schema_invalid_output(raw: str) -> None:
    expected = (
        '{"action_label":"DIRECT_TEXT","payload":'
        '{"body":"hello","target_agent_id":"P7"}}'
    )
    result = evaluate_foundation_serialization_text(
        _serialization_record(expected),
        raw,
    )
    assert result.schema_valid is False
    assert result.semantic_correct is False
    assert result.parse_error is not None


def test_serialization_evaluator_separates_schema_valid_from_semantic_correct() -> None:
    expected = (
        '{"action_label":"DIRECT_TEXT","payload":'
        '{"body":"hello","target_agent_id":"P7"}}'
    )
    wrong_but_valid = (
        '{"payload":{"target_agent_id":"P8","body":"hello"},'
        '"action_label":"DIRECT_TEXT"}'
    )
    result = evaluate_foundation_serialization_text(
        _serialization_record(expected),
        wrong_but_valid,
    )
    assert result.schema_valid is True
    assert result.semantic_correct is False
    assert result.canonical_output == (
        '{"action_label":"DIRECT_TEXT","payload":'
        '{"body":"hello","target_agent_id":"P8"}}'
    )


def test_serialization_evaluator_canonicalizes_key_order() -> None:
    expected = (
        '{"action_label":"DIRECT_TEXT","payload":'
        '{"body":"hello","target_agent_id":"P7"}}'
    )
    reordered = (
        '{"payload":{"target_agent_id":"P7","body":"hello"},'
        '"action_label":"DIRECT_TEXT"}'
    )
    result = evaluate_foundation_serialization_text(
        _serialization_record(expected),
        reordered,
    )
    assert result.schema_valid is True
    assert result.semantic_correct is True
    assert result.parse_error is None


def test_scalar_evaluation_artifact_is_deterministic() -> None:
    scores = (
        CandidateSequenceScore("INCOMING", (1,), -0.1, -0.1, 1),
        CandidateSequenceScore("OUTGOING", (2, 3), -0.8, -0.4, 2),
    )
    result = FoundationScalarEvaluation(
        example_id="F0-TEST-1",
        semantic_family="MESSAGE_DIRECTION",
        expected="INCOMING",
        predicted="INCOMING",
        exact_match=True,
        ranking_metric=FOUNDATION_RANKING_METRIC,
        prompt_hash="a" * 64,
        scores=scores,
    )
    first = foundation_evaluation_bytes(result)
    assert first == foundation_evaluation_bytes(result)
    document = json.loads(first)
    assert document["evaluator_id"] == FOUNDATION_EVALUATOR_ID
    assert document["ranking_metric"] == FOUNDATION_RANKING_METRIC
    assert document["scores"][0]["candidate"] == "INCOMING"


def test_serialization_result_rejects_semantic_correct_without_schema_valid() -> None:
    with pytest.raises(ValueError):
        FoundationSerializationEvaluation(
            example_id="F0-TEST-2",
            semantic_family="ALREADY_SELECTED_ACTION_SERIALIZATION",
            expected="{}",
            raw_model_output="{}",
            schema_valid=False,
            semantic_correct=True,
            canonical_output=None,
            parse_error="bad",
        )
