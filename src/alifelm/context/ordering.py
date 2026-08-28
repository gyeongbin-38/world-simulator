"""Version-pinned neutral ordering for non-causal ContextPack collections."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Callable, Iterable, TypeVar

from alifelm.domain import OpportunityId, RunId, Tick

from .types import OrderingPolicy


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class OrderingBinding:
    run_id: RunId
    opportunity_id: OpportunityId
    bound_tick: Tick

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, RunId):
            raise TypeError("run_id must be a RunId")
        if not isinstance(self.opportunity_id, OpportunityId):
            raise TypeError("opportunity_id must be an OpportunityId")
        if not isinstance(self.bound_tick, Tick):
            raise TypeError("bound_tick must be a Tick")


class NeutralOrdering:
    """Compute SHA-256 ranks from frozen causal identities only."""

    def __init__(self, policy: OrderingPolicy, binding: OrderingBinding) -> None:
        if not isinstance(policy, OrderingPolicy):
            raise TypeError("policy must be an OrderingPolicy")
        if not isinstance(binding, OrderingBinding):
            raise TypeError("binding must be an OrderingBinding")
        self.policy = policy
        self.binding = binding

    def rank(self, *, category: str, stable_item_key: str) -> bytes:
        if not isinstance(category, str) or not category:
            raise ValueError("ordering category must be non-empty")
        if not isinstance(stable_item_key, str) or not stable_item_key:
            raise ValueError("stable_item_key must be non-empty")
        material = [
            self.policy.unordered_collection_algorithm,
            self.policy.ordering_seed_digest,
            self.binding.run_id.value,
            self.binding.opportunity_id.value,
            int(self.binding.bound_tick),
            category,
            stable_item_key,
        ]
        encoded = json.dumps(
            material, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).digest()

    def order(
        self,
        values: Iterable[T],
        *,
        category: str,
        stable_key: Callable[[T], str],
    ) -> tuple[T, ...]:
        materialized = tuple(values)
        keyed = tuple((value, stable_key(value)) for value in materialized)
        keys = [key for _, key in keyed]
        if len(set(keys)) != len(keys):
            raise ValueError("stable ordering keys must be unique within a category")
        return tuple(
            value
            for value, _ in sorted(
                keyed,
                key=lambda item: (
                    self.rank(category=category, stable_item_key=item[1]),
                    item[1],
                ),
            )
        )

