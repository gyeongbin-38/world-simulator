"""Researcher-only deterministic sensor normalization for F0.

This module is an experiment/evaluation utility. It does not modify ContextPack,
canonical WORLD state, or EXP-000 agent-visible runtime information. Its first
purpose is to separate deterministic observables from neural grounding metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from .foundation_data import SemanticFamily, canonical_json


SENSOR_NORMALIZER_ID = "F0_SENSOR_NORMALIZER_V1"
SENSOR_NORMALIZER_VERSION = "1.0.0"


class SensorNormalizationError(ValueError):
    """A visible-state record violates the deterministic F0 sensor contract."""


@dataclass(frozen=True, slots=True)
class NormalizedMessage:
    message_id: str
    sender: str
    receiver: str
    body: str


@dataclass(frozen=True, slots=True)
class NormalizedProposal:
    proposal_id: str
    owner: str
    target: str


@dataclass(frozen=True, slots=True)
class NormalizedFoundationSensorState:
    self_handle: str
    visible_peer_handles: tuple[str, ...]
    visible_peer_count: int
    messages: tuple[NormalizedMessage, ...]
    proposals: tuple[NormalizedProposal, ...]
    neutral_state_value: int
    sensor_payload_hash: str

    def __post_init__(self) -> None:
        if self.visible_peer_count != len(self.visible_peer_handles):
            raise SensorNormalizationError(
                "visible_peer_count does not match peer handles"
            )
        if len(self.sensor_payload_hash) != 64 or any(
            value not in "0123456789abcdef" for value in self.sensor_payload_hash
        ):
            raise SensorNormalizationError(
                "sensor_payload_hash must be a lowercase SHA-256 digest"
            )


def _required_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise SensorNormalizationError(f"{field_name} must be a non-empty string")
    return value


def _sequence(value: Any, field_name: str) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)):
        raise SensorNormalizationError(f"{field_name} must be a sequence")
    return tuple(value)


def _unique(values: tuple[str, ...], field_name: str) -> None:
    if len(values) != len(set(values)):
        raise SensorNormalizationError(f"{field_name} must not contain duplicates")


def _payload(
    *,
    self_handle: str,
    peer_handles: tuple[str, ...],
    messages: tuple[NormalizedMessage, ...],
    proposals: tuple[NormalizedProposal, ...],
    neutral_state_value: int,
) -> dict[str, Any]:
    return {
        "normalizer_id": SENSOR_NORMALIZER_ID,
        "normalizer_version": SENSOR_NORMALIZER_VERSION,
        "self_handle": self_handle,
        "visible_peer_handles": list(peer_handles),
        "visible_peer_count": len(peer_handles),
        "messages": [
            {
                "message_id": message.message_id,
                "sender": message.sender,
                "receiver": message.receiver,
                "body": message.body,
            }
            for message in messages
        ],
        "proposals": [
            {
                "proposal_id": proposal.proposal_id,
                "owner": proposal.owner,
                "target": proposal.target,
            }
            for proposal in proposals
        ],
        "neutral_state_value": neutral_state_value,
    }


def normalize_foundation_visible_state(
    visible_state: Mapping[str, Any],
) -> NormalizedFoundationSensorState:
    """Validate and normalize one frozen F0 visible-state object.

    Source ordering is preserved. The normalizer derives only deterministic
    observables; it does not infer directions, social meaning, or action policy.
    """

    if not isinstance(visible_state, Mapping):
        raise SensorNormalizationError("visible_state must be a mapping")

    required = {
        "self_handle",
        "peer_handles",
        "messages",
        "proposals",
        "neutral_state_value",
    }
    if set(visible_state) != required:
        raise SensorNormalizationError(
            "visible_state must contain exactly the frozen F0 sensor fields"
        )

    self_handle = _required_string(visible_state["self_handle"], "self_handle")
    peer_handles = tuple(
        _required_string(value, "peer_handle")
        for value in _sequence(visible_state["peer_handles"], "peer_handles")
    )
    _unique(peer_handles, "peer_handles")
    if self_handle in peer_handles:
        raise SensorNormalizationError("self_handle must not appear in peer_handles")

    visible_handles = {self_handle, *peer_handles}

    messages: list[NormalizedMessage] = []
    message_ids: list[str] = []
    for raw in _sequence(visible_state["messages"], "messages"):
        if not isinstance(raw, Mapping) or set(raw) != {
            "message_id",
            "sender",
            "receiver",
            "body",
        }:
            raise SensorNormalizationError("message record has invalid fields")
        message = NormalizedMessage(
            message_id=_required_string(raw["message_id"], "message_id"),
            sender=_required_string(raw["sender"], "message.sender"),
            receiver=_required_string(raw["receiver"], "message.receiver"),
            body=_required_string(raw["body"], "message.body"),
        )
        if (
            message.sender not in visible_handles
            or message.receiver not in visible_handles
        ):
            raise SensorNormalizationError(
                f"message {message.message_id} references a non-visible endpoint"
            )
        message_ids.append(message.message_id)
        messages.append(message)
    _unique(tuple(message_ids), "message_ids")

    proposals: list[NormalizedProposal] = []
    proposal_ids: list[str] = []
    for raw in _sequence(visible_state["proposals"], "proposals"):
        if not isinstance(raw, Mapping) or set(raw) != {
            "proposal_id",
            "owner",
            "target",
        }:
            raise SensorNormalizationError("proposal record has invalid fields")
        proposal = NormalizedProposal(
            proposal_id=_required_string(raw["proposal_id"], "proposal_id"),
            owner=_required_string(raw["owner"], "proposal.owner"),
            target=_required_string(raw["target"], "proposal.target"),
        )
        if (
            proposal.owner not in visible_handles
            or proposal.target not in visible_handles
        ):
            raise SensorNormalizationError(
                f"proposal {proposal.proposal_id} references a non-visible endpoint"
            )
        proposal_ids.append(proposal.proposal_id)
        proposals.append(proposal)
    _unique(tuple(proposal_ids), "proposal_ids")

    neutral_state_value = visible_state["neutral_state_value"]
    if type(neutral_state_value) is not int:
        raise SensorNormalizationError("neutral_state_value must be an integer")

    message_tuple = tuple(messages)
    proposal_tuple = tuple(proposals)
    payload = _payload(
        self_handle=self_handle,
        peer_handles=peer_handles,
        messages=message_tuple,
        proposals=proposal_tuple,
        neutral_state_value=neutral_state_value,
    )
    payload_hash = hashlib.sha256(
        canonical_json(payload).encode("utf-8")
    ).hexdigest()
    return NormalizedFoundationSensorState(
        self_handle=self_handle,
        visible_peer_handles=peer_handles,
        visible_peer_count=len(peer_handles),
        messages=message_tuple,
        proposals=proposal_tuple,
        neutral_state_value=neutral_state_value,
        sensor_payload_hash=payload_hash,
    )


def normalize_foundation_record(
    record: Mapping[str, Any],
) -> NormalizedFoundationSensorState:
    if "visible_state" not in record:
        raise SensorNormalizationError("F0 record does not contain visible_state")
    state = record["visible_state"]
    if not isinstance(state, Mapping):
        raise SensorNormalizationError("record visible_state must be a mapping")
    return normalize_foundation_visible_state(state)


def deterministic_sensor_answer(record: Mapping[str, Any]) -> str | None:
    """Return only answers owned entirely by deterministic sensor derivation.

    At Study v1, VISIBLE_PEER_COUNT is the sole neural-scoring exclusion. Other
    visible facts remain neural grounding tasks even though their raw fields are
    validated by this normalizer.
    """

    family = SemanticFamily(str(record["semantic_family"]))
    if family is SemanticFamily.VISIBLE_PEER_COUNT:
        return str(normalize_foundation_record(record).visible_peer_count)
    return None


def sensor_invariant_document(record: Mapping[str, Any]) -> dict[str, Any]:
    normalized = normalize_foundation_record(record)
    deterministic_answer = deterministic_sensor_answer(record)
    ground_truth = str(record.get("ground_truth", ""))
    return {
        "normalizer_id": SENSOR_NORMALIZER_ID,
        "normalizer_version": SENSOR_NORMALIZER_VERSION,
        "example_id": str(record.get("example_id", "")),
        "semantic_family": str(record["semantic_family"]),
        "sensor_payload_hash": normalized.sensor_payload_hash,
        "visible_peer_count": normalized.visible_peer_count,
        "deterministic_answer": deterministic_answer,
        "ground_truth_agrees": (
            None
            if deterministic_answer is None
            else deterministic_answer == ground_truth
        ),
    }


def sensor_invariant_bytes(record: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            sensor_invariant_document(record),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
