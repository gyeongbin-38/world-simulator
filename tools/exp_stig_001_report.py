#!/usr/bin/env python3
"""Observer-only aggregate export from a completed EXP-STIG-001 receipt.

Never generates model requests or changes the canonical database. Run the
companion notebook/replay audit separately before treating this export as final.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sealed(value):
    assert value["manifest_digest"] == digest(encode({
        k: v for k, v in value.items() if k != "manifest_digest"}))


def export(root):
    def read(name):
        return json.loads((root / name).read_bytes())

    def cas(reference):
        data = (root / "cas" / reference[:2] / reference).read_bytes()
        assert digest(data) == reference
        return json.loads(data)

    result, planned = read("result.json"), read("planned.json")
    sealed(result)
    sealed(planned)
    assert result["status"] == "COMPLETE"
    assert result["planned_digest"] == planned["manifest_digest"]
    for filename, expected in result["evidence_hashes"].items():
        assert digest((root / filename).read_bytes()) == expected, filename
    conditions = {c: Counter() for c in "ABC"}
    models = {m["sha256"]: Counter() for m in planned["models"]}
    reasons = {c: Counter() for c in "ABC"}
    actors = {}
    db = sqlite3.connect((root / "world.sqlite").as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        rows = db.execute("SELECT * FROM stig_commits ORDER BY run,tick").fetchall()
        assert len(rows) == 36
        for row in rows:
            condition = row["run"].rsplit("-", 1)[1]
            attempts = {a["actor"]: a for a in json.loads(row["request"])["attempts"]}
            events = json.loads(row["events"])
            assert len(attempts) == len(events) == 3
            for event in events:
                actor = event["actor"]
                counters = (conditions[condition], models[attempts[actor]["model"]],
                            actors.setdefault(row["run"] + "/" + actor, Counter()))
                for counter in counters:
                    counter["opportunities"] += 1
                    counter[event["status"]] += 1
                    if event["status"] == "ACCEPTED":
                        counter[event["action"]] += 1
                if event["status"] != "ACCEPTED":
                    reasons[condition][event.get("reason", "UNRECORDED")] += 1
    finally:
        db.close()
    assert all(c["opportunities"] == 36 for c in conditions.values())
    assert sorted(m["opportunities"] for m in models.values()) == [36, 72]
    for run, metrics in result["worlds"].items():
        target = conditions[run.rsplit("-", 1)[1]]
        for key in ("foreign_environment_uses", "third_agent_reuse_traces",
                    "repeated_directed_pairs", "duplicate_trace_bodies", "register_changes"):
            target[key] += metrics[key]
    costs = {c: Counter() for c in "ABC"}
    stop_types = {c: Counter() for c in "ABC"}
    for item in read("costs.json"):
        condition = item["run_id"].rsplit("-", 1)[1]
        target = costs[condition]
        target[item["phase"] + "_requests"] += 1
        target["prompt_tokens"] += item["timings"].get("prompt_n", 0)
        target["generated_tokens"] += item["timings"].get("predicted_n", 0)
        target["request_seconds"] += item["seconds"]
        if item["phase"] == "primary":
            response = cas(item["response_ref"])
            stop_types[condition][str(response.get("stop_type", "UNRECORDED"))] += 1
    probes = read("counterfactuals.json")
    attribution = {c: Counter() for c in "ABC"}
    for probe in probes:
        target = attribution[probe["run_id"].rsplit("-", 1)[1]]
        target["exposures"] += 1
        target["stable_intact_repeats"] += int(probe["attribution"]["stable"])
        target["attributable_chains"] += int(probe["attribution"]["attributable"])
        target["attributable_register_changes"] += int(
            probe["attribution"]["attributable"] and probe["attribution"]["register_change"])
    assert sum(c["primary_requests"] for c in costs.values()) == 108
    assert sum(c["generated_tokens"] for c in costs.values()) == result["tokens_generated"]
    assert sum(c["prompt_tokens"] for c in costs.values()) == result["tokens_prompt"]
    report = {
        "analysis_id": "EXP_STIG_001_R2_OBSERVER_ANALYSIS_V1",
        "result_manifest_digest": result["manifest_digest"],
        "planned_manifest_digest": planned["manifest_digest"],
        "interpretation": result["interpretation"], "conditions": conditions,
        "models": models, "rejection_reasons": reasons,
        "action_counts_by_actor_world": actors, "costs": costs,
        "execution_wall_seconds": result["wall_seconds"],
        "model_load_seconds": sum(item["seconds"] for item in read("loads.json")),
        "requests": result["requests"],
        "primary_requests": result["primary_requests"],
        "primary_stop_types": stop_types, "attribution": attribution,
        "paired_differences": result["paired_differences"],
        "limits": [
            "S0 means no demonstrated effect, not statistical equivalence.",
            "Rejected output is not model-chosen WAIT or voluntary inactivity.",
            "Artifact-use rates alone do not identify useful task performance.",
            "Duplicate text counts do not establish duplicated-work reduction.",
            "Four ticks do not establish durable specialization.",
            "The censored first run is not pooled with this fresh execution.",
        ],
    }
    report["manifest_digest"] = digest(encode(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = export(args.evidence.resolve(strict=True))
    data = encode(report)
    if args.output.exists():
        if args.output.read_bytes() != data:
            raise ValueError("immutable analysis mismatch")
    else:
        with args.output.open("xb") as stream:
            stream.write(data)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
