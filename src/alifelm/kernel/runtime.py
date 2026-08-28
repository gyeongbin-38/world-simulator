"""Deterministic fake cognition runtime used by the vertical slice."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable, Mapping
import hashlib

from alifelm.domain import (
    ActionIntent,
    ActionKind,
    AgentId,
    IntentId,
    Tick,
    WaitAction,
)

from .opportunities import CognitionOpportunity


@dataclass(frozen=True, slots=True)
class FakeDeterministicModelRuntime:
    """Return scripted intents without invoking an LLM or model backend."""

    script: Mapping[tuple[Tick, AgentId], ActionIntent] | Callable[[CognitionOpportunity], ActionIntent] | None = None

    def __post_init__(self) -> None:
        if self.script is None or callable(self.script):
            return
        script = dict(self.script)
        for key, intent in script.items():
            if (
                not isinstance(key, tuple)
                or len(key) != 2
                or not isinstance(key[0], Tick)
                or not isinstance(key[1], AgentId)
            ):
                raise TypeError("script keys must be (Tick, AgentId) pairs")
            if not isinstance(intent, ActionIntent):
                raise TypeError("script values must be ActionIntent values")
        object.__setattr__(self, "script", MappingProxyType(script))

    def infer(self, opportunity: CognitionOpportunity) -> ActionIntent:
        if callable(self.script):
            scripted = self.script(opportunity)
            if not isinstance(scripted, ActionIntent):
                raise TypeError("fake runtime callable must return an ActionIntent")
            if scripted.actor_id != opportunity.agent_id or scripted.tick != opportunity.tick:
                raise ValueError("scripted intent actor/tick does not match opportunity")
            return scripted
        key = (opportunity.tick, opportunity.agent_id)
        scripted = None if self.script is None else self.script.get(key)
        if scripted is not None:
            if scripted.actor_id != opportunity.agent_id or scripted.tick != opportunity.tick:
                raise ValueError("scripted intent actor/tick does not match opportunity")
            return scripted
        return ActionIntent(
            intent_id=_default_intent_id(
                opportunity.run_id, opportunity.tick, opportunity.agent_id
            ),
            actor_id=opportunity.agent_id,
            tick=opportunity.tick,
            kind=ActionKind.WAIT,
            payload=WaitAction(),
        )


def _default_intent_id(run_id, tick: Tick, agent_id: AgentId) -> IntentId:
    value = f"wait|{run_id.value}|{int(tick)}|{agent_id.value}"
    return IntentId(hashlib.sha256(value.encode("utf-8")).hexdigest())
