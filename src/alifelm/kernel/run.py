"""Run configuration and the sole in-memory current-snapshot holder."""

from __future__ import annotations

from dataclasses import dataclass

from alifelm.domain import (
    AgentId,
    AgentState,
    Duration,
    LifecycleState,
    RunId,
    StateVersion,
    Tick,
    validate_fixed_global_lifespan,
)
from .state import RunStatus, Snapshot


@dataclass(slots=True)
class SimulationRun:
    """Canonical run configuration plus a commit-owned current snapshot."""

    run_id: RunId
    lifespan_ticks: Duration
    maturity_delay_ticks: Duration
    refractory_interval_ticks: Duration
    _snapshot: Snapshot
    population_capacity: int | None = None
    horizon: Tick | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, RunId):
            raise TypeError("run_id must be a RunId")
        if not isinstance(self.lifespan_ticks, Duration) or self.lifespan_ticks < 1:
            raise ValueError("lifespan_ticks must be a positive Duration")
        if not isinstance(self.maturity_delay_ticks, Duration):
            raise TypeError("maturity_delay_ticks must be a Duration")
        if not isinstance(self.refractory_interval_ticks, Duration):
            raise TypeError("refractory_interval_ticks must be a Duration")
        if not isinstance(self._snapshot, Snapshot):
            raise TypeError("_snapshot must be a Snapshot")
        if self._snapshot.run_id != self.run_id:
            raise ValueError("snapshot run_id must match the run")
        if self.population_capacity is not None:
            if type(self.population_capacity) is not int or self.population_capacity < 0:
                raise ValueError("population_capacity must be a non-negative integer or None")
        if self.horizon is not None and not isinstance(self.horizon, Tick):
            raise TypeError("horizon must be a Tick or None")
        if any(agent.lifespan_ticks != self.lifespan_ticks for agent in self._snapshot.agents):
            raise ValueError("all agents must use the run-level fixed lifespan")
        validate_fixed_global_lifespan(self._snapshot.agents)

    @classmethod
    def bootstrap(
        cls,
        run_id: RunId,
        *,
        lifespan_ticks: Duration,
        maturity_delay_ticks: Duration = Duration(0),
        refractory_interval_ticks: Duration = Duration(0),
        founder_ids: tuple[AgentId, ...] = (),
        population_capacity: int | None = None,
        horizon: Tick | None = None,
    ) -> SimulationRun:
        if len(set(founder_ids)) != len(founder_ids):
            raise ValueError("founder IDs must be unique")
        if any(not isinstance(agent_id, AgentId) for agent_id in founder_ids):
            raise TypeError("founder_ids must contain AgentId values")
        agents = tuple(
            AgentState(
                agent_id=agent_id,
                birth_tick=Tick(0),
                first_active_tick=Tick(0),
                lifespan_ticks=lifespan_ticks,
                maturity_delay_ticks=maturity_delay_ticks,
                state=LifecycleState.ALIVE,
            )
            for agent_id in sorted(founder_ids, key=str)
        )
        snapshot = Snapshot(
            run_id=run_id,
            tick=Tick(0),
            state_version=StateVersion(0),
            agents=agents,
            messages=(),
            proposals=(),
            events=(),
        )
        return cls(
            run_id=run_id,
            lifespan_ticks=lifespan_ticks,
            maturity_delay_ticks=maturity_delay_ticks,
            refractory_interval_ticks=refractory_interval_ticks,
            _snapshot=snapshot,
            population_capacity=population_capacity,
            horizon=horizon,
        )

    @property
    def snapshot(self) -> Snapshot:
        return self._snapshot

    @property
    def status(self) -> RunStatus:
        return self._snapshot.status

    def state_hash(self) -> str:
        return self._snapshot.state_hash()

    def _publish_snapshot(self, snapshot: Snapshot, expected_state_version: StateVersion) -> None:
        """Commit-only mutation hook; callers must use InMemoryCommitCoordinator."""

        if self._snapshot.state_version != expected_state_version:
            raise ValueError("current snapshot changed before publication")
        if snapshot.run_id != self.run_id:
            raise ValueError("published snapshot belongs to another run")
        self._snapshot = snapshot
