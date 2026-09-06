"""Durable LIVE EXP-000 run composition and read-only observation.

This module intentionally owns no lifecycle, communication, reproduction,
context, or model semantics. It only composes the already-reviewed kernel,
context pipeline, candidate runtime, and SQLite reference persistence into a
continuous experiment controller.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from alifelm.context import ContextCognitionPipeline
from alifelm.domain import AgentId, Duration, RunId, Tick
from alifelm.kernel import DeterministicKernel, RunStatus, SimulationRun, TickResult
from alifelm.persistence import SQLiteReferenceStore


@dataclass(frozen=True, slots=True)
class LiveExperimentConfig:
    run_id: str
    founders: tuple[str, ...]
    lifespan_ticks: int
    maturity_delay_ticks: int = 0
    refractory_interval_ticks: int = 0
    population_capacity: int | None = None
    horizon_ticks: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id:
            raise ValueError("run_id must be a non-empty string")
        if not isinstance(self.founders, tuple) or not self.founders:
            raise ValueError("founders must be a non-empty tuple")
        if any(not isinstance(value, str) or not value for value in self.founders):
            raise ValueError("founders must contain non-empty strings")
        if len(set(self.founders)) != len(self.founders):
            raise ValueError("founders must be unique")
        for value, name, positive in (
            (self.lifespan_ticks, "lifespan_ticks", True),
            (self.maturity_delay_ticks, "maturity_delay_ticks", False),
            (self.refractory_interval_ticks, "refractory_interval_ticks", False),
        ):
            if type(value) is not int or value < (1 if positive else 0):
                relation = "positive" if positive else "non-negative"
                raise ValueError(f"{name} must be a {relation} integer")
        if self.population_capacity is not None and (
            type(self.population_capacity) is not int or self.population_capacity < 0
        ):
            raise ValueError("population_capacity must be a non-negative integer or None")
        if self.horizon_ticks is not None and (
            type(self.horizon_ticks) is not int or self.horizon_ticks < 0
        ):
            raise ValueError("horizon_ticks must be a non-negative integer or None")

    def bootstrap_run(self) -> SimulationRun:
        return SimulationRun.bootstrap(
            RunId(self.run_id),
            lifespan_ticks=Duration(self.lifespan_ticks),
            maturity_delay_ticks=Duration(self.maturity_delay_ticks),
            refractory_interval_ticks=Duration(self.refractory_interval_ticks),
            founder_ids=tuple(AgentId(value) for value in self.founders),
            population_capacity=self.population_capacity,
            horizon=None if self.horizon_ticks is None else Tick(self.horizon_ticks),
        )


@dataclass(frozen=True, slots=True)
class LiveRunObservation:
    """Researcher-facing read-only projection of committed simulation truth."""

    run_id: str
    tick: int
    state_version: int
    status: str
    state_hash: str
    alive_agents: tuple[str, ...]
    message_count: int
    pending_proposals: tuple[str, ...]
    event_count: int
    recent_events: tuple[tuple[int, str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "tick": self.tick,
            "state_version": self.state_version,
            "status": self.status,
            "state_hash": self.state_hash,
            "alive_agents": list(self.alive_agents),
            "message_count": self.message_count,
            "pending_proposals": list(self.pending_proposals),
            "event_count": self.event_count,
            "recent_events": [
                {"commit_tick": tick, "event_type": event_type}
                for tick, event_type in self.recent_events
            ],
        }


def observe_run(run: SimulationRun, *, recent_event_limit: int = 20) -> LiveRunObservation:
    """Project committed state without mutating or advancing the simulation."""

    if type(recent_event_limit) is not int or recent_event_limit < 0:
        raise ValueError("recent_event_limit must be a non-negative integer")
    snapshot = run.snapshot
    recent = snapshot.events[-recent_event_limit:] if recent_event_limit else ()
    return LiveRunObservation(
        run_id=run.run_id.value,
        tick=int(snapshot.tick),
        state_version=int(snapshot.state_version),
        status=snapshot.status.value,
        state_hash=snapshot.state_hash(),
        alive_agents=tuple(agent.agent_id.value for agent in snapshot.agents),
        message_count=len(snapshot.messages),
        pending_proposals=tuple(
            proposal.proposal_id.value
            for proposal in snapshot.proposals
            if proposal.state.value == "PENDING"
        ),
        event_count=len(snapshot.events),
        recent_events=tuple(
            (int(event.commit_tick), event.event_type) for event in recent
        ),
    )


class LiveExperimentController:
    """Continuous durable run controller for one already-loaded candidate runtime."""

    def __init__(
        self,
        run: SimulationRun,
        runtime,
        context_pipeline: ContextCognitionPipeline,
        store: SQLiteReferenceStore,
    ) -> None:
        if not isinstance(run, SimulationRun):
            raise TypeError("run must be a SimulationRun")
        if not isinstance(context_pipeline, ContextCognitionPipeline):
            raise TypeError("context_pipeline must be a ContextCognitionPipeline")
        if not isinstance(store, SQLiteReferenceStore):
            raise TypeError("store must be a SQLiteReferenceStore")
        if not hasattr(runtime, "infer"):
            raise TypeError("runtime must provide infer(compiled_context)")
        self.run = run
        self.runtime = runtime
        self.context_pipeline = context_pipeline
        self.store = store
        self.kernel = DeterministicKernel(
            run,
            runtime,
            committer=store.commit_store,
            context_pipeline=context_pipeline,
        )

    @classmethod
    def create(
        cls,
        config: LiveExperimentConfig,
        *,
        runtime,
        context_pipeline: ContextCognitionPipeline,
        store: SQLiteReferenceStore,
    ) -> "LiveExperimentController":
        if not isinstance(config, LiveExperimentConfig):
            raise TypeError("config must be a LiveExperimentConfig")
        run = config.bootstrap_run()
        store.create_run(run)
        return cls(run, runtime, context_pipeline, store)

    @classmethod
    def resume(
        cls,
        run_id: str | RunId,
        *,
        runtime,
        context_pipeline: ContextCognitionPipeline,
        store: SQLiteReferenceStore,
    ) -> "LiveExperimentController":
        identity = run_id if isinstance(run_id, RunId) else RunId(run_id)
        run = store.load_run(identity)
        return cls(run, runtime, context_pipeline, store)

    def observe(self, *, recent_event_limit: int = 20) -> LiveRunObservation:
        return observe_run(self.run, recent_event_limit=recent_event_limit)

    def run_one_tick(self) -> TickResult:
        if self.run.status is not RunStatus.RUNNING:
            raise RuntimeError(f"run is not RUNNING: {self.run.status.value}")
        result = self.kernel.run_tick()
        if not result.commit_result.committed:
            raise RuntimeError("LIVE EXP-000 tick did not commit")
        return result

    def run_until_stop(self, *, max_ticks: int | None = None) -> tuple[TickResult, ...]:
        if max_ticks is not None and (type(max_ticks) is not int or max_ticks < 0):
            raise ValueError("max_ticks must be a non-negative integer or None")
        if max_ticks is None and self.run.horizon is None:
            raise ValueError("run_until_stop requires max_ticks or a finite run horizon")
        results: list[TickResult] = []
        while self.run.status is RunStatus.RUNNING:
            if max_ticks is not None and len(results) >= max_ticks:
                break
            results.append(self.run_one_tick())
        return tuple(results)
