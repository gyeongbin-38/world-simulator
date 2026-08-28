import pytest

from alifelm.domain import AgentId, AgentState, Duration, LifecycleState, Tick
from alifelm.domain.lifecycle import (
    can_reproduce,
    is_active,
    should_die_after_tick,
    validate_fixed_global_lifespan,
)


def agent(**overrides: object) -> AgentState:
    values: dict[str, object] = {
        "agent_id": AgentId("agent-1"),
        "birth_tick": Tick(0),
        "first_active_tick": Tick(0),
        "lifespan_ticks": Duration(3),
        "maturity_delay_ticks": Duration(1),
    }
    values.update(overrides)
    return AgentState(**values)


def test_founder_and_offspring_activation_boundaries() -> None:
    founder = agent()
    child = agent(
        agent_id=AgentId("agent-2"),
        birth_tick=Tick(4),
        first_active_tick=Tick(5),
    )

    assert founder.is_active(Tick(0))
    assert founder.is_active(Tick(2))
    assert not founder.is_active(Tick(3))
    assert not child.is_active(Tick(4))
    assert child.is_active(Tick(5))


def test_natural_death_and_final_tick() -> None:
    current = agent()
    assert current.natural_death_tick == Tick(3)
    assert should_die_after_tick(current, Tick(2))
    assert not should_die_after_tick(current, Tick(1))


def test_maturity_gates_reproduction_but_not_activity() -> None:
    current = agent(maturity_delay_ticks=Duration(2))
    assert is_active(current, Tick(1))
    assert not can_reproduce(current, Tick(1))
    assert can_reproduce(current, Tick(2))


def test_refractory_gates_reproduction_only() -> None:
    current = agent(refractory_until_tick=Tick(4), lifespan_ticks=Duration(6))
    assert current.is_active(Tick(2))
    assert not current.can_reproduce(Tick(2))
    assert current.can_reproduce(Tick(4))


def test_nonexistent_is_a_boundary_not_an_agent_record() -> None:
    with pytest.raises(ValueError):
        agent(state=LifecycleState.NONEXISTENT)


def test_dead_agent_is_terminal_for_activity() -> None:
    dead = agent(state=LifecycleState.DEAD)
    assert not dead.is_active(Tick(0))


def test_baseline_agents_share_one_fixed_global_lifespan() -> None:
    first = agent()
    second = agent(agent_id=AgentId("agent-2"))
    assert validate_fixed_global_lifespan((first, second)) == Duration(3)

    different = agent(agent_id=AgentId("agent-3"), lifespan_ticks=Duration(4))
    with pytest.raises(ValueError, match="fixed global lifespan"):
        validate_fixed_global_lifespan((first, different))
