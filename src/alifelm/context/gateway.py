"""Bind model-visible action candidates to hidden opportunity identity."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from alifelm.domain import (
    AcceptAction,
    ActionIntent,
    ActionKind,
    AgentId,
    IntentId,
    ProposalId,
    ProposeAction,
    RejectAction,
    SendAction,
    WaitAction,
)
from alifelm.kernel.opportunities import CognitionOpportunity

from .serialization import canonical_bytes
from .types import ActionPresentation, DEFAULT_ACTION_PRESENTATION


@dataclass(frozen=True, slots=True)
class ModelActionCandidate:
    """Model-generated fields only: neutral label and immutable payload."""

    action_label: str
    payload: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.action_label, str) or not self.action_label:
            raise ValueError("action_label must be non-empty")
        if not isinstance(self.payload, tuple) or any(
            not isinstance(item, tuple)
            or len(item) != 2
            or not isinstance(item[0], str)
            or not isinstance(item[1], str)
            for item in self.payload
        ):
            raise TypeError("payload must be immutable string field/value pairs")
        keys = [key for key, _ in self.payload]
        if keys != sorted(keys) or len(keys) != len(set(keys)):
            raise ValueError("payload fields must be unique and key-sorted")

    def payload_dict(self) -> dict[str, str]:
        return dict(self.payload)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate model output field: {key}")
        result[key] = value
    return result


class ModelActionParser:
    """Strict parser for the neutral model-output contract."""

    def parse(
        self,
        value: ModelActionCandidate | Mapping[str, Any] | str | bytes,
    ) -> ModelActionCandidate:
        if isinstance(value, ModelActionCandidate):
            return value
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        if isinstance(value, str):
            value = json.loads(value, object_pairs_hook=_unique_object)
        if not isinstance(value, Mapping):
            raise TypeError("model output must be an object")
        if set(value) != {"action_label", "payload"}:
            raise ValueError("model output may contain only action_label and payload")
        payload = value["payload"]
        if not isinstance(payload, Mapping):
            raise TypeError("model output payload must be an object")
        pairs = tuple(sorted(payload.items()))
        return ModelActionCandidate(action_label=value["action_label"], payload=pairs)


class CognitionGateway:
    """Create ActionIntent identity from the bound opportunity, never the model."""

    def __init__(
        self,
        presentation: ActionPresentation = DEFAULT_ACTION_PRESENTATION,
        parser: ModelActionParser | None = None,
    ) -> None:
        self.presentation = presentation
        self.parser = parser or ModelActionParser()

    def bind(
        self,
        model_output: ModelActionCandidate | Mapping[str, Any] | str | bytes,
        opportunity: CognitionOpportunity,
    ) -> ActionIntent:
        if not isinstance(opportunity, CognitionOpportunity):
            raise TypeError("opportunity must be a CognitionOpportunity")
        candidate = self.parser.parse(model_output)
        matching = tuple(
            entry
            for entry in self.presentation.actions
            if entry.model_label == candidate.action_label
        )
        if len(matching) != 1:
            raise ValueError("unknown neutral action label")
        entry = matching[0]
        payload = candidate.payload_dict()
        if set(payload) != set(entry.payload_fields):
            raise ValueError("action payload fields do not match the contract")

        if entry.internal_action == "WAIT":
            kind, typed_payload = ActionKind.WAIT, WaitAction()
        elif entry.internal_action == "SEND":
            kind = ActionKind.SEND
            typed_payload = SendAction(AgentId(payload["target_agent_id"]), payload["body"])
        elif entry.internal_action == "PROPOSE":
            kind = ActionKind.PROPOSE
            typed_payload = ProposeAction(AgentId(payload["target_agent_id"]))
        elif entry.internal_action == "ACCEPT":
            kind = ActionKind.ACCEPT
            typed_payload = AcceptAction(ProposalId(payload["proposal_id"]))
        else:
            kind = ActionKind.REJECT
            typed_payload = RejectAction(ProposalId(payload["proposal_id"]))

        identity_material = {
            "domain": "ALIFELM_COGNITION_GATEWAY_V1",
            "run_id": opportunity.run_id.value,
            "opportunity_id": opportunity.opportunity_id.value,
            "actor_id": opportunity.agent_id.value,
            "tick": int(opportunity.tick),
            "action_label": candidate.action_label,
            "payload": payload,
        }
        intent_id = IntentId(hashlib.sha256(canonical_bytes(identity_material)).hexdigest())
        return ActionIntent(
            intent_id=intent_id,
            actor_id=opportunity.agent_id,
            tick=opportunity.tick,
            kind=kind,
            payload=typed_payload,
        )

