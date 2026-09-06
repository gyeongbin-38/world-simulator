"""Explicit JSON read models; never inputs to canonical simulation code."""
from typing import Any, Literal, TypedDict


class AgentObservation(TypedDict):
    id: str
    alias: str
    slot: int
    generation: int
    lifecycle: Literal["born", "active", "dead"]
    birth_tick: int
    first_active_tick: int
    death_tick: int | None
    death_commit_tick: int | None
    age: int
    parents: list[str]
    children: list[str]
    has_cognition: bool


class EventObservation(TypedDict):
    id: str
    tick: int
    category: str
    title: str
    detail: str
    agent_ids: list[str]
    canonical: bool
    evidence_ref: str
    record: dict[str, Any]


class ActionAttemptObservation(TypedDict):
    id: str
    tick: int
    agent_id: str
    selected_action: str
    law_admitted: bool
    target_id: str | None
    evidence_ref: str
    raw_ref: str | None
    gateway_intent: dict[str, Any] | None
    proposal_grounding: dict[str, Any] | None
    probabilities: dict[str, float]
    score_vector: dict[str, float]
    parse_status: str


class TickObservation(TypedDict):
    run_id: str
    tick: int
    boundary_tick: int
    state_version: int
    state_hash: str
    status: str
    mode: str
    metrics: dict[str, int]
    agents: list[AgentObservation]
    attempts: list[ActionAttemptObservation]
    events: list[EventObservation]
    messages: list[dict[str, Any]]
    proposals: list[dict[str, Any]]
    lineage: list[dict[str, Any]]
    evidence_ref: str | None
    projection_schema: str
