#!/usr/bin/env python3
"""EXP-STIG-002 instrumental-persistence deterministic gate and real pilot.

The pilot is deliberately bounded to one world per treatment, three persistent
identities and two ticks (18 model opportunities).  It uses the R4 grounded
grammar builder and the local llama.cpp HTTP adapter, but has its own state,
event and evidence boundary.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import copy
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

from alifelm.experiments import instrumental_affordance as afford
from alifelm.experiments import instrumental_world as world
from alifelm.persistence.cas import FileSystemArtifactStore
import exp_stig_001_r3 as r3

SPEC = ROOT / "specs/experiments/EXP-STIG-002-v1.yaml"
PROFILE = ROOT / "specs/experiments/EXP-STIG-002-execution-pilot.yaml"
BOUND = [
    SPEC, PROFILE, Path(__file__),
    ROOT / "src/alifelm/experiments/instrumental_affordance.py",
    ROOT / "src/alifelm/experiments/instrumental_world.py",
    ROOT / "src/alifelm/experiments/stigmergy.py",
    ROOT / "src/alifelm/persistence/cas.py",
    ROOT / "src/alifelm/persistence/migrations.py",
    ROOT / "tests/test_instrumental_persistence.py",
    ROOT / "tests/test_stigmergy.py",
    ROOT / "tests/test_action_codec.py",
    ROOT / "tests/test_action_affordance.py",
]


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sources() -> dict[str, str]:
    return {path.relative_to(ROOT).as_posix(): sha(path) for path in BOUND}


def write_new(path: Path, value) -> None:
    data = world.encode(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError("immutable evidence mismatch: " + str(path))
        return
    with path.open("xb") as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())


def seal(value: dict) -> dict:
    return {**value, "manifest_digest": world.digest(value)}


def check_seal(value: dict) -> None:
    if value.get("manifest_digest") != world.digest({k: v for k, v in value.items() if k != "manifest_digest"}):
        raise ValueError("manifest self-digest mismatch")


def effective_config() -> dict:
    config = json.loads(SPEC.read_bytes())
    profile = json.loads(PROFILE.read_bytes())
    if sha(SPEC) != profile["scientific_config_sha256"]:
        raise ValueError("scientific configuration hash mismatch")
    if profile["execution_id"] != "EXP-STIG-002-PILOT" or profile["pilot_opportunities"] != 18:
        raise ValueError("pilot profile mismatch")
    if profile["conditions"] != ["A", "B", "C"] or profile["agents"] != list(world.AGENTS):
        raise ValueError("treatment/cohort mismatch")
    if profile["worlds_per_condition"] != 1 or profile["ticks"] != 2:
        raise ValueError("pilot size mismatch")
    if profile["model_assignment"] != [[0, 1, 0]]:
        raise ValueError("heterogeneous assignment mismatch")
    expected_generation = {
        "temperature": 0.0, "top_k": 1, "top_p": 1.0, "min_p": 0.0,
        "repeat_penalty": 1.0, "n_predict": 128, "cache_prompt": False,
        "stream": False,
    }
    if profile["generation"] != expected_generation:
        raise ValueError("generation policy changed")
    if any(profile.get(key) for key in ("retries", "fallback", "repair")):
        raise ValueError("retry/fallback/repair forbidden")
    config["profile"] = profile
    return config


def _fixture_attempts(state: dict, cas, overrides: dict[str, bytes] | None = None) -> list[dict]:
    overrides = overrides or {}
    items = []
    for actor in world.AGENTS:
        prompt, desc = afford.build(state, actor)
        items.append(world.attempt(
            state, actor, "CAPABILITY_FIXTURE", 1, prompt, desc,
            overrides.get(actor, world.encode({"action": "WAIT", "payload": {}})),
            {"tokens": [], "fixture": True}, cas,
        ))
    return items


def affordance_qualification() -> dict:
    """Check conditional language and references without model behavior."""
    records = []
    for condition in ("A", "B", "C"):
        state = world.initial_state("QUAL-002-" + condition, condition)
        desc = afford.affordance(state, "X17")
        records.append({"state": condition + "_initial", "actions": list(desc["actions"]),
                        "refs": desc["visible_refs"], "grammar_sha256": desc["grammar_sha256"]})
        assert "REUSE" not in desc["actions"]
        assert "TCTRL" not in desc["grammar"]
        if condition == "C":
            candidate = {"action": "COMMIT", "payload": {"fact_id": "F1", "value": "amber"}}
            afford.validate_candidate(candidate, desc)
        controlled = copy.deepcopy(state)
        controlled["traces"].append({"id": "TCTRL", "creator": "X29", "fact_id": "F1",
                                      "value": "amber", "note": "fixture", "parent": None, "tick": 0})
        visible = afford.affordance(controlled, "X17")
        if condition in ("B", "C"):
            assert "REUSE" in visible["actions"] and visible["actions"]["REUSE"]["trace_ids"] == ["TCTRL"]
            afford.validate_candidate({"action": "REUSE", "payload": {"trace_id": "TCTRL"}}, visible)
        else:
            assert "REUSE" not in visible["actions"]
        with_error = {"action": "REUSE", "payload": {"trace_id": "TSTALE"}}
        try:
            afford.validate_candidate(with_error, visible)
        except ValueError:
            pass
        else:
            raise AssertionError("stale trace reference was afforded")
        records.append({"state": condition + "_controlled_trace", "actions": list(visible["actions"]),
                        "refs": visible["visible_refs"], "grammar_sha256": visible["grammar_sha256"]})
    # Exhausted objective facts must omit INSPECT from the language.
    complete = world.initial_state("QUAL-002-COMPLETE", "B")
    complete["knowledge"]["X17"]["F2"] = "cedar"
    complete_desc = afford.affordance(complete, "X17")
    assert "INSPECT" not in complete_desc["actions"]
    # Strict parser behavior remains independent of grammar enforcement.
    try:
        world.parse(b'{"action":"WAIT","payload":{}} trailing', "B")
    except (ValueError, json.JSONDecodeError):
        pass
    else:
        raise AssertionError("trailing data accepted")
    try:
        world.parse(b'{"action":"WAIT","payload":{},"authority":"admin"}', "B")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown authority field accepted")
    return {"status": "PASS", "states": records,
            "policy_id": afford.POLICY_ID, "builder_version": afford.BUILDER_VERSION}


def validation_gate(output: Path) -> None:
    config = effective_config()
    frozen = sources()
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    command = [sys.executable, "-m", "pytest", "tests/test_instrumental_persistence.py",
               "tests/test_stigmergy.py", "tests/test_action_codec.py", "tests/test_action_affordance.py", "-q"]
    run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    qualification = affordance_qualification()
    if run.returncode or qualification["status"] != "PASS" or frozen != sources():
        raise RuntimeError("EXP-STIG-002 deterministic gate failed: " + run.stdout + run.stderr)
    write_new(output / "validation.json", seal({
        "status": "PASS", "phase": "DETERMINISTIC_FAULT_REPLAY_AND_AFFORDANCE_GATE",
        "sources": frozen, "config_digest": world.digest(config), "qualification": qualification,
        "command": "python -m pytest tests/test_instrumental_persistence.py tests/test_stigmergy.py tests/test_action_codec.py tests/test_action_affordance.py -q",
        "stdout": run.stdout, "stderr": run.stderr, "python": sys.version,
    }))
    print(json.dumps({"gate": "PASS", "tests": run.stdout.strip(), "affordance": "PASS"}), flush=True)


def seed_for(condition: str, tick: int, actor: str) -> int:
    return int(world.digest(["EXP-STIG-002-PILOT", condition, tick, actor])[:8], 16) & 0x7fffffff


def _failure_kind(error: BaseException) -> str:
    text = repr(error).lower()
    return "inference_timeout" if "timeout" in text or "timed out" in text else "transport_runtime_failure"


def _gpu_info() -> str:
    try:
        return subprocess.check_output(["nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.free",
                                       "--format=csv,noheader"], text=True, stderr=subprocess.STDOUT).strip()
    except (OSError, subprocess.CalledProcessError) as error:
        return "UNAVAILABLE: " + str(error)


def _git_info() -> tuple[str, str]:
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
        return commit, dirty
    except (OSError, subprocess.CalledProcessError) as error:
        return "UNAVAILABLE", repr(error)


def _classify(output: Path, store: world.InstrumentalStore, jobs_by_tick: dict[int, list[dict]], failures: dict[tuple[str, int, str], str]):
    counts = Counter()
    actions = Counter()
    observations = []
    bootstrap = reuse = 0
    duplicated = Counter()
    submitted = []
    chains = []
    for condition in ("A", "B", "C"):
        run_id = f"EXP-STIG-002-PILOT-{condition}"
        state = world.initial_state(run_id, condition)
        for tick in range(2):
            jobs = {(j["run_id"], j["actor"]): j for j in jobs_by_tick[tick] if j["run_id"] == run_id}
            before_trace_ids = {t["id"] for t in state["traces"]}
            for actor in world.AGENTS:
                item = next(a for a in json.loads(store.history(run_id)[tick]["request"])['attempts'] if a["actor"] == actor)
                event = next(e for e in json.loads(store.history(run_id)[tick]["events"]) if e["actor"] == actor)
                key = (run_id, tick, actor)
                failure = failures.get(key)
                raw = world.base.resolve(store.cas, item["raw_ref"])
                record = {"run_id": run_id, "condition": condition, "tick": tick, "actor": actor,
                          "attempt_id": item["attempt_id"], "event": event, "failure_kind": failure}
                if failure:
                    counts[failure] += 1
                    observations.append(record)
                    continue
                try:
                    candidate = world.parse(raw, condition)
                except (ValueError, TypeError, UnicodeError, json.JSONDecodeError):
                    counts["protocol_rejection"] += 1
                    observations.append(record)
                    continue
                counts["parser_valid_candidates"] += 1
                action = candidate["action"]
                actions[action] += 1
                counts["valid_model_action_intent"] += 1
                try:
                    desc = json.loads(world.base.resolve(store.cas, item["affordance_ref"]))
                    afford.validate_candidate(candidate, desc)
                    counts["affordance_valid_candidates"] += 1
                except (ValueError, TypeError, UnicodeError, json.JSONDecodeError):
                    counts["affordance_rejection"] += 1
                    observations.append(record)
                    continue
                if event["gateway"] == "PASS":
                    counts["gateway_valid_intents"] += 1
                    counts["committed_actions"] += 1
                    if action == "TRACE" and not before_trace_ids:
                        bootstrap += 1
                        counts["trace_bootstrap"] += 1
                    if action == "REUSE" and before_trace_ids:
                        reuse += 1
                        counts["trace_reuse"] += 1
                        source = event.get("source_creator")
                        if source and source != actor and not any(m["sender"] == source and m["target"] == actor for m in state["messages"]):
                            chains.append({"run_id": run_id, "tick": tick, "actor": actor,
                                           "source_creator": source, "trace_id": event.get("trace_id")})
                    if action == "INSPECT":
                        duplicated[candidate["payload"]["fact_id"]] += 1
                    if action == "SUBMIT":
                        submitted.append({"condition": condition, "actor": actor,
                                           "correct": event.get("correct", False),
                                           "exploration_cost": event.get("exploration_cost", 0)})
                else:
                    if event["status"] == "CONFLICT":
                        counts["kernel_conflict"] += 1
                    else:
                        counts["semantic_rejection"] += 1
                record["action"] = action
                record["candidate"] = candidate
                observations.append(record)
            state = json.loads(store.history(run_id)[tick]["state"])
    counts["generation_opportunities"] = 18
    counts["generation_completed"] = 18 - sum(v for k, v in counts.items() if k in {
        "inference_timeout", "transport_runtime_failure", "model_load_failure"})
    counts["duplicated_exploration"] = sum(max(0, n - 1) for n in duplicated.values())
    counts["stigmery_chains"] = len(chains)
    return dict(counts), dict(actions), observations, submitted, chains


def execute(args) -> None:
    output = args.output.resolve()
    validation = json.loads((output / "validation.json").read_bytes())
    check_seal(validation)
    config = effective_config()
    if validation["status"] != "PASS" or validation["sources"] != sources() or validation["config_digest"] != world.digest(config):
        raise ValueError("validation gate absent or stale")
    if any((output / name).exists() for name in ("planned.json", "world.sqlite", "result.json")):
        raise ValueError("evidence root already started; no resume/rerun permitted")
    model_files = [path.resolve(strict=True) for path in args.models]
    if len(model_files) != 2 or len(set(model_files)) != 2:
        raise ValueError("exactly two heterogeneous model artifacts required")
    model_info = [{"path": str(path), "sha256": sha(path), "bytes": path.stat().st_size} for path in model_files]
    for actual, expected in zip(model_info, config["profile"]["models"], strict=True):
        if actual["sha256"] != expected["sha256"]:
            raise ValueError("model artifact differs from frozen profile")
    executable = args.server.resolve(strict=True)
    commit, dirty = _git_info()
    planned = seal({
        "experiment": world.VERSION, "execution_id": config["profile"]["execution_id"],
        "scientific_config_sha256": sha(SPEC), "profile": config["profile"],
        "sources": sources(), "git_commit": commit, "worktree": dirty,
        "models": model_info, "server": {"path": str(executable), "sha256": sha(executable)},
        "gpu": _gpu_info(), "python": sys.version, "platform": platform.platform(),
        "generation": config["profile"]["generation"], "constraint_transport": "llama.cpp_completion_grammar",
        "constraint_policy_id": afford.POLICY_ID, "builder_version": afford.BUILDER_VERSION,
        "assignment": config["profile"]["model_assignment"], "seeds": "SHA256(EXP-STIG-002-PILOT,condition,tick,actor)",
        "phase": "REAL_MODEL_PILOT_18_OPPORTUNITIES", "large_run_authorized": False,
    })
    write_new(output / "planned.json", planned)
    cas = FileSystemArtifactStore(output / "cas")
    store = world.InstrumentalStore(output / "world.sqlite", cas)
    runs = {condition: f"EXP-STIG-002-PILOT-{condition}" for condition in ("A", "B", "C")}
    for condition, run_id in runs.items():
        store.create(world.initial_state(run_id, condition))
    jobs_by_tick = defaultdict(list)
    failures: dict[tuple[str, int, str], str] = {}
    costs, loads = [], []
    started = time.monotonic()
    try:
        for tick in range(2):
            jobs = []
            for condition, run_id in runs.items():
                state = store.state(run_id)
                for index, actor in enumerate(world.AGENTS):
                    prompt, desc = afford.build(state, actor)
                    jobs.append({"run_id": run_id, "condition": condition, "state": state, "actor": actor,
                                 "model_index": config["profile"]["model_assignment"][0][index],
                                 "seed": seed_for(condition, tick, actor), "prompt": prompt, "desc": desc})
                    jobs_by_tick[tick].append(jobs[-1])
            completed = defaultdict(list)
            for model_index, model_path in enumerate(model_files):
                selected = [job for job in jobs if job["model_index"] == model_index]
                server = None
                try:
                    try:
                        server = r3.Server(executable, model_path, config["profile"]["runtime"],
                                           output / f"server-{tick}-{model_index}.log", args.port)
                        loads.append({"tick": tick, "model_index": model_index, "status": "PASS",
                                      "seconds": server.load_seconds, "command": server.command})
                    except BaseException as error:
                        loads.append({"tick": tick, "model_index": model_index, "status": "FAIL",
                                      "failure": repr(error)})
                        for job in selected:
                            kind = "model_load_failure"
                            failures[(job["run_id"], tick, job["actor"])] = kind
                            item = world.attempt(job["state"], job["actor"], model_info[model_index]["sha256"],
                                                 job["seed"], job["prompt"], job["desc"], b"",
                                                 {"failure_kind": kind}, cas)
                            completed[job["run_id"]].append(item)
                        continue
                    for job in selected:
                        raw = b""
                        response = None
                        failure = None
                        request_started = time.monotonic()
                        try:
                            raw, response = server.generate(job["prompt"], job["seed"], config["profile"]["generation"],
                                                            grammar=job["desc"]["grammar"])
                        except BaseException as error:
                            failure = _failure_kind(error)
                            failures[(job["run_id"], tick, job["actor"])] = failure
                            response = {"failure_kind": failure, "error": repr(error),
                                        "observed_wall_seconds": time.monotonic() - request_started}
                        item = world.attempt(job["state"], job["actor"], model_info[model_index]["sha256"],
                                             job["seed"], job["prompt"], job["desc"], raw, response or {}, cas)
                        completed[job["run_id"]].append(item)
                        costs.append({"run_id": job["run_id"], "condition": job["condition"], "tick": tick,
                                      "actor": job["actor"], "model_index": model_index, "seed": job["seed"],
                                      "prompt_bytes": len(job["prompt"]), "raw_bytes": len(raw),
                                      "seconds": (response or {}).get("observed_wall_seconds", time.monotonic() - request_started),
                                      "timings": (response or {}).get("timings", {}), "response_ref": item["response_ref"],
                                      "failure_kind": failure})
                finally:
                    if server is not None:
                        server.close()
            tick_observations = []
            for condition, run_id in runs.items():
                after = store.commit(store.state(run_id), completed[run_id])
                events = json.loads(store.history(run_id)[tick]["events"])
                attempts = {a["actor"]: a for a in completed[run_id]}
                for event in events:
                    tick_observations.append({"run_id": run_id, "tick": tick, "actor": event["actor"],
                                              "attempt_id": attempts[event["actor"]]["attempt_id"], "event": event,
                                              "failure_kind": failures.get((run_id, tick, event["actor"]))})
            write_new(output / f"tick-{tick}.json", {"tick": tick, "observations": tick_observations,
                                                   "world_hashes": {run_id: world.digest(store.replay(run_id)) for run_id in runs.values()}})
        store.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        counts, actions, observations, submissions, chains = _classify(output, store, jobs_by_tick, failures)
        metrics = {run_id: world.metrics(store, run_id) for run_id in runs.values()}
        writes = [item for item in observations if item.get("action") in ("TRACE", "REUSE")]
        result = {
            "status": "PILOT_COMPLETE", "planned_digest": planned["manifest_digest"],
            "worlds": metrics, "outcome_counts": counts, "action_counts": actions,
            "submissions": submissions, "attributable_stigmergic_chains": chains,
            "requests": len(costs), "primary_requests": len(costs),
            "tokens_prompt": sum(c["timings"].get("prompt_n", 0) for c in costs),
            "tokens_generated": sum(c["timings"].get("predicted_n", 0) for c in costs),
            "prompt_bytes": sum(c["prompt_bytes"] for c in costs), "raw_bytes": sum(c["raw_bytes"] for c in costs),
            "wall_seconds": time.monotonic() - started,
            "pre_registered": {"P0": counts.get("trace_bootstrap", 0) == 0,
                               "P1": counts.get("trace_bootstrap", 0) > 0,
                               "P2": counts.get("trace_reuse", 0) > 0,
                               "P3": "UNTESTABLE_WITHOUT_TRACE_SIGNAL",
                               "P4": "UNTESTABLE_IN_SINGLE_WORLD_PER_CONDITION_PILOT"},
            "pilot_signal": counts.get("trace_bootstrap", 0) > 0,
            "large_run": "NOT_RUN_BY_PREREGISTERED_STOP_RULE",
            "evidence_hashes": {},
            "limits": ["pilot only: one world per condition", "three persistent identities, two ticks",
                        "no population estimate or cross-world replication", "no trace means reuse/utility cannot be inferred"],
        }
        write_new(output / "costs.json", costs)
        write_new(output / "loads.json", loads)
        write_new(output / "observations.json", observations)
        result["evidence_hashes"] = {path.name: sha(path) for path in output.iterdir()
                                      if path.is_file() and path.name not in ("result.json",) and not path.name.endswith(("-wal", "-shm"))}
        check_seal(planned)
        result = seal(result)
        audit(output, candidate=result)
        write_new(output / "result.json", result)
        print(json.dumps({"run": "COMPLETE", "requests": len(costs), "trace_bootstrap": counts.get("trace_bootstrap", 0),
                          "trace_reuse": counts.get("trace_reuse", 0), "result": result["manifest_digest"]}), flush=True)
    except BaseException as error:
        try:
            store.close()
        finally:
            write_new(output / "failure.json", {"status": "INCOMPLETE_INVALID", "error": repr(error),
                                                 "planned_digest": planned["manifest_digest"]})
        raise
    finally:
        try:
            store.close()
        except Exception:
            pass


def audit(output: Path, candidate: dict | None = None) -> None:
    planned = json.loads((output / "planned.json").read_bytes())
    result = candidate if candidate is not None else json.loads((output / "result.json").read_bytes())
    check_seal(planned)
    check_seal(result)
    if result["planned_digest"] != planned["manifest_digest"]:
        raise ValueError("planned/final binding mismatch")
    for name, expected in result["evidence_hashes"].items():
        if sha(output / name) != expected:
            raise ValueError("evidence hash mismatch: " + name)
    cas = FileSystemArtifactStore(output / "cas")
    store = world.InstrumentalStore(output / "world.sqlite", cas)
    try:
        for run_id, expected in result["worlds"].items():
            if world.metrics(store, run_id) != expected:
                raise ValueError("world metrics/replay mismatch")
            store.replay(run_id)
        for row in json.loads((output / "observations.json").read_bytes()):
            if row.get("attempt_id"):
                # The attempt and all referenced bytes are validated by replay;
                # this check ensures the observation is tied to a committed row.
                if not any(row["attempt_id"] in json.loads(commit["events"])[i].get("attempt_id", "")
                           for commit in store.history(row["run_id"]) for i in range(len(json.loads(commit["events"])))):
                    # Observations are keyed from history but a rejected protocol
                    # event still has an attempt id; fail closed if it disappears.
                    raise ValueError("observation attempt not present in history")
    finally:
        store.close()
    print(json.dumps({"audit": "PASS", "manifest_digest": result["manifest_digest"]}), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--validate-only", action="store_true")
    modes.add_argument("--execute", action="store_true")
    modes.add_argument("--audit", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--server", type=Path)
    parser.add_argument("--models", nargs=2, type=Path)
    parser.add_argument("--port", type=int, default=18872)
    args = parser.parse_args()
    if not args.output.is_absolute() or (os.name == "nt" and args.output.drive.upper() != "E:"):
        parser.error("explicit E: evidence path required on Windows; absolute path elsewhere")
    if args.validate_only:
        validation_gate(args.output)
    elif args.audit:
        audit(args.output)
    else:
        if not args.server or not args.models:
            parser.error("execute requires --server and two --models")
        execute(args)


if __name__ == "__main__":
    main()
