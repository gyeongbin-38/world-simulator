"""Researcher-only I-05R4 selector and reference-grounding treatments."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Mapping

from alifelm.context import (
    DEFAULT_ACTION_PRESENTATION,
    CompiledContext,
    DeliveredMessagePayload,
    IncomingProposalPayload,
    ModelActionCandidate,
    ModelActionParser,
    ModelInput,
    OutgoingProposalPayload,
    PeerDirectoryEntry,
    ProtocolResolutionPayload,
    SentMessagePayload,
    VisibleRecord,
    VisibleRecordCategory,
    render_model_input_bytes,
)
from alifelm.domain import AgentId

from .evidence import ModelOutputStatus, classify_parse_failure
from .transformers_backend import GenerationError, TransformersModelRuntime
from .treatments import InterfaceMode, InterfaceTreatment
from .typed_codec import CodecValidityStatus


SELECTOR_CODES = ("Q", "V", "X", "Z", "K")
SELECTOR_PREFIX = b'\nSelector JSON:\n{"selector":"'
SELECTOR_TREATMENT_VERSION = "1.0.0"
GROUNDING_TREATMENT_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class SelectorCodebook:
    codebook_id: str
    action_to_code: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        actions = DEFAULT_ACTION_PRESENTATION.presentation_order
        mapping = dict(self.action_to_code)
        if tuple(action for action, _ in self.action_to_code) != actions:
            raise ValueError("codebook actions must use canonical presentation order")
        if set(mapping.values()) != set(SELECTOR_CODES):
            raise ValueError("codebook must use each opaque selector exactly once")

    @property
    def code_to_action(self) -> dict[str, str]:
        return {code: action for action, code in self.action_to_code}

    @property
    def digest(self) -> str:
        document = {
            "domain": "ALIFELM_I05R4_SELECTOR_CODEBOOK_V1",
            "codebook_id": self.codebook_id,
            "action_to_code": dict(self.action_to_code),
        }
        return hashlib.sha256(_json_bytes(document)).hexdigest()


def balanced_selector_codebooks() -> tuple[SelectorCodebook, ...]:
    """Five cyclic codebooks: every action occupies every selector once."""

    actions = DEFAULT_ACTION_PRESENTATION.presentation_order
    return tuple(
        SelectorCodebook(
            codebook_id=f"i05r4-balanced-{offset}",
            action_to_code=tuple(
                (action, SELECTOR_CODES[(index + offset) % len(SELECTOR_CODES)])
                for index, action in enumerate(actions)
            ),
        )
        for offset in range(len(SELECTOR_CODES))
    )


def selector_treatment(codebook: SelectorCodebook) -> InterfaceTreatment:
    return InterfaceTreatment(
        treatment_id=f"i05r4-i4-{codebook.codebook_id}",
        version=SELECTOR_TREATMENT_VERSION,
        mode=InterfaceMode.I4,
        completion_suffix=SELECTOR_PREFIX.decode("utf-8"),
        constraint_policy_id=f"i05r4-selector-{codebook.codebook_id}-v1",
    )


def render_selector_interface(compiled: CompiledContext, codebook: SelectorCodebook) -> bytes:
    """Replace action labels with opaque codes while preserving neutral mechanics."""

    baseline = compiled.rendered_input.decode("utf-8")
    marker = "\nActions:\n"
    if baseline.count(marker) != 1:
        raise ValueError("canonical action section is not uniquely identifiable")
    visible_state, _ = baseline.split(marker)
    mapping = dict(codebook.action_to_code)
    lines = [visible_state, "Actions:"]
    for action in DEFAULT_ACTION_PRESENTATION.presentation_order:
        entry = DEFAULT_ACTION_PRESENTATION.entry(action)
        fields = ",".join(entry.payload_fields) if entry.payload_fields else "none"
        lines.append(f"- {mapping[action]}: {entry.description} payload_fields={fields}")
    return "\n".join(lines).encode("utf-8")


def selector_codec_json_schema(codebook: SelectorCodebook) -> dict[str, Any]:
    mapping = dict(codebook.action_to_code)
    opaque = {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$"}
    fields = {
        "target_agent_id": opaque,
        "proposal_id": opaque,
        "body": {"type": "string"},
    }
    branches = []
    for action in DEFAULT_ACTION_PRESENTATION.presentation_order:
        entry = DEFAULT_ACTION_PRESENTATION.entry(action)
        branches.append({
            "type": "object",
            "additionalProperties": False,
            "required": ["selector", "payload"],
            "properties": {
                "selector": {"const": mapping[action]},
                "payload": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": list(entry.payload_fields),
                    "properties": {name: fields[name] for name in entry.payload_fields},
                },
            },
        })
    return {"oneOf": branches}


class SelectorCandidateParser(ModelActionParser):
    """Map an I4 selector to the unchanged canonical model candidate contract."""

    def __init__(self, codebook: SelectorCodebook) -> None:
        self.codebook = codebook

    def parse(self, value) -> ModelActionCandidate:
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        if isinstance(value, str):
            value = json.loads(value)
        if not isinstance(value, Mapping) or set(value) != {"selector", "payload"}:
            raise ValueError("selector output may contain only selector and payload")
        selector = value["selector"]
        payload = value["payload"]
        if not isinstance(selector, str) or selector not in self.codebook.code_to_action:
            raise ValueError("unknown opaque selector")
        if not isinstance(payload, Mapping) or any(
            not isinstance(key, str) or not isinstance(item, str)
            for key, item in payload.items()
        ):
            raise TypeError("selector payload must contain string fields")
        action = self.codebook.code_to_action[selector]
        label = DEFAULT_ACTION_PRESENTATION.entry(action).model_label
        return ModelActionCandidate(label, tuple(sorted(payload.items())))


@dataclass(frozen=True, slots=True)
class SelectorScore:
    selector: str
    mapped_action: str
    token_ids: tuple[int, ...]
    total_log_probability: float
    mean_log_probability: float
    rank: int

    def __post_init__(self) -> None:
        if self.selector not in SELECTOR_CODES or not self.token_ids:
            raise ValueError("invalid selector score")
        if not math.isfinite(self.total_log_probability) or not math.isfinite(self.mean_log_probability):
            raise ValueError("selector probabilities must be finite")


def score_selectors(
    runtime: TransformersModelRuntime,
    *,
    rendered_input: bytes,
    codebook: SelectorCodebook,
) -> tuple[SelectorScore, ...]:
    """Teacher-force complete selector sequences; never generate or act."""

    torch_module = runtime.torch_module
    if torch_module is None:
        raise GenerationError("selector scoring requires loaded PyTorch")
    prefix = rendered_input + SELECTOR_PREFIX
    encoded = runtime.tokenizer(
        prefix.decode("utf-8"), return_tensors="pt",
        add_special_tokens=runtime.profile.add_special_tokens,
    )
    input_ids = encoded["input_ids"]
    if runtime.profile.device != "auto" and hasattr(input_ids, "to"):
        input_ids = input_ids.to(runtime.profile.device)
    tokenized = {
        selector: tuple(runtime.tokenizer.encode(selector, add_special_tokens=False))
        for selector in codebook.code_to_action
    }
    if any(len(ids) != 1 for ids in tokenized.values()):
        raise GenerationError("I4 selectors must be single-token under the loaded tokenizer")
    context = torch_module.inference_mode() if hasattr(torch_module, "inference_mode") else nullcontext()
    with context:
        logits = runtime.model(input_ids=input_ids, attention_mask=torch_module.ones_like(input_ids)).logits[0, -1]
    logp = torch_module.log_softmax(logits, dim=-1)
    values = []
    for selector, action in codebook.code_to_action.items():
        ids = tokenized[selector]
        total = float(logp[ids[0]].detach().cpu())
        values.append((selector, action, ids, total))
    ordered = sorted(values, key=lambda item: (-item[3], item[0]))
    return tuple(
        SelectorScore(selector, action, ids, total, total / len(ids), rank)
        for rank, (selector, action, ids, total) in enumerate(ordered, 1)
    )


@dataclass(frozen=True, slots=True)
class GroundingHandleMap:
    peer_handles: tuple[tuple[str, str], ...]
    proposal_handles: tuple[tuple[str, str], ...]

    @property
    def handle_to_canonical(self) -> dict[str, str]:
        return {handle: canonical for canonical, handle in self.peer_handles + self.proposal_handles}


def _alias_record(record: VisibleRecord, peers: dict[str, str], proposals: dict[str, str]) -> VisibleRecord:
    payload = record.payload
    if isinstance(payload, DeliveredMessagePayload):
        aliased = DeliveredMessagePayload(AgentId(peers.get(str(payload.sender_id), str(payload.sender_id))), payload.body)
    elif isinstance(payload, SentMessagePayload):
        aliased = SentMessagePayload(AgentId(peers.get(str(payload.recipient_id), str(payload.recipient_id))), payload.body)
    elif isinstance(payload, IncomingProposalPayload):
        aliased = IncomingProposalPayload(proposals[payload.proposal_id], AgentId(peers.get(str(payload.proposer_id), str(payload.proposer_id))))
    elif isinstance(payload, OutgoingProposalPayload):
        aliased = OutgoingProposalPayload(proposals[payload.proposal_id], AgentId(peers.get(str(payload.target_id), str(payload.target_id))))
    elif isinstance(payload, ProtocolResolutionPayload):
        counterparty = None if payload.counterparty_id is None else AgentId(peers.get(str(payload.counterparty_id), str(payload.counterparty_id)))
        aliased = ProtocolResolutionPayload(proposals[payload.proposal_id], counterparty, payload.result)
    else:  # pragma: no cover - VisibleRecord guards the union
        raise TypeError("unsupported visible payload")
    return VisibleRecord(record.category, aliased)


def render_with_local_handles(compiled: CompiledContext) -> tuple[bytes, GroundingHandleMap]:
    """Render context-local aliases without changing ContextPack or canonical IDs."""

    source = compiled.context_pack.model_input
    peer_pairs = tuple((str(entry.agent_id), f"P{index}") for index, entry in enumerate(source.peer_directory))
    peer_map = dict(peer_pairs)
    proposal_ids = []
    for records in (source.newly_delivered, source.visible_protocol_state, source.prior_history):
        for record in records:
            proposal_id = getattr(record.payload, "proposal_id", None)
            if proposal_id is not None and proposal_id not in proposal_ids:
                proposal_ids.append(proposal_id)
    proposal_pairs = tuple((value, f"R{index}") for index, value in enumerate(proposal_ids))
    proposal_map = dict(proposal_pairs)
    aliased = ModelInput(
        stable_prefix=source.stable_prefix,
        current_self=source.current_self,
        peer_directory=tuple(PeerDirectoryEntry(AgentId(peer_map[str(item.agent_id)])) for item in source.peer_directory),
        newly_delivered=tuple(_alias_record(item, peer_map, proposal_map) for item in source.newly_delivered),
        visible_protocol_state=tuple(_alias_record(item, peer_map, proposal_map) for item in source.visible_protocol_state),
        prior_history=tuple(_alias_record(item, peer_map, proposal_map) for item in source.prior_history),
    )
    return render_model_input_bytes(aliased), GroundingHandleMap(peer_pairs, proposal_pairs)


def forced_grounding_schema(
    internal_action: str,
    *,
    pointer_values: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    entry = DEFAULT_ACTION_PRESENTATION.entry(internal_action)
    properties: dict[str, Any] = {}
    for field in entry.payload_fields:
        if field == "body":
            properties[field] = {"type": "string"}
        elif pointer_values is None:
            properties[field] = {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$"}
        else:
            properties[field] = {"type": "string", "enum": list(pointer_values)}
    return {
        "type": "object", "additionalProperties": False,
        "required": ["action_label", "payload"],
        "properties": {
            "action_label": {"const": entry.model_label},
            "payload": {"type": "object", "additionalProperties": False,
                        "required": list(entry.payload_fields), "properties": properties},
        },
    }


def map_handle_candidate(raw_text: str, handles: GroundingHandleMap) -> str:
    """Research-side alias resolution before the unchanged domain validator."""

    candidate = ModelActionParser().parse(raw_text)
    mapping = handles.handle_to_canonical
    payload = {key: mapping.get(value, value) for key, value in candidate.payload}
    return json.dumps({"action_label": candidate.action_label, "payload": payload}, sort_keys=True, separators=(",", ":"))


def codec_status_for_selector(raw_text: str, parser: SelectorCandidateParser) -> CodecValidityStatus:
    if not raw_text.strip():
        return CodecValidityStatus.EMPTY
    try:
        candidate = parser.parse(raw_text)
        entry = next(item for item in DEFAULT_ACTION_PRESENTATION.actions if item.model_label == candidate.action_label)
        return CodecValidityStatus.CODEC_VALID if set(candidate.payload_dict()) == set(entry.payload_fields) else CodecValidityStatus.ACTION_PAYLOAD_TYPE_MISMATCH
    except json.JSONDecodeError as error:
        status = classify_parse_failure(raw_text, error)
        return CodecValidityStatus.TRUNCATED if status is ModelOutputStatus.TRUNCATED else CodecValidityStatus.MALFORMED_SYNTAX
    except (TypeError, ValueError):
        return CodecValidityStatus.ACTION_PAYLOAD_TYPE_MISMATCH


def motor_diagnostic_bytes(document: Mapping[str, Any]) -> bytes:
    return _json_bytes({"artifact_kind": "I05R4_MOTOR_DIAGNOSTIC", "version": "1.0.0", **dict(document)})


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
