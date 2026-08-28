"""Immutable runtime values for the bounded EXP-000 context boundary.

This module mirrors the reviewed context machine contracts without adding the
full compiler.  In particular, it does not calculate ordering ranks or
ContextPack hashes.  Those identities are supplied by the later integration
boundary after the complete source/provenance set has been bound.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
from typing import TypeAlias

from alifelm.domain import AgentId, ArtifactRef, OpportunityId, RunId, StateVersion, Tick


_OPAQUE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_DIGEST = re.compile(r"^[a-f0-9]{64}$")


def _opaque_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not _OPAQUE_ID.fullmatch(value):
        raise ValueError(
            f"{field_name} must match [A-Za-z0-9][A-Za-z0-9_-]{{0,127}}"
        )


def _version(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not _VERSION.fullmatch(value):
        raise ValueError(f"{field_name} must be a semantic version")


def _digest(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")


def _non_negative_int(value: int, field_name: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")


class VisibleRecordCategory(StrEnum):
    DELIVERED_MESSAGE = "DELIVERED_MESSAGE"
    SENT_MESSAGE = "SENT_MESSAGE"
    INCOMING_PROPOSAL = "INCOMING_PROPOSAL"
    OUTGOING_PROPOSAL = "OUTGOING_PROPOSAL"
    PROTOCOL_RESOLUTION = "PROTOCOL_RESOLUTION"


class ProtocolResolutionResult(StrEnum):
    COMPLETED = "COMPLETED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"
    CONFIRMATION_NOT_APPLIED = "CONFIRMATION_NOT_APPLIED"


class ProjectionKind(StrEnum):
    DELIVERED_MESSAGE = "DELIVERED_MESSAGE"
    SENT_MESSAGE = "SENT_MESSAGE"
    INCOMING_PROPOSAL = "INCOMING_PROPOSAL"
    OUTGOING_PROPOSAL = "OUTGOING_PROPOSAL"
    PROTOCOL_RESOLUTION = "PROTOCOL_RESOLUTION"
    SELF_STATE = "SELF_STATE"
    PEER_DIRECTORY_ENTRY = "PEER_DIRECTORY_ENTRY"
    STABLE_PREFIX = "STABLE_PREFIX"


class SourceKind(StrEnum):
    STATE = "STATE"
    EVENT = "EVENT"
    ARTIFACT = "ARTIFACT"


@dataclass(frozen=True, slots=True)
class SourceBinding:
    """Research-only binding from one projection to committed evidence."""

    source_kind: SourceKind
    source_id: str
    source_state_version: StateVersion
    commit_id: str | None
    commit_tick: Tick | None
    commit_order: int | None
    artifact_refs: tuple[ArtifactRef, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.source_kind, SourceKind):
            raise TypeError("source_kind must be a SourceKind")
        _opaque_text(self.source_id, "source_binding.source_id")
        if not isinstance(self.source_state_version, StateVersion):
            raise TypeError("source_state_version must be a StateVersion")
        if self.commit_id is not None:
            _opaque_text(self.commit_id, "source_binding.commit_id")
        if self.commit_tick is not None and not isinstance(self.commit_tick, Tick):
            raise TypeError("commit_tick must be a Tick or None")
        if self.commit_order is not None:
            _non_negative_int(self.commit_order, "source_binding.commit_order")
        if not isinstance(self.artifact_refs, tuple) or any(
            not isinstance(ref, ArtifactRef) for ref in self.artifact_refs
        ):
            raise TypeError("artifact_refs must be ArtifactRef values")
        object.__setattr__(
            self,
            "artifact_refs",
            tuple(
                sorted(
                    set(self.artifact_refs),
                    key=lambda ref: (ref.artifact_id.value, ref.digest),
                )
            ),
        )


@dataclass(frozen=True, slots=True)
class VisibilityPolicy:
    policy_version: str
    own_opaque_id: bool
    current_tick: bool
    own_age: bool
    active_peer_directory: bool
    delivered_messages_to_self: bool
    own_sent_message_history: bool
    incoming_pending_proposals: bool
    own_outgoing_proposals: bool
    own_committed_resolutions: bool
    exact_lifespan_or_death_tick: bool
    lineage_or_parent_ids: bool
    agent_birth_seq: bool
    causal_seeds: bool
    model_runtime_identity: bool
    peer_private_records: bool
    uncommitted_protocol_work: bool
    same_tick_peer_outputs: bool
    researcher_or_analysis_labels: bool
    sprite_or_ui_identity: bool

    def __post_init__(self) -> None:
        _version(self.policy_version, "visibility.policy_version")
        expected = {
            "own_opaque_id": True,
            "current_tick": False,
            "own_age": True,
            "active_peer_directory": True,
            "delivered_messages_to_self": True,
            "own_sent_message_history": True,
            "incoming_pending_proposals": True,
            "own_outgoing_proposals": True,
            "own_committed_resolutions": True,
            "exact_lifespan_or_death_tick": False,
            "lineage_or_parent_ids": False,
            "agent_birth_seq": False,
            "causal_seeds": False,
            "model_runtime_identity": False,
            "peer_private_records": False,
            "uncommitted_protocol_work": False,
            "same_tick_peer_outputs": False,
            "researcher_or_analysis_labels": False,
            "sprite_or_ui_identity": False,
        }
        for name, value in expected.items():
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"visibility.{name} must be a boolean")
            if getattr(self, name) is not value:
                raise ValueError(f"EXP-000 visibility.{name} must be {value}")

    @classmethod
    def exp000(cls, *, policy_version: str = "1.0.0") -> VisibilityPolicy:
        return cls(
            policy_version=policy_version,
            own_opaque_id=True,
            current_tick=False,
            own_age=True,
            active_peer_directory=True,
            delivered_messages_to_self=True,
            own_sent_message_history=True,
            incoming_pending_proposals=True,
            own_outgoing_proposals=True,
            own_committed_resolutions=True,
            exact_lifespan_or_death_tick=False,
            lineage_or_parent_ids=False,
            agent_birth_seq=False,
            causal_seeds=False,
            model_runtime_identity=False,
            peer_private_records=False,
            uncommitted_protocol_work=False,
            same_tick_peer_outputs=False,
            researcher_or_analysis_labels=False,
            sprite_or_ui_identity=False,
        )


@dataclass(frozen=True, slots=True)
class HistoryPolicy:
    max_prior_visible_records: int
    selection: str
    mandatory_current_categories_outside_limit: bool
    lossy_summarization: bool
    model_written_semantic_memory: bool

    def __post_init__(self) -> None:
        _non_negative_int(self.max_prior_visible_records, "history.max_prior_visible_records")
        if self.selection != "LATEST_COMMITTED_GROUPS_THEN_PRESENT_CHRONOLOGICALLY":
            raise ValueError("unsupported EXP-000 history selection")
        if self.mandatory_current_categories_outside_limit is not True:
            raise ValueError("mandatory current categories must be outside the history limit")
        if self.lossy_summarization is not False:
            raise ValueError("EXP-000 does not use lossy history summarization")
        if self.model_written_semantic_memory is not False:
            raise ValueError("EXP-000 does not use model-written semantic memory")


@dataclass(frozen=True, slots=True)
class OrderingPolicy:
    policy_version: str
    unordered_collection_algorithm: str
    digest_algorithm: str
    ordering_seed_id: str
    ordering_seed_digest: str
    cross_tick_order: str
    tie_breaker: str

    def __post_init__(self) -> None:
        _version(self.policy_version, "ordering.policy_version")
        if self.unordered_collection_algorithm != "ALIFELM_CONTEXT_ORDER_V1":
            raise ValueError("unsupported context ordering algorithm")
        if self.digest_algorithm != "sha256":
            raise ValueError("context ordering must use sha256")
        _opaque_text(self.ordering_seed_id, "ordering.ordering_seed_id")
        _digest(self.ordering_seed_digest, "ordering.ordering_seed_digest")
        if self.cross_tick_order != "COMMITTED_TICK_CHRONOLOGICAL":
            raise ValueError("unsupported cross-tick context ordering")
        if self.tie_breaker != "FULL_STABLE_ITEM_KEY":
            raise ValueError("unsupported context ordering tie breaker")


@dataclass(frozen=True, slots=True)
class RecallPolicy:
    mode: str
    agent_triggered: bool
    semantic_retrieval: bool

    def __post_init__(self) -> None:
        if self.mode != "DISABLED":
            raise ValueError("EXP-000 recall mode is disabled")
        if self.agent_triggered is not False or self.semantic_retrieval is not False:
            raise ValueError("EXP-000 has no agent-triggered or semantic recall")


@dataclass(frozen=True, slots=True)
class CanonicalizationPolicy:
    policy: str
    digest_algorithm: str

    def __post_init__(self) -> None:
        if self.policy != "ALIFELM_CONTEXT_CANONICAL_JSON_V1":
            raise ValueError("unsupported ContextPack canonicalization policy")
        if self.digest_algorithm != "sha256":
            raise ValueError("ContextPack canonicalization must use sha256")


@dataclass(frozen=True, slots=True)
class ActionPresentationRef:
    policy_id: str
    version: str
    contract_digest: str

    def __post_init__(self) -> None:
        if self.policy_id != "exp000-neutral-actions":
            raise ValueError("unsupported EXP-000 action presentation policy")
        if self.version != "1.0.0":
            raise ValueError("unsupported EXP-000 action presentation version")
        _digest(self.contract_digest, "action_presentation.contract_digest")


@dataclass(frozen=True, slots=True)
class ContextPolicy:
    """Frozen EXP-000 treatment configuration.

    The ordering seed is metadata only here.  This bounded worker deliberately
    does not implement the reviewed seeded permutation algorithm.
    """

    policy_id: str
    version: str
    context_schema_version: str
    visibility: VisibilityPolicy
    history: HistoryPolicy
    ordering: OrderingPolicy
    recall: RecallPolicy
    canonicalization: CanonicalizationPolicy
    action_presentation: ActionPresentationRef

    def __post_init__(self) -> None:
        _opaque_text(self.policy_id, "context policy_id")
        _version(self.version, "context version")
        if self.context_schema_version != "1.0.0":
            raise ValueError("unsupported ContextPack schema version")
        if not isinstance(self.visibility, VisibilityPolicy):
            raise TypeError("visibility must be a VisibilityPolicy")
        if not isinstance(self.history, HistoryPolicy):
            raise TypeError("history must be a HistoryPolicy")
        if not isinstance(self.ordering, OrderingPolicy):
            raise TypeError("ordering must be an OrderingPolicy")
        if not isinstance(self.recall, RecallPolicy):
            raise TypeError("recall must be a RecallPolicy")
        if not isinstance(self.canonicalization, CanonicalizationPolicy):
            raise TypeError("canonicalization must be a CanonicalizationPolicy")
        if not isinstance(self.action_presentation, ActionPresentationRef):
            raise TypeError("action_presentation must be an ActionPresentationRef")

    @classmethod
    def exp000(
        cls,
        *,
        max_prior_visible_records: int,
        ordering: OrderingPolicy,
        action_presentation_digest: str,
        policy_id: str = "exp000-context",
        version: str = "1.0.0",
        visibility_version: str = "1.0.0",
    ) -> ContextPolicy:
        return cls(
            policy_id=policy_id,
            version=version,
            context_schema_version="1.0.0",
            visibility=VisibilityPolicy.exp000(policy_version=visibility_version),
            history=HistoryPolicy(
                max_prior_visible_records=max_prior_visible_records,
                selection="LATEST_COMMITTED_GROUPS_THEN_PRESENT_CHRONOLOGICALLY",
                mandatory_current_categories_outside_limit=True,
                lossy_summarization=False,
                model_written_semantic_memory=False,
            ),
            ordering=ordering,
            recall=RecallPolicy(
                mode="DISABLED", agent_triggered=False, semantic_retrieval=False
            ),
            canonicalization=CanonicalizationPolicy(
                policy="ALIFELM_CONTEXT_CANONICAL_JSON_V1", digest_algorithm="sha256"
            ),
            action_presentation=ActionPresentationRef(
                policy_id="exp000-neutral-actions",
                version="1.0.0",
                contract_digest=action_presentation_digest,
            ),
        )


@dataclass(frozen=True, slots=True)
class ActionPresentationEntry:
    """One internal action's exact model-facing neutral presentation."""

    internal_action: str
    model_label: str
    description: str
    payload_fields: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.internal_action or not self.model_label or not self.description:
            raise ValueError("action presentation text must be non-empty")
        if not isinstance(self.payload_fields, tuple) or any(
            not isinstance(field, str) for field in self.payload_fields
        ):
            raise TypeError("payload_fields must be a tuple of strings")


@dataclass(frozen=True, slots=True)
class ActionPresentation:
    """Immutable runtime mirror of the action-presentation contract."""

    policy_id: str
    version: str
    output_contract_id: str
    model_supplied_fields: tuple[str, ...]
    gateway_supplied_fields: tuple[str, ...]
    one_primary_action_per_opportunity: bool
    presentation_order: tuple[str, ...]
    actions: tuple[ActionPresentationEntry, ...]

    def __post_init__(self) -> None:
        if self.policy_id != "exp000-neutral-actions" or self.version != "1.0.0":
            raise ValueError("unsupported action presentation identity")
        if self.output_contract_id != "urn:alifelm:model-output:neutral-action-selection:1.0.0":
            raise ValueError("unsupported model output contract")
        if self.model_supplied_fields != ("action_label", "payload"):
            raise ValueError("model supplied fields do not match the contract")
        if self.gateway_supplied_fields != ("intent_id", "actor_id", "tick"):
            raise ValueError("gateway supplied fields do not match the contract")
        if self.one_primary_action_per_opportunity is not True:
            raise ValueError("one primary action per opportunity is required")
        if self.presentation_order != ("WAIT", "SEND", "PROPOSE", "ACCEPT", "REJECT"):
            raise ValueError("action presentation order does not match the contract")
        if tuple(entry.internal_action for entry in self.actions) != self.presentation_order:
            raise ValueError("action entries must follow the contract presentation order")
        actual = tuple(
            (
                entry.internal_action,
                entry.model_label,
                entry.description,
                entry.payload_fields,
            )
            for entry in self.actions
        )
        if actual != _EXPECTED_ACTION_PRESENTATION:
            raise ValueError("action wording/payloads do not match version 1.0.0")

    def entry(self, internal_action: str) -> ActionPresentationEntry:
        for entry in self.actions:
            if entry.internal_action == internal_action:
                return entry
        raise KeyError(internal_action)


_EXPECTED_ACTION_PRESENTATION = (
    (
        "WAIT",
        "NO_DIRECTED_ACTION",
        "Submit no directed text or bilateral request in this opportunity.",
        (),
    ),
    (
        "SEND",
        "DIRECT_TEXT",
        "Provide text to one listed opaque agent identity.",
        ("target_agent_id", "body"),
    ),
    (
        "PROPOSE",
        "OPEN_BILATERAL_REQUEST",
        "Open a request with one listed opaque identity; if later confirmed and system conditions permit, one additional opaque agent may be created.",
        ("target_agent_id",),
    ),
    (
        "ACCEPT",
        "CONFIRM_BILATERAL_REQUEST",
        "Confirm one visible pending request addressed to this agent; system rules determine the committed result.",
        ("proposal_id",),
    ),
    (
        "REJECT",
        "DECLINE_BILATERAL_REQUEST",
        "Decline one visible pending request addressed to this agent.",
        ("proposal_id",),
    ),
)


DEFAULT_ACTION_PRESENTATION = ActionPresentation(
    policy_id="exp000-neutral-actions",
    version="1.0.0",
    output_contract_id="urn:alifelm:model-output:neutral-action-selection:1.0.0",
    model_supplied_fields=("action_label", "payload"),
    gateway_supplied_fields=("intent_id", "actor_id", "tick"),
    one_primary_action_per_opportunity=True,
    presentation_order=("WAIT", "SEND", "PROPOSE", "ACCEPT", "REJECT"),
    actions=tuple(ActionPresentationEntry(*values) for values in _EXPECTED_ACTION_PRESENTATION),
)


@dataclass(frozen=True, slots=True)
class DeliveredMessagePayload:
    sender_id: AgentId
    body: str

    def __post_init__(self) -> None:
        if not isinstance(self.sender_id, AgentId):
            raise TypeError("sender_id must be an AgentId")
        if not isinstance(self.body, str):
            raise TypeError("body must be a string")


@dataclass(frozen=True, slots=True)
class SentMessagePayload:
    recipient_id: AgentId
    body: str

    def __post_init__(self) -> None:
        if not isinstance(self.recipient_id, AgentId):
            raise TypeError("recipient_id must be an AgentId")
        if not isinstance(self.body, str):
            raise TypeError("body must be a string")


@dataclass(frozen=True, slots=True)
class IncomingProposalPayload:
    proposal_id: str
    proposer_id: AgentId
    state: str = "OPEN"

    def __post_init__(self) -> None:
        _opaque_text(self.proposal_id, "incoming proposal_id")
        if not isinstance(self.proposer_id, AgentId):
            raise TypeError("proposer_id must be an AgentId")
        if self.state != "OPEN":
            raise ValueError("only open pending proposals are model-visible")


@dataclass(frozen=True, slots=True)
class OutgoingProposalPayload:
    proposal_id: str
    target_id: AgentId
    state: str = "OPEN"

    def __post_init__(self) -> None:
        _opaque_text(self.proposal_id, "outgoing proposal_id")
        if not isinstance(self.target_id, AgentId):
            raise TypeError("target_id must be an AgentId")
        if self.state != "OPEN":
            raise ValueError("only open pending proposals are model-visible")


@dataclass(frozen=True, slots=True)
class ProtocolResolutionPayload:
    proposal_id: str
    counterparty_id: AgentId | None
    result: ProtocolResolutionResult

    def __post_init__(self) -> None:
        _opaque_text(self.proposal_id, "resolution proposal_id")
        if self.counterparty_id is not None and not isinstance(
            self.counterparty_id, AgentId
        ):
            raise TypeError("counterparty_id must be an AgentId or None")
        if not isinstance(self.result, ProtocolResolutionResult):
            raise TypeError("result must be a ProtocolResolutionResult")


VisiblePayload: TypeAlias = (
    DeliveredMessagePayload
    | SentMessagePayload
    | IncomingProposalPayload
    | OutgoingProposalPayload
    | ProtocolResolutionPayload
)


@dataclass(frozen=True, slots=True)
class VisibleRecord:
    category: VisibleRecordCategory
    payload: VisiblePayload

    def __post_init__(self) -> None:
        if not isinstance(self.category, VisibleRecordCategory):
            raise TypeError("category must be a VisibleRecordCategory")
        expected = {
            VisibleRecordCategory.DELIVERED_MESSAGE: DeliveredMessagePayload,
            VisibleRecordCategory.SENT_MESSAGE: SentMessagePayload,
            VisibleRecordCategory.INCOMING_PROPOSAL: IncomingProposalPayload,
            VisibleRecordCategory.OUTGOING_PROPOSAL: OutgoingProposalPayload,
            VisibleRecordCategory.PROTOCOL_RESOLUTION: ProtocolResolutionPayload,
        }
        if not isinstance(self.payload, expected[self.category]):
            raise TypeError(f"{self.category} has an incompatible payload")


@dataclass(frozen=True, slots=True)
class StablePrefix:
    mechanics_profile_id: str = "exp000-minimal-mechanics-v1"
    action_presentation_policy_id: str = "exp000-neutral-actions"
    action_presentation_version: str = "1.0.0"

    def __post_init__(self) -> None:
        if self.mechanics_profile_id != "exp000-minimal-mechanics-v1":
            raise ValueError("unsupported EXP-000 mechanics profile")
        if self.action_presentation_policy_id != "exp000-neutral-actions":
            raise ValueError("unsupported action presentation policy")
        if self.action_presentation_version != "1.0.0":
            raise ValueError("unsupported action presentation version")


@dataclass(frozen=True, slots=True)
class CurrentSelf:
    agent_id: AgentId
    age: int

    def __post_init__(self) -> None:
        if not isinstance(self.agent_id, AgentId):
            raise TypeError("current_self.agent_id must be an AgentId")
        _non_negative_int(self.age, "current_self.age")


@dataclass(frozen=True, slots=True)
class PeerDirectoryEntry:
    agent_id: AgentId

    def __post_init__(self) -> None:
        if not isinstance(self.agent_id, AgentId):
            raise TypeError("peer_directory.agent_id must be an AgentId")


@dataclass(frozen=True, slots=True)
class ModelInput:
    stable_prefix: StablePrefix
    current_self: CurrentSelf
    peer_directory: tuple[PeerDirectoryEntry, ...]
    newly_delivered: tuple[VisibleRecord, ...]
    visible_protocol_state: tuple[VisibleRecord, ...]
    prior_history: tuple[VisibleRecord, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.stable_prefix, StablePrefix):
            raise TypeError("stable_prefix must be a StablePrefix")
        if not isinstance(self.current_self, CurrentSelf):
            raise TypeError("current_self must be a CurrentSelf")
        for name in (
            "peer_directory",
            "newly_delivered",
            "visible_protocol_state",
            "prior_history",
        ):
            value = getattr(self, name)
            if not isinstance(value, tuple):
                raise TypeError(f"{name} must be a tuple")
        if any(not isinstance(item, PeerDirectoryEntry) for item in self.peer_directory):
            raise TypeError("peer_directory contains an invalid entry")
        peer_ids = [item.agent_id for item in self.peer_directory]
        if len(peer_ids) != len(set(peer_ids)):
            raise ValueError("peer_directory entries must be unique")
        for name in ("newly_delivered", "visible_protocol_state", "prior_history"):
            if any(not isinstance(item, VisibleRecord) for item in getattr(self, name)):
                raise TypeError(f"{name} contains an invalid visible record")


@dataclass(frozen=True, slots=True)
class Provenance:
    model_path: str
    projection_kind: ProjectionKind
    source_kind: SourceKind
    source_id: str
    source_state_version: int
    commit_id: str | None
    commit_tick: int | None
    commit_order: int | None
    artifact_refs: tuple[ArtifactRef, ...]

    def __post_init__(self) -> None:
        if not self.model_path.startswith("/model_input/"):
            raise ValueError("provenance model_path must point into model_input")
        if not isinstance(self.projection_kind, ProjectionKind):
            raise TypeError("projection_kind must be a ProjectionKind")
        if not isinstance(self.source_kind, SourceKind):
            raise TypeError("source_kind must be a SourceKind")
        _opaque_text(self.source_id, "provenance.source_id")
        _non_negative_int(self.source_state_version, "provenance.source_state_version")
        if self.commit_id is not None:
            _opaque_text(self.commit_id, "provenance.commit_id")
        if self.commit_tick is not None:
            _non_negative_int(self.commit_tick, "provenance.commit_tick")
        if self.commit_order is not None:
            _non_negative_int(self.commit_order, "provenance.commit_order")
        if not isinstance(self.artifact_refs, tuple) or any(
            not isinstance(ref, ArtifactRef) for ref in self.artifact_refs
        ):
            raise TypeError("provenance.artifact_refs must be ArtifactRef values")
        object.__setattr__(
            self,
            "artifact_refs",
            tuple(
                sorted(
                    set(self.artifact_refs),
                    key=lambda ref: (ref.artifact_id.value, ref.digest),
                )
            ),
        )


@dataclass(frozen=True, slots=True)
class ContextEvidence:
    run_id: RunId
    opportunity_id: OpportunityId
    agent_id: AgentId
    bound_tick: int
    bound_state_version: int
    bound_state_hash: str
    context_policy_id: str
    context_policy_version: str
    context_policy_digest: str
    visibility_policy_version: str
    ordering_policy_version: str
    ordering_seed_id: str
    ordering_seed_digest: str
    action_presentation_policy_id: str
    action_presentation_version: str
    action_presentation_digest: str
    provenance: tuple[Provenance, ...]
    artifact_refs: tuple[ArtifactRef, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, RunId):
            raise TypeError("evidence.run_id must be a RunId")
        if not isinstance(self.opportunity_id, OpportunityId):
            raise TypeError("evidence.opportunity_id must be an OpportunityId")
        if not isinstance(self.agent_id, AgentId):
            raise TypeError("evidence.agent_id must be an AgentId")
        _non_negative_int(self.bound_tick, "evidence.bound_tick")
        _non_negative_int(self.bound_state_version, "evidence.bound_state_version")
        _digest(self.bound_state_hash, "evidence.bound_state_hash")
        _opaque_text(self.context_policy_id, "evidence.context_policy_id")
        _version(self.context_policy_version, "evidence.context_policy_version")
        _digest(self.context_policy_digest, "evidence.context_policy_digest")
        _version(self.visibility_policy_version, "evidence.visibility_policy_version")
        _version(self.ordering_policy_version, "evidence.ordering_policy_version")
        _opaque_text(self.ordering_seed_id, "evidence.ordering_seed_id")
        _digest(self.ordering_seed_digest, "evidence.ordering_seed_digest")
        if self.action_presentation_policy_id != "exp000-neutral-actions":
            raise ValueError("unsupported evidence action presentation policy")
        if self.action_presentation_version != "1.0.0":
            raise ValueError("unsupported evidence action presentation version")
        _digest(self.action_presentation_digest, "evidence.action_presentation_digest")
        if not isinstance(self.provenance, tuple) or any(
            not isinstance(item, Provenance) for item in self.provenance
        ):
            raise TypeError("evidence.provenance must be Provenance values")
        if not isinstance(self.artifact_refs, tuple) or any(
            not isinstance(ref, ArtifactRef) for ref in self.artifact_refs
        ):
            raise TypeError("evidence.artifact_refs must be ArtifactRef values")
        object.__setattr__(
            self,
            "artifact_refs",
            tuple(
                sorted(
                    set(self.artifact_refs),
                    key=lambda ref: (ref.artifact_id.value, ref.digest),
                )
            ),
        )


@dataclass(frozen=True, slots=True)
class VisibleRecordCounts:
    peers: int
    newly_delivered: int
    visible_protocol_state: int
    prior_history: int

    def __post_init__(self) -> None:
        for field_name in (
            "peers",
            "newly_delivered",
            "visible_protocol_state",
            "prior_history",
        ):
            _non_negative_int(getattr(self, field_name), f"visible_record_counts.{field_name}")


@dataclass(frozen=True, slots=True)
class CacheTelemetry:
    cache_profile_id: str
    hit: bool

    def __post_init__(self) -> None:
        _opaque_text(self.cache_profile_id, "cache_profile_id")
        if type(self.hit) is not bool:
            raise TypeError("cache telemetry hit must be a boolean")


@dataclass(frozen=True, slots=True)
class InfrastructureMetadata:
    model_profile_id: str
    generation_policy_id: str
    generation_seed_id: str
    visible_record_counts: VisibleRecordCounts
    tokenizer_profile_id: str | None
    rendered_input_token_count: int | None
    cache_telemetry: CacheTelemetry | None

    def __post_init__(self) -> None:
        _opaque_text(self.model_profile_id, "infrastructure.model_profile_id")
        _opaque_text(self.generation_policy_id, "infrastructure.generation_policy_id")
        _opaque_text(self.generation_seed_id, "infrastructure.generation_seed_id")
        if not isinstance(self.visible_record_counts, VisibleRecordCounts):
            raise TypeError("visible_record_counts must be VisibleRecordCounts")
        if self.tokenizer_profile_id is not None:
            _opaque_text(self.tokenizer_profile_id, "tokenizer_profile_id")
        if self.rendered_input_token_count is not None:
            _non_negative_int(
                self.rendered_input_token_count, "rendered_input_token_count"
            )
        if self.cache_telemetry is not None and not isinstance(
            self.cache_telemetry, CacheTelemetry
        ):
            raise TypeError("cache_telemetry must be CacheTelemetry or None")


@dataclass(frozen=True, slots=True)
class ContextPack:
    """Immutable ContextPack envelope; identity/hash are supplied, not computed."""

    context_pack_id: str
    schema_version: str
    context_hash: str
    model_input: ModelInput
    evidence: ContextEvidence
    infrastructure: InfrastructureMetadata

    def __post_init__(self) -> None:
        _opaque_text(self.context_pack_id, "context_pack_id")
        if self.schema_version != "1.0.0":
            raise ValueError("unsupported ContextPack schema version")
        _digest(self.context_hash, "context_hash")
        if not isinstance(self.model_input, ModelInput):
            raise TypeError("model_input must be ModelInput")
        if not isinstance(self.evidence, ContextEvidence):
            raise TypeError("evidence must be ContextEvidence")
        if not isinstance(self.infrastructure, InfrastructureMetadata):
            raise TypeError("infrastructure must be InfrastructureMetadata")
        if self.evidence.agent_id != self.model_input.current_self.agent_id:
            raise ValueError("ContextPack evidence actor must match current_self")
        counts = self.infrastructure.visible_record_counts
        actual_counts = (
            len(self.model_input.peer_directory),
            len(self.model_input.newly_delivered),
            len(self.model_input.visible_protocol_state),
            len(self.model_input.prior_history),
        )
        if actual_counts != (
            counts.peers,
            counts.newly_delivered,
            counts.visible_protocol_state,
            counts.prior_history,
        ):
            raise ValueError("ContextPack visible record counts do not match model_input")
