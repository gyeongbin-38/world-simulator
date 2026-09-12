"""Persistent instrumental-persistence world for EXP-STIG-002.

This is a bounded pilot world: agents have overlapping individual objectives,
partial private knowledge, a costly INSPECT action, persistent TRACE/REUSE in B
and C, and a validated canonical COMMIT action in C.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import sqlite3
from typing import Any

from alifelm.persistence.migrations import configure_connection
from . import instrumental_affordance as afford
from . import stigmergy as base

VERSION = "EXP-STIG-002/1.0.0"
AGENTS = ("X17", "X29", "X43")
FACTS = {"F1": "amber", "F2": "cedar", "F3": "violet"}
OBJECTIVES = {
    "X17": {"id": "OBJ-X17", "fact_ids": ["F1", "F2"], "answer_format": "F1=value|F2=value"},
    "X29": {"id": "OBJ-X29", "fact_ids": ["F1", "F3"], "answer_format": "F1=value|F3=value"},
    "X43": {"id": "OBJ-X43", "fact_ids": ["F2", "F3"], "answer_format": "F2=value|F3=value"},
}
INITIAL_KNOWLEDGE = {"X17": {"F1": FACTS["F1"]}, "X29": {"F3": FACTS["F3"]}, "X43": {"F2": FACTS["F2"]}}


def encode(value: Any) -> bytes:
    return base.encode(value)


def digest(value: Any) -> str:
    return base.digest(value)


def _expected_answer(state: dict, actor: str) -> str:
    return "|".join(f"{fact}={state['hidden_facts'][fact]}" for fact in state["objectives"][actor]["fact_ids"])


def initial_state(run_id: str, condition: str) -> dict:
    if condition not in afford.ACTIONS:
        raise ValueError("unknown condition")
    return {
        "run_id": run_id,
        "condition": condition,
        "tick": 0,
        "agents": list(AGENTS),
        "objectives": json.loads(json.dumps(OBJECTIVES)),
        "hidden_facts": dict(FACTS),
        "knowledge": json.loads(json.dumps(INITIAL_KNOWLEDGE)),
        "exploration_cost": {actor: 0 for actor in AGENTS},
        "messages": [],
        "traces": [],
        "submissions": [],
        "world_state": {},
    }


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


def parse(raw: bytes, condition: str) -> dict:
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
    if not isinstance(value, dict) or set(value) != {"action", "payload"}:
        raise ValueError("expected action and payload only")
    action, payload = value["action"], value["payload"]
    if not isinstance(action, str) or action not in afford.ACTIONS[condition] or not isinstance(payload, dict):
        raise ValueError("unavailable action or payload")
    fields = {
        "WAIT": set(),
        "SEND": {"target", "body"},
        "INSPECT": {"fact_id"},
        "SUBMIT": {"answer"},
        "TRACE": {"fact_id", "value", "note"},
        "REUSE": {"trace_id"},
        "COMMIT": {"fact_id", "value"},
    }[action]
    if set(payload) != fields:
        raise ValueError("payload fields mismatch")
    for key, item in payload.items():
        if not isinstance(item, str) or len(item) > 256:
            raise ValueError("payload type or capacity")
        item.encode("utf-8", errors="strict")
    return value


def validate(state: dict, actor: str, candidate: dict, cas) -> None:
    action, payload = candidate["action"], candidate["payload"]
    if actor not in state["agents"] or action not in afford.ACTIONS[state["condition"]]:
        raise ValueError("actor or condition")
    if action == "SEND" and (payload["target"] not in state["agents"] or payload["target"] == actor):
        raise ValueError("target is not a visible peer")
    objective = state["objectives"][actor]
    known = state["knowledge"][actor]
    if action == "INSPECT":
        if payload["fact_id"] not in objective["fact_ids"] or payload["fact_id"] in known:
            raise ValueError("fact is not inspectable")
    if action == "TRACE":
        fact_id = payload["fact_id"]
        if fact_id not in known or state["hidden_facts"][fact_id] != payload["value"]:
            raise ValueError("trace value is not known")
    if action == "REUSE":
        if payload["trace_id"] not in {trace["id"] for trace in state["traces"]}:
            raise ValueError("trace is not visible")
    if action == "COMMIT":
        fact_id = payload["fact_id"]
        if fact_id not in known or state["hidden_facts"][fact_id] != payload["value"]:
            raise ValueError("commit value is not known")
        if state["condition"] != "C":
            raise ValueError("world commit unavailable")
    if action == "SUBMIT":
        payload["answer"].encode("utf-8", errors="strict")


def attempt(state: dict, actor: str, model: str, seed: int, prompt: bytes,
            desc: dict, raw: bytes, response: dict, cas) -> dict:
    context_ref = base.put(cas, prompt)
    raw_ref = base.put(cas, raw)
    base.put(cas, encode(response))
    response_ref = base.put(cas, encode({"model": model, "seed": seed, "context_ref": context_ref, "raw_ref": raw_ref}))
    core = {
        "actor": actor,
        "model": model,
        "seed": seed,
        "context_ref": context_ref,
        "raw_ref": raw_ref,
        "response_ref": response_ref,
        "opportunity": digest([VERSION, state["run_id"], state["tick"], actor]),
        "state_hash": digest(state),
        "condition": state["condition"],
        "affordance_ref": base.put(cas, encode(desc)),
        "affordance_sha256": afford.descriptor_hash(desc),
        "context_version": desc["context_version"],
        "grammar_sha256": desc["grammar_sha256"],
    }
    core["attempt_id"] = base.put(cas, encode(core))
    return core


def _check_affordance(state: dict, actor: str, item: dict, cas) -> dict:
    expected_prompt, expected = afford.build(state, actor)
    if base.resolve(cas, item["context_ref"]) != expected_prompt:
        raise ValueError("grounded context mismatch")
    recorded = json.loads(base.resolve(cas, item["affordance_ref"]))
    if recorded != expected or item["affordance_sha256"] != afford.descriptor_hash(expected):
        raise ValueError("affordance descriptor mismatch")
    if item["condition"] != state["condition"] or item["context_version"] != expected["context_version"]:
        raise ValueError("affordance version mismatch")
    return expected


def plan(state: dict, attempts: list[dict], cas) -> tuple[dict, list[dict]]:
    if len(attempts) != len(state["agents"]) or sorted(a["actor"] for a in attempts) != sorted(state["agents"]):
        raise ValueError("exactly one attempt per opportunity required")
    events = []
    candidates = {}
    for item in sorted(attempts, key=lambda a: a["actor"]):
        actor = item["actor"]
        core = {key: value for key, value in item.items() if key != "attempt_id"}
        if digest(core) != item["attempt_id"] or item["state_hash"] != digest(state):
            raise ValueError("attempt identity mismatch")
        if item["opportunity"] != digest([VERSION, state["run_id"], state["tick"], actor]):
            raise ValueError("opportunity mismatch")
        event = {
            "actor": actor,
            "attempt_id": item["attempt_id"],
            "status": "ACCEPTED",
            "action": None,
            "parser": "NOT_RUN",
            "affordance": "NOT_RUN",
            "gateway": "NOT_RUN",
            "context_version": item.get("context_version"),
            "grammar_sha256": item.get("grammar_sha256"),
        }
        try:
            desc = _check_affordance(state, actor, item, cas)
            event["affordance"] = "PASS"
            response = json.loads(base.resolve(cas, item["response_ref"]))
            if response != {key: item[key] for key in ("model", "seed", "context_ref", "raw_ref")}:
                raise ValueError("generation evidence identity mismatch")
            raw = base.resolve(cas, item["raw_ref"])
            candidate = parse(raw, state["condition"])
            event["parser"] = "PASS"
            afford.validate_candidate(candidate, desc)
            validate(state, actor, candidate, cas)
            event.update(gateway="PASS", action=candidate["action"])
            candidates[actor] = candidate
        except (ValueError, TypeError, UnicodeError, json.JSONDecodeError) as error:
            event.update(status="REJECTED", reason=str(error))
            if event["parser"] == "PASS" and event["gateway"] == "NOT_RUN":
                event["affordance"] = "FAIL"
            elif event["parser"] == "NOT_RUN":
                event["parser"] = "FAIL"
            elif event["affordance"] == "PASS":
                event["gateway"] = "FAIL"
        events.append(event)

    after = json.loads(encode(state))
    for event in events:
        actor = event["actor"]
        candidate = candidates.get(actor)
        if candidate is None:
            continue
        action, payload = candidate["action"], candidate["payload"]
        if action == "SEND":
            after["messages"].append({
                "sender": actor, "target": payload["target"], "body": payload["body"], "tick": state["tick"],
            })
            event["target"] = payload["target"]
        elif action == "INSPECT":
            fact_id = payload["fact_id"]
            after["knowledge"][actor][fact_id] = state["hidden_facts"][fact_id]
            after["exploration_cost"][actor] += 1
            event.update(fact_id=fact_id, cost=1)
        elif action == "TRACE":
            trace_id = "T" + digest([state["run_id"], actor, state["tick"], payload["fact_id"], payload["value"]])[:16]
            after["traces"].append({
                "id": trace_id, "creator": actor, "fact_id": payload["fact_id"],
                "value": payload["value"], "note": payload["note"], "parent": None, "tick": state["tick"],
            })
            event.update(trace_id=trace_id, fact_id=payload["fact_id"])
        elif action == "REUSE":
            trace = next(trace for trace in state["traces"] if trace["id"] == payload["trace_id"])
            after["knowledge"][actor][trace["fact_id"]] = trace["value"]
            event.update(trace_id=trace["id"], fact_id=trace["fact_id"], source_creator=trace["creator"])
        elif action == "SUBMIT":
            expected = _expected_answer(state, actor)
            submission = {
                "actor": actor, "answer": payload["answer"], "expected": expected,
                "correct": payload["answer"] == expected,
                "tick": state["tick"], "exploration_cost": state["exploration_cost"][actor],
            }
            after["submissions"].append(submission)
            event.update(correct=submission["correct"], exploration_cost=submission["exploration_cost"])
        elif action == "COMMIT":
            fact_id = payload["fact_id"]
            changed = after["world_state"].get(fact_id) != payload["value"]
            after["world_state"][fact_id] = payload["value"]
            event.update(fact_id=fact_id, changed=changed)
    after["tick"] += 1
    return after, events


class InstrumentalStore:
    def __init__(self, path, cas):
        self.cas = cas
        self.db = sqlite3.connect(path)
        configure_connection(self.db)
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS inst_runs(id TEXT PRIMARY KEY, initial BLOB NOT NULL, state BLOB NOT NULL, hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS inst_commits(run TEXT, tick INTEGER, id TEXT UNIQUE, request BLOB, events BLOB, state BLOB, hash TEXT, PRIMARY KEY(run,tick));
        CREATE TABLE IF NOT EXISTS inst_outbox(commit_id TEXT, ordinal INTEGER, event BLOB, PRIMARY KEY(commit_id,ordinal));
        """)

    def close(self):
        self.db.close()

    def create(self, state):
        encoded = encode(state)
        old = self.db.execute("SELECT initial FROM inst_runs WHERE id=?", (state["run_id"],)).fetchone()
        if old:
            if old[0] != encoded:
                raise ValueError("run already exists with different initial state")
            return
        with self.db:
            self.db.execute("INSERT INTO inst_runs VALUES(?,?,?,?)", (state["run_id"], encoded, encoded, digest(state)))

    def state(self, run_id):
        row = self.db.execute("SELECT state,hash FROM inst_runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise ValueError("unknown run")
        state = json.loads(row[0])
        if digest(state) != row[1]:
            raise ValueError("materialized state hash mismatch")
        return state

    def history(self, run_id):
        return self.db.execute("SELECT * FROM inst_commits WHERE run=? ORDER BY tick", (run_id,)).fetchall()

    def commit(self, before, attempts, fault=None):
        request = {"before": digest(before), "attempts": sorted(attempts, key=lambda x: x["actor"])}
        commit_id = digest([VERSION, before["run_id"], before["tick"], request])
        after, events = plan(before, request["attempts"], self.cas)
        if fault:
            fault.check("BEFORE_TRANSACTION")
        try:
            self.db.execute("BEGIN IMMEDIATE")
            old = self.db.execute("SELECT request,state FROM inst_commits WHERE id=?", (commit_id,)).fetchone()
            if old:
                if old[0] != encode(request) or old[1] != encode(after):
                    raise ValueError("idempotency corruption")
                self.db.rollback()
                return json.loads(old[1])
            if digest(self.state(before["run_id"])) != digest(before):
                raise ValueError("stale boundary")
            self.db.execute("INSERT INTO inst_commits VALUES(?,?,?,?,?,?,?)", (
                before["run_id"], before["tick"], commit_id, encode(request), encode(events), encode(after), digest(after),
            ))
            for index, event in enumerate(events):
                self.db.execute("INSERT INTO inst_outbox VALUES(?,?,?)", (commit_id, index, encode(event)))
            self.db.execute("UPDATE inst_runs SET state=?,hash=? WHERE id=?", (encode(after), digest(after), before["run_id"]))
            if fault:
                fault.check("BEFORE_COMMIT")
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise
        if fault:
            fault.check("AFTER_COMMIT")
        return after

    def replay(self, run_id):
        row = self.db.execute("SELECT initial FROM inst_runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise ValueError("unknown run")
        state = json.loads(row[0])
        for entry in self.history(run_id):
            request = json.loads(entry["request"])
            if entry["tick"] != state["tick"] or request["before"] != digest(state):
                raise ValueError("replay boundary mismatch")
            if entry["id"] != digest([VERSION, run_id, state["tick"], request]):
                raise ValueError("commit identity mismatch")
            after, events = plan(state, request["attempts"], self.cas)
            if encode(after) != entry["state"] or digest(after) != entry["hash"] or encode(events) != entry["events"]:
                raise ValueError("replay state/event mismatch")
            outbox = self.db.execute("SELECT event FROM inst_outbox WHERE commit_id=? ORDER BY ordinal", (entry["id"],)).fetchall()
            if [row[0] for row in outbox] != [encode(event) for event in events]:
                raise ValueError("replay outbox mismatch")
            state = after
        if state != self.state(run_id):
            raise ValueError("replay/materialized disagreement")
        return state


def metrics(store: InstrumentalStore, run_id: str) -> dict:
    final = store.replay(run_id)
    events = [event for row in store.history(run_id) for event in json.loads(row["events"])]
    accepted = [event for event in events if event["status"] == "ACCEPTED"]
    submissions = final["submissions"]
    correct = sum(bool(item["correct"]) for item in submissions)
    return {
        "opportunities": len(events),
        "accepted": len(accepted),
        "rejected": len(events) - len(accepted),
        "actions": dict(Counter(event["action"] for event in accepted)),
        "trace_count": len(final["traces"]),
        "trace_bootstrap_count": sum(event["action"] == "TRACE" for event in accepted),
        "trace_reuse_count": sum(event["action"] == "REUSE" for event in accepted),
        "submissions": len(submissions),
        "correct_submissions": correct,
        "accuracy": correct / len(submissions) if submissions else 0.0,
        "exploration_cost": dict(final["exploration_cost"]),
        "world_state": dict(final["world_state"]),
        "direct_messages": sum(event["action"] == "SEND" for event in accepted),
        "final_state_hash": digest(final),
    }
