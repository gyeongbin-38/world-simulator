"""EXP-STIG-004 stigmergic persistence dependence tests."""

import json

import pytest

from alifelm.experiments import retention_affordance as a
from alifelm.experiments import retention_world as w
from alifelm.persistence.cas import FileSystemArtifactStore

WORLD = "EXP-STIG-004"


def setup(tmp_path, condition="B"):
    cas = FileSystemArtifactStore(tmp_path / "cas")
    store = w.RetentionStore(tmp_path / "world.sqlite", cas)
    state = w.initial_state("test-004-" + condition, condition, WORLD)
    store.create(state)
    return store, state


def raw(action, **payload):
    return w.encode({"action": action, "payload": payload})


def attempts(store, state, outputs=None):
    outputs = outputs or {}
    result = []
    for actor in w.AGENTS:
        prompt, desc = a.build(state, actor)
        result.append(w.attempt(state, actor, "model", 1, prompt, desc, outputs.get(actor, raw("WAIT")), {"tokens": []}, store.cas))
    return result


def test_legacy_world_state_is_byte_identical():
    state = w.initial_state("legacy-check", "B")
    assert "world_id" not in state
    assert "version" not in state
    assert "peer_objectives_visible" not in state
    assert state["scannable"] == {"X17": ["F2"], "X29": ["F4"], "X43": ["F6"]}


def test_stig005_world_law_parity_with_stig004():
    for condition in ("A", "B", "C"):
        five = w.initial_state("parity-005", condition, "EXP-STIG-005")
        four = w.initial_state("parity-005", condition, "EXP-STIG-004")
        five.pop("world_id"); five.pop("version")
        four.pop("world_id"); four.pop("version")
        assert w.digest(five) == w.digest(four)
        assert five["peer_objectives_visible"] is True
        assert five["scannable"] == {"X17": ["F4"], "X29": ["F2"], "X43": ["F6"]}


def test_stig004_scannable_dependence_and_public_board(tmp_path):
    store, state = setup(tmp_path, "B")
    assert state["world_id"] == WORLD
    assert state["peer_objectives_visible"] is True
    assert state["scannable"] == {"X17": ["F4"], "X29": ["F2"], "X43": ["F6"]}
    _, x17 = a.build(state, "X17")
    # X17 cannot inspect its own missing fact; it can inspect X29's missing fact.
    assert x17["actions"]["INSPECT"]["fact_ids"] == ["F4"]
    board = {p["agent"]: p for p in x17["visible"]["peer_objectives"]}
    assert set(board) == {"X29", "X43"}
    assert board["X29"]["fact_ids"] == ["F3", "F4"]
    assert board["X29"]["scannable"] == ["F2"]
    _, x29 = a.build(state, "X29")
    assert x29["actions"]["INSPECT"]["fact_ids"] == ["F2"]
    assert {p["agent"] for p in x29["visible"]["peer_objectives"]} == {"X17", "X43"}
    _, x43 = a.build(state, "X43")
    assert x43["actions"]["INSPECT"]["fact_ids"] == ["F6"]
    store.close()


def test_cross_scan_materializes_and_expires(tmp_path):
    store, state = setup(tmp_path, "B")
    after = store.commit(state, attempts(store, state, {"X17": raw("INSPECT", fact_id="F4")}))
    assert after["scans"]["X17"] == {"F4": "umber"}
    assert after["scans"]["X29"] == {}
    # The scan is private to its creator: X29 sees no scan and cannot TRACE it.
    _, desc29 = a.build(after, "X29")
    assert desc29["visible"]["field_scans"] == []
    assert "TRACE" not in desc29["actions"]
    store.close()


def test_commit_of_unscannable_missing_fact_is_rejected(tmp_path):
    store, state = setup(tmp_path, "C")
    after = store.commit(state, attempts(store, state, {"X17": raw("COMMIT", fact_id="F2", value="cedar")}))
    event = next(e for e in json.loads(store.history(state["run_id"])[0]["events"]) if e["actor"] == "X17")
    assert event["status"] == "REJECTED"
    assert after["world_state"] == {}
    store.close()


def test_send_cannot_inject_value_into_peer_grammar(tmp_path):
    store, state = setup(tmp_path, "B")
    after = store.commit(state, attempts(store, state, {
        "X29": raw("SEND", target="X17", body="F2=cedar")}))
    assert len(after["messages"]) == 1
    windowed = dict(after)
    windowed["tick"] = after["submission_tick"]
    _, desc = a.build(windowed, "X17")
    assert '"cedar"' not in desc["grammar"]
    assert '"umber"' not in desc["grammar"]
    assert '"amber"' in desc["grammar"]
    store.close()


def test_b_trace_chain_completes_for_dependent_objective(tmp_path):
    store, state = setup(tmp_path, "B")
    after = store.commit(state, attempts(store, state, {"X17": raw("INSPECT", fact_id="F4")}))
    traced = store.commit(after, attempts(store, after, {"X17": raw("TRACE", fact_id="F4", value="umber", note="for-x29")}))
    trace_id = traced["traces"][0]["id"]
    # The peer's trace is visible to X29 and enters X29's submission options.
    reused = store.commit(traced, attempts(store, traced, {"X29": raw("REUSE", trace_id=trace_id)}))
    assert reused["knowledge"]["X29"]["F4"] == "umber"
    assert reused["tick"] == reused["submission_tick"]
    submitted = store.commit(reused, attempts(store, reused, {
        "X29": raw("SUBMIT", answer="F3=violet|F4=umber")}))
    submission = submitted["submissions"][-1]
    assert submission["correct"] is True and submission["verified"] is True
    metrics = w.metrics(store, state["run_id"])
    assert metrics["objective_persistence_acts"] == 0  # F4 is not X17's objective
    assert metrics["trace_bootstrap_count"] == 1 and metrics["trace_reuse_count"] == 1
    store.close()


def test_c_commit_chain_completes_for_dependent_objective(tmp_path):
    store, state = setup(tmp_path, "C")
    after = store.commit(state, attempts(store, state, {"X17": raw("INSPECT", fact_id="F4")}))
    committed = store.commit(after, attempts(store, after, {"X17": raw("COMMIT", fact_id="F4", value="umber")}))
    assert committed["world_state"] == {"F4": "umber"}
    # X29's window grammar now offers the peer-carried value.
    windowed = dict(committed)
    windowed["tick"] = committed["submission_tick"]
    _, desc = a.build(windowed, "X29")
    assert '"umber"' in desc["grammar"]
    window = store.commit(committed, attempts(store, committed))
    submitted = store.commit(window, attempts(store, window, {
        "X29": raw("SUBMIT", answer="F3=violet|F4=umber")}))
    submission = submitted["submissions"][-1]
    assert submission["correct"] is True
    assert submission["verified"] is False  # no REUSE internalization
    assert submission["provenance"]["F4"] == "environmental_world_state"
    store.close()


def test_a_dependent_objective_is_impossible(tmp_path):
    store, state = setup(tmp_path, "A")
    after = store.commit(state, attempts(store, state, {"X29": raw("INSPECT", fact_id="F2")}))
    assert after["scans"]["X29"] == {"F2": "cedar"}
    assert "TRACE" not in a.affordance(after, "X29")["actions"]
    assert "COMMIT" not in a.affordance(after, "X29")["actions"]
    window = dict(after)
    window["tick"] = after["submission_tick"]
    window["scans"] = {actor: {} for actor in w.AGENTS}
    _, desc = a.build(window, "X17")
    assert '"cedar"' not in desc["grammar"]
    store.close()


def test_window_boundary_still_holds(tmp_path):
    store, state = setup(tmp_path, "B")
    after = store.commit(state, attempts(store, state, {"X17": raw("INSPECT", fact_id="F4")}))
    windowed = dict(after)
    windowed["tick"] = after["submission_tick"]
    windowed["scans"] = {actor: {} for actor in w.AGENTS}
    _, desc = a.build(windowed, "X17")
    assert list(desc["actions"]) == ["WAIT", "SUBMIT"]
    assert desc["actions"]["SUBMIT"]["values"] == ["amber"]
    store.close()


def test_replay_and_metrics_for_cross_world(tmp_path):
    store, state = setup(tmp_path, "C")
    current = state
    for step in range(4):
        outputs = {}
        if step == 0:
            outputs = {"X17": raw("INSPECT", fact_id="F4"), "X29": raw("INSPECT", fact_id="F2"),
                       "X43": raw("INSPECT", fact_id="F6")}
        elif step == 1:
            outputs = {"X29": raw("COMMIT", fact_id="F2", value="cedar")}
        elif step == 3:
            outputs = {"X17": raw("SUBMIT", answer="F1=amber|F2=cedar")}
        current = store.commit(current, attempts(store, current, outputs))
    submission = current["submissions"][-1]
    assert submission["correct"] is True
    assert submission["provenance"] == {"F2": "environmental_world_state"}
    assert store.replay(state["run_id"]) == current
    metrics = w.metrics(store, state["run_id"])
    assert metrics["commit_count"] == 1 and metrics["correct_submissions"] == 1
    assert metrics["objective_persistence_acts"] == 0  # other-serving, not X29's own
    store.close()
