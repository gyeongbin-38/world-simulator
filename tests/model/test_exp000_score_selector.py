from __future__ import annotations

from dataclasses import FrozenInstanceError
import math
import random

import pytest

from alifelm.domain import AgentId, OpportunityId, RunId, Tick
from alifelm.model.p2_d1_boundary import D1_ACTION_ORDER
from alifelm.model.score_selector import (
    SCORE_SELECTOR_ACTION_ORDER,
    SCORE_SELECTOR_V1_DOMAIN,
    SCORE_SELECTOR_V1_TEMPERATURE,
    score_selector_probabilities,
    score_selector_seed_material,
    select_score_action,
)


@pytest.fixture
def identity():
    return {
        "run_id": RunId("RUN_A"),
        "tick": Tick(7),
        "opportunity_id": OpportunityId("OPP_0001"),
        "agent_id": AgentId("AGENT_A"),
    }


def _scores(**updates: float) -> dict[str, float]:
    values = {action: 0.0 for action in SCORE_SELECTOR_ACTION_ORDER}
    values.update(updates)
    return values


def test_frozen_action_order_matches_d1_and_temperature_is_one() -> None:
    assert SCORE_SELECTOR_ACTION_ORDER == D1_ACTION_ORDER
    assert SCORE_SELECTOR_V1_TEMPERATURE == 1.0


def test_softmax_probabilities_follow_known_ratio() -> None:
    scores = {
        "WAIT": math.log(1.0),
        "SEND": math.log(2.0),
        "PROPOSE": math.log(3.0),
        "ACCEPT": math.log(4.0),
        "REJECT": math.log(5.0),
    }
    probabilities = dict(score_selector_probabilities(scores))
    assert probabilities == pytest.approx(
        {
            "WAIT": 1 / 15,
            "SEND": 2 / 15,
            "PROPOSE": 3 / 15,
            "ACCEPT": 4 / 15,
            "REJECT": 5 / 15,
        },
        abs=1e-15,
    )


def test_equal_scores_are_uniform() -> None:
    assert dict(score_selector_probabilities(_scores())) == pytest.approx(
        {action: 0.2 for action in SCORE_SELECTOR_ACTION_ORDER},
        abs=1e-15,
    )


def test_seed_material_and_uniform_are_frozen(identity) -> None:
    material = score_selector_seed_material(**identity)
    assert material == "WORLD_EXP000_SCORE_SELECTOR_V1|RUN_A|7|OPP_0001|AGENT_A"
    assert material.startswith(SCORE_SELECTOR_V1_DOMAIN + "|")

    decision = select_score_action(_scores(), **identity)
    assert decision.seed_digest == "8f89a3f85bb56c5c0d761a049b6dd23e936dbe55ce29ad2f8014c988f7fdf3ea"
    assert decision.uniform == pytest.approx(0.5606939774840691, abs=0.0)
    assert 0 < decision.uniform_fraction < 1


def test_known_uniform_selects_first_cumulative_probability_ge_u(identity) -> None:
    decision = select_score_action(_scores(), **identity)
    # Equal scores partition the unit interval into five 0.2-wide bins.
    # u ~= 0.56069 therefore lands in the third frozen branch.
    assert decision.selected_action == "PROPOSE"


def test_decision_is_reproducible_and_independent_of_global_rng(identity) -> None:
    scores = _scores(WAIT=0.7, SEND=0.4, PROPOSE=-0.2, ACCEPT=-0.5, REJECT=-2.0)
    random.seed(1)
    first = select_score_action(scores, **identity)
    for _ in range(100):
        random.random()
    random.seed(999999)
    second = select_score_action(scores, **identity)
    assert first == second


def test_completion_order_does_not_change_identity_bound_decisions() -> None:
    scores = _scores(WAIT=0.3, SEND=0.2, PROPOSE=0.1, ACCEPT=0.0, REJECT=-0.1)
    identities = [
        {
            "run_id": RunId("RUN_X"),
            "tick": Tick(3),
            "opportunity_id": OpportunityId(f"OPP_{index}"),
            "agent_id": AgentId(f"AGENT_{index}"),
        }
        for index in range(4)
    ]

    def evaluate(items):
        return {
            item["agent_id"].value: select_score_action(scores, **item)
            for item in items
        }

    assert evaluate(identities) == evaluate(tuple(reversed(identities)))


def test_selected_label_is_immutable_before_payload_stage(identity) -> None:
    decision = select_score_action(_scores(), **identity)
    with pytest.raises(FrozenInstanceError):
        decision.selected_action = "WAIT"  # type: ignore[misc]


def test_selector_has_no_legality_mask_or_fallback_surface(identity) -> None:
    decision = select_score_action(_scores(), **identity)
    assert set(decision.probability_dict()) == set(SCORE_SELECTOR_ACTION_ORDER)
    with pytest.raises(TypeError):
        select_score_action(_scores(), availability={"WAIT": True}, **identity)  # type: ignore[call-arg]


def test_score_contract_fails_closed(identity) -> None:
    missing = _scores()
    missing.pop("REJECT")
    with pytest.raises(ValueError):
        select_score_action(missing, **identity)

    extra = _scores(EXTRA=0.0)
    with pytest.raises(ValueError):
        select_score_action(extra, **identity)

    nonfinite = _scores(WAIT=float("nan"))
    with pytest.raises(ValueError):
        select_score_action(nonfinite, **identity)
