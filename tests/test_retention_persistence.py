"""EXP-STIG-003 deterministic and grounding tests."""

import json

import pytest

from alifelm.experiments import retention_affordance as a
from alifelm.experiments import retention_world as w
from alifelm.persistence.cas import FileSystemArtifactStore


def setup(tmp_path, condition="B"):
    cas = FileSystemArtifactStore(tmp_path / "cas")
    store = w.RetentionStore(tmp_path / "world.sqlite", cas)
    state = w.initial_state("test-003-" + condition, condition)
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


def test_initial_affordance_shape_and_window(tmp_path):
    store, state = setup(tmp_path, "B")
    _, x17 = a.build(state, "X17")
    assert x17["visible"]["known_facts"] == [{"fact_id": "F1", "value": "amber"}]
    assert x17["visible"]["field_scans"] == []
    assert x17["visible"]["submission_window_open"] is False
    assert x17["visible"]["submission_tick"] == 3
    assert list(x17["actions"]) == ["WAIT", "SEND", "INSPECT", "TRACE"]
    assert x17["actions"]["INSPECT"]["fact_ids"] == ["F2"]
    assert x17["actions"]["TRACE"]["fact_ids"] == ["F1"]
    assert "REUSE" not in x17["actions"]
    assert "SUBMIT" not in x17["actions"]
    assert "F2" in x17["grammar"]
    store.close()


def test_scan_is_ephemeral_and_captureable(tmp_path):
    store, state = setup(tmp_path, "B")
    after = store.commit(state, attempts(store, state, {"X17": raw("INSPECT", fact_id="F2")}))
    assert after["scans"]["X17"] == {"F2": "cedar"}
    assert after["knowledge"]["X17"] == {"F1": "amber"}
    assert after["exploration_cost"]["X17"] == 1
    _, desc = a.build(after, "X17")
    assert desc["visible"]["field_scans"] == [{"fact_id": "F2", "value": "cedar",
                                             "expires": "when the submission window opens"}]
    assert desc["actions"]["TRACE"]["fact_ids"] == ["F1", "F2"]
    assert "INSPECT" not in desc["actions"]
    store.close()


def test_trace_of_scanned_fact_persists_it(tmp_path):
    store, state = setup(tmp_path, "B")
    after = store.commit(state, attempts(store, state, {"X17": raw("INSPECT", fact_id="F2")}))
    traced = store.commit(after, attempts(store, after, {"X17": raw("TRACE", fact_id="F2", value="cedar", note="keep")}))
    assert len(traced["traces"]) == 1
    trace = traced["traces"][0]
    assert trace["fact_id"] == "F2" and trace["value"] == "cedar" and trace["creator"] == "X17"
    assert w.metrics(store, state["run_id"])["objective_persistence_acts"] == 1
    store.close()


def test_trace_of_unknown_fact_is_rejected(tmp_path):
    store, state = setup(tmp_path, "B")
    after = store.commit(state, attempts(store, state, {"X17": raw("TRACE", fact_id="F2", value="cedar", note="no scan")}))
    event = json.loads(store.history(state["run_id"])[0]["events"])[0]
    assert event["status"] == "REJECTED"
    assert after["traces"] == []
    store.close()


def test_scan_expires_at_submission_window(tmp_path):
    store, state = setup(tmp_path, "B")
    current = state
    current = store.commit(current, attempts(store, current, {"X17": raw("INSPECT", fact_id="F2")}))
    current = store.commit(current, attempts(store, current))
    current = store.commit(current, attempts(store, current))
    assert current["tick"] == 3
    assert current["scans"]["X17"] == {}
    _, desc = a.build(current, "X17")
    assert desc["visible"]["submission_window_open"] is True
    assert desc["visible"]["field_scans"] == []
    assert list(desc["actions"]) == ["WAIT", "SUBMIT"]
    store.close()


def test_inspect_not_afforded_one_tick_before_window(tmp_path):
    store, state = setup(tmp_path, "B")
    current = store.commit(state, attempts(store, state))
    current = store.commit(current, attempts(store, current))
    assert current["tick"] == 2
    _, desc = a.build(current, "X17")
    assert "INSPECT" not in desc["actions"]
    store.close()


def test_early_submit_is_rejected_without_mutation(tmp_path):
    store, state = setup(tmp_path, "B")
    after = store.commit(state, attempts(store, state, {"X17": raw("SUBMIT", answer="F1=amber|F2=cedar")}))
    event = json.loads(store.history(state["run_id"])[0]["events"])[0]
    assert event["status"] == "REJECTED"
    assert event["parser"] == "PASS"
    assert event["affordance"] == "FAIL"
    assert after["submissions"] == []
    store.close()


def test_full_chain_inspect_trace_reuse_submit_verified(tmp_path):
    store, state = setup(tmp_path, "B")
    current = store.commit(state, attempts(store, state, {"X17": raw("INSPECT", fact_id="F2")}))
    current = store.commit(current, attempts(store, current, {"X17": raw("TRACE", fact_id="F2", value="cedar", note="n")}))
    trace_id = current["traces"][0]["id"]
    current = store.commit(current, attempts(store, current, {"X17": raw("REUSE", trace_id=trace_id)}))
    assert current["knowledge"]["X17"] == {"F1": "amber", "F2": "cedar"}
    current = store.commit(current, attempts(store, current, {"X17": raw("SUBMIT", answer="F1=amber|F2=cedar")}))
    submission = current["submissions"][-1]
    assert submission["correct"] is True
    assert submission["verified"] is True
    assert submission["provenance"] == {}
    assert store.replay(state["run_id"]) == current
    store.close()


def test_submit_via_visible_trace_is_correct_but_unverified(tmp_path):
    store, state = setup(tmp_path, "B")
    current = store.commit(state, attempts(store, state, {"X17": raw("INSPECT", fact_id="F2")}))
    current = store.commit(current, attempts(store, current, {"X17": raw("TRACE", fact_id="F2", value="cedar", note="n")}))
    current = store.commit(current, attempts(store, current))
    current = store.commit(current, attempts(store, current, {"X17": raw("SUBMIT", answer="F1=amber|F2=cedar")}))
    submission = current["submissions"][-1]
    assert submission["correct"] is True
    assert submission["verified"] is False
    assert submission["provenance"] == {"F2": "environmental_trace"}
    store.close()


def test_c_commit_channel_and_non_c_rejection(tmp_path):
    store, state = setup(tmp_path, "C")
    current = store.commit(state, attempts(store, state, {"X17": raw("INSPECT", fact_id="F2")}))
    current = store.commit(current, attempts(store, current, {"X17": raw("COMMIT", fact_id="F2", value="cedar")}))
    assert current["world_state"] == {"F2": "cedar"}
    current = store.commit(current, attempts(store, current))
    current = store.commit(current, attempts(store, current, {"X17": raw("SUBMIT", answer="F1=amber|F2=cedar")}))
    submission = current["submissions"][-1]
    assert submission["correct"] is True
    assert submission["provenance"] == {"F2": "environmental_world_state"}
    store.close()

    store_b, state_b = setup(tmp_path / "b", "B")
    after_b = store_b.commit(state_b, attempts(store_b, state_b, {"X17": raw("COMMIT", fact_id="F1", value="amber")}))
    event_b = json.loads(store_b.history(state_b["run_id"])[0]["events"])[0]
    assert event_b["status"] == "REJECTED"
    assert after_b["world_state"] == {}
    store_b.close()


def test_unexplained_correct_submit_in_a_is_flagged(tmp_path):
    store, state = setup(tmp_path / "a", "A")
    current = state
    for _ in range(3):
        current = store.commit(current, attempts(store, current))
    current = store.commit(current, attempts(store, current, {"X17": raw("SUBMIT", answer="F1=amber|F2=cedar")}))
    submission = current["submissions"][-1]
    assert submission["correct"] is True
    assert submission["provenance"] == {"F2": "unexplained"}
    store.close()


def test_stale_and_malformed_inputs_fail_without_mutation(tmp_path):
    store, state = setup(tmp_path, "B")
    malformed = raw("REUSE", trace_id="TSTALE")
    after = store.commit(state, attempts(store, state, {"X17": malformed}))
    event = json.loads(store.history(state["run_id"])[0]["events"])[0]
    assert event["parser"] == "PASS"
    assert event["affordance"] == "FAIL"
    assert event["status"] == "REJECTED"
    assert after["traces"] == []
    with pytest.raises(ValueError):
        w.parse(b'{"action":"WAIT","payload":{}} trailing', "B")
    store.close()


def test_fault_idempotency(tmp_path):
    store, state = setup(tmp_path, "B")
    items = attempts(store, state)
    class Fault:
        def check(self, point):
            if point == "BEFORE_COMMIT":
                raise OSError("fault")
    with pytest.raises(OSError):
        store.commit(state, items, Fault())
    assert store.state(state["run_id"])["tick"] == 0
    store.close()
