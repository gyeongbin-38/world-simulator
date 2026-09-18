"""Persistence-necessary retention world for EXP-STIG-003.

Bounded pilot world: each agent's missing objective fact is observable only as
a private ephemeral scan that never survives into the submission window, so a
correct terminal answer requires carrying the scanned value through a
committed persistent channel (TRACE/REUSE in B, plus COMMIT in C).
"""
from __future__ import annotations

from collections import Counter
import json
import sqlite3
from typing import Any

from alifelm.persistence.migrations import configure_connection
from . import retention_affordance as afford
from . import stigmergy as base

VERSION = "EXP-STIG-003/1.0.0"
AGENTS = ("X17", "X29", "X43")
SUBMISSION_TICK = 3
TICKS = 4
FACTS = {"F1": "amber", "F2": "cedar", "F3": "violet",
         "F4": "umber", "F5": "onyx", "F6": "maple"}
OBJECTIVES = {
    "X17": {"id": "OBJ-X17", "fact_ids": ["F1", "F2"], "answer_format": "F1=value|F2=value"},
    "X29": {"id": "OBJ-X29", "fact_ids": ["F3", "F4"], "answer_format": "F3=value|F4=value"},
    "X43": {"id": "OBJ-X43", "fact_ids": ["F5", "F6"], "answer_format": "F5=value|F6=value"},
}
INITIAL_KNOWLEDGE = {"X17": {"F1": FACTS["F1"]}, "X29": {"F3": FACTS["F3"]}, "X43": {"F5": FACTS["F5"]}}
SCANNABLE = {"X17": ["F2"], "X29": ["F4"], "X43": ["F6"]}

WORLDS = {
    "EXP-STIG-003": {
        "version": VERSION,
        "objectives": OBJECTIVES,
        "initial_knowledge": INITIAL_KNOWLEDGE,
        "scannable": SCANNABLE,
    },
    "EXP-STIG-004": {
        "version": "EXP-STIG-004/1.0.0",
        "objectives": OBJECTIVES,
        "initial_knowledge": INITIAL_KNOWLEDGE,
        "scannable": {"X17": ["F4"], "X29": ["F2"], "X43": ["F6"]},
        "peer_objectives_visible": True,
        "inspect_scope": "scannable",
        "affordance_policy": "EXP-STIG-004-GROUNDED-AFFORDANCE-V1",
        "builder_version": "retention-stigmergic-grammar-v1",
    },
    # EXP-STIG-005 reuses the EXP-STIG-004 world law unchanged; the experiment
    # differs only in model cohort (three families) and assignment coverage.
    "EXP-STIG-005": {
        "version": "EXP-STIG-005/1.0.0",
        "objectives": OBJECTIVES,
        "initial_knowledge": INITIAL_KNOWLEDGE,
        "scannable": {"X17": ["F4"], "X29": ["F2"], "X43": ["F6"]},
        "peer_objectives_visible": True,
        "inspect_scope": "scannable",
        "affordance_policy": "EXP-STIG-004-GROUNDED-AFFORDANCE-V1",
        "builder_version": "retention-stigmergic-grammar-v1",
    },
    # EXP-STIG-006 keeps the EXP-STIG-005 dependence structure but removes
    # raw trace values from window answer options: a trace's value reaches
    # the submission grammar only through persistent knowledge (REUSE).
    "EXP-STIG-006": {
        "version": "EXP-STIG-006/1.0.0",
        "objectives": OBJECTIVES,
        "initial_knowledge": INITIAL_KNOWLEDGE,
        "scannable": {"X17": ["F4"], "X29": ["F2"], "X43": ["F6"]},
        "peer_objectives_visible": True,
        "inspect_scope": "scannable",
        "trace_direct_read": False,
        "affordance_policy": "EXP-STIG-004-GROUNDED-AFFORDANCE-V1",
        "builder_version": "retention-stigmergic-grammar-v1",
    },
}


def encode(value: Any) -> bytes:
    return base.encode(value)


def digest(value: Any) -> str:
    return base.digest(value)


def _expected_answer(state: dict, actor: str) -> str:
    return "|".join(f"{fact}={state['hidden_facts'][fact]}" for fact in state["objectives"][actor]["fact_ids"])


def initial_state(run_id: str, condition: str, world_id: str = "EXP-STIG-003") -> dict:
    if condition not in afford.ACTIONS:
        raise ValueError("unknown condition")
    spec = WORLDS[world_id]
    state = {
        "run_id": run_id,
        "condition": condition,
        "tick": 0,
        "ticks": TICKS,
        "submission_tick": SUBMISSION_TICK,
        "agents": list(AGENTS),
        "objectives": json.loads(json.dumps(spec["objectives"])),
        "hidden_facts": dict(FACTS),
        "knowledge": json.loads(json.dumps(spec["initial_knowledge"])),
        "scannable": json.loads(json.dumps(spec["scannable"])),
        "scans": {actor: {} for actor in AGENTS},
        "exploration_cost": {actor: 0 for actor in AGENTS},
        "messages": [],
        "traces": [],
        "submissions": [],
        "world_state": {},
    }
    if world_id != "EXP-STIG-003":
        state.update({
            "world_id": world_id,
            "version": spec["version"],
            "initial_knowledge": json.loads(json.dumps(spec["initial_knowledge"])),
            "peer_objectives_visible": bool(spec.get("peer_objectives_visible")),
            "inspect_scope": spec.get("inspect_scope", "missing"),
            "affordance_policy": spec.get("affordance_policy", afford.POLICY_ID),
            "builder_version": spec.get("builder_version", afford.BUILDER_VERSION),
        })
        if "trace_direct_read" in spec:
            state["trace_direct_read"] = spec["trace_direct_read"]
    return state


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
    if state["tick"] == state["submission_tick"] and action not in ("WAIT", "SUBMIT"):
        raise ValueError("submission window action set")
    if action == "SEND" and (payload["target"] not in state["agents"] or payload["target"] == actor):
        raise ValueError("target is not a visible peer")
    objective = state["objectives"][actor]
    known = state["knowledge"][actor]
    scan = state["scans"][actor]
    if action == "INSPECT":
        if (payload["fact_id"] not in state["scannable"][actor]
                or payload["fact_id"] in known or payload["fact_id"] in scan):
            raise ValueError("fact is not inspectable")
        if state["tick"] + 1 >= state["submission_tick"]:
            raise ValueError("scan cannot materialize before the submission window")
    if action in ("TRACE", "COMMIT"):
        fact_id = payload["fact_id"]
        if fact_id not in known and fact_id not in scan:
            raise ValueError("fact is neither known nor scanned")
        if state["hidden_facts"][fact_id] != payload["value"]:
            raise ValueError("value is not the fact value")
        if action == "COMMIT" and state["condition"] != "C":
            raise ValueError("world commit unavailable")
    if action == "REUSE":
        if payload["trace_id"] not in {trace["id"] for trace in state["traces"]}:
            raise ValueError("trace is not visible")
    if action == "SUBMIT":
        if state["tick"] != state["submission_tick"]:
            raise ValueError("submission window closed")
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
        "opportunity": digest([state.get("version", VERSION), state["run_id"], state["tick"], actor]),
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


def _provenance(state: dict, actor: str, fact_id: str) -> str:
    if fact_id in state["knowledge"][actor]:
        return "persistent_knowledge"
    value = state["hidden_facts"][fact_id]
    if any(trace["fact_id"] == fact_id and trace["value"] == value for trace in state["traces"]):
        return "environmental_trace"
    if state["world_state"].get(fact_id) == value:
        return "environmental_world_state"
    if any(value in message["body"] for message in state["messages"]
           if actor in (message["sender"], message["target"])):
        return "peer_relay"
    return "unexplained"


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
        if item["opportunity"] != digest([state.get("version", VERSION), state["run_id"], state["tick"], actor]):
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
            after["scans"][actor][fact_id] = state["hidden_facts"][fact_id]
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
            missing = [fact for fact in state["objectives"][actor]["fact_ids"]
                       if fact not in state["knowledge"][actor]]
            submission = {
                "actor": actor, "answer": payload["answer"], "expected": expected,
                "correct": payload["answer"] == expected,
                "tick": state["tick"], "exploration_cost": state["exploration_cost"][actor],
                "verified": all(fact in state["knowledge"][actor] for fact in state["objectives"][actor]["fact_ids"]),
                "provenance": {fact: _provenance(state, actor, fact) for fact in missing},
            }
            after["submissions"].append(submission)
            event.update(correct=submission["correct"], verified=submission["verified"],
                         provenance=submission["provenance"],
                         exploration_cost=submission["exploration_cost"])
        elif action == "COMMIT":
            fact_id = payload["fact_id"]
            changed = after["world_state"].get(fact_id) != payload["value"]
            after["world_state"][fact_id] = payload["value"]
            event.update(fact_id=fact_id, changed=changed)
    after["tick"] += 1
    if after["tick"] == after["submission_tick"]:
        for actor in after["agents"]:
            after["scans"][actor] = {}
    return after, events


class RetentionStore:
    def __init__(self, path, cas):
        self.cas = cas
        self.db = sqlite3.connect(path)
        configure_connection(self.db)
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS ret_runs(id TEXT PRIMARY KEY, initial BLOB NOT NULL, state BLOB NOT NULL, hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS ret_commits(run TEXT, tick INTEGER, id TEXT UNIQUE, request BLOB, events BLOB, state BLOB, hash TEXT, PRIMARY KEY(run,tick));
        CREATE TABLE IF NOT EXISTS ret_outbox(commit_id TEXT, ordinal INTEGER, event BLOB, PRIMARY KEY(commit_id,ordinal));
        """)

    def close(self):
        self.db.close()

    def create(self, state):
        encoded = encode(state)
        old = self.db.execute("SELECT initial FROM ret_runs WHERE id=?", (state["run_id"],)).fetchone()
        if old:
            if old[0] != encoded:
                raise ValueError("run already exists with different initial state")
            return
        with self.db:
            self.db.execute("INSERT INTO ret_runs VALUES(?,?,?,?)", (state["run_id"], encoded, encoded, digest(state)))

    def state(self, run_id):
        row = self.db.execute("SELECT state,hash FROM ret_runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise ValueError("unknown run")
        state = json.loads(row[0])
        if digest(state) != row[1]:
            raise ValueError("materialized state hash mismatch")
        return state

    def history(self, run_id):
        return self.db.execute("SELECT * FROM ret_commits WHERE run=? ORDER BY tick", (run_id,)).fetchall()

    def commit(self, before, attempts, fault=None):
        request = {"before": digest(before), "attempts": sorted(attempts, key=lambda x: x["actor"])}
        commit_id = digest([before.get("version", VERSION), before["run_id"], before["tick"], request])
        after, events = plan(before, request["attempts"], self.cas)
        if fault:
            fault.check("BEFORE_TRANSACTION")
        try:
            self.db.execute("BEGIN IMMEDIATE")
            old = self.db.execute("SELECT request,state FROM ret_commits WHERE id=?", (commit_id,)).fetchone()
            if old:
                if old[0] != encode(request) or old[1] != encode(after):
                    raise ValueError("idempotency corruption")
                self.db.rollback()
                return json.loads(old[1])
            if digest(self.state(before["run_id"])) != digest(before):
                raise ValueError("stale boundary")
            self.db.execute("INSERT INTO ret_commits VALUES(?,?,?,?,?,?,?)", (
                before["run_id"], before["tick"], commit_id, encode(request), encode(events), encode(after), digest(after),
            ))
            for index, event in enumerate(events):
                self.db.execute("INSERT INTO ret_outbox VALUES(?,?,?)", (commit_id, index, encode(event)))
            self.db.execute("UPDATE ret_runs SET state=?,hash=? WHERE id=?", (encode(after), digest(after), before["run_id"]))
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
        row = self.db.execute("SELECT initial FROM ret_runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise ValueError("unknown run")
        state = json.loads(row[0])
        for entry in self.history(run_id):
            request = json.loads(entry["request"])
            if entry["tick"] != state["tick"] or request["before"] != digest(state):
                raise ValueError("replay boundary mismatch")
            if entry["id"] != digest([state.get("version", VERSION), run_id, state["tick"], request]):
                raise ValueError("commit identity mismatch")
            after, events = plan(state, request["attempts"], self.cas)
            if encode(after) != entry["state"] or digest(after) != entry["hash"] or encode(events) != entry["events"]:
                raise ValueError("replay state/event mismatch")
            outbox = self.db.execute("SELECT event FROM ret_outbox WHERE commit_id=? ORDER BY ordinal", (entry["id"],)).fetchall()
            if [row[0] for row in outbox] != [encode(event) for event in events]:
                raise ValueError("replay outbox mismatch")
            state = after
        if state != self.state(run_id):
            raise ValueError("replay/materialized disagreement")
        return state


def metrics(store: RetentionStore, run_id: str) -> dict:
    final = store.replay(run_id)
    events = [event for row in store.history(run_id) for event in json.loads(row["events"])]
    accepted = [event for event in events if event["status"] == "ACCEPTED"]
    submissions = final["submissions"]
    correct = sum(bool(item["correct"]) for item in submissions)
    verified = sum(bool(item.get("verified")) for item in submissions)
    initial_knowledge = final.get("initial_knowledge") or INITIAL_KNOWLEDGE
    missing_of = {actor: [fact for fact in final["objectives"][actor]["fact_ids"]
                          if fact not in initial_knowledge[actor]] for actor in AGENTS}
    persistence_acts = sum(
        event["action"] in ("TRACE", "COMMIT")
        and event.get("fact_id") in missing_of[event["actor"]]
        for event in accepted
    )
    return {
        "opportunities": len(events),
        "accepted": len(accepted),
        "rejected": len(events) - len(accepted),
        "actions": dict(Counter(event["action"] for event in accepted)),
        "scans_created": sum(event["action"] == "INSPECT" for event in accepted),
        "trace_count": len(final["traces"]),
        "trace_bootstrap_count": sum(event["action"] == "TRACE" for event in accepted),
        "trace_reuse_count": sum(event["action"] == "REUSE" for event in accepted),
        "commit_count": sum(event["action"] == "COMMIT" for event in accepted),
        "objective_persistence_acts": persistence_acts,
        "submissions": len(submissions),
        "correct_submissions": correct,
        "verified_submissions": verified,
        "accuracy": correct / len(submissions) if submissions else 0.0,
        "exploration_cost": dict(final["exploration_cost"]),
        "world_state": dict(final["world_state"]),
        "direct_messages": sum(event["action"] == "SEND" for event in accepted),
        "final_state_hash": digest(final),
    }
