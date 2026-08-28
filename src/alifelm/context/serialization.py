"""Canonical ContextPack representation, bytes, and identity hashing."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from alifelm.domain import (
    AgentId,
    ArtifactId,
    ArtifactRef,
    OpportunityId,
    RunId,
)

from .types import (
    ActionPresentation,
    CacheTelemetry,
    ContextEvidence,
    ContextPack,
    ContextPolicy,
    CurrentSelf,
    DeliveredMessagePayload,
    InfrastructureMetadata,
    IncomingProposalPayload,
    ModelInput,
    OutgoingProposalPayload,
    PeerDirectoryEntry,
    ProjectionKind,
    ProtocolResolutionPayload,
    ProtocolResolutionResult,
    Provenance,
    SentMessagePayload,
    SourceKind,
    StablePrefix,
    VisibleRecord,
    VisibleRecordCategory,
    VisibleRecordCounts,
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def artifact_ref_to_dict(reference: ArtifactRef) -> dict[str, str]:
    return {"artifact_id": reference.artifact_id.value, "digest": reference.digest}


def policy_to_dict(policy: ContextPolicy) -> dict[str, Any]:
    return {
        "policy_id": policy.policy_id,
        "version": policy.version,
        "context_schema_version": policy.context_schema_version,
        "visibility": {
            name: getattr(policy.visibility, name)
            for name in policy.visibility.__dataclass_fields__
        },
        "history": {
            name: getattr(policy.history, name)
            for name in policy.history.__dataclass_fields__
        },
        "ordering": {
            name: getattr(policy.ordering, name)
            for name in policy.ordering.__dataclass_fields__
        },
        "recall": {
            name: getattr(policy.recall, name)
            for name in policy.recall.__dataclass_fields__
        },
        "canonicalization": {
            name: getattr(policy.canonicalization, name)
            for name in policy.canonicalization.__dataclass_fields__
        },
        "action_presentation": {
            name: getattr(policy.action_presentation, name)
            for name in policy.action_presentation.__dataclass_fields__
        },
    }


def context_policy_digest(policy: ContextPolicy) -> str:
    return canonical_digest(policy_to_dict(policy))


def action_presentation_to_dict(presentation: ActionPresentation) -> dict[str, Any]:
    return {
        "policy_id": presentation.policy_id,
        "version": presentation.version,
        "output_contract_id": presentation.output_contract_id,
        "model_supplied_fields": list(presentation.model_supplied_fields),
        "gateway_supplied_fields": list(presentation.gateway_supplied_fields),
        "one_primary_action_per_opportunity": (
            presentation.one_primary_action_per_opportunity
        ),
        "presentation_order": list(presentation.presentation_order),
        "actions": {
            entry.internal_action: {
                "model_label": entry.model_label,
                "description": entry.description,
                "payload_fields": list(entry.payload_fields),
            }
            for entry in presentation.actions
        },
    }


def action_presentation_digest(presentation: ActionPresentation) -> str:
    return canonical_digest(action_presentation_to_dict(presentation))


def visible_record_to_dict(record: VisibleRecord) -> dict[str, Any]:
    payload = record.payload
    if isinstance(payload, DeliveredMessagePayload):
        value = {"sender_id": payload.sender_id.value, "body": payload.body}
    elif isinstance(payload, SentMessagePayload):
        value = {"recipient_id": payload.recipient_id.value, "body": payload.body}
    elif isinstance(payload, IncomingProposalPayload):
        value = {
            "proposal_id": payload.proposal_id,
            "proposer_id": payload.proposer_id.value,
            "state": payload.state,
        }
    elif isinstance(payload, OutgoingProposalPayload):
        value = {
            "proposal_id": payload.proposal_id,
            "target_id": payload.target_id.value,
            "state": payload.state,
        }
    else:
        assert isinstance(payload, ProtocolResolutionPayload)
        value = {
            "proposal_id": payload.proposal_id,
            "counterparty_id": (
                payload.counterparty_id.value
                if payload.counterparty_id is not None
                else None
            ),
            "result": payload.result.value,
        }
    return {"category": record.category.value, "payload": value}


def model_input_to_dict(model_input: ModelInput) -> dict[str, Any]:
    return {
        "stable_prefix": {
            "mechanics_profile_id": model_input.stable_prefix.mechanics_profile_id,
            "action_presentation_policy_id": (
                model_input.stable_prefix.action_presentation_policy_id
            ),
            "action_presentation_version": (
                model_input.stable_prefix.action_presentation_version
            ),
        },
        "current_self": {
            "agent_id": model_input.current_self.agent_id.value,
            "age": model_input.current_self.age,
        },
        "peer_directory": [
            {"agent_id": entry.agent_id.value}
            for entry in model_input.peer_directory
        ],
        "newly_delivered": [
            visible_record_to_dict(record) for record in model_input.newly_delivered
        ],
        "visible_protocol_state": [
            visible_record_to_dict(record)
            for record in model_input.visible_protocol_state
        ],
        "prior_history": [
            visible_record_to_dict(record) for record in model_input.prior_history
        ],
    }


def provenance_to_dict(provenance: Provenance) -> dict[str, Any]:
    return {
        "model_path": provenance.model_path,
        "projection_kind": provenance.projection_kind.value,
        "source_kind": provenance.source_kind.value,
        "source_id": provenance.source_id,
        "source_state_version": provenance.source_state_version,
        "commit_id": provenance.commit_id,
        "commit_tick": provenance.commit_tick,
        "commit_order": provenance.commit_order,
        "artifact_refs": [artifact_ref_to_dict(ref) for ref in provenance.artifact_refs],
    }


def evidence_to_dict(evidence: ContextEvidence) -> dict[str, Any]:
    return {
        "run_id": evidence.run_id.value,
        "opportunity_id": evidence.opportunity_id.value,
        "agent_id": evidence.agent_id.value,
        "bound_tick": evidence.bound_tick,
        "bound_state_version": evidence.bound_state_version,
        "bound_state_hash": evidence.bound_state_hash,
        "context_policy_id": evidence.context_policy_id,
        "context_policy_version": evidence.context_policy_version,
        "context_policy_digest": evidence.context_policy_digest,
        "visibility_policy_version": evidence.visibility_policy_version,
        "ordering_policy_version": evidence.ordering_policy_version,
        "ordering_seed_id": evidence.ordering_seed_id,
        "ordering_seed_digest": evidence.ordering_seed_digest,
        "action_presentation_policy_id": evidence.action_presentation_policy_id,
        "action_presentation_version": evidence.action_presentation_version,
        "action_presentation_digest": evidence.action_presentation_digest,
        "provenance": [provenance_to_dict(item) for item in evidence.provenance],
        "artifact_refs": [artifact_ref_to_dict(ref) for ref in evidence.artifact_refs],
    }


def infrastructure_to_dict(infrastructure: InfrastructureMetadata) -> dict[str, Any]:
    cache = infrastructure.cache_telemetry
    return {
        "model_profile_id": infrastructure.model_profile_id,
        "generation_policy_id": infrastructure.generation_policy_id,
        "generation_seed_id": infrastructure.generation_seed_id,
        "visible_record_counts": {
            "peers": infrastructure.visible_record_counts.peers,
            "newly_delivered": (
                infrastructure.visible_record_counts.newly_delivered
            ),
            "visible_protocol_state": (
                infrastructure.visible_record_counts.visible_protocol_state
            ),
            "prior_history": infrastructure.visible_record_counts.prior_history,
        },
        "tokenizer_profile_id": infrastructure.tokenizer_profile_id,
        "rendered_input_token_count": infrastructure.rendered_input_token_count,
        "cache_telemetry": (
            {"cache_profile_id": cache.cache_profile_id, "hit": cache.hit}
            if cache is not None
            else None
        ),
    }


def context_identity_dict(
    schema_version: str,
    model_input: ModelInput,
    evidence: ContextEvidence,
) -> dict[str, Any]:
    return {
        "identity_policy": "ALIFELM_CONTEXT_CANONICAL_JSON_V1",
        "schema_version": schema_version,
        "model_input": model_input_to_dict(model_input),
        "evidence": evidence_to_dict(evidence),
    }


def compute_context_hash(
    schema_version: str,
    model_input: ModelInput,
    evidence: ContextEvidence,
) -> str:
    return canonical_digest(context_identity_dict(schema_version, model_input, evidence))


def finalize_context_pack(
    model_input: ModelInput,
    evidence: ContextEvidence,
    infrastructure: InfrastructureMetadata,
) -> ContextPack:
    digest = compute_context_hash("1.0.0", model_input, evidence)
    return ContextPack(
        context_pack_id=f"context-{digest}",
        schema_version="1.0.0",
        context_hash=digest,
        model_input=model_input,
        evidence=evidence,
        infrastructure=infrastructure,
    )


def context_pack_to_dict(pack: ContextPack) -> dict[str, Any]:
    return {
        "context_pack_id": pack.context_pack_id,
        "schema_version": pack.schema_version,
        "context_hash": pack.context_hash,
        "model_input": model_input_to_dict(pack.model_input),
        "evidence": evidence_to_dict(pack.evidence),
        "infrastructure": infrastructure_to_dict(pack.infrastructure),
    }


def serialize_context_pack(pack: ContextPack) -> bytes:
    expected = compute_context_hash(pack.schema_version, pack.model_input, pack.evidence)
    if pack.context_hash != expected or pack.context_pack_id != f"context-{expected}":
        raise ValueError("ContextPack identity does not match its canonical content")
    return canonical_bytes(context_pack_to_dict(pack))


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _artifact_ref(value: dict[str, Any]) -> ArtifactRef:
    return ArtifactRef(ArtifactId(value["artifact_id"]), value["digest"])


def _visible_record(value: dict[str, Any]) -> VisibleRecord:
    category = VisibleRecordCategory(value["category"])
    payload = value["payload"]
    if category is VisibleRecordCategory.DELIVERED_MESSAGE:
        typed = DeliveredMessagePayload(AgentId(payload["sender_id"]), payload["body"])
    elif category is VisibleRecordCategory.SENT_MESSAGE:
        typed = SentMessagePayload(AgentId(payload["recipient_id"]), payload["body"])
    elif category is VisibleRecordCategory.INCOMING_PROPOSAL:
        typed = IncomingProposalPayload(
            payload["proposal_id"], AgentId(payload["proposer_id"]), payload["state"]
        )
    elif category is VisibleRecordCategory.OUTGOING_PROPOSAL:
        typed = OutgoingProposalPayload(
            payload["proposal_id"], AgentId(payload["target_id"]), payload["state"]
        )
    else:
        counterparty = payload["counterparty_id"]
        typed = ProtocolResolutionPayload(
            payload["proposal_id"],
            AgentId(counterparty) if counterparty is not None else None,
            ProtocolResolutionResult(payload["result"]),
        )
    return VisibleRecord(category, typed)


def _model_input(value: dict[str, Any]) -> ModelInput:
    stable = value["stable_prefix"]
    current = value["current_self"]
    return ModelInput(
        stable_prefix=StablePrefix(**stable),
        current_self=CurrentSelf(AgentId(current["agent_id"]), current["age"]),
        peer_directory=tuple(
            PeerDirectoryEntry(AgentId(entry["agent_id"]))
            for entry in value["peer_directory"]
        ),
        newly_delivered=tuple(_visible_record(item) for item in value["newly_delivered"]),
        visible_protocol_state=tuple(
            _visible_record(item) for item in value["visible_protocol_state"]
        ),
        prior_history=tuple(_visible_record(item) for item in value["prior_history"]),
    )


def _evidence(value: dict[str, Any]) -> ContextEvidence:
    provenance = tuple(
        Provenance(
            model_path=item["model_path"],
            projection_kind=ProjectionKind(item["projection_kind"]),
            source_kind=SourceKind(item["source_kind"]),
            source_id=item["source_id"],
            source_state_version=item["source_state_version"],
            commit_id=item["commit_id"],
            commit_tick=item["commit_tick"],
            commit_order=item["commit_order"],
            artifact_refs=tuple(_artifact_ref(ref) for ref in item["artifact_refs"]),
        )
        for item in value["provenance"]
    )
    return ContextEvidence(
        run_id=RunId(value["run_id"]),
        opportunity_id=OpportunityId(value["opportunity_id"]),
        agent_id=AgentId(value["agent_id"]),
        bound_tick=value["bound_tick"],
        bound_state_version=value["bound_state_version"],
        bound_state_hash=value["bound_state_hash"],
        context_policy_id=value["context_policy_id"],
        context_policy_version=value["context_policy_version"],
        context_policy_digest=value["context_policy_digest"],
        visibility_policy_version=value["visibility_policy_version"],
        ordering_policy_version=value["ordering_policy_version"],
        ordering_seed_id=value["ordering_seed_id"],
        ordering_seed_digest=value["ordering_seed_digest"],
        action_presentation_policy_id=value["action_presentation_policy_id"],
        action_presentation_version=value["action_presentation_version"],
        action_presentation_digest=value["action_presentation_digest"],
        provenance=provenance,
        artifact_refs=tuple(_artifact_ref(ref) for ref in value["artifact_refs"]),
    )


def _infrastructure(value: dict[str, Any]) -> InfrastructureMetadata:
    counts = value["visible_record_counts"]
    cache = value["cache_telemetry"]
    return InfrastructureMetadata(
        model_profile_id=value["model_profile_id"],
        generation_policy_id=value["generation_policy_id"],
        generation_seed_id=value["generation_seed_id"],
        visible_record_counts=VisibleRecordCounts(**counts),
        tokenizer_profile_id=value["tokenizer_profile_id"],
        rendered_input_token_count=value["rendered_input_token_count"],
        cache_telemetry=(CacheTelemetry(**cache) if cache is not None else None),
    )


def deserialize_context_pack(data: bytes) -> ContextPack:
    if not isinstance(data, bytes):
        raise TypeError("ContextPack data must be bytes")
    value = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
    pack = ContextPack(
        context_pack_id=value["context_pack_id"],
        schema_version=value["schema_version"],
        context_hash=value["context_hash"],
        model_input=_model_input(value["model_input"]),
        evidence=_evidence(value["evidence"]),
        infrastructure=_infrastructure(value["infrastructure"]),
    )
    if serialize_context_pack(pack) != data:
        raise ValueError("ContextPack bytes are not canonical")
    return pack

