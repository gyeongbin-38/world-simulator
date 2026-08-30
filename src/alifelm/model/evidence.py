"""Research-side evidence for one real cognition dry run.

The values in this module are immutable ARTIFACT/PROTOCOL evidence.  They do
not become simulation state and the dry-run path never invokes a commit
coordinator.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
from typing import Any

from alifelm.context import (
    CognitionGateway,
    CompiledContext,
    ModelActionCandidate,
    ModelActionParser,
    serialize_context_pack,
)
from alifelm.domain import ActionIntent, ArtifactRef
from alifelm.persistence import ArtifactStore

from .adapter import (
    ModelRuntime,
    generation_request_for,
    validate_raw_generation_result,
)
from .generation import GenerationPolicy, GenerationRequest, RawGenerationResult
from .profile import ModelProfile
from .treatments import I0_STRICT_FREE_GENERATION, InterfaceTreatment


class ModelOutputStatus(StrEnum):
    VALID = "VALID"
    MALFORMED_SYNTAX = "MALFORMED_SYNTAX"
    UNKNOWN_ACTION = "UNKNOWN_ACTION"
    INVALID_PAYLOAD = "INVALID_PAYLOAD"
    EXTRA_FORBIDDEN_FIELD = "EXTRA_FORBIDDEN_FIELD"
    TRUNCATED = "TRUNCATED"
    EMPTY = "EMPTY"
    BACKEND_FAILURE = "BACKEND_FAILURE"
    DOMAIN_REJECTED = "DOMAIN_REJECTED"


@dataclass(frozen=True, slots=True)
class RejectedModelOutput:
    generation_id: str
    status: ModelOutputStatus
    error_type: str
    error_message: str


@dataclass(frozen=True, slots=True)
class CognitionEvidence:
    generation_id: str
    context_hash: str
    rendered_input_hash: str
    interface_treatment_id: str
    interface_treatment_version: str
    interface_treatment_digest: str
    constraint_policy_id: str | None
    context_pack_ref: ArtifactRef
    rendered_input_ref: ArtifactRef
    raw_text_ref: ArtifactRef
    raw_generation_ref: ArtifactRef
    model_profile_id: str
    model_revision: str | None
    tokenizer_identifier: str
    tokenizer_revision: str | None
    generation_policy_id: str
    generation_policy_version: str
    generation_seed_id: str
    generation_seed: int | None
    parse_status: ModelOutputStatus
    candidate: ModelActionCandidate | None
    action_intent: ActionIntent | None
    rejection: RejectedModelOutput | None


@dataclass(frozen=True, slots=True)
class CognitionDryRunResult:
    raw_generation: RawGenerationResult
    evidence: CognitionEvidence
    evidence_ref: ArtifactRef


@dataclass(frozen=True, slots=True)
class CognitionEvidencePreparation:
    """Durable raw evidence and parsed candidate, before Gateway binding."""

    request: GenerationRequest
    raw_generation: RawGenerationResult
    context_pack_ref: ArtifactRef
    rendered_input_ref: ArtifactRef
    raw_text_ref: ArtifactRef
    raw_generation_ref: ArtifactRef
    parse_status: ModelOutputStatus
    candidate: ModelActionCandidate | None
    rejection: RejectedModelOutput | None


def _artifact_ref_dict(reference: ArtifactRef) -> dict[str, str]:
    return {
        "artifact_id": reference.artifact_id.value,
        "digest": reference.digest,
    }


def _candidate_dict(candidate: ModelActionCandidate | None) -> dict[str, Any] | None:
    if candidate is None:
        return None
    return {
        "action_label": candidate.action_label,
        "payload": dict(candidate.payload),
    }


def _intent_dict(intent: ActionIntent | None) -> dict[str, Any] | None:
    if intent is None:
        return None
    payload = intent.payload
    values = {
        name: getattr(payload, name).value
        if hasattr(getattr(payload, name), "value")
        else getattr(payload, name)
        for name in getattr(payload, "__dataclass_fields__", {})
    }
    return {
        "intent_id": intent.intent_id.value,
        "actor_id": intent.actor_id.value,
        "tick": int(intent.tick),
        "kind": intent.kind.value,
        "payload": values,
    }


def raw_generation_bytes(result: RawGenerationResult) -> bytes:
    value = {
        "opportunity_id": result.opportunity_id.value,
        "generation_id": result.generation_id,
        "context_pack_id": result.context_pack_id,
        "context_hash": result.context_hash,
        "rendered_input_hash": result.rendered_input_hash,
        "interface_treatment_id": result.interface_treatment_id,
        "interface_treatment_version": result.interface_treatment_version,
        "interface_treatment_digest": result.interface_treatment_digest,
        "constraint_policy_id": result.constraint_policy_id,
        "raw_text": result.raw_text,
        "token_ids": list(result.token_ids) if result.token_ids is not None else None,
        "model_profile_id": result.model_profile_id,
        "generation_policy_id": result.generation_policy_id,
        "generation_policy_version": result.generation_policy_version,
        "generation_seed_id": result.generation_seed_id,
        "generation_seed": result.generation_seed,
        "finish_reason": result.finish_reason,
    }
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def cognition_evidence_bytes(evidence: CognitionEvidence) -> bytes:
    rejection = evidence.rejection
    value = {
        "generation_id": evidence.generation_id,
        "context_hash": evidence.context_hash,
        "rendered_input_hash": evidence.rendered_input_hash,
        "interface_treatment_id": evidence.interface_treatment_id,
        "interface_treatment_version": evidence.interface_treatment_version,
        "interface_treatment_digest": evidence.interface_treatment_digest,
        "constraint_policy_id": evidence.constraint_policy_id,
        "context_pack_ref": _artifact_ref_dict(evidence.context_pack_ref),
        "rendered_input_ref": _artifact_ref_dict(evidence.rendered_input_ref),
        "raw_text_ref": _artifact_ref_dict(evidence.raw_text_ref),
        "raw_generation_ref": _artifact_ref_dict(evidence.raw_generation_ref),
        "model_profile_id": evidence.model_profile_id,
        "model_revision": evidence.model_revision,
        "tokenizer_identifier": evidence.tokenizer_identifier,
        "tokenizer_revision": evidence.tokenizer_revision,
        "generation_policy_id": evidence.generation_policy_id,
        "generation_policy_version": evidence.generation_policy_version,
        "generation_seed_id": evidence.generation_seed_id,
        "generation_seed": evidence.generation_seed,
        "parse_status": evidence.parse_status.value,
        "candidate": _candidate_dict(evidence.candidate),
        "action_intent": _intent_dict(evidence.action_intent),
        "rejection": (
            {
                "generation_id": rejection.generation_id,
                "status": rejection.status.value,
                "error_type": rejection.error_type,
                "error_message": rejection.error_message,
            }
            if rejection is not None
            else None
        ),
    }
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def classify_parse_failure(raw_text: str, error: Exception) -> ModelOutputStatus:
    stripped = raw_text.strip()
    if not stripped:
        return ModelOutputStatus.EMPTY
    if isinstance(error, json.JSONDecodeError):
        if stripped.startswith("{") and (
            not stripped.endswith("}")
            or error.pos >= max(0, len(stripped) - 1)
            or "unterminated" in error.msg.lower()
        ):
            return ModelOutputStatus.TRUNCATED
        return ModelOutputStatus.MALFORMED_SYNTAX
    message = str(error).lower()
    if "only action_label and payload" in message or "duplicate model output field" in message:
        return ModelOutputStatus.EXTRA_FORBIDDEN_FIELD
    if "unknown neutral action label" in message:
        return ModelOutputStatus.UNKNOWN_ACTION
    if "payload" in message or "model output" in message:
        return ModelOutputStatus.INVALID_PAYLOAD
    return ModelOutputStatus.MALFORMED_SYNTAX


def prepare_cognition_evidence(
    compiled: CompiledContext,
    runtime: ModelRuntime,
    profile: ModelProfile,
    generation_policy: GenerationPolicy,
    artifact_store: ArtifactStore,
    *,
    generation_seed: int | None = None,
    parser: ModelActionParser | None = None,
    interface_treatment: InterfaceTreatment = I0_STRICT_FREE_GENERATION,
    prefix_allowed_tokens_fn=None,
) -> CognitionEvidencePreparation:
    """Generate once, durably store raw evidence, then parse.

    No Gateway binding occurs here; the caller remains the sole identity
    authority and can finalize evidence after binding exactly once.
    """

    snapshot_hash = compiled.opportunity.snapshot.state_hash()
    context_bytes = serialize_context_pack(compiled.context_pack)
    if compiled.artifact_ref is None:
        context_ref = artifact_store.put_bytes(
            context_bytes,
            media_type="application/json",
            contract_id="context-pack-1.0.0",
        )
    else:
        context_ref = compiled.artifact_ref
        if artifact_store.resolve(context_ref) != context_bytes:
            raise ValueError("ContextPack artifact does not match compiled bytes")

    request = generation_request_for(
        compiled,
        profile,
        generation_policy,
        generation_seed=generation_seed,
        interface_treatment=interface_treatment,
        prefix_allowed_tokens_fn=prefix_allowed_tokens_fn,
    )
    rendered_ref = artifact_store.put_bytes(
        request.rendered_input,
        media_type="text/plain; charset=utf-8",
        contract_id="rendered-model-input-1.0.0",
    )
    raw = runtime.generate(request)
    validate_raw_generation_result(request, raw, profile, generation_policy)

    # ARC-270: both raw artifacts are durable before parsing.
    raw_text_ref = artifact_store.put_bytes(
        raw.raw_text.encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        contract_id="raw-model-text-1.0.0",
    )
    raw_ref = artifact_store.put_bytes(
        raw_generation_bytes(raw),
        media_type="application/json",
        contract_id="raw-generation-result-1.0.0",
    )

    selected_parser = parser or ModelActionParser()
    candidate: ModelActionCandidate | None = None
    rejection: RejectedModelOutput | None = None
    try:
        candidate = selected_parser.parse(raw.raw_text)
        status = ModelOutputStatus.VALID
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError) as error:
        status = classify_parse_failure(raw.raw_text, error)
        rejection = RejectedModelOutput(
            generation_id=raw.generation_id,
            status=status,
            error_type=type(error).__name__,
            error_message=str(error),
        )
    if compiled.opportunity.snapshot.state_hash() != snapshot_hash:
        raise AssertionError("live cognition preparation mutated its bound Snapshot")
    return CognitionEvidencePreparation(
        request=request,
        raw_generation=raw,
        context_pack_ref=context_ref,
        rendered_input_ref=rendered_ref,
        raw_text_ref=raw_text_ref,
        raw_generation_ref=raw_ref,
        parse_status=status,
        candidate=candidate,
        rejection=rejection,
    )


def finalize_cognition_evidence(
    preparation: CognitionEvidencePreparation,
    profile: ModelProfile,
    generation_policy: GenerationPolicy,
    artifact_store: ArtifactStore,
    *,
    action_intent: ActionIntent | None = None,
    rejection: RejectedModelOutput | None = None,
) -> ArtifactRef:
    """Write final evidence after the Gateway has optionally bound identity."""

    evidence = build_cognition_evidence(
        preparation,
        profile,
        generation_policy,
        action_intent=action_intent,
        rejection=rejection,
    )
    return artifact_store.put_bytes(
        cognition_evidence_bytes(evidence),
        media_type="application/json",
        contract_id="cognition-evidence-1.0.0",
    )


def build_cognition_evidence(
    preparation: CognitionEvidencePreparation,
    profile: ModelProfile,
    generation_policy: GenerationPolicy,
    *,
    action_intent: ActionIntent | None = None,
    rejection: RejectedModelOutput | None = None,
) -> CognitionEvidence:
    """Construct, but do not store, final evidence for a prepared attempt."""

    validate_raw_generation_result(
        preparation.request,
        preparation.raw_generation,
        profile,
        generation_policy,
    )
    effective_rejection = rejection or preparation.rejection
    if action_intent is not None and preparation.candidate is None:
        raise ValueError("an ActionIntent requires a parsed model candidate")
    status = (
        effective_rejection.status
        if effective_rejection is not None
        else preparation.parse_status
    )
    return CognitionEvidence(
        generation_id=preparation.raw_generation.generation_id,
        context_hash=preparation.raw_generation.context_hash,
        rendered_input_hash=preparation.raw_generation.rendered_input_hash,
        interface_treatment_id=preparation.raw_generation.interface_treatment_id,
        interface_treatment_version=preparation.raw_generation.interface_treatment_version,
        interface_treatment_digest=preparation.raw_generation.interface_treatment_digest,
        constraint_policy_id=preparation.raw_generation.constraint_policy_id,
        context_pack_ref=preparation.context_pack_ref,
        rendered_input_ref=preparation.rendered_input_ref,
        raw_text_ref=preparation.raw_text_ref,
        raw_generation_ref=preparation.raw_generation_ref,
        model_profile_id=profile.profile_id,
        model_revision=profile.model_revision,
        tokenizer_identifier=profile.tokenizer_identifier,
        tokenizer_revision=profile.tokenizer_revision,
        generation_policy_id=generation_policy.policy_id,
        generation_policy_version=generation_policy.version,
        generation_seed_id=preparation.request.generation_seed_id,
        generation_seed=preparation.request.generation_seed,
        parse_status=status,
        candidate=preparation.candidate,
        action_intent=action_intent,
        rejection=effective_rejection,
    )


class RealCognitionDryRunner:
    """Execute generation once, persist raw evidence, then parse and bind."""

    def __init__(
        self,
        runtime: ModelRuntime,
        profile: ModelProfile,
        generation_policy: GenerationPolicy,
        artifact_store: ArtifactStore,
        *,
        generation_seed: int | None = None,
        parser: ModelActionParser | None = None,
        gateway: CognitionGateway | None = None,
        interface_treatment: InterfaceTreatment = I0_STRICT_FREE_GENERATION,
        prefix_allowed_tokens_fn=None,
    ) -> None:
        self.runtime = runtime
        self.profile = profile
        self.generation_policy = generation_policy
        self.artifact_store = artifact_store
        self.generation_seed = generation_seed
        self.parser = parser or ModelActionParser()
        self.gateway = gateway or CognitionGateway(parser=self.parser)
        self.interface_treatment = interface_treatment
        self.prefix_allowed_tokens_fn = prefix_allowed_tokens_fn

    def run(self, compiled: CompiledContext) -> CognitionDryRunResult:
        preparation = prepare_cognition_evidence(
            compiled,
            self.runtime,
            self.profile,
            self.generation_policy,
            self.artifact_store,
            generation_seed=self.generation_seed,
            parser=self.parser,
            interface_treatment=self.interface_treatment,
            prefix_allowed_tokens_fn=self.prefix_allowed_tokens_fn,
        )
        intent: ActionIntent | None = None
        rejection = preparation.rejection
        status = preparation.parse_status
        try:
            if preparation.candidate is not None:
                intent = self.gateway.bind(preparation.candidate, compiled.opportunity)
                status = ModelOutputStatus.VALID
        except (ValueError, TypeError, UnicodeError, json.JSONDecodeError) as error:
            status = ModelOutputStatus.DOMAIN_REJECTED
            rejection = RejectedModelOutput(
                generation_id=preparation.raw_generation.generation_id,
                status=status,
                error_type=type(error).__name__,
                error_message=str(error),
            )
        evidence_ref = finalize_cognition_evidence(
            preparation,
            self.profile,
            self.generation_policy,
            self.artifact_store,
            action_intent=intent,
            rejection=rejection,
        )
        evidence = build_cognition_evidence(
            preparation,
            self.profile,
            self.generation_policy,
            action_intent=intent,
            rejection=rejection,
        )
        return CognitionDryRunResult(
            raw_generation=preparation.raw_generation,
            evidence=evidence,
            evidence_ref=evidence_ref,
        )
