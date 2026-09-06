"""Deterministic EXP-000 V1 action selector over model-derived branch scores.

This module implements only the preregistered categorical label selection
boundary.  It owns no canonical simulation state, legality masking, payload
generation, retry, fallback, repair, action-frequency target, or social
utility.  The selected label is an immutable value that a later payload stage
may consume without re-selecting the action.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import math
from typing import Mapping

from alifelm.domain import AgentId, OpportunityId, RunId, Tick


SCORE_SELECTOR_V1_DOMAIN = "WORLD_EXP000_SCORE_SELECTOR_V1"
SCORE_SELECTOR_V1_TEMPERATURE = 1.0
SCORE_SELECTOR_ACTION_ORDER = ("WAIT", "SEND", "PROPOSE", "ACCEPT", "REJECT")


@dataclass(frozen=True, slots=True)
class ScoreSelectorDecision:
    """Immutable evidence-shaped result of one V1 categorical selection."""

    selected_action: str
    score_vector: tuple[tuple[str, float], ...]
    probabilities: tuple[tuple[str, float], ...]
    seed_material: str
    seed_digest: str
    uniform_numerator: int
    uniform_denominator: int

    def __post_init__(self) -> None:
        if self.selected_action not in SCORE_SELECTOR_ACTION_ORDER:
            raise ValueError("selected_action is outside the frozen V1 action order")
        if tuple(name for name, _ in self.score_vector) != SCORE_SELECTOR_ACTION_ORDER:
            raise ValueError("score_vector must follow the frozen V1 action order")
        if tuple(name for name, _ in self.probabilities) != SCORE_SELECTOR_ACTION_ORDER:
            raise ValueError("probabilities must follow the frozen V1 action order")
        if not self.seed_material.startswith(SCORE_SELECTOR_V1_DOMAIN + "|"):
            raise ValueError("seed_material must use the frozen V1 domain")
        if len(self.seed_digest) != 64 or any(c not in "0123456789abcdef" for c in self.seed_digest):
            raise ValueError("seed_digest must be a lowercase SHA-256 digest")
        if type(self.uniform_numerator) is not int or type(self.uniform_denominator) is not int:
            raise TypeError("uniform numerator/denominator must be integers")
        if self.uniform_denominator != 1 << 257:
            raise ValueError("uniform denominator must encode (n + 0.5) / 2^256 exactly")
        if not 0 < self.uniform_numerator < self.uniform_denominator:
            raise ValueError("uniform variate must lie strictly inside (0, 1)")

    @property
    def uniform_fraction(self) -> Fraction:
        return Fraction(self.uniform_numerator, self.uniform_denominator)

    @property
    def uniform(self) -> float:
        """Human-readable float projection; exact selection uses ``uniform_fraction``."""

        return float(self.uniform_fraction)

    def probability_dict(self) -> dict[str, float]:
        return dict(self.probabilities)

    def score_dict(self) -> dict[str, float]:
        return dict(self.score_vector)


def _canonical_scores(mean_scores: Mapping[str, float]) -> tuple[tuple[str, float], ...]:
    if not isinstance(mean_scores, Mapping):
        raise TypeError("mean_scores must be a mapping")
    if set(mean_scores) != set(SCORE_SELECTOR_ACTION_ORDER):
        raise ValueError("mean_scores must contain exactly the five frozen V1 actions")
    values: list[tuple[str, float]] = []
    for action in SCORE_SELECTOR_ACTION_ORDER:
        value = mean_scores[action]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("every action score must be a real number")
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ValueError("every action score must be finite")
        values.append((action, numeric))
    return tuple(values)


def score_selector_probabilities(
    mean_scores: Mapping[str, float],
) -> tuple[tuple[str, float], ...]:
    """Return the frozen T=1.0 softmax over D1/I3 mean branch log-probabilities."""

    scores = _canonical_scores(mean_scores)
    maximum = max(value for _, value in scores)
    weights = tuple(math.exp(value - maximum) for _, value in scores)
    denominator = math.fsum(weights)
    if not math.isfinite(denominator) or denominator <= 0.0:
        raise ValueError("categorical denominator is invalid")
    return tuple(
        (action, weight / denominator)
        for (action, _), weight in zip(scores, weights, strict=True)
    )


def score_selector_seed_material(
    *,
    run_id: RunId,
    tick: Tick,
    opportunity_id: OpportunityId,
    agent_id: AgentId,
) -> str:
    """Build the exact preregistered identity string for one opportunity."""

    if not isinstance(run_id, RunId):
        raise TypeError("run_id must be a RunId")
    if not isinstance(tick, Tick):
        raise TypeError("tick must be a Tick")
    if not isinstance(opportunity_id, OpportunityId):
        raise TypeError("opportunity_id must be an OpportunityId")
    if not isinstance(agent_id, AgentId):
        raise TypeError("agent_id must be an AgentId")
    return (
        f"{SCORE_SELECTOR_V1_DOMAIN}|{run_id.value}|{int(tick)}|"
        f"{opportunity_id.value}|{agent_id.value}"
    )


def _uniform_from_digest(seed_digest: str) -> tuple[int, int]:
    n = int(seed_digest, 16)
    # (n + 0.5) / 2^256 == (2n + 1) / 2^257.  Keep this exact so a
    # platform-global RNG or float rounding can never determine the sample.
    return 2 * n + 1, 1 << 257


def select_score_action(
    mean_scores: Mapping[str, float],
    *,
    run_id: RunId,
    tick: Tick,
    opportunity_id: OpportunityId,
    agent_id: AgentId,
) -> ScoreSelectorDecision:
    """Select exactly one action using the frozen V1 categorical rule.

    There is deliberately no temperature argument, legality mask, retry,
    fallback, action rewrite, or externally supplied random variate.
    """

    score_vector = _canonical_scores(mean_scores)
    probabilities = score_selector_probabilities(mean_scores)
    seed_material = score_selector_seed_material(
        run_id=run_id,
        tick=tick,
        opportunity_id=opportunity_id,
        agent_id=agent_id,
    )
    seed_digest = hashlib.sha256(seed_material.encode("utf-8")).hexdigest()
    numerator, denominator = _uniform_from_digest(seed_digest)
    uniform = Fraction(numerator, denominator)

    cumulative = 0.0
    selected = SCORE_SELECTOR_ACTION_ORDER[-1]
    for index, (action, probability) in enumerate(probabilities):
        cumulative = math.fsum((cumulative, probability))
        # The final branch closes the categorical partition despite any last
        # bit of binary floating-point summation error.
        if index == len(probabilities) - 1 or Fraction.from_float(cumulative) >= uniform:
            selected = action
            break

    return ScoreSelectorDecision(
        selected_action=selected,
        score_vector=score_vector,
        probabilities=probabilities,
        seed_material=seed_material,
        seed_digest=seed_digest,
        uniform_numerator=numerator,
        uniform_denominator=denominator,
    )
