#!/usr/bin/env python3
"""EXP-STIG-001 R4: state-grounded action affordance comparison."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
from alifelm.experiments import action_affordance as afford
from alifelm.experiments import grounded_world as gw
from alifelm.experiments import stigmergy as s
from alifelm.persistence.cas import FileSystemArtifactStore
import exp_stig_001_r3 as r3

SPEC = ROOT / "specs/experiments/EXP-STIG-001-v1.yaml"
PROFILE = ROOT / "specs/experiments/EXP-STIG-001-execution-r4.yaml"
BOUND = [
    SPEC, PROFILE, Path(__file__),
    ROOT / "src/alifelm/experiments/stigmergy.py",
    ROOT / "src/alifelm/experiments/action_affordance.py",
    ROOT / "src/alifelm/experiments/grounded_world.py",
    ROOT / "tests/test_stigmergy.py",
    ROOT / "tests/test_action_codec.py",
    ROOT / "tests/test_action_affordance.py",
    ROOT / "src/alifelm/persistence/cas.py",
    ROOT / "src/alifelm/persistence/migrations.py",
]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sources():
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in BOUND}


def write_new(path, value):
    data = s.encode(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError("immutable evidence mismatch: " + str(path))
        return
    with path.open("xb") as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())


def seal(value):
    return {**value, "manifest_digest": s.digest(value)}


def check_seal(value):
    if value.get("manifest_digest") != s.digest({k: v for k, v in value.items() if k != "manifest_digest"}):
        raise ValueError("manifest self-digest mismatch")


def validate_config(config):
    if config["conditions"] != ["A", "B", "C"] or config["agents"] != list(s.AGENTS):
        raise ValueError("condition/cohort mismatch")
    if config["ticks"] != 4 or config["blocks"] != [1701, 2901, 4301] or config["registers"] != list(s.KEYS):
        raise ValueError("frozen design mismatch")
    if any(config[k] for k in ("teacher_LM", "retries", "fallback", "repair", "reproduction", "heredity")):
        raise ValueError("forbidden mechanism")
    if config["model_assignment"] != [[0, 1, 0], [1, 0, 0], [0, 0, 1]]:
        raise ValueError("matched model assignment mismatch")
    expected_generation = {
        "temperature": 0.0, "top_k": 1, "top_p": 1.0,
        "min_p": 0.0, "repeat_penalty": 1.0, "n_predict": 128,
        "cache_prompt": False, "stream": False,
    }
    if config["generation"] != expected_generation:
        raise ValueError("generation freeze mismatch")


def effective_config():
    config = json.loads(SPEC.read_bytes())
    profile = json.loads(PROFILE.read_bytes())
    if sha(SPEC) != profile["scientific_config_sha256"]:
        raise ValueError("R4 scientific configuration mismatch")
    expected = {
        "execution_id": "EXP-STIG-001-R4",
        "qualification_status": "PASS",
        "request_timeout_seconds": 900,
        "model_load_timeout_seconds": 600,
        "maximum_operational_replications": 1,
        "reuse_previous_responses": False,
        "scientific_treatment_changes": False,
        "treatment_definitions_unchanged": True,
        "generation_policy_unchanged": True,
    }
    if any(profile.get(k) != v for k, v in expected.items()):
        raise ValueError("unregistered R4 qualification profile")
    if profile["action_affordance_policy_id"] != afford.POLICY_ID:
        raise ValueError("R4 affordance policy mismatch")
    if profile["affordance_builder_sha256"] != sha(ROOT / "src/alifelm/experiments/action_affordance.py"):
        raise ValueError("R4 affordance builder changed")
    config["execution_id"] = profile["execution_id"]
    config["runtime"]["request_timeout_seconds"] = profile["request_timeout_seconds"]
    config["runtime"]["model_load_timeout_seconds"] = profile["model_load_timeout_seconds"]
    config["operational_r4"] = profile
    validate_config(config)
    return config


def validation_gate(output):
    config = effective_config()
    frozen = sources()
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_stigmergy.py",
         "tests/test_action_codec.py", "tests/test_action_affordance.py", "-q"],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )
    if run.returncode or frozen != sources():
        raise RuntimeError("R4 deterministic/affordance gate failed: " + run.stdout + run.stderr)
    write_new(output / "validation.json", seal({
        "status": "PASS",
        "sources": frozen,
        "config_digest": s.digest(config),
        "affordance_policy_id": afford.POLICY_ID,
        "builder_sha256": sha(ROOT / "src/alifelm/experiments/action_affordance.py"),
        "command": "python -m pytest tests/test_stigmergy.py tests/test_action_codec.py tests/test_action_affordance.py -q",
        "stdout": run.stdout,
        "stderr": run.stderr,
        "python": sys.version,
    }))
    print(json.dumps({"gate": "PASS", "tests": run.stdout.strip()}), flush=True)


def _initial_from_history(store, run_id):
    return json.loads(store.db.execute("SELECT initial FROM stig_runs WHERE id=?", (run_id,)).fetchone()[0])


def _classify(store, worlds):
    counts = Counter()
    actions = Counter()
    bootstrap = 0
    reuse = 0
    committed = 0
    for run_id, _, _ in worlds:
        state = _initial_from_history(store, run_id)
        for row in store.history(run_id):
            events = json.loads(row["events"])
            attempts = {item["actor"]: item for item in json.loads(row["request"])["attempts"]}
            for event in events:
                item = attempts[event["actor"]]
                raw = s.resolve(store.cas, item["raw_ref"])
                try:
                    candidate = s.parse(raw, state["condition"])
                except (ValueError, TypeError, UnicodeError, json.JSONDecodeError):
                    counts["protocol_rejection"] += 1
                    continue
                counts["parser_valid_candidates"] += 1
                try:
                    desc = json.loads(s.resolve(store.cas, item["affordance_ref"]))
                    afford.validate_candidate(candidate, desc)
                    counts["affordance_valid_candidates"] += 1
                except (ValueError, TypeError, UnicodeError, json.JSONDecodeError):
                    counts["affordance_rejection"] += 1
                action = candidate["action"]
                actions[action] += 1
                counts[action] += 1
                if event["gateway"] == "PASS":
                    counts["gateway_valid_intents"] += 1
                if event["status"] == "ACCEPTED":
                    counts["committed_actions"] += 1
                    committed += 1
                    if action == "WAIT":
                        counts["semantic_WAIT"] += 1
                    if action == "TRACE" and not state["traces"]:
                        bootstrap += 1
                    if action == "REUSE" and state["traces"]:
                        reuse += 1
                elif event.get("layer") == "kernel" or event["status"] == "CONFLICT":
                    counts["kernel_rejection"] += 1
                elif event["gateway"] == "FAIL":
                    counts["semantic_rejection"] += 1
            state = json.loads(row["state"])
    counts["trace_bootstrap"] = bootstrap
    counts["trace_reuse"] = reuse
    counts["committed_actions"] = committed
    counts["inference_timeout"] = 0
    counts["transport_failure"] = 0
    counts["model_load_failure"] = 0
    return counts, actions


def audit(output, candidate=None):
    planned = json.loads((output / "planned.json").read_bytes())
    result = candidate if candidate is not None else json.loads((output / "result.json").read_bytes())
    check_seal(planned)
    check_seal(result)
    if result["planned_digest"] != planned["manifest_digest"]:
        raise ValueError("planned/final binding mismatch")
    for path, expected in result["evidence_hashes"].items():
        if sha(output / path) != expected:
            raise ValueError("evidence file mismatch: " + path)
    cas = FileSystemArtifactStore(output / "cas")
    store = gw.GroundedStore(output / "world.sqlite", cas)
    try:
        for run_id, expected in result["worlds"].items():
            if gw.metrics(store, run_id) != expected:
                raise ValueError("analysis/replay mismatch")
        for row in store.history(result["world_ids"][0]):
            request = json.loads(row["request"])
            for item in request["attempts"]:
                for key in ("context_ref", "raw_ref", "response_ref", "affordance_ref"):
                    s.resolve(cas, item[key])
        for cost in json.loads((output / "costs.json").read_bytes()):
            if "response_ref" in cost:
                response = json.loads(s.resolve(cas, cost["response_ref"]))
                if not response.get("generation_settings", {}).get("grammar"):
                    raise ValueError("constrained grammar missing from response evidence")
        probes = json.loads((output / "counterfactuals.json").read_bytes())
        for probe in probes:
            for key in ("intact_prompt_ref", "ablated_prompt_ref", "primary_raw_ref",
                        "repeat_raw_ref", "ablated_raw_ref", "repeat_response_ref", "ablated_response_ref"):
                s.resolve(cas, probe[key])
            history = store.history(probe["run_id"])
            before = json.loads(history[probe["tick"]-1]["state"]) if probe["tick"] else _initial_from_history(store, probe["run_id"])
            intact, intact_desc = afford.build(before, probe["actor"], cas)
            ablated, ablated_desc = afford.build(before, probe["actor"], cas, remove_traces=True)
            if s.resolve(cas, probe["intact_prompt_ref"]) != intact:
                raise ValueError("counterfactual intact context mismatch")
            if s.resolve(cas, probe["ablated_prompt_ref"]) != ablated:
                raise ValueError("counterfactual ablated context mismatch")
            event = next(e for e in json.loads(history[probe["tick"]]["events"]) if e["actor"] == probe["actor"])
            primary = s.resolve(cas, probe["primary_raw_ref"])
            repeat = s.resolve(cas, probe["repeat_raw_ref"])
            ablated_raw = s.resolve(cas, probe["ablated_raw_ref"])
            recalculated = s.attribution(before, probe["actor"], primary, repeat, ablated_raw, cas)
            if event["status"] != "ACCEPTED":
                recalculated["attributable"] = False
            if recalculated != probe["attribution"]:
                raise ValueError("counterfactual attribution mismatch")
            if probe["intact_grammar_sha256"] != intact_desc["grammar_sha256"] or probe["ablated_grammar_sha256"] != ablated_desc["grammar_sha256"]:
                raise ValueError("counterfactual grammar binding mismatch")
    finally:
        store.close()
    print(json.dumps({"audit": "PASS", "manifest_digest": result["manifest_digest"],
                      "interpretation": result["interpretation"]}), flush=True)


def execute(args):
    output = args.output.resolve()
    receipt = json.loads((output / "validation.json").read_bytes())
    check_seal(receipt)
    if receipt["status"] != "PASS" or receipt["sources"] != sources():
        raise ValueError("validation gate absent or stale")
    if (output / "planned.json").exists() or (output / "world.sqlite").exists():
        raise ValueError("evidence root already started; no model rerun/resume permitted")
    config = effective_config()
    if receipt.get("config_digest") != s.digest(config):
        raise ValueError("validation receipt has a different execution configuration")
    run_prefix = config["execution_id"]
    model_files = [p.resolve(strict=True) for p in args.models]
    if len(model_files) != 2 or len(set(model_files)) != 2:
        raise ValueError("exactly two distinct model artifacts required")
    model_info = [{"path": str(p), "sha256": sha(p), "bytes": p.stat().st_size} for p in model_files]
    for actual, expected in zip(model_info, config["models"], strict=True):
        if actual["sha256"] != expected["sha256"]:
            raise ValueError("model artifact differs from frozen provenance")
    executable = args.server.resolve(strict=True)
    git = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    gpu = subprocess.check_output([
        "nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.free", "--format=csv,noheader",
    ], text=True).strip()
    planned = seal({
        "experiment": s.VERSION,
        "config": config,
        "sources": sources(),
        "git_commit": git,
        "worktree": dirty,
        "models": model_info,
        "server": {"path": str(executable), "sha256": sha(executable),
                   "library_hashes": {p.name: sha(p) for p in sorted(executable.parent.glob("*.dll"))}},
        "validation_digest": receipt["manifest_digest"],
        "python": sys.version,
        "platform": platform.platform(),
        "gpu": gpu,
        "inference": "LOCAL_LLAMA_CPP_DIRECT_COMPLETION_Q8_GROUNDED_AFFORDANCE",
        "affordance_policy_id": afford.POLICY_ID,
        "affordance_builder_sha256": sha(ROOT / "src/alifelm/experiments/action_affordance.py"),
        "phase": "EXP-STIG-001-R4",
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    write_new(output / "planned.json", planned)
    cas = FileSystemArtifactStore(output / "cas")
    store = gw.GroundedStore(output / "world.sqlite", cas)
    worlds = []
    for block_index, block in enumerate(config["blocks"]):
        for condition in config["conditions"]:
            run_id = f"{run_prefix}-{block}-{condition}"
            store.create(s.initial_state(run_id, condition, cas))
            worlds.append((run_id, block, config["model_assignment"][block_index]))
    exposed = set()
    probes = []
    costs = []
    loads = []
    started = time.monotonic()
    try:
        for tick in range(config["ticks"]):
            jobs = []
            for run_id, block, assignment in worlds:
                state = store.state(run_id)
                for index, actor in enumerate(s.AGENTS):
                    prompt, desc = afford.build(state, actor, cas)
                    s.put(cas, prompt)
                    jobs.append({
                        "run_id": run_id,
                        "state": state,
                        "actor": actor,
                        "condition": state["condition"],
                        "model_index": assignment[index],
                        "seed": r3.seed_for(block, tick, actor),
                        "prompt": prompt,
                        "affordance": desc,
                    })
            completed = {run_id: [] for run_id, _, _ in worlds}
            for model_index, path in enumerate(model_files):
                server = r3.Server(
                    executable, path, config["runtime"],
                    output / f"server-primary-{tick}-{model_index}.log", args.port,
                )
                loads.append({"phase": "primary", "tick": tick, "model": model_index,
                              "seconds": server.load_seconds, "command": server.command})
                try:
                    for job in [j for j in jobs if j["model_index"] == model_index]:
                        raw, response = server.generate(
                            job["prompt"], job["seed"], config["generation"],
                            grammar=job["affordance"]["grammar"],
                        )
                        item = gw.attempt(
                            job["state"], job["actor"], model_info[model_index]["sha256"],
                            job["seed"], job["prompt"], job["affordance"], raw, response, cas,
                        )
                        completed[job["run_id"]].append(item)
                        response_ref = s.put(cas, s.encode(response))
                        costs.append({
                            "phase": "primary",
                            "run_id": job["run_id"],
                            "tick": job["state"]["tick"],
                            "actor": job["actor"],
                            "model": model_index,
                            "state_hash": s.digest(job["state"]),
                            "context_version": job["affordance"]["context_version"],
                            "affordance_sha256": job["affordance"]["affordance_sha256"],
                            "grammar_sha256": job["affordance"]["grammar_sha256"],
                            "actions_exposed": list(job["affordance"]["actions"]),
                            "visible_refs": job["affordance"]["visible_refs"],
                            "timings": response.get("timings", {}),
                            "seconds": response["observed_wall_seconds"],
                            "response_ref": response_ref,
                        })
                        key = (job["run_id"], job["actor"])
                        if key not in exposed and any(t["creator"] != job["actor"] for t in job["state"]["traces"]):
                            exposed.add(key)
                            probes.append({**job, "primary_raw_ref": item["raw_ref"], "attempt_id": item["attempt_id"]})
                        print(json.dumps({
                            "phase": "primary", "tick": tick, "run": job["run_id"],
                            "actor": job["actor"], "request_complete": True,
                        }), flush=True)
                finally:
                    server.close()
            for run_id, _, _ in worlds:
                store.commit(store.state(run_id), completed[run_id])
            write_new(output / f"tick-{tick}.json", {
                run_id: s.digest(store.replay(run_id)) for run_id, _, _ in worlds
            })
        probe_evidence = []
        for model_index, path in enumerate(model_files):
            selected = [j for j in probes if j["model_index"] == model_index]
            if not selected:
                continue
            server = r3.Server(
                executable, path, config["runtime"],
                output / f"server-counterfactual-{model_index}.log", args.port,
            )
            loads.append({"phase": "counterfactual", "model": model_index,
                          "seconds": server.load_seconds, "command": server.command})
            try:
                for job in selected:
                    intact, intact_desc = afford.build(job["state"], job["actor"], cas)
                    ablated, ablated_desc = afford.build(job["state"], job["actor"], cas, remove_traces=True)
                    repeat, repeat_response = server.generate(
                        intact, job["seed"], config["generation"], grammar=intact_desc["grammar"],
                    )
                    ablated_raw, ablated_response = server.generate(
                        ablated, job["seed"], config["generation"], grammar=ablated_desc["grammar"],
                    )
                    record = {
                        "run_id": job["run_id"],
                        "tick": job["state"]["tick"],
                        "actor": job["actor"],
                        "model": model_index,
                        "seed": job["seed"],
                        "attempt_id": job["attempt_id"],
                        "intact_prompt_ref": s.put(cas, intact),
                        "ablated_prompt_ref": s.put(cas, ablated),
                        "intact_grammar_sha256": intact_desc["grammar_sha256"],
                        "ablated_grammar_sha256": ablated_desc["grammar_sha256"],
                        "primary_raw_ref": job["primary_raw_ref"],
                        "repeat_raw_ref": s.put(cas, repeat),
                        "ablated_raw_ref": s.put(cas, ablated_raw),
                        "repeat_response_ref": s.put(cas, s.encode(repeat_response)),
                        "ablated_response_ref": s.put(cas, s.encode(ablated_response)),
                    }
                    record["attribution"] = s.attribution(
                        job["state"], job["actor"],
                        s.resolve(cas, job["primary_raw_ref"]), repeat, ablated_raw, cas,
                    )
                    row = store.history(job["run_id"])[job["state"]["tick"]]
                    event = next(e for e in json.loads(row["events"]) if e["actor"] == job["actor"])
                    if event["status"] != "ACCEPTED":
                        record["attribution"]["attributable"] = False
                    probe_evidence.append(record)
                    for response in (repeat_response, ablated_response):
                        costs.append({
                            "phase": "counterfactual",
                            "model": model_index,
                            "run_id": job["run_id"],
                            "seconds": response["observed_wall_seconds"],
                            "timings": response.get("timings", {}),
                            "response_ref": s.put(cas, s.encode(response)),
                        })
            finally:
                server.close()
        write_new(output / "counterfactuals.json", probe_evidence)
        write_new(output / "costs.json", costs)
        write_new(output / "loads.json", loads)
        results = {run_id: gw.metrics(store, run_id) for run_id, _, _ in worlds}
        deltas = []
        for block in config["blocks"]:
            a_result, b_result, c_result = [
                results[f"{run_prefix}-{block}-{condition}"] for condition in "ABC"
            ]
            deltas.append({
                "block": block,
                "B_minus_A_use_rate": b_result["environment_use_rate"] - a_result["environment_use_rate"],
                "C_minus_B_use_rate": c_result["environment_use_rate"] - b_result["environment_use_rate"],
            })
        chains = [probe for probe in probe_evidence if probe["attribution"]["attributable"]]
        s1 = all(d["B_minus_A_use_rate"] > 0 for d in deltas) and any(p["run_id"].endswith("-B") for p in chains)
        s2 = all(d["C_minus_B_use_rate"] > 0 for d in deltas) and any(
            p["run_id"].endswith("-C") and p["attribution"]["register_change"] for p in chains
        )
        s3 = (s1 or s2) and len({p["model"] for p in chains}) == 2 and len(
            {p["run_id"].split("-")[-2] for p in chains}
        ) >= 2
        interpretation = "S3" if s3 else "S2" if s2 else "S1" if s1 else "S0"
        outcome_counts, action_counts = _classify(store, worlds)
        outcome_counts["primary_opportunities"] = len(config["blocks"]) * len(config["conditions"]) * len(s.AGENTS) * config["ticks"]
        store.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        store.close()
        store = None
        evidence = {
            p.name: sha(p) for p in output.iterdir()
            if p.is_file() and p.name not in ("result.json", "REPORT.md")
            and not p.name.endswith(("-wal", "-shm"))
        }
        final = seal({
            "status": "COMPLETE",
            "planned_digest": planned["manifest_digest"],
            "world_ids": [run_id for run_id, _, _ in worlds],
            "worlds": results,
            "paired_differences": deltas,
            "attributable_chains": len(chains),
            "counterfactual_exposures": len(probes),
            "S1": bool(s1),
            "S2": bool(s2),
            "S3": bool(s3),
            "interpretation": interpretation,
            "outcome_counts": dict(outcome_counts),
            "action_counts": dict(action_counts),
            "requests": len(costs),
            "primary_requests": sum(c["phase"] == "primary" for c in costs),
            "tokens_prompt": sum(c["timings"].get("prompt_n", 0) for c in costs),
            "tokens_generated": sum(c["timings"].get("predicted_n", 0) for c in costs),
            "wall_seconds": time.monotonic() - started,
            "evidence_hashes": evidence,
            "limits": [
                "R4 is a bounded exploratory assay; no population inference",
                "S0 is no demonstrated effect in this run, not proof traces lack value",
                "no scientific fitness or broad utility claim",
            ],
        })
        if sources() != planned["sources"]:
            raise ValueError("source/protocol changed during execution")
        audit(output, candidate=final)
        write_new(output / "result.json", final)
    except BaseException as error:
        if store is not None:
            store.close()
        write_new(output / "failure.json", {
            "status": "INCOMPLETE_INVALID",
            "error": repr(error),
            "no_semantic_retry": True,
            "planned_digest": planned["manifest_digest"],
        })
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--validate-only", action="store_true")
    modes.add_argument("--execute", action="store_true")
    modes.add_argument("--audit", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--server", type=Path)
    parser.add_argument("--models", nargs=2, type=Path)
    parser.add_argument("--port", type=int, default=18989)
    args = parser.parse_args()
    if not args.output.is_absolute() or (os.name == "nt" and args.output.drive.upper() != "E:"):
        parser.error("explicit E: evidence path required on Windows; absolute path elsewhere")
    if args.validate_only:
        validation_gate(args.output)
    elif args.audit:
        audit(args.output)
    else:
        if not args.server or not args.models:
            parser.error("execute requires server and two model paths")
        execute(args)


if __name__ == "__main__":
    main()
