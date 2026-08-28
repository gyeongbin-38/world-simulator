"""Researcher-only I3 codec/domain/commit-layer diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json

from alifelm.context import CognitionGateway, DEFAULT_ACTION_PRESENTATION, ModelActionCandidate, ModelActionParser
from alifelm.domain import (
    ActionIntent,
    AgentId,
    IntentBatch,
    ProposalId,
    ProposalState,
    can_reproduce,
)
from alifelm.kernel.engine import _plan_fragments
from alifelm.kernel.run import SimulationRun
from alifelm.kernel.validation import LawValidator
from alifelm.kernel.opportunities import CognitionOpportunity
from alifelm.kernel.transitions import TransitionKind

from .evidence import ModelOutputStatus, classify_parse_failure


class CodecValidityStatus(StrEnum):
    CODEC_VALID = "CODEC_VALID"
    MALFORMED_SYNTAX = "MALFORMED_SYNTAX"
    ACTION_PAYLOAD_TYPE_MISMATCH = "ACTION_PAYLOAD_TYPE_MISMATCH"
    TRUNCATED = "TRUNCATED"
    EMPTY = "EMPTY"


class DomainValidityStatus(StrEnum):
    DOMAIN_VALID = "DOMAIN_VALID"
    UNKNOWN_TARGET = "UNKNOWN_TARGET"
    UNKNOWN_PROPOSAL = "UNKNOWN_PROPOSAL"
    INELIGIBLE_REPRODUCTION = "INELIGIBLE_REPRODUCTION"
    INVALID_PARTICIPANT = "INVALID_PARTICIPANT"
    DOMAIN_REJECTED = "DOMAIN_REJECTED"
    NOT_CODEC_VALID = "NOT_CODEC_VALID"


class CommitValidityStatus(StrEnum):
    COMMIT_VALID = "COMMIT_VALID"
    DOMAIN_INVALID = "DOMAIN_INVALID"
    BOUNDARY_CONFLICT = "BOUNDARY_CONFLICT"
    PLANNING_FAILED = "PLANNING_FAILED"


@dataclass(frozen=True, slots=True)
class TypedCodecEvaluation:
    codec_status: CodecValidityStatus
    domain_status: DomainValidityStatus
    commit_status: CommitValidityStatus
    candidate: ModelActionCandidate | None
    intent: ActionIntent | None
    planned_fragment_count: int


def typed_codec_evaluation_bytes(
    evaluation: TypedCodecEvaluation,
    *,
    generation_id: str,
    context_hash: str,
    treatment_id: str,
    treatment_version: str,
) -> bytes:
    """Serialize researcher-only I3 evidence without making it domain state."""

    candidate = evaluation.candidate
    intent = evaluation.intent
    document = {
        "candidate": (
            None
            if candidate is None
            else {
                "action_label": candidate.action_label,
                "payload": candidate.payload_dict(),
            }
        ),
        "codec_status": evaluation.codec_status.value,
        "commit_status": evaluation.commit_status.value,
        "context_hash": context_hash,
        "domain_status": evaluation.domain_status.value,
        "generation_id": generation_id,
        "gateway_bound_intent": (
            None
            if intent is None
            else {
                "actor_id": str(intent.actor_id),
                "intent_id": str(intent.intent_id),
                "tick": int(intent.tick),
            }
        ),
        "planned_fragment_count": evaluation.planned_fragment_count,
        "treatment_id": treatment_id,
        "treatment_version": treatment_version,
    }
    return json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _codec_candidate(raw_text: str) -> tuple[CodecValidityStatus, ModelActionCandidate | None]:
    parser = ModelActionParser()
    if not raw_text.strip():
        return CodecValidityStatus.EMPTY, None
    try:
        candidate = parser.parse(raw_text)
    except json.JSONDecodeError as error:
        status = classify_parse_failure(raw_text, error)
        mapped = {
            ModelOutputStatus.TRUNCATED: CodecValidityStatus.TRUNCATED,
            ModelOutputStatus.EMPTY: CodecValidityStatus.EMPTY,
        }.get(status, CodecValidityStatus.MALFORMED_SYNTAX)
        return mapped, None
    except (TypeError, ValueError, UnicodeError):
        return CodecValidityStatus.ACTION_PAYLOAD_TYPE_MISMATCH, None

    matching = tuple(
        entry
        for entry in DEFAULT_ACTION_PRESENTATION.actions
        if entry.model_label == candidate.action_label
    )
    if len(matching) != 1:
        return CodecValidityStatus.ACTION_PAYLOAD_TYPE_MISMATCH, candidate
    if set(candidate.payload_dict()) != set(matching[0].payload_fields):
        return CodecValidityStatus.ACTION_PAYLOAD_TYPE_MISMATCH, candidate
    payload = candidate.payload_dict()
    try:
        if "target_agent_id" in payload:
            AgentId(payload["target_agent_id"])
        if "proposal_id" in payload:
            ProposalId(payload["proposal_id"])
    except ValueError:
        return CodecValidityStatus.ACTION_PAYLOAD_TYPE_MISMATCH, candidate
    return CodecValidityStatus.CODEC_VALID, candidate


def _domain_status(
    candidate: ModelActionCandidate,
    opportunity: CognitionOpportunity,
) -> DomainValidityStatus:
    entry = next(
        item
        for item in DEFAULT_ACTION_PRESENTATION.actions
        if item.model_label == candidate.action_label
    )
    payload = candidate.payload_dict()
    snapshot = opportunity.snapshot
    actor = snapshot.agent(opportunity.agent_id)
    if actor is None or not actor.is_active(snapshot.tick):
        return DomainValidityStatus.INVALID_PARTICIPANT
    if entry.internal_action == "WAIT":
        return DomainValidityStatus.DOMAIN_VALID
    if entry.internal_action in {"SEND", "PROPOSE"}:
        target_id = AgentId(payload["target_agent_id"])
        target = snapshot.agent(target_id)
        if target is None or not target.is_active(snapshot.tick):
            return DomainValidityStatus.UNKNOWN_TARGET
        if entry.internal_action == "PROPOSE":
            if target_id == opportunity.agent_id:
                return DomainValidityStatus.INVALID_PARTICIPANT
            if not can_reproduce(actor, snapshot.tick) or not can_reproduce(
                target, snapshot.tick
            ):
                return DomainValidityStatus.INELIGIBLE_REPRODUCTION
        return DomainValidityStatus.DOMAIN_VALID

    proposal_id = ProposalId(payload["proposal_id"])
    proposal = next(
        (item for item in snapshot.proposals if item.proposal_id == proposal_id),
        None,
    )
    if proposal is None or proposal.state is not ProposalState.PENDING:
        return DomainValidityStatus.UNKNOWN_PROPOSAL
    if proposal.target_id != opportunity.agent_id or not proposal.visible_at(snapshot.tick):
        return DomainValidityStatus.INVALID_PARTICIPANT
    if entry.internal_action == "ACCEPT":
        proposer = snapshot.agent(proposal.proposer_id)
        if proposer is None or not proposer.is_active(snapshot.tick):
            return DomainValidityStatus.INVALID_PARTICIPANT
        if not can_reproduce(actor, snapshot.tick) or not can_reproduce(
            proposer, snapshot.tick
        ):
            return DomainValidityStatus.INELIGIBLE_REPRODUCTION
    return DomainValidityStatus.DOMAIN_VALID


def evaluate_typed_codec(
    raw_text: str,
    opportunity: CognitionOpportunity,
    run: SimulationRun,
) -> TypedCodecEvaluation:
    """Evaluate without committing or changing canonical state."""

    codec_status, candidate = _codec_candidate(raw_text)
    if codec_status is not CodecValidityStatus.CODEC_VALID or candidate is None:
        return TypedCodecEvaluation(
            codec_status,
            DomainValidityStatus.NOT_CODEC_VALID,
            CommitValidityStatus.DOMAIN_INVALID,
            candidate,
            None,
            0,
        )
    domain_status = _domain_status(candidate, opportunity)
    if domain_status is not DomainValidityStatus.DOMAIN_VALID:
        return TypedCodecEvaluation(
            codec_status,
            domain_status,
            CommitValidityStatus.DOMAIN_INVALID,
            candidate,
            None,
            0,
        )
    try:
        intent = CognitionGateway().bind(candidate, opportunity)
        batch = IntentBatch(tick=opportunity.tick, intents=(intent,))
        validated = LawValidator().validate(batch, opportunity.snapshot, run)
        if len(validated) != 1:
            return TypedCodecEvaluation(
                codec_status,
                DomainValidityStatus.DOMAIN_REJECTED,
                CommitValidityStatus.DOMAIN_INVALID,
                candidate,
                intent,
                0,
            )
        fragments = _plan_fragments(opportunity.snapshot, run, validated)
    except (TypeError, ValueError):
        return TypedCodecEvaluation(
            codec_status,
            DomainValidityStatus.DOMAIN_REJECTED,
            CommitValidityStatus.PLANNING_FAILED,
            candidate,
            None,
            0,
        )
    commit_status = (
        CommitValidityStatus.BOUNDARY_CONFLICT
        if any(
            fragment.kind is TransitionKind.BIRTH_CONFLICT_REJECTED
            for fragment in fragments
        )
        else CommitValidityStatus.COMMIT_VALID
    )
    return TypedCodecEvaluation(
        codec_status,
        DomainValidityStatus.DOMAIN_VALID,
        commit_status,
        candidate,
        intent,
        len(fragments),
    )
