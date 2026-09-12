"""R4 commit adapter for state-grounded ActionIntents.

The existing EXP-STIG implementation remains the R2/R3 authority. R4 uses a
separate adapter because its persisted model context is dynamically grounded;
the commit, idempotency, optimistic boundary, and replay laws are equivalent.
"""
from __future__ import annotations

from collections import Counter
import json
from typing import Any

from . import action_affordance as afford
from . import stigmergy as s


def attempt(state: dict, actor: str, model: str, seed: int, prompt: bytes,
            desc: dict[str, Any], raw: bytes, response: dict, store) -> dict:
    context_ref = s.put(store, prompt)
    raw_ref = s.put(store, raw)
    s.put(store, s.encode(response))
    response_ref = s.put(store, s.encode({
        "model": model, "seed": seed, "context_ref": context_ref, "raw_ref": raw_ref,
    }))
    core = {
        "actor": actor,
        "model": model,
        "seed": seed,
        "context_ref": context_ref,
        "raw_ref": raw_ref,
        "response_ref": response_ref,
        "opportunity": s.digest([s.VERSION, state["run_id"], state["tick"], actor]),
        "state_hash": s.digest(state),
        "condition": state["condition"],
        "affordance_ref": s.put(store, s.encode(desc)),
        "affordance_sha256": afford.descriptor_hash(desc),
        "context_version": desc["context_version"],
        "grammar_sha256": desc["grammar_sha256"],
    }
    core["attempt_id"] = s.put(store, s.encode(core))
    return core


def _check_affordance(state: dict, actor: str, item: dict, store) -> dict[str, Any]:
    expected_prompt, expected = afford.build(state, actor, store)
    if s.resolve(store, item["context_ref"]) != expected_prompt:
        raise ValueError("grounded context mismatch")
    recorded = json.loads(s.resolve(store, item["affordance_ref"]))
    if recorded != expected:
        raise ValueError("affordance descriptor mismatch")
    if item["affordance_sha256"] != afford.descriptor_hash(expected):
        raise ValueError("affordance identity mismatch")
    if item["condition"] != state["condition"] or item["context_version"] != expected["context_version"]:
        raise ValueError("affordance version mismatch")
    return expected


def plan(state: dict, attempts: list[dict], store) -> tuple[dict, list[dict]]:
    if len(attempts) != len(state["agents"]) or sorted(a["actor"] for a in attempts) != sorted(state["agents"]):
        raise ValueError("exactly one attempt per opportunity required")
    events: list[dict] = []
    candidates: dict[str, dict] = {}
    for item in sorted(attempts, key=lambda a: a["actor"]):
        actor = item["actor"]
        core = {k: v for k, v in item.items() if k != "attempt_id"}
        if s.digest(core) != item["attempt_id"] or item["state_hash"] != s.digest(state):
            raise ValueError("attempt identity mismatch")
        if item["opportunity"] != s.digest([s.VERSION, state["run_id"], state["tick"], actor]):
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
            desc = _check_affordance(state, actor, item, store)
            event["affordance"] = "PASS"
            response = json.loads(s.resolve(store, item["response_ref"]))
            if response != {k: item[k] for k in ("model", "seed", "context_ref", "raw_ref")}:
                raise ValueError("generation evidence identity mismatch")
            raw = s.resolve(store, item["raw_ref"])
            candidate = s.parse(raw, state["condition"])
            event["parser"] = "PASS"
            afford.validate_candidate(candidate, desc)
            a = candidate["action"]
            s.validate(state, actor, candidate, store)
            event.update(gateway="PASS", action=a)
            candidates[actor] = candidate
        except (ValueError, TypeError, UnicodeError, json.JSONDecodeError) as error:
            event.update(status="REJECTED", reason=str(error))
            if event["parser"] == "NOT_RUN":
                event["parser"] = "FAIL" if "JSON" in str(error) or "payload" in str(error) or "action" in str(error) else event["parser"]
            if event["parser"] == "PASS" and event["gateway"] == "NOT_RUN":
                event["affordance"] = "FAIL"
            elif event["affordance"] == "PASS" and event["parser"] == "PASS":
                event["gateway"] = "FAIL"
        except RuntimeError as error:
            event.update(status="REJECTED", reason=str(error), gateway="FAIL", layer="kernel")
        events.append(event)

    writes = Counter(c["payload"]["key"] for c in candidates.values() if c["action"] == "SET")
    after = json.loads(s.encode(state))
    for event in events:
        actor = event["actor"]
        if actor not in candidates:
            continue
        candidate = candidates[actor]
        action, payload = candidate["action"], candidate["payload"]
        if action == "SET" and writes[payload["key"]] > 1:
            event.update(status="CONFLICT", reason="same-boundary register conflict", gateway="FAIL", layer="kernel")
            continue
        if action == "SEND":
            body = s.put(store, payload["body"].encode())
            after["messages"].append({"sender": actor, "target": payload["target"], "ref": body, "tick": state["tick"]})
            event["target"] = payload["target"]
        if action in ("TRACE", "REUSE"):
            source = payload.get("trace_id")
            body = s.put(store, payload["body"].encode()) if action == "TRACE" else next(
                t["ref"] for t in state["traces"] if t["id"] == source
            )
            trace_id = "T" + s.digest([state["run_id"], actor, state["tick"], body])[:16]
            after["traces"].append({
                "id": trace_id, "creator": actor, "ref": body, "parent": source, "tick": state["tick"],
            })
            event.update(trace_id=trace_id, source=source, body_ref=body)
        if action == "SET":
            after["registers"][payload["key"]] = {
                "ref": s.put(store, payload["value"].encode()),
                "writer": actor,
                "source": payload["source"],
            }
            event.update(
                key=payload["key"],
                source=payload["source"],
                changed=after["registers"][payload["key"]]["ref"] != state["registers"][payload["key"]]["ref"],
            )
    after["tick"] += 1
    return after, events


class GroundedStore(s.StigStore):
    def commit(self, before: dict, attempts: list[dict], fault=None) -> dict:
        request = {"before": s.digest(before), "attempts": sorted(attempts, key=lambda x: x["actor"])}
        commit_id = s.digest([s.VERSION, before["run_id"], before["tick"], request])
        after, events = plan(before, request["attempts"], self.cas)
        for value in s._refs(after):
            s.resolve(self.cas, value)
        if fault:
            fault.check("BEFORE_TRANSACTION")
        try:
            self.db.execute("BEGIN IMMEDIATE")
            old = self.db.execute("SELECT request,state FROM stig_commits WHERE id=?", (commit_id,)).fetchone()
            if old:
                if old[0] != s.encode(request) or old[1] != s.encode(after):
                    raise ValueError("idempotency corruption")
                self.db.rollback()
                return json.loads(old[1])
            if s.digest(self.state(before["run_id"])) != s.digest(before):
                raise ValueError("stale boundary")
            self.db.execute(
                "INSERT INTO stig_commits VALUES(?,?,?,?,?,?,?)",
                (before["run_id"], before["tick"], commit_id, s.encode(request),
                 s.encode(events), s.encode(after), s.digest(after)),
            )
            for index, event in enumerate(events):
                self.db.execute("INSERT INTO stig_outbox VALUES(?,?,?)", (commit_id, index, s.encode(event)))
            self.db.execute("UPDATE stig_runs SET state=?,hash=? WHERE id=?",
                            (s.encode(after), s.digest(after), before["run_id"]))
            if fault:
                fault.check("BEFORE_COMMIT")
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise
        if fault:
            fault.check("AFTER_COMMIT")
        return after

    def replay(self, run_id: str) -> dict:
        row = self.db.execute("SELECT initial FROM stig_runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise ValueError("unknown run")
        state = json.loads(row[0])
        for entry in self.history(run_id):
            request = json.loads(entry["request"])
            if entry["tick"] != state["tick"] or request["before"] != s.digest(state):
                raise ValueError("replay boundary mismatch")
            if entry["id"] != s.digest([s.VERSION, run_id, state["tick"], request]):
                raise ValueError("commit identity mismatch")
            persisted = json.loads(entry["state"])
            for value in s._refs(persisted):
                s.resolve(self.cas, value)
            after, events = plan(state, request["attempts"], self.cas)
            if s.encode(after) != entry["state"] or s.digest(after) != entry["hash"] or s.encode(events) != entry["events"]:
                raise ValueError("replay state/event mismatch")
            outbox = self.db.execute(
                "SELECT event FROM stig_outbox WHERE commit_id=? ORDER BY ordinal", (entry["id"],)
            ).fetchall()
            if [row[0] for row in outbox] != [s.encode(event) for event in events]:
                raise ValueError("replay outbox mismatch")
            state = after
        if state != self.state(run_id):
            raise ValueError("replay/materialized disagreement")
        return state


def metrics(store: GroundedStore, run_id: str) -> dict:
    final = store.replay(run_id)
    events = [event for row in store.history(run_id) for event in json.loads(row["events"])]
    accepted = [event for event in events if event["status"] == "ACCEPTED"]
    counts = Counter(event["action"] for event in accepted)
    traces = {trace["id"]: trace for trace in final["traces"]}
    uses = [
        event for event in accepted
        if event.get("source") and traces[event["source"]]["creator"] != event["actor"]
    ]
    consumers = {trace_id: {event["actor"] for event in uses if event["source"] == trace_id} for trace_id in traces}
    pairs = Counter((event["actor"], event["target"]) for event in accepted if event["action"] == "SEND")
    original = [event["body_ref"] for event in accepted if event["action"] == "TRACE"]
    return {
        "opportunities": len(events),
        "accepted": len(accepted),
        "rejected": len(events) - len(accepted),
        "actions": dict(counts),
        "foreign_environment_uses": len(uses),
        "environment_use_rate": len(uses) / len(events) if events else 0,
        "third_agent_reuse_traces": sum(len(consumers[trace_id]) >= 2 for trace_id in consumers),
        "repeated_directed_pairs": sum(count >= 2 for count in pairs.values()),
        "duplicate_trace_bodies": len(original) - len(set(original)),
        "register_changes": sum(bool(event.get("changed")) for event in accepted),
        "action_counts_by_agent": {
            actor: dict(Counter(event["action"] for event in accepted if event["actor"] == actor))
            for actor in s.AGENTS
        },
        "final_state_hash": s.digest(final),
    }
