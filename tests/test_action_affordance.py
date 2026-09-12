"""R4 grounded-affordance and commit-boundary tests."""

import json

import pytest

from alifelm.experiments import action_affordance as a
from alifelm.experiments import grounded_world as g
from alifelm.experiments import stigmergy as s
from alifelm.persistence.cas import FileSystemArtifactStore


def setup(tmp_path, condition="C"):
    cas = FileSystemArtifactStore(tmp_path / "cas")
    store = g.GroundedStore(tmp_path / "world.sqlite", cas)
    state = s.initial_state("r4-" + condition, condition, cas)
    store.create(state)
    return store, state


def raw(action, **payload):
    return s.encode({"action": action, "payload": payload})


def grounded_attempts(store, state, outputs=None):
    outputs = outputs or {}
    items = []
    for actor in s.AGENTS:
        prompt, desc = a.build(state, actor, store.cas)
        items.append(g.attempt(
            state, actor, "model", 1, prompt, desc,
            outputs.get(actor, raw("WAIT")), {"tokens": []}, store.cas,
        ))
    return items


def add_trace(state, store, trace_id="TCTRL", creator="X29", body=b"controlled"):
    ref = s.put(store, body)
    updated = json.loads(s.encode(state))
    updated["traces"].append({"id": trace_id, "creator": creator, "ref": ref, "parent": None, "tick": 0})
    return updated


def test_no_trace_omits_reuse_and_grounds_targets(tmp_path):
    store, state = setup(tmp_path, "B")
    desc = a.affordance(state, "X17", store.cas)
    assert list(desc["actions"]) == ["WAIT", "SEND", "TRACE"]
    assert "reuseobject" not in desc["grammar"]
    assert 'TCTRL' not in desc["grammar"]
    assert desc["visible_refs"]["peer_ids"] == ["X29", "X43"]
    a.validate_candidate({"action": "SEND", "payload": {"target": "X29", "body": "x"}}, desc)
    with pytest.raises(ValueError, match="not afforded"):
        a.validate_candidate({"action": "REUSE", "payload": {"trace_id": "TCTRL"}}, desc)
    store.close()


def test_visible_trace_and_c_targets_are_exactly_grounded(tmp_path):
    store, state = setup(tmp_path, "C")
    state = add_trace(state, store.cas)
    desc = a.affordance(state, "X17", store.cas)
    assert list(desc["actions"]) == ["WAIT", "SEND", "TRACE", "REUSE", "SET"]
    assert desc["actions"]["REUSE"]["trace_ids"] == ["TCTRL"]
    assert desc["actions"]["SET"]["key_ids"] == ["K17", "K29", "K43"]
    assert desc["actions"]["SET"]["source_ids"] == ["TCTRL", None]
    assert 'TCTRL' in desc["grammar"]
    assert 'TNOT' not in desc["grammar"]
    a.validate_candidate({"action": "REUSE", "payload": {"trace_id": "TCTRL"}}, desc)
    a.validate_candidate({"action": "SET", "payload": {"key": "K17", "value": "v", "source": None}}, desc)
    with pytest.raises(ValueError, match="not afforded"):
        a.validate_candidate({"action": "REUSE", "payload": {"trace_id": "TNOT"}}, desc)
    with pytest.raises(ValueError, match="not afforded"):
        a.validate_candidate({"action": "SEND", "payload": {"target": "X17", "body": "self"}}, desc)
    store.close()


def test_descriptor_binds_state_version_and_context(tmp_path):
    store, state = setup(tmp_path, "B")
    prompt, first = a.build(state, "X17", store.cas)
    assert first["state_hash"] == s.digest(state)
    assert first["context_version"] == s.digest(state)
    assert first["grammar_sha256"] == __import__("hashlib").sha256(first["grammar"].encode()).hexdigest()
    assert first["affordance_sha256"] == s.digest({k: v for k, v in first.items() if k != "affordance_sha256"})
    changed = json.loads(s.encode(state))
    changed["tick"] = 1
    _, second = a.build(changed, "X17", store.cas)
    assert second["context_version"] != first["context_version"]
    store.close()


def test_grounded_commit_accepts_bootstrap_and_replays(tmp_path):
    store, state = setup(tmp_path, "B")
    attempts = grounded_attempts(store, state, {"X17": raw("TRACE", body="first")})
    after = store.commit(state, attempts)
    events = json.loads(store.history(state["run_id"])[0]["events"])
    assert events[0]["status"] == "ACCEPTED"
    assert events[0]["action"] == "TRACE"
    assert len(after["traces"]) == 1
    assert store.replay(state["run_id"]) == after
    store.close()


def test_grounded_commit_rejects_stale_reference_before_gateway(tmp_path):
    store, state = setup(tmp_path, "B")
    attempts = grounded_attempts(store, state, {"X17": raw("REUSE", trace_id="TSTALE")})
    after = store.commit(state, attempts)
    event = json.loads(store.history(state["run_id"])[0]["events"])[0]
    assert event["parser"] == "PASS"
    assert event["affordance"] == "FAIL"
    assert event["status"] == "REJECTED"
    assert after["traces"] == []
    assert store.replay(state["run_id"]) == after
    store.close()


@pytest.mark.parametrize("raw_value", [
    b'{"action":"WAIT","action":"TRACE","payload":{}}',
    b'{"action":"WAIT","payload":{},"authority":"admin"}',
    b'{"action":"WAIT","payload":{}} trailing',
])
def test_strict_parser_rejects_malformed_inputs(tmp_path, raw_value):
    store, state = setup(tmp_path, "C")
    attempts = grounded_attempts(store, state, {"X17": raw_value})
    after = store.commit(state, attempts)
    event = json.loads(store.history(state["run_id"])[0]["events"])[0]
    assert event["status"] == "REJECTED"
    assert after["traces"] == []
    store.close()
