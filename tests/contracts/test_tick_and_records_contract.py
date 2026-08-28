from alifelm.domain import (
    ArtifactId,
    ArtifactRef,
    DomainEvent,
    EventId,
    RecordKind,
    TICK_PHASES,
    Tick,
    TickPhase,
)
from alifelm.domain.ticks import is_valid_phase_order


def test_tick_phase_order_is_frozen_and_commit_is_p11() -> None:
    assert len(TICK_PHASES) == 13
    assert TICK_PHASES[0] is TickPhase.OPEN
    assert TICK_PHASES[11] is TickPhase.COMMITTED
    assert TICK_PHASES[12] is TickPhase.PUBLISHED
    assert is_valid_phase_order(TICK_PHASES)


def test_record_categories_keep_state_event_artifact_protocol_distinct() -> None:
    assert tuple(RecordKind) == (
        RecordKind.STATE,
        RecordKind.EVENT,
        RecordKind.ARTIFACT,
        RecordKind.PROTOCOL,
    )

    evidence = ArtifactRef(ArtifactId("artifact-1"), "digest-1")
    event = DomainEvent(EventId("event-1"), "AgentBorn", Tick(3), 0, (evidence,))
    assert event.commit_tick == Tick(3)
    assert event.commit_order == 0
    assert event.artifact_refs == (evidence,)
