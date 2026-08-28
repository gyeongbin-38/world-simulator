"""Deterministic, storage-independent ContextPack compiler."""

from __future__ import annotations

from dataclasses import dataclass

from alifelm.domain import ArtifactRef
from alifelm.kernel.opportunities import CognitionOpportunity

from .history import PersonalVisibleHistory, PersonalVisibleRecord
from .ordering import NeutralOrdering, OrderingBinding
from .provenance import validate_context_provenance
from .serialization import (
    action_presentation_digest,
    context_policy_digest,
    finalize_context_pack,
)
from .types import (
    ContextEvidence,
    ContextPack,
    ContextPolicy,
    CurrentSelf,
    DEFAULT_ACTION_PRESENTATION,
    InfrastructureMetadata,
    ModelInput,
    ProjectionKind,
    Provenance,
    SourceBinding,
    SourceKind,
    StablePrefix,
    VisibleRecordCounts,
)
from .visibility import (
    ProjectedPeer,
    ProjectedRecord,
    VisibilityProjection,
    VisibilityProjectionResult,
)


@dataclass(frozen=True, slots=True)
class _ModelAssembly:
    model_input: ModelInput
    peers: tuple[ProjectedPeer, ...]
    newly_delivered: tuple[ProjectedRecord, ...]
    protocol: tuple[ProjectedRecord, ...]
    history: tuple[PersonalVisibleRecord, ...]


def _projected_key(record: ProjectedRecord) -> str:
    return (
        f"{record.model_value.category.value}|{record.source.source_kind.value}|"
        f"{record.source.source_id}"
    )


def _assemble_model_input(
    projection: VisibilityProjectionResult,
    policy: ContextPolicy,
    history: tuple[PersonalVisibleRecord, ...],
    ordering: NeutralOrdering | None,
) -> _ModelAssembly:
    if any(
        record.agent_id != projection.agent_id
        or record.committed_tick >= projection.bound_tick
        for record in history
    ):
        raise ValueError("history must be agent-scoped and prior to the bound tick")

    peers = projection.active_peers
    newly_delivered = tuple(
        record
        for record in projection.delivered_messages
        if record.first_visible_tick == projection.bound_tick
    )
    protocol = (
        *projection.incoming_pending_proposals,
        *projection.outgoing_pending_proposals,
    )
    if ordering is not None:
        peers = ordering.order(
            peers,
            category="peer_directory",
            stable_key=lambda peer: f"agent|{peer.model_value.agent_id.value}",
        )
        newly_delivered = ordering.order(
            newly_delivered,
            category="newly_delivered",
            stable_key=_projected_key,
        )
        protocol = ordering.order(
            protocol,
            category="visible_protocol_state",
            stable_key=_projected_key,
        )

    current_source_ids = {
        record.source.source_id for record in (*newly_delivered, *protocol)
    }
    if current_source_ids.intersection(record.source_id for record in history):
        raise ValueError("history cannot duplicate a current visible source")

    model_input = ModelInput(
        stable_prefix=StablePrefix(
            action_presentation_policy_id=policy.action_presentation.policy_id,
            action_presentation_version=policy.action_presentation.version,
        ),
        current_self=CurrentSelf(projection.agent_id, projection.age),
        peer_directory=tuple(peer.model_value for peer in peers),
        newly_delivered=tuple(record.model_value for record in newly_delivered),
        visible_protocol_state=tuple(record.model_value for record in protocol),
        prior_history=tuple(record.model_value for record in history),
    )
    return _ModelAssembly(
        model_input=model_input,
        peers=peers,
        newly_delivered=newly_delivered,
        protocol=tuple(protocol),
        history=history,
    )


def build_model_input(
    projection: VisibilityProjectionResult,
    policy: ContextPolicy,
    history: tuple[PersonalVisibleRecord, ...] = (),
    *,
    ordering: NeutralOrdering | None = None,
) -> ModelInput:
    """Build only the model-facing structure.

    The complete ContextCompiler always supplies neutral ordering and builds
    provenance.  This smaller function remains useful for focused visibility
    tests without claiming a finalized ContextPack identity.
    """

    if not isinstance(projection, VisibilityProjectionResult):
        raise TypeError("projection must be a VisibilityProjectionResult")
    if not isinstance(policy, ContextPolicy):
        raise TypeError("policy must be a ContextPolicy")
    if not isinstance(history, tuple):
        raise TypeError("history must be a tuple")
    return _assemble_model_input(projection, policy, history, ordering).model_input


def _provenance(path: str, kind: ProjectionKind, source: SourceBinding) -> Provenance:
    return Provenance(
        model_path=path,
        projection_kind=kind,
        source_kind=source.source_kind,
        source_id=source.source_id,
        source_state_version=int(source.source_state_version),
        commit_id=source.commit_id,
        commit_tick=(int(source.commit_tick) if source.commit_tick is not None else None),
        commit_order=source.commit_order,
        artifact_refs=source.artifact_refs,
    )


def _record_kind(record: ProjectedRecord | PersonalVisibleRecord) -> ProjectionKind:
    return ProjectionKind(record.model_value.category.value)


class ContextCompiler:
    """Compile one immutable ContextPack from one bound cognition opportunity."""

    def compile(
        self,
        opportunity: CognitionOpportunity,
        policy: ContextPolicy,
        *,
        model_profile_id: str,
        generation_policy_id: str,
        generation_seed_id: str,
        committed_history: tuple[PersonalVisibleRecord, ...] = (),
        source_artifact_refs: tuple[ArtifactRef, ...] = (),
    ) -> ContextPack:
        if not isinstance(opportunity, CognitionOpportunity):
            raise TypeError("opportunity must be a CognitionOpportunity")
        if not isinstance(policy, ContextPolicy):
            raise TypeError("policy must be a ContextPolicy")
        expected_action_digest = action_presentation_digest(
            DEFAULT_ACTION_PRESENTATION
        )
        if policy.action_presentation.contract_digest != expected_action_digest:
            raise ValueError("ContextPolicy action presentation digest is not canonical")
        if not isinstance(source_artifact_refs, tuple) or any(
            not isinstance(ref, ArtifactRef) for ref in source_artifact_refs
        ):
            raise TypeError("source_artifact_refs must contain ArtifactRef values")

        snapshot = opportunity.snapshot
        before_hash = snapshot.state_hash()
        projection = VisibilityProjection.project(snapshot, opportunity.agent_id, policy)
        ordering = NeutralOrdering(
            policy.ordering,
            OrderingBinding(
                run_id=opportunity.run_id,
                opportunity_id=opportunity.opportunity_id,
                bound_tick=opportunity.tick,
            ),
        )
        history = PersonalVisibleHistory.select(
            projection,
            policy,
            committed_records=committed_history,
            ordering=ordering,
        )
        assembly = _assemble_model_input(projection, policy, history, ordering)

        contract_source = SourceBinding(
            source_kind=SourceKind.ARTIFACT,
            source_id=policy.action_presentation.policy_id,
            source_state_version=snapshot.state_version,
            commit_id=None,
            commit_tick=None,
            commit_order=None,
            artifact_refs=(),
        )
        provenance: list[Provenance] = [
            _provenance(
                "/model_input/stable_prefix",
                ProjectionKind.STABLE_PREFIX,
                contract_source,
            ),
            _provenance(
                "/model_input/current_self",
                ProjectionKind.SELF_STATE,
                projection.self_source,
            ),
        ]
        provenance.extend(
            _provenance(
                f"/model_input/peer_directory/{index}",
                ProjectionKind.PEER_DIRECTORY_ENTRY,
                peer.source,
            )
            for index, peer in enumerate(assembly.peers)
        )
        for region, records in (
            ("newly_delivered", assembly.newly_delivered),
            ("visible_protocol_state", assembly.protocol),
        ):
            provenance.extend(
                _provenance(
                    f"/model_input/{region}/{index}",
                    _record_kind(record),
                    record.source,
                )
                for index, record in enumerate(records)
            )
        provenance.extend(
            _provenance(
                f"/model_input/prior_history/{index}",
                _record_kind(record),
                record.source,
            )
            for index, record in enumerate(assembly.history)
        )

        artifact_refs = tuple(
            sorted(
                set(source_artifact_refs),
                key=lambda ref: (ref.artifact_id.value, ref.digest),
            )
        )
        evidence = ContextEvidence(
            run_id=opportunity.run_id,
            opportunity_id=opportunity.opportunity_id,
            agent_id=opportunity.agent_id,
            bound_tick=int(opportunity.tick),
            bound_state_version=int(snapshot.state_version),
            bound_state_hash=before_hash,
            context_policy_id=policy.policy_id,
            context_policy_version=policy.version,
            context_policy_digest=context_policy_digest(policy),
            visibility_policy_version=policy.visibility.policy_version,
            ordering_policy_version=policy.ordering.policy_version,
            ordering_seed_id=policy.ordering.ordering_seed_id,
            ordering_seed_digest=policy.ordering.ordering_seed_digest,
            action_presentation_policy_id=policy.action_presentation.policy_id,
            action_presentation_version=policy.action_presentation.version,
            action_presentation_digest=expected_action_digest,
            provenance=tuple(provenance),
            artifact_refs=artifact_refs,
        )
        counts = VisibleRecordCounts(
            peers=len(assembly.model_input.peer_directory),
            newly_delivered=len(assembly.model_input.newly_delivered),
            visible_protocol_state=len(assembly.model_input.visible_protocol_state),
            prior_history=len(assembly.model_input.prior_history),
        )
        infrastructure = InfrastructureMetadata(
            model_profile_id=model_profile_id,
            generation_policy_id=generation_policy_id,
            generation_seed_id=generation_seed_id,
            visible_record_counts=counts,
            tokenizer_profile_id=None,
            rendered_input_token_count=None,
            cache_telemetry=None,
        )
        pack = finalize_context_pack(assembly.model_input, evidence, infrastructure)
        validate_context_provenance(pack, snapshot)
        if snapshot.state_hash() != before_hash:
            raise RuntimeError("ContextCompiler mutated its bound Snapshot")
        return pack
