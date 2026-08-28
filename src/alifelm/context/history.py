"""Bounded exact personal-visible history selection."""

from __future__ import annotations

from dataclasses import dataclass

from alifelm.domain import AgentId, Tick

from .ordering import NeutralOrdering
from .types import ContextPolicy, SourceBinding, VisibleRecord
from .visibility import ProjectedRecord, VisibilityProjectionResult


@dataclass(frozen=True, slots=True)
class PersonalVisibleRecord:
    """One agent-scoped visible record with complete committed provenance."""

    agent_id: AgentId
    model_value: VisibleRecord
    source: SourceBinding

    def __post_init__(self) -> None:
        if not isinstance(self.agent_id, AgentId):
            raise TypeError("history agent_id must be an AgentId")
        if not isinstance(self.model_value, VisibleRecord):
            raise TypeError("history model_value must be a VisibleRecord")
        if not isinstance(self.source, SourceBinding):
            raise TypeError("history source must be a SourceBinding")
        if self.source.commit_tick is None:
            raise ValueError("history requires an exact committed tick")

    @property
    def source_id(self) -> str:
        return self.source.source_id

    @property
    def committed_tick(self) -> Tick:
        assert self.source.commit_tick is not None
        return self.source.commit_tick

    @property
    def visible_record(self) -> VisibleRecord:
        return self.model_value


def _history_record(agent_id: AgentId, projected: ProjectedRecord) -> PersonalVisibleRecord:
    return PersonalVisibleRecord(
        agent_id=agent_id,
        model_value=projected.model_value,
        source=projected.source,
    )


class PersonalVisibleHistory:
    """Select committed records using semantic record limits only."""

    @staticmethod
    def select(
        projection: VisibilityProjectionResult,
        policy: ContextPolicy,
        *,
        committed_records: tuple[PersonalVisibleRecord, ...] = (),
        ordering: NeutralOrdering | None = None,
    ) -> tuple[PersonalVisibleRecord, ...]:
        if not isinstance(projection, VisibilityProjectionResult):
            raise TypeError("projection must be a VisibilityProjectionResult")
        if not isinstance(policy, ContextPolicy):
            raise TypeError("policy must be a ContextPolicy")
        if not isinstance(committed_records, tuple) or any(
            not isinstance(record, PersonalVisibleRecord)
            for record in committed_records
        ):
            raise TypeError("committed_records must contain PersonalVisibleRecord values")

        candidates: list[PersonalVisibleRecord] = []
        current_source_ids = {
            record.source.source_id
            for record in projection.delivered_messages
            if record.first_visible_tick == projection.bound_tick
        }
        current_source_ids.update(
            record.source.source_id
            for record in (
                *projection.incoming_pending_proposals,
                *projection.outgoing_pending_proposals,
            )
        )

        if policy.visibility.own_sent_message_history:
            candidates.extend(
                _history_record(projection.agent_id, record)
                for record in projection.own_sent_messages
            )
        if policy.visibility.delivered_messages_to_self:
            candidates.extend(
                _history_record(projection.agent_id, record)
                for record in projection.delivered_messages
            )
        candidates.extend(committed_records)

        first_active_tick = Tick(projection.bound_tick - projection.age)
        deduplicated: list[PersonalVisibleRecord] = []
        seen_projection_sources: set[tuple[str, str, str]] = set()
        for candidate in candidates:
            if candidate.agent_id != projection.agent_id:
                continue
            if candidate.source.source_state_version > projection.self_source.source_state_version:
                continue
            if not first_active_tick <= candidate.committed_tick < projection.bound_tick:
                continue
            if candidate.source_id in current_source_ids:
                continue
            dedup_key = (
                candidate.model_value.category.value,
                candidate.source.source_kind.value,
                candidate.source_id,
            )
            if dedup_key in seen_projection_sources:
                continue
            seen_projection_sources.add(dedup_key)
            deduplicated.append(candidate)

        groups: dict[int, list[PersonalVisibleRecord]] = {}
        for candidate in deduplicated:
            groups.setdefault(int(candidate.committed_tick), []).append(candidate)

        remaining = policy.history.max_prior_visible_records
        selected_by_tick: dict[int, tuple[PersonalVisibleRecord, ...]] = {}
        for tick in sorted(groups, reverse=True):
            if remaining == 0:
                break
            group = groups[tick]
            if len(group) > 1:
                if ordering is None:
                    raise ValueError("same-boundary history requires neutral ordering")
                ordered_group = ordering.order(
                    group,
                    category=f"prior_history:{tick}",
                    stable_key=lambda record: (
                        f"{record.model_value.category.value}|"
                        f"{record.source.source_kind.value}|{record.source_id}"
                    ),
                )
            else:
                ordered_group = tuple(group)
            selected_by_tick[tick] = ordered_group[:remaining]
            remaining -= len(selected_by_tick[tick])

        return tuple(
            record
            for tick in sorted(selected_by_tick)
            for record in selected_by_tick[tick]
        )


def select_personal_visible_history(
    projection: VisibilityProjectionResult,
    policy: ContextPolicy,
    *,
    committed_records: tuple[PersonalVisibleRecord, ...] = (),
    ordering: NeutralOrdering | None = None,
) -> tuple[PersonalVisibleRecord, ...]:
    return PersonalVisibleHistory.select(
        projection,
        policy,
        committed_records=committed_records,
        ordering=ordering,
    )

