"""GPU-free law, fault and causal-attribution gates for EXP-STIG-001."""

import json
import importlib.util
from itertools import permutations
from pathlib import Path

import pytest

from alifelm.experiments import stigmergy as s
from alifelm.persistence.cas import FileSystemArtifactStore
from alifelm.persistence.contracts import ArtifactMissingError


WAIT = s.encode({"action": "WAIT", "payload": {}})


def action(kind, **payload):
    return s.encode({"action": kind, "payload": payload})


def setup(tmp_path, condition="C"):
    tmp_path.mkdir(parents=True, exist_ok=True)
    cas = FileSystemArtifactStore(tmp_path / "cas")
    store = s.StigStore(tmp_path / "world.sqlite", cas)
    state = s.initial_state("test-" + condition, condition, cas)
    store.create(state)
    return store, state


def attempts(store, state, outputs=None):
    outputs = outputs or {}
    return [s.attempt(state, a, "model-sha", 1, s.render(state, a, store.cas),
                      outputs.get(a, WAIT), {"tokens": []}, store.cas) for a in s.AGENTS]


@pytest.mark.parametrize("condition", ["A", "B", "C"])
def test_mixed_rejection_not_wait_and_replay(tmp_path, condition):
    store, before = setup(tmp_path, condition)
    items = attempts(store, before, {"X17": action("SEND", target="X29", body="opaque payload"), "X29": b"not json"})
    after = store.commit(before, items)
    events = json.loads(store.history(before["run_id"])[0]["events"])
    assert [e["status"] for e in events] == ["ACCEPTED", "REJECTED", "ACCEPTED"]
    assert events[1]["action"] is None
    assert events[2]["action"] == "WAIT"
    assert b"not json" not in s.encode(after)
    assert b"opaque payload" not in s.encode(after)
    assert s.resolve(store.cas, items[1]["raw_ref"]) == b"not json"
    assert store.replay(before["run_id"]) == after
    assert "opaque payload" in s.render(after, "X29", store.cas).decode()
    assert "opaque payload" not in s.render(after, "X43", store.cas).decode()
    store.close()


@pytest.mark.parametrize("condition", ["A", "B", "C"])
def test_completion_order_invariant(tmp_path, condition):
    hashes = []
    for index, order in enumerate(permutations(s.AGENTS)):
        store, before = setup(tmp_path / str(index), condition)
        items = attempts(store, before, {"X17": action("SEND", target="X29", body="x"), "X29": b"{"})
        ordered = [next(i for i in items if i["actor"] == a) for a in order]
        after = store.commit(before, ordered)
        hashes.append((s.digest(after), store.history(before["run_id"])[0]["id"]))
        assert store.replay(before["run_id"]) == after
        store.close()
    assert len(set(hashes)) == 1


@pytest.mark.parametrize("condition", ["A", "B", "C"])
@pytest.mark.parametrize("point", ["BEFORE_TRANSACTION", "BEFORE_COMMIT", "AFTER_COMMIT"])
def test_crash_reopen_idempotent_atomic_outbox(tmp_path, condition, point):
    store, before = setup(tmp_path, condition)
    items = attempts(store, before, {"X17": action("SEND", target="X43", body="durable")})
    class Fault:
        def check(self, current):
            if current == point:
                raise OSError("simulated crash")
    with pytest.raises(OSError):
        store.commit(before, items, Fault())
    assert store.state(before["run_id"])["tick"] == (1 if point == "AFTER_COMMIT" else 0)
    prepared_refs = [item["attempt_id"] for item in items]
    del items
    store.close()
    store = s.StigStore(tmp_path / "world.sqlite", FileSystemArtifactStore(tmp_path / "cas"))
    items = [{**json.loads(s.resolve(store.cas, value)), "attempt_id": value} for value in prepared_refs]
    after = store.commit(before, items)
    assert store.commit(before, items) == after
    assert len(store.history(before["run_id"])) == 1
    assert store.db.execute("SELECT COUNT(*) FROM stig_outbox").fetchone()[0] == 3
    assert store.replay(before["run_id"]) == after
    store.close()


@pytest.mark.parametrize("condition,kind,accepted", [("A", "TRACE", False), ("B", "TRACE", True),
    ("C", "TRACE", True), ("A", "SET", False), ("B", "SET", False), ("C", "SET", True)])
def test_condition_capabilities(tmp_path, condition, kind, accepted):
    store, state = setup(tmp_path, condition)
    raw = action(kind, body="v") if kind == "TRACE" else action(kind, key="K17", value="v", source=None)
    after = store.commit(state, attempts(store, state, {"X17": raw}))
    event = json.loads(store.history(state["run_id"])[0]["events"])[0]
    assert (event["status"] == "ACCEPTED") == accepted
    assert store.replay(state["run_id"]) == after
    store.close()


def test_conflict_and_same_tick_trace_not_visible(tmp_path):
    store, state = setup(tmp_path)
    raw = action("SET", key="K17", value="v", source=None)
    after = store.commit(state, attempts(store, state, {"X17": raw, "X29": raw, "X43": action("REUSE", trace_id="invented")}))
    events = json.loads(store.history(state["run_id"])[0]["events"])
    assert [e["status"] for e in events] == ["CONFLICT", "CONFLICT", "REJECTED"]
    assert after["registers"] == state["registers"]
    store.close()


def test_trace_ancestry_third_agent_and_causal_intervention(tmp_path):
    store, state = setup(tmp_path)
    after = store.commit(state, attempts(store, state, {"X17": action("TRACE", body="x")}))
    source = after["traces"][0]["id"]
    reuse = action("REUSE", trace_id=source)
    assert s.attribution(after, "X29", reuse, reuse, WAIT, store.cas)["attributable"]
    assert not s.attribution(after, "X29", reuse, WAIT, WAIT, store.cas)["attributable"]
    assert not s.attribution(after, "X29", reuse, reuse, reuse, store.cas)["attributable"]
    next_state = store.commit(after, attempts(store, after, {"X29": reuse, "X43": reuse}))
    assert s.metrics(store, state["run_id"])["third_agent_reuse_traces"] == 1
    assert s.metrics(store, state["run_id"])["foreign_environment_uses"] == 2
    with_message = json.loads(s.encode(after))
    with_message["messages"].append({"sender": "X17", "target": "X29", "ref": s.put(store.cas, b"x"), "tick": 0})
    assert not s.attribution(with_message, "X29", reuse, reuse, WAIT, store.cas)["attributable"]
    set_raw = action("SET", key="K17", value="x", source=source)
    assert s.attribution(after, "X43", set_raw, set_raw, WAIT, store.cas)["register_change"]
    with pytest.raises(ValueError, match="source content"):
        s.validate(after, "X43", s.parse(action("SET", key="K17", value="y", source=source), "C"), store.cas)
    assert store.replay(state["run_id"]) == next_state
    store.close()


def test_missing_cas_is_not_repaired_on_replay(tmp_path):
    store, state = setup(tmp_path)
    after = store.commit(state, attempts(store, state, {"X17": action("TRACE", body="required")}))
    value = after["traces"][0]["ref"]
    (store.cas.root / value[:2] / value).unlink()
    with pytest.raises(ArtifactMissingError):
        store.replay(state["run_id"])
    assert not (store.cas.root / value[:2] / value).exists()
    store.close()


def test_identity_and_cas_fail_before_commit(tmp_path, monkeypatch):
    store, state = setup(tmp_path)
    items = attempts(store, state)
    items[0]["state_hash"] = "wrong"
    with pytest.raises(ValueError, match="identity"):
        store.commit(state, items)
    assert not store.history(state["run_id"])
    def fail(*args, **kwargs):
        raise OSError("CAS unavailable")
    monkeypatch.setattr(store.cas, "put_bytes", fail)
    with pytest.raises(OSError):
        attempts(store, state)
    assert store.state(state["run_id"]) == state
    store.close()


def test_outbox_tamper_and_stale_tick_fail_closed(tmp_path):
    store, state = setup(tmp_path)
    store.commit(state, attempts(store, state))
    with pytest.raises(ValueError, match="stale"):
        store.commit(state, attempts(store, state, {"X17": b"wrong"}))
    store.db.execute("DELETE FROM stig_outbox WHERE ordinal=0")
    with pytest.raises(ValueError, match="outbox"):
        store.replay(state["run_id"])
    store.close()


@pytest.mark.parametrize("raw", [b'{"action":"WAIT","action":"SEND","payload":{}}',
    b'{"action":"WAIT","payload":{},"actor":"X43"}', b'```json\n{}\n```',
    action("SEND", target="X17", body="self"), action("REUSE", trace_id="not visible"),
    b'{"action":"TRACE","payload":{"body":"\\ud800"}}'])
def test_no_repair_self_send_or_hidden_handles(tmp_path, raw):
    store, state = setup(tmp_path)
    store.commit(state, attempts(store, state, {"X17": raw}))
    event = json.loads(store.history(state["run_id"])[0]["events"])[0]
    assert event["status"] == "REJECTED"
    assert event["action"] is None
    store.close()


def test_no_hidden_authority_and_all_wait_valid(tmp_path):
    store, state = setup(tmp_path)
    context = s.render(state, "X17", store.cas)
    for hidden in (state["run_id"], s.digest(state), "reward", "cooperate", "helpful", "leader", "lineage"):
        assert hidden.encode() not in context
    after = store.commit(state, attempts(store, state))
    assert after["traces"] == after["messages"] == []
    assert s.metrics(store, state["run_id"])["actions"] == {"WAIT": 3}
    store.close()


def test_compile_all_before_infer_no_retry(tmp_path, monkeypatch):
    store, state = setup(tmp_path)
    seen = []
    original = s.render
    def rendering(*args, **kwargs):
        result = original(*args, **kwargs)
        seen.append(args[1])
        return result
    monkeypatch.setattr(s, "render", rendering)
    requests = []
    def backend(model, prompt, seed):
        assert set(seen) == set(s.AGENTS)
        requests.append(prompt)
        return b"malformed", {"model": model}
    after = s.tick(store, state["run_id"], backend, {a: "fake" for a in s.AGENTS}, 1)
    assert len(requests) == 3
    assert after["tick"] == 1
    assert s.metrics(store, state["run_id"])["rejected"] == 3
    store.close()


def runner():
    path = Path(__file__).resolve().parents[1] / "tools/exp_stig_001.py"
    spec = importlib.util.spec_from_file_location("exp_stig_runner_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runner_frozen_config_and_identity(tmp_path):
    r = runner()
    config = json.loads(r.SPEC.read_bytes())
    r.validate_config(config)
    assert len(config["models"]) == 2
    assert len(set(m["sha256"] for m in config["models"])) == 2
    assert all(len(h) == 64 for h in r.sources().values())
    assert r.seed_for(1701, 0, "X17") == r.seed_for(1701, 0, "X17")
    value = r.seal({"status": "PASS"})
    r.check_seal(value)
    r.write_new(tmp_path / "receipt.json", value)
    r.write_new(tmp_path / "receipt.json", value)
    with pytest.raises(ValueError, match="immutable"):
        r.write_new(tmp_path / "receipt.json", {"status": "different"})
    value["status"] = "tampered"
    with pytest.raises(ValueError, match="digest"):
        r.check_seal(value)
    config["retries"] = True
    with pytest.raises(ValueError, match="forbidden"):
        r.validate_config(config)


def test_operational_timing_does_not_enter_causal_identity(tmp_path):
    store, state = setup(tmp_path)
    prompt = s.render(state, "X17", store.cas)
    first = s.attempt(state, "X17", "model", 1, prompt, WAIT, {"seconds": 1}, store.cas)
    second = s.attempt(state, "X17", "model", 1, prompt, WAIT, {"seconds": 999}, store.cas)
    assert first == second
    store.close()


def test_validation_does_not_invoke_model(tmp_path, monkeypatch):
    r = runner()
    class TestResult:
        returncode = 0
        stdout = "CPU fake receipt test"
        stderr = ""
    monkeypatch.setattr(r.subprocess, "run", lambda *a, **k: TestResult())
    def prohibited(*args, **kwargs):
        raise AssertionError("model loader must not run during validation")
    monkeypatch.setattr(r, "Server", prohibited)
    r.validation_gate(tmp_path)
    receipt = json.loads((tmp_path / "validation.json").read_bytes())
    assert receipt["status"] == "PASS"
    r.check_seal(receipt)


def test_recovery_changes_only_waiting_bounds_and_namespace():
    r = runner()
    frozen_bytes = r.SPEC.read_bytes()
    base = r.effective_config()
    recovered = r.effective_config(True)
    assert recovered.pop("execution_id") == "EXP-STIG-001-R2"
    profile = recovered.pop("operational_recovery")
    assert not profile["reuse_previous_responses"]
    assert not profile["scientific_treatment_changes"]
    assert recovered["runtime"].pop("model_load_timeout_seconds") == 600
    assert recovered["runtime"]["request_timeout_seconds"] == 900
    recovered["runtime"]["request_timeout_seconds"] = base["runtime"]["request_timeout_seconds"]
    assert recovered == base
    assert r.SPEC.read_bytes() == frozen_bytes


def test_recovery_refuses_scientific_config_change(monkeypatch):
    r = runner()
    actual_sha = r.sha
    monkeypatch.setattr(r, "sha", lambda p: "wrong" if p == r.SPEC else actual_sha(p))
    with pytest.raises(ValueError, match="scientific configuration mismatch"):
        r.effective_config(True)
