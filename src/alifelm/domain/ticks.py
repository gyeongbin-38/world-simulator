"""The frozen causal phase vocabulary for one simulation tick."""

from __future__ import annotations

from enum import StrEnum


class TickPhase(StrEnum):
    OPEN = "P0_OPEN_TICK"
    SNAPSHOT_BOUND = "P1_BIND_SNAPSHOT"
    OPPORTUNITIES_ENUMERATED = "P2_ENUMERATE_OPPORTUNITIES"
    CONTEXTS_COMPILED = "P3_COMPILE_CONTEXTS"
    COGNITION_EXECUTED = "P4_EXECUTE_COGNITION"
    INTENTS_CLOSED = "P5_CLOSE_INTENT_BATCH"
    INTENTS_VALIDATED = "P6_VALIDATE_INTENTS"
    DOMAIN_PLANNED = "P7_PLAN_DOMAIN_TRANSITIONS"
    EXOGENOUS_PLANNED = "P8_PLAN_EXOGENOUS_EFFECTS"
    LIFECYCLE_PLANNED = "P9_PLAN_LIFECYCLE"
    CAPACITY_EVALUATED = "P10_EVALUATE_CAPACITY_AND_HORIZON"
    COMMITTED = "P11_ATOMIC_COMMIT"
    PUBLISHED = "P12_PUBLISH_NEXT_SNAPSHOT"


TICK_PHASES: tuple[TickPhase, ...] = tuple(TickPhase)


def is_valid_phase_order(phases: tuple[TickPhase, ...]) -> bool:
    """Return whether phases exactly match the canonical frozen sequence."""

    return phases == TICK_PHASES
