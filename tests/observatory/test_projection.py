from copy import deepcopy
from collections import Counter

import pytest

from alifelm.observatory import projection
from alifelm.observatory.evidence import BASE_DIGEST, GROUNDING_DIGEST, ARCHIVE_SHA, EvidenceError, IntegrityConflict

CHILD1 = "dc9506bb1d703f455def753c4a92793a98befa01114871216c901eacf7204544"
CHILD2 = "11ebd37d5eabb4e00a61e6e07045aba6a3bb0cd8774f2b220f5826c06441b07f"


def test_real_final_semantics(observation):
    f = observation.frame(20)
    assert observation.founders == 3
    assert f["metrics"] == dict(population=2, generation=1, births=2, deaths=3, messages=9, proposals=8)
    assert Counter(a["selected_action"] for a in f["attempts"]) == dict(WAIT=35, SEND=16, PROPOSE=8, ACCEPT=5)
    assert sum(e["category"] == "message" and e["canonical"] for e in f["events"]) == 9
    assert sum(e["category"] == "birth" and e["canonical"] for e in f["events"]) == 2
    assert sum(e["category"] == "death" and e["canonical"] for e in f["events"]) == 3
    assert observation.integrity()["final_result"]["birth_conflicts"] == 0


@pytest.mark.parametrize("tick", range(21))
def test_every_frame_has_no_future_leakage(observation, tick):
    f = observation.frame(tick)
    assert f["boundary_tick"] == min(tick + 1, 20)
    assert all(a["birth_tick"] <= tick for a in f["agents"])
    assert all(e["tick"] <= tick for e in f["events"])
    assert all(a["tick"] <= tick for a in f["attempts"])
    assert all(m["committed_tick"] <= tick for m in f["messages"])
    assert all(p["created_tick"] <= tick for p in f["proposals"])
    assert all(b["birth_tick"] <= tick for b in f["lineage"])
    existing = {a["id"] for a in f["agents"]}
    assert all(set(a["children"]).issubset(existing) for a in f["agents"])
    assert f["metrics"]["population"] == sum(a["lifecycle"] != "dead" for a in f["agents"])
    if tick < 19:
        assert all(a["death_tick"] is None and a["death_commit_tick"] is None for a in f["agents"])
        assert CHILD2 not in repr(f)
    if tick < 15:
        assert CHILD1 not in repr(f)


def test_first_birth_activation_rejected_send_and_two_parents(observation):
    with pytest.raises(KeyError):
        observation.agent(CHILD1, 14)
    born = observation.agent(CHILD1, 15)
    assert born["agent"]["lifecycle"] == "born"
    assert born["agent"]["age"] == 0
    assert born["agent"]["parents"] == ["EXP000_FOUNDER_C", "EXP000_FOUNDER_B"]
    assert born["agent"]["birth_tick"] == 15
    assert born["agent"]["first_active_tick"] == 16
    assert born["attempts"] == []
    active = observation.agent(CHILD1, 16)
    assert active["agent"]["lifecycle"] == "active"
    assert active["agent"]["age"] == 1
    attempt, = active["attempts"]
    assert attempt["selected_action"] == "SEND" and attempt["law_admitted"] is False
    assert attempt["target_id"] == CHILD1
    assert active["messages"] == []
    assert not any(e["category"] == "message" for e in active["events"])
    assert not any(m["committed_tick"] == 16 for m in observation.frame(16)["messages"])
    assert observation.frame(16)["lineage"][0]["parent_ids"] == born["agent"]["parents"]


@pytest.mark.parametrize("tick,action", [(17, "PROPOSE"), (18, "PROPOSE"), (19, "WAIT")])
def test_child_later_cognition_is_exact(observation, tick, action):
    attempts = observation.agent(CHILD1, tick)["attempts"]
    a = next(a for a in attempts if a["tick"] == tick)
    assert a["selected_action"] == action
    assert a["law_admitted"] is True


def test_final_child_has_no_post_horizon_action(observation):
    with pytest.raises(KeyError):
        observation.agent(CHILD2, 18)
    assert observation.agent(CHILD2, 19)["agent"]["lifecycle"] == "born"
    child = observation.agent(CHILD2, 20)
    assert child["agent"]["birth_tick"] == 19 and child["agent"]["first_active_tick"] == 20
    assert child["agent"]["lifecycle"] == "active" and child["agent"]["has_cognition"] is False
    assert child["attempts"] == []
    assert not any(a["tick"] == 20 for a in observation.frame(20)["attempts"])


def test_death_commit_boundary_and_proposal_temporal_state(observation):
    before = observation.agent("EXP000_FOUNDER_B", 18)["agent"]
    after = observation.agent("EXP000_FOUNDER_B", 19)["agent"]
    assert before["lifecycle"] == "active" and before["death_tick"] is None
    assert after["lifecycle"] == "dead" and after["death_tick"] == 20 and after["death_commit_tick"] == 19
    assert after["age"] == 20
    pid = observation.frame(15)["lineage"][0]["proposal_id"]
    assert next(p for p in observation.frame(14)["proposals"] if p["proposal_id"] == pid)["state"] == "PENDING"
    assert next(p for p in observation.frame(15)["proposals"] if p["proposal_id"] == pid)["state"] == "ACCEPTED"


def test_integrity_and_grounding_mapping(observation):
    i = observation.integrity()
    assert i["scope"] == "Full Run"
    assert i["checks"]["archive_sha256"] == ARCHIVE_SHA
    assert i["checks"]["sqlite"] == "ok" and i["checks"]["checkpoint_chain"] == 20
    assert i["recorded"]["base_digest"] == BASE_DIGEST
    assert i["recorded"]["grounding_digest"] == GROUNDING_DIGEST
    assert all(i["recorded"]["gates"].values())
    a = next(a for a in observation.frame(15)["attempts"] if a["tick"] == 15 and a["selected_action"] == "ACCEPT")
    mapping = a["proposal_grounding"]
    assert mapping["handle_map"][0]["handle"] == "R0"
    assert mapping["handle_map"][0]["canonical_proposal_id"] == a["gateway_intent"]["payload"]["proposal_id"]


def test_returned_projection_cannot_modify_future_reads(observation):
    a = observation.frame(15)
    a["agents"][0]["parents"].append("invented")
    a["events"].clear()
    assert "invented" not in repr(observation.frame(15))
    assert observation.frame(15)["events"]


@pytest.mark.parametrize("case", ["tick_hash", "birth_parent", "missing_tick", "law_admission", "future_message"])
def test_disagreement_or_missing_evidence_is_a_conflict(sealed_bundle, monkeypatch, case):
    original = projection.read_json
    def altered(path):
        record = deepcopy(original(path))
        if path.name == "tick_0015.json":
            if case == "missing_tick":
                raise EvidenceError("Missing tick evidence")
            if case == "tick_hash":
                record["commit"]["state_hash_after"] = "0" * 64
            if case == "birth_parent":
                record["fragments"][0]["birth"]["parent_ids"][0] = "EXP000_FOUNDER_A"
            if case == "law_admission":
                record["cognition"][0]["law_admitted"] = False
            if case == "future_message":
                record["events"].append(dict(event_id="invented", commit_tick=16, commit_order=3, event_type="MessageCommitted"))
        return record
    monkeypatch.setattr(projection, "read_json", altered)
    with pytest.raises((IntegrityConflict, EvidenceError)):
        projection.Observatory(sealed_bundle)
