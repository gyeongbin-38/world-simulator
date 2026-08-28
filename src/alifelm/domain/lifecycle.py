"""Deterministic lifecycle values and predicates from LC-210."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from .identifiers import AgentId
from .values import Duration, Tick


class LifecycleState(StrEnum):
    NONEXISTENT = "NONEXISTENT"
    ALIVE = "ALIVE"
    DEAD = "DEAD"


@dataclass(frozen=True, slots=True)
class AgentState:
    """A successfully created agent record.

    ``NONEXISTENT`` is a transition boundary, not a valid persisted agent
    record.  Newborns have ``birth_tick=t`` and ``first_active_tick=t+1``;
    founders may use zero for both fields.
    """

    agent_id: AgentId
    birth_tick: Tick
    first_active_tick: Tick
    lifespan_ticks: Duration
    maturity_delay_ticks: Duration
    state: LifecycleState = LifecycleState.ALIVE
    refractory_until_tick: Tick | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.agent_id, AgentId):
            raise TypeError("agent_id must be an AgentId")
        if not isinstance(self.birth_tick, Tick):
            raise TypeError("birth_tick must be a Tick")
        if not isinstance(self.first_active_tick, Tick):
            raise TypeError("first_active_tick must be a Tick")
        if not isinstance(self.lifespan_ticks, Duration):
            raise TypeError("lifespan_ticks must be a Duration")
        if not isinstance(self.maturity_delay_ticks, Duration):
            raise TypeError("maturity_delay_ticks must be a Duration")
        if not isinstance(self.state, LifecycleState):
            raise TypeError("state must be a LifecycleState")
        if self.state is LifecycleState.NONEXISTENT:
            raise ValueError("a created AgentState cannot be NONEXISTENT")
        if self.first_active_tick < self.birth_tick:
            raise ValueError("first_active_tick cannot precede birth_tick")
        if self.lifespan_ticks < 1:
            raise ValueError("lifespan_ticks must be positive")
        if self.refractory_until_tick is not None and not isinstance(
            self.refractory_until_tick, Tick
        ):
            raise TypeError("refractory_until_tick must be a Tick or None")

    @property
    def natural_death_tick(self) -> Tick:
        return natural_death_tick(self.first_active_tick, self.lifespan_ticks)

    @property
    def maturity_tick(self) -> Tick:
        return maturity_tick(self.first_active_tick, self.maturity_delay_ticks)

    def is_active(self, tick: Tick) -> bool:
        return is_active(self, tick)

    def is_mature(self, tick: Tick) -> bool:
        _require_tick(tick)
        return self.state is LifecycleState.ALIVE and tick >= self.maturity_tick

    def is_refractory(self, tick: Tick) -> bool:
        _require_tick(tick)
        return (
            self.refractory_until_tick is not None
            and tick < self.refractory_until_tick
        )

    def can_reproduce(self, tick: Tick) -> bool:
        return can_reproduce(self, tick)


def natural_death_tick(first_active_tick: Tick, lifespan_ticks: Duration) -> Tick:
    """Compute ``first_active_tick + lifespan_ticks``."""

    _require_tick(first_active_tick)
    if not isinstance(lifespan_ticks, Duration):
        raise TypeError("lifespan_ticks must be a Duration")
    return Tick(first_active_tick + lifespan_ticks)


def maturity_tick(first_active_tick: Tick, maturity_delay_ticks: Duration) -> Tick:
    """Compute ``first_active_tick + maturity_delay_ticks``."""

    _require_tick(first_active_tick)
    if not isinstance(maturity_delay_ticks, Duration):
        raise TypeError("maturity_delay_ticks must be a Duration")
    return Tick(first_active_tick + maturity_delay_ticks)


def is_active(agent: AgentState, tick: Tick) -> bool:
    """Apply the canonical half-open active interval."""

    _require_tick(tick)
    return (
        agent.state is LifecycleState.ALIVE
        and agent.first_active_tick <= tick < agent.natural_death_tick
    )


def should_die_after_tick(agent: AgentState, tick: Tick) -> bool:
    """Whether natural lifecycle planning removes the agent at ``t -> t+1``."""

    return is_active(agent, tick) and agent.natural_death_tick == tick + 1


def can_reproduce(agent: AgentState, tick: Tick) -> bool:
    """Apply only baseline lifecycle gates, never mate-selection criteria."""

    return is_active(agent, tick) and agent.is_mature(tick) and not agent.is_refractory(tick)


def validate_fixed_global_lifespan(agents: Iterable[AgentState]) -> Duration | None:
    """Validate the EXP-000 fixed lifespan invariant for one agent collection.

    The run-level owner/configuration is intentionally not implemented here;
    this foundation check gives that future boundary a deterministic guard.
    """

    lifespans = {agent.lifespan_ticks for agent in agents}
    if len(lifespans) > 1:
        raise ValueError("all baseline agents must use one fixed global lifespan")
    return next(iter(lifespans), None)


def _require_tick(value: Tick) -> None:
    if not isinstance(value, Tick):
        raise TypeError("tick must be a Tick")
