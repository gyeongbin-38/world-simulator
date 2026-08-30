from __future__ import annotations

import json

import pytest

from alifelm.model.foundation_sensor import (
    SENSOR_NORMALIZER_ID,
    SensorNormalizationError,
    deterministic_sensor_answer,
    normalize_foundation_visible_state,
    sensor_invariant_bytes,
)


def _state() -> dict:
    return {
        "self_handle": "A10",
        "peer_handles": ["P1", "P2"],
        "messages": [
            {
                "message_id": "M1",
                "sender": "P1",
                "receiver": "A10",
                "body": "X1",
            }
        ],
        "proposals": [
            {
                "proposal_id": "R1",
                "owner": "A10",
                "target": "P2",
            }
        ],
        "neutral_state_value": 7,
    }


def test_sensor_normalizer_derives_visible_peer_count_without_social_inference() -> None:
    normalized = normalize_foundation_visible_state(_state())
    assert normalized.self_handle == "A10"
    assert normalized.visible_peer_handles == ("P1", "P2")
    assert normalized.visible_peer_count == 2
    assert len(normalized.sensor_payload_hash) == 64


def test_sensor_normalizer_rejects_duplicate_peer_handles() -> None:
    state = _state()
    state["peer_handles"] = ["P1", "P1"]
    with pytest.raises(SensorNormalizationError):
        normalize_foundation_visible_state(state)


def test_sensor_normalizer_rejects_non_visible_message_endpoint() -> None:
    state = _state()
    state["messages"][0]["sender"] = "P999"
    with pytest.raises(SensorNormalizationError):
        normalize_foundation_visible_state(state)


def test_only_visible_peer_count_is_removed_from_neural_scoring_in_study_v1() -> None:
    count_record = {
        "example_id": "F0-X",
        "semantic_family": "VISIBLE_PEER_COUNT",
        "visible_state": _state(),
        "ground_truth": "2",
    }
    direction_record = {
        "example_id": "F0-Y",
        "semantic_family": "MESSAGE_DIRECTION",
        "visible_state": _state(),
        "ground_truth": "INCOMING",
    }
    assert deterministic_sensor_answer(count_record) == "2"
    assert deterministic_sensor_answer(direction_record) is None


def test_sensor_invariant_artifact_is_deterministic() -> None:
    record = {
        "example_id": "F0-X",
        "semantic_family": "VISIBLE_PEER_COUNT",
        "visible_state": _state(),
        "ground_truth": "2",
    }
    first = sensor_invariant_bytes(record)
    assert first == sensor_invariant_bytes(record)
    document = json.loads(first)
    assert document["normalizer_id"] == SENSOR_NORMALIZER_ID
    assert document["ground_truth_agrees"] is True
