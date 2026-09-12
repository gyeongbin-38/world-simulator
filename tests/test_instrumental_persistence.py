"""EXP-STIG-002 deterministic and grounding tests."""

import json

import pytest

from alifelm.experiments import instrumental_affordance as a
from alifelm.experiments import instrumental_world as w
from alifelm.persistence.cas import FileSystemArtifactStore


def setup(tmp_path, condition="B"):
    cas = FileSystemArtifactStore(tmp_path / "cas")
    store = w.InstrumentalStore(tmp_path / "world.sqlite", cas)
    state = w.initial_state("test-002-" + condition, condition)
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


def test_partial_knowledge_and_grounded_actions(tmp_path):
    store, state = setup(tmp_path, "B")
    _, x17 = a.build(state, "X17")
    assert x17["visible"]["known_facts"] == [{"fact_id": "F1", "value": "amber"}]
    assert x17["visible"]["inspectable_fact_ids"] == ["F2"]
    assert list(x17["actions"]) == ["WAIT", "SEND", "INSPECT", "SUBMIT", "TRACE"]
    assert "REUSE" not in x17["actions"]
    assert "F2" in x17["grammar"]
    store.close()


def test_trace_and_reuse_are_state_grounded(tmp_path):
    store, state = setup(tmp_path, "B")
    trace_attempts = attempts(store, state, {"X17": raw("TRACE", fact_id="F1", value="amber", note="useful")})
    after = store.commit(state, trace_attempts)
    assert len(after["traces"]) == 1
    _, desc = a.build(after, "X29")
    assert desc["actions"]["REUSE"]["trace_ids"] == [after["traces"][0]["id"]]
    reuse = raw("REUSE", trace_id=after["traces"][0]["id"])
    second = attempts(store, after, {"X29": reuse})
    after2 = store.commit(after, second)
    assert after2["knowledge"]["X29"]["F1"] == "amber"
    assert w.metrics(store, state["run_id"])["trace_reuse_count"] == 1
    assert store.replay(state["run_id"]) == after2
    store.close()


def test_inspect_has_measurable_cost_and_submit_is_checkable(tmp_path):
    store, state = setup(tmp_path, "B")
    after = store.commit(state, attempts(store, state, {"X17": raw("INSPECT", fact_id="F2")}))
    assert after["knowledge"]["X17"]["F2"] == "cedar"
    assert after["exploration_cost"]["X17"] == 1
    answer = "F1=amber|F2=cedar"
    after2 = store.commit(after, attempts(store, after, {"X17": raw("SUBMIT", answer=answer)}))
    assert after2["submissions"][-1]["correct"] is True
    assert w.metrics(store, state["run_id"])["accuracy"] == 1.0
    store.close()


def test_c_commit_is_canonical_and_non_c_is_rejected(tmp_path):
    store, state = setup(tmp_path, "C")
    after = store.commit(state, attempts(store, state, {"X17": raw("COMMIT", fact_id="F1", value="amber")}))
    assert after["world_state"] == {"F1": "amber"}
    event = json.loads(store.history(state["run_id"])[0]["events"])[0]
    assert event["status"] == "ACCEPTED"
    assert store.replay(state["run_id"]) == after
    store.close()

    store_a, state_a = setup(tmp_path / "a", "A")
    after_a = store_a.commit(state_a, attempts(store_a, state_a, {"X17": raw("COMMIT", fact_id="F1", value="amber")}))
    event_a = json.loads(store_a.history(state_a["run_id"])[0]["events"])[0]
    assert event_a["status"] == "REJECTED"
    assert after_a["world_state"] == {}
    store_a.close()


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
