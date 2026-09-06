"""Validate recorded checkpoints, then derive temporally bounded read models.

No transitions are executed here. Existing pure snapshot hashing supplies the
canonical hash contract; SQLite adapters and inference runtimes are never built.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from alifelm.persistence.serialization import snapshot_from_dict

from .evidence import (
    ARCHIVE_SHA, BASE_DIGEST, DIGEST, GROUNDING_DIGEST, GROUNDING_SHA, MANIFEST_SHA,
    RUN_ID, EvidenceBundle, EvidenceError, IntegrityConflict, observation_connection,
    read_json, require, sha256, verify_file,
)
from .models import ActionAttemptObservation, AgentObservation, EventObservation, TickObservation


def canonical_digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def by_id(values: list[dict], key: str) -> dict[str, dict]:
    return {item[key]: item for item in values}


class Observatory:
    """One authenticated closed run, immutable after construction."""

    def __init__(self, bundle: EvidenceBundle):
        self.bundle = bundle
        self.refs: dict[str, tuple[Path, int | None, str]] = {}
        self.snapshots: dict[int, dict] = {}
        self.hashes: dict[int, str] = {}
        self.ticks: dict[int, dict] = {}
        self.births: list[dict] = []
        self.deaths: list[dict] = []
        self.events: list[EventObservation] = []
        self.attempts: list[ActionAttemptObservation] = []
        self.tick_refs: dict[int, str] = {}
        self.agents: dict[str, dict] = {}
        try:
            self._load()
        except (KeyError, TypeError, IndexError, sqlite3.Error, OSError, ValueError) as exc:
            if isinstance(exc, EvidenceError):
                raise
            raise IntegrityConflict("Invalid or inconsistent recorded evidence: " + str(exc)) from exc

    def _register(self, path: Path, tick: int | None, label: str) -> str:
        digest = sha256(path)
        old = self.refs.get(digest)
        if old is None or (tick is not None and (old[1] is None or tick < old[1])):
            self.refs[digest] = (path, tick, label)
        return digest

    def _load(self):
        root = self.bundle.root
        self.sealed_file_count = self.bundle.verify_cache()
        self.manifest = read_json(root / "manifest.json")
        self.grounding = read_json(root / "grounding_manifest.json")
        for filename, doc, expected_hash, expected_digest in (
            ("manifest.json", self.manifest, MANIFEST_SHA, BASE_DIGEST),
            ("grounding_manifest.json", self.grounding, GROUNDING_SHA, GROUNDING_DIGEST),
        ):
            verify_file(root / filename, expected_hash)
            require(doc["result_digest"] == expected_digest, "Unexpected result identity")
            require(canonical_digest({k: v for k, v in doc.items() if k != "result_digest"})
                    == expected_digest, "Manifest result digest mismatch")
            self._register(root / filename, None, filename + " · Full Run")
        require(self.grounding["parent_manifest_sha256"] == MANIFEST_SHA, "Grounding parent mismatch")
        require(self.grounding["parent_result_digest"] == BASE_DIGEST, "Grounding result parent mismatch")
        require(self.manifest["trajectory"] == self.grounding["trajectory"], "Manifest trajectories disagree")
        with observation_connection(root / "run.sqlite") as db:
            require(db.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "SQLite integrity failure")
            require(db.execute("PRAGMA foreign_key_check").fetchone() is None, "SQLite foreign-key failure")
            require(db.execute("SELECT schema_version FROM schema_meta").fetchone()[0] == 1,
                    "Unsupported SQLite schema")
            runs = [dict(r) for r in db.execute("SELECT * FROM runs")]
            require(len(runs) == 1 and runs[0]["run_id"] == RUN_ID, "Unexpected run identity")
            self.run = runs[0]
            self.horizon = self.run["horizon"]
            require(self.horizon == 20 and self.run["current_tick"] == 20, "Incomplete closed run")
            for row in db.execute("SELECT * FROM snapshots ORDER BY state_version"):
                value = json.loads(row["snapshot_json"])
                version = row["state_version"]
                require(value["run_id"] == RUN_ID and value["state_version"] == version
                        and value["tick"] == row["tick"] == version, "Snapshot identity mismatch")
                require(snapshot_from_dict(value).state_hash() == row["state_hash"], "Snapshot hash mismatch")
                self.snapshots[version] = value
                self.hashes[version] = row["state_hash"]
            require(list(self.snapshots) == list(range(self.horizon + 1)), "Missing snapshot boundary")
            self.agents = deepcopy(by_id(self.snapshots[0]["agents"], "agent_id"))
            for slot, agent in enumerate(self.agents.values()):
                agent.update(alias=f"Founder {chr(65 + slot)}", generation=0, parents=[], slot=slot,
                             death_tick=None, death_commit_tick=None)
            self.founders = len(self.agents)
            commits = [dict(r) for r in db.execute("SELECT * FROM commits ORDER BY commit_seq")]
            require(len(commits) == self.horizon, "Missing canonical commit")
            artifacts = [dict(r) for r in db.execute("SELECT * FROM commit_artifacts")]
            for tick, commit in enumerate(commits):
                before, after = self.snapshots[tick], self.snapshots[tick + 1]
                require(commit["run_id"] == RUN_ID and commit["commit_seq"] == tick + 1
                        and commit["tick"] == tick and commit["state_version_before"] == tick
                        and commit["state_version_after"] == tick + 1, "Noncontiguous commit chain")
                require(commit["previous_state_hash"] == self.hashes[tick]
                        and commit["resulting_state_hash"] == self.hashes[tick + 1]
                        and json.loads(commit["resulting_snapshot_json"]) == after,
                        "Commit and snapshot disagree")
                require(after["events"][:len(before["events"])] == before["events"], "Event history changed")
                suffix = after["events"][len(before["events"]):]
                db_events = [dict(r) for r in db.execute(
                    "SELECT * FROM commit_events WHERE commit_id=? ORDER BY event_ordinal", (commit["commit_id"],))]
                require(len(db_events) == len(suffix), "Missing canonical event")
                for order, (row, event) in enumerate(zip(db_events, suffix)):
                    require(row["event_ordinal"] == order and event["commit_order"] == order,
                            "Invalid canonical event order")
                    require(all(row[k] == event[k] for k in ("event_id", "event_type", "commit_tick", "commit_order"))
                            and json.loads(row["artifact_refs_json"]) == event["artifact_refs"],
                            "Canonical event and snapshot disagree")
                path = root / "ticks" / f"tick_{tick:04d}.json"
                record = read_json(path)
                self.tick_refs[tick] = self._register(path, tick, f"Tick {tick} · recorded evidence")
                self.ticks[tick] = record
                self._verify_tick(tick, before, after, suffix)
                commit_refs = {r["digest"] for r in artifacts if r["commit_id"] == commit["commit_id"]}
                require(commit_refs == {r["digest"] for r in record["context_artifact_refs"]},
                        "Tick and commit artifact references disagree")
                for digest in commit_refs:
                    self.bundle.artifact(digest)
                    self._register(root / "cas" / digest[:2] / digest, tick, "CAS artifact")
            require(len(list((root / "ticks").glob("tick_*.json"))) == self.horizon, "Unexpected tick evidence")
            self.artifact_count = len({r["digest"] for r in artifacts})
            final = self.snapshots[self.horizon]
            require(self.run["current_state_hash"] == self.hashes[self.horizon]
                    and self.run["current_state_version"] == self.horizon
                    and self.run["status"] == final["status"], "Current run and checkpoint disagree")
            for table, key in (("agents", "agent_id"), ("messages", "message_id"), ("proposals", "proposal_id")):
                rows = [{k: v for k, v in dict(r).items() if k != "run_id"}
                        for r in db.execute(f"SELECT * FROM {table}_current WHERE run_id=?", (RUN_ID,))]
                require(by_id(rows, key) == by_id(final[table], key), "Materialized " + table + " disagree")
        self._reconcile_manifest()

    def _verify_tick(self, tick: int, before: dict, after: dict, suffix: list[dict]):
        r = self.ticks[tick]
        require(r["tick"] == tick and r["state_version_before"] == tick
                and r["state_hash_before"] == self.hashes[tick]
                and r["population_before"] == len(before["agents"]), "Tick before-state conflict")
        c = r["commit"]
        require(c["committed"] and not c["capacity_censored"] and c["state_version_after"] == tick + 1
                and c["tick_after"] == tick + 1 and c["state_hash_after"] == self.hashes[tick + 1]
                and c["population_after"] == len(after["agents"]) and c["status_after"] == after["status"],
                "Tick after-state conflict")
        require(r["events"] == [{k: v for k, v in e.items() if k != "artifact_refs"} for e in suffix],
                "Tick events differ from SQLite")
        prev_agents, next_agents = by_id(before["agents"], "agent_id"), by_id(after["agents"], "agent_id")
        next_messages, next_proposals = by_id(after["messages"], "message_id"), by_id(after["proposals"], "proposal_id")
        prev_proposals = by_id(before["proposals"], "proposal_id")
        subjects: dict[tuple[str, str], list[str]] = {}
        found_births, found_deaths, found_messages, found_proposals = set(), set(), set(), set()
        for fragment in r["fragments"]:
            kind, fid = fragment["kind"], fragment["fragment_id"]
            if kind == "BIRTH":
                birth = deepcopy(fragment["birth"])
                child, parents, pid = birth["child_id"], birth["parent_ids"], birth["proposal_id"]
                proposal = prev_proposals[pid]
                require(parents == [proposal["proposer_id"], proposal["target_id"]]
                        and len(set(parents)) == 2 and all(p in prev_agents for p in parents), "Birth parents conflict")
                require(child not in prev_agents and child in next_agents and birth["birth_tick"] == tick
                        and birth["first_active_tick"] == tick + 1
                        and next_agents[child]["birth_tick"] == tick
                        and next_agents[child]["first_active_tick"] == tick + 1
                        and next_proposals[pid]["state"] == "ACCEPTED", "Birth state conflict")
                found_births.add(child)
                self.births.append(birth)
                self.agents[child] = dict(next_agents[child], alias=f"Child {len(self.births):02d}",
                    slot=self.founders + len(self.births) - 1, parents=parents,
                    generation=1 + max(self.agents[p]["generation"] for p in parents),
                    death_tick=None, death_commit_tick=None)
                subjects[("AgentBorn", child)] = [child, *parents]
                subjects[("ReproductionProposalAccepted", fid)] = parents
            elif kind == "NATURAL_DEATH":
                aid = fragment["death"]["agent_id"]
                require(aid in prev_agents and aid not in next_agents, "Death not reflected in snapshot")
                require(prev_agents[aid]["first_active_tick"] + prev_agents[aid]["lifespan_ticks"] == tick + 1,
                        "Natural death boundary conflict")
                self.agents[aid].update(death_tick=tick + 1, death_commit_tick=tick)
                self.deaths.append(dict(agent_id=aid, commit_tick=tick, death_tick=tick + 1))
                found_deaths.add(aid)
                subjects[("AgentDied", aid)] = [aid]
            elif kind == "MESSAGE":
                m = fragment["message"]
                require(next_messages[m["message_id"]] == m, "Message fragment conflict")
                found_messages.add(m["message_id"])
                subjects[("MessageCommitted", fid)] = [m["sender_id"], m["recipient_id"]]
            elif kind == "PROPOSAL_CREATED":
                p = fragment["proposal"]
                require(all(next_proposals[p["proposal_id"]][k] == v for k, v in p.items()), "Proposal fragment conflict")
                found_proposals.add(p["proposal_id"])
                subjects[("ReproductionProposalCreated", fid)] = [p["proposer_id"], p["target_id"]]
            else:
                raise IntegrityConflict("Unsupported fragment in this sealed pilot")
        require(found_births == set(next_agents) - set(prev_agents), "Unbound birth")
        require(found_deaths == set(prev_agents) - set(next_agents), "Unbound death")
        require(found_messages == set(next_messages) - set(by_id(before["messages"], "message_id")), "Unbound message")
        require(found_proposals == set(next_proposals) - set(prev_proposals), "Unbound proposal")
        for pid, p in next_proposals.items():
            if p["state"] in ("INVALIDATED", "EXPIRED") and prev_proposals.get(pid, {}).get("state") != p["state"]:
                subjects[("ReproductionProposal" + p["state"].title(), pid)] = [p["proposer_id"], p["target_id"]]
        # This is the existing recorded event-ID contract, not event generation.
        associations = {hashlib.sha256(f"{RUN_ID}|{tick}|{kind}|{key}".encode()).hexdigest(): agents
                        for (kind, key), agents in subjects.items()}
        require(set(associations) == {e["event_id"] for e in suffix}, "Event subjects cannot be bound exactly")
        titles = {"AgentBorn": ("birth", "A child is born"), "AgentDied": ("death", "Natural death"),
                  "MessageCommitted": ("message", "Message committed"),
                  "ReproductionProposalCreated": ("proposal", "Proposal created"),
                  "ReproductionProposalAccepted": ("proposal", "Proposal accepted"),
                  "ReproductionProposalInvalidated": ("proposal", "Proposal invalidated"),
                  "ReproductionProposalExpired": ("proposal", "Proposal expired")}
        for e in suffix:
            category, title = titles[e["event_type"]]
            ids = associations[e["event_id"]]
            detail = " → ".join(self.agents[a]["alias"] for a in ids)
            if category == "birth":
                detail = f"{self.agents[ids[0]]['alias']} · first active tick {tick + 1}"
            elif category == "death":
                detail += f" · effective at boundary {tick + 1}"
            self.events.append(dict(id=e["event_id"], tick=tick, category=category, title=title, detail=detail,
                agent_ids=ids, canonical=True, evidence_ref=self.tick_refs[tick], record=e))
        admitted = {i["intent_id"] for i in r["validated_intents"]}
        require(len(r["cognition"]) == r["opportunities"] == len(prev_agents), "Cognition opportunities conflict")
        require({a["agent_id"] for a in r["cognition"]} == set(prev_agents), "Cognition agent set conflict")
        for a in r["cognition"]:
            intent = a["gateway_intent"]
            require(a["law_admitted"] == (intent is not None and intent["intent_id"] in admitted), "Law admission conflict")
            if intent:
                require(intent["actor_id"] == a["agent_id"] and intent["tick"] == tick
                        and intent["kind"] == a["selected_action"], "Gateway/selection identity conflict")
            raw_ref = a["evidence_ref"]["digest"] if a["evidence_ref"] else None
            if raw_ref:
                require(raw_ref in {r["digest"] for r in r["context_artifact_refs"]}, "Unbound raw artifact")
            attempt: ActionAttemptObservation = dict(id=a["opportunity_id"], tick=tick, agent_id=a["agent_id"],
                selected_action=a["selected_action"], law_admitted=a["law_admitted"],
                target_id=(intent or {}).get("payload", {}).get("target_agent_id"),
                gateway_intent=intent, proposal_grounding=a["proposal_grounding"],
                probabilities=a["probabilities"], score_vector=a["score_vector"], parse_status=a["parse_status"],
                evidence_ref=self.tick_refs[tick], raw_ref=raw_ref)
            self.attempts.append(attempt)
            self.events.append(dict(id=a["opportunity_id"], tick=tick, category="action",
                title=f"{a['selected_action']} selected", detail=self.agents[a["agent_id"]]["alias"] +
                (" · Admitted by Law" if a["law_admitted"] else " · Rejected by Law"),
                agent_ids=[a["agent_id"]], canonical=False, evidence_ref=self.tick_refs[tick], record={"attempt_id": a["opportunity_id"]}))
            if not a["law_admitted"]:
                self.events.append(dict(id=a["opportunity_id"] + "-rejected", tick=tick, category="rejection",
                    title=f"{a['selected_action']} rejected by Law", detail=self.agents[a["agent_id"]]["alias"] +
                    (" · No message committed" if a["selected_action"] == "SEND" else " · No transition committed"),
                    agent_ids=[a["agent_id"]], canonical=False, evidence_ref=self.tick_refs[tick], record={"attempt_id": a["opportunity_id"]}))
        if before["status"] != after["status"]:
            self.events.append(dict(id=f"boundary-{tick + 1}", tick=tick, category="run", title="Run completed",
                detail=f"Final boundary S{tick + 1} · no later cognition recorded", agent_ids=[], canonical=True,
                evidence_ref=self.tick_refs[tick], record={"source": "snapshot.status", "status": after["status"]}))

    def _reconcile_manifest(self):
        final, tr = self.snapshots[self.horizon], self.manifest["trajectory"]
        require(tr["final_state_hash"] == self.hashes[self.horizon] == self.manifest["replay"]["final_state_hash"],
                "Final manifest hash conflict")
        require(tr["births"] == self.births, "Manifest births conflict")
        require(tr["final_population"] == len(final["agents"]) and tr["final_tick"] == self.horizon
                and tr["final_state_version"] == self.horizon and tr["final_status"] == final["status"], "Final result conflict")
        require(tr["generation_depth"] == {k: v["generation"] for k, v in self.agents.items()}, "Lineage depth conflict")
        require(tr["selected_action_distribution"] == dict(Counter(a["selected_action"] for a in self.attempts)),
                "Selected-action distribution conflict")
        require(tr["law_rejections"] == sum(not a["law_admitted"] for a in self.attempts), "Law rejection total conflict")
        require(tr["total_cognition_opportunities"] == len(self.attempts), "Cognition total conflict")
        require(by_id(tr["messages"], "message_id") == by_id(final["messages"], "message_id"), "Manifest messages conflict")
        require(len(tr["proposals_created"]) == len(final["proposals"]), "Manifest proposal total conflict")
        for p in tr["proposals_created"]:
            require(all(by_id(final["proposals"], "proposal_id")[p["proposal_id"]][k] == v for k, v in p.items()),
                    "Manifest proposal record conflict")
        require(tr["natural_deaths"] == [{"agent_id": d["agent_id"]} for d in self.deaths], "Manifest death record conflict")
        require(tr["population_by_tick"] == [dict(tick=t, before=len(self.snapshots[t]["agents"]),
                    after=len(self.snapshots[t + 1]["agents"])) for t in range(self.horizon)], "Manifest population history conflict")
        sequences = {aid: [dict(tick=a["tick"], selected_action=a["selected_action"],
                    gateway_intent_kind=a["gateway_intent"]["kind"] if a["gateway_intent"] else None,
                    law_admitted=a["law_admitted"]) for a in self.attempts if a["agent_id"] == aid]
                    for aid in self.agents}
        # The recorded trajectory omits agents with zero cognition opportunities.
        require(tr["per_agent_action_sequence"] == {k: v for k, v in sequences.items() if v},
                "Manifest per-agent cognition conflict")
        require(tr["final_agents"] == [a["agent_id"] for a in final["agents"]], "Final agent identity conflict")
        require(tr["max_generation_depth"] == max(a["generation"] for a in self.agents.values()), "Maximum generation conflict")

    def validate_tick(self, tick: int) -> int:
        if isinstance(tick, bool) or not isinstance(tick, int) or not 0 <= tick <= self.horizon:
            raise EvidenceError(f"Tick must be between 0 and {self.horizon}")
        return tick

    def summary(self) -> dict:
        return dict(id=RUN_ID, name="EXP-000", title="A world, unfolding.", horizon=self.horizon,
                    founders=self.founders, observation="Sealed replay", integrity="verified")

    def frame(self, tick: int) -> TickObservation:
        self.validate_tick(tick)
        boundary = min(tick + 1, self.horizon)
        snap = self.snapshots[boundary]
        living = {a["agent_id"] for a in snap["agents"]}
        agents = []
        for aid, a in self.agents.items():
            if a["generation"] > 0 and a["birth_tick"] > tick:
                continue
            death_committed = a["death_commit_tick"] is not None and a["death_commit_tick"] <= tick
            death_tick = a["death_tick"] if death_committed else None
            agent: AgentObservation = dict(id=aid, alias=a["alias"], slot=a["slot"], generation=a["generation"],
                lifecycle="dead" if death_committed else "born" if tick < a["first_active_tick"] else "active",
                birth_tick=a["birth_tick"], first_active_tick=a["first_active_tick"],
                death_tick=death_tick, death_commit_tick=a["death_commit_tick"] if death_committed else None,
                age=max(0, min(boundary, death_tick or boundary) - a["first_active_tick"]),
                parents=a["parents"], children=[b["child_id"] for b in self.births if b["birth_tick"] <= tick and aid in b["parent_ids"]],
                has_cognition=any(at["agent_id"] == aid and at["tick"] <= tick for at in self.attempts))
            require((agent["lifecycle"] != "dead") == (aid in living), "Projected population conflict")
            agents.append(agent)
        births = [b for b in self.births if b["birth_tick"] <= tick]
        events = sorted([e for e in self.events if e["tick"] <= tick], key=lambda e: -e["tick"])
        result: TickObservation = dict(run_id=RUN_ID, tick=tick, boundary_tick=boundary,
            state_version=snap["state_version"], state_hash=self.hashes[boundary], status=snap["status"],
            mode="Final boundary" if tick == self.horizon else "After closing tick",
            metrics=dict(population=len(living), generation=max(a["generation"] for a in agents),
                births=len(births), deaths=sum(a["lifecycle"] == "dead" for a in agents),
                messages=len(snap["messages"]), proposals=len(snap["proposals"])),
            agents=agents, attempts=[a for a in self.attempts if a["tick"] <= tick], events=events,
            messages=snap["messages"], proposals=snap["proposals"], lineage=births,
            evidence_ref=self.tick_refs.get(tick), projection_schema="observatory.v1")
        return deepcopy(result)

    def agent(self, aid: str, tick: int) -> dict:
        frame = self.frame(tick)
        match = next((a for a in frame["agents"] if a["id"] == aid), None)
        if match is None:
            raise KeyError("Agent does not exist at the selected tick")
        return dict(agent=match, tick=tick,
                    attempts=[a for a in frame["attempts"] if a["agent_id"] == aid],
                    messages=[m for m in frame["messages"] if aid in (m["sender_id"], m["recipient_id"])],
                    proposals=[p for p in frame["proposals"] if aid in (p["proposer_id"], p["target_id"])],
                    events=[e for e in frame["events"] if aid in e["agent_ids"]])

    def integrity(self) -> dict:
        return dict(scope="Full Run", run_id=RUN_ID, local_status="Verified",
            checks=dict(archive_sha256=ARCHIVE_SHA, manifest_sha256=MANIFEST_SHA, grounding_manifest_sha256=GROUNDING_SHA,
                        sqlite="ok", checkpoint_chain=self.horizon, cas_artifacts=self.artifact_count,
                        extracted_files=self.sealed_file_count,
                        materialized_state="matches final checkpoint", tick_records="match SQLite",
                        manifest_digests="recomputed", read_only="mode=ro&immutable=1; query_only=ON"),
            recorded=dict(base_status=self.manifest["status"], base_digest=BASE_DIGEST,
                          grounding_status=self.grounding["status"], grounding_digest=GROUNDING_DIGEST,
                          gates=self.grounding["gates"], replay=self.manifest["replay"],
                          code_commit=self.manifest["git_commit"]),
            final_result=dict(self.frame(self.horizon)["metrics"], founders=self.founders,
                              selected_actions=dict(Counter(a["selected_action"] for a in self.attempts)),
                              birth_conflicts=len(self.manifest["trajectory"]["birth_conflicts"])),
            manifests=[dict(ref=MANIFEST_SHA, label="Base manifest"), dict(ref=GROUNDING_SHA, label="Grounding manifest")])

    def evidence(self, digest: str, tick: int, full_run: bool = False) -> dict:
        self.validate_tick(tick)
        if not DIGEST.fullmatch(digest):
            raise EvidenceError("Invalid evidence digest")
        if digest not in self.refs:
            raise KeyError("Unknown evidence reference")
        path, earliest, label = self.refs[digest]
        if (earliest is None and not full_run) or (earliest is not None and earliest > tick and not full_run):
            raise KeyError("Evidence is outside the selected observation scope")
        verify_file(path, digest)
        raw = path.read_bytes()
        try:
            content = raw.decode("utf-8")
        except UnicodeError as exc:
            raise EvidenceError("Artifact is not UTF-8 text") from exc
        # Keep raw JSON source as text: JS numbers cannot represent selector seed fractions exactly.
        return dict(ref=digest, label=label, scope="Full Run" if full_run else f"Through tick {tick}",
                    verified=True, byte_length=len(raw), content=content)
