#!/usr/bin/env python3
"""EXP-STIG-003 persistence-necessary retention deterministic gate and real pilot.

The pilot is deliberately bounded to one world per treatment, three persistent
identities and four ticks (36 model opportunities).  It uses the grounded
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

from alifelm.experiments import retention_affordance as afford
from alifelm.experiments import retention_world as world
from alifelm.persistence.cas import FileSystemArtifactStore
import exp_stig_001_r3 as r3

SPEC = ROOT / "specs/experiments/EXP-STIG-003-v3.yaml"
PROFILE = ROOT / "specs/experiments/EXP-STIG-003-execution-pilot-v3.yaml"
BOUND = [
    SPEC, PROFILE, Path(__file__),
    ROOT / "src/alifelm/experiments/retention_affordance.py",
    ROOT / "src/alifelm/experiments/retention_world.py",
    ROOT / "src/alifelm/experiments/stigmergy.py",
    ROOT / "src/alifelm/persistence/cas.py",
    ROOT / "src/alifelm/persistence/migrations.py",
    ROOT / "tests/test_retention_persistence.py",
    ROOT / "tests/test_instrumental_persistence.py",
    ROOT / "tests/test_stigmergy.py",
    ROOT / "tests/test_action_codec.py",
    ROOT / "tests/test_action_affordance.py",
]
ENVIRONMENTAL = {"persistent_knowledge", "environmental_trace", "environmental_world_state"}
SCAN_ONLY_VALUES = {world.FACTS[fact] for facts in world.SCANNABLE.values() for fact in facts}


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
    if profile["execution_id"] != "EXP-STIG-003-PILOT-V3" or profile["pilot_opportunities"] != 36:
        raise ValueError("pilot profile mismatch")
    if profile["conditions"] != ["A", "B", "C"] or profile["agents"] != list(world.AGENTS):
        raise ValueError("treatment/cohort mismatch")
    if profile["worlds_per_condition"] != 1 or profile["ticks"] != 4 or profile["submission_tick"] != 3:
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


def capability_chain(work: Path) -> dict:
    """One full INSPECT -> TRACE -> REUSE -> SUBMIT chain per persistent treatment."""
    chains = []
    for condition in ("B", "C"):
        cas = FileSystemArtifactStore(work / f"capability-{condition}" / "cas")
        store = world.RetentionStore(work / f"capability-{condition}" / "world.sqlite", cas)
        try:
            state = world.initial_state("QUAL-003-CHAIN-" + condition, condition)
            store.create(state)
            current = store.commit(state, _fixture_attempts(state, cas, {"X17": world.encode(
                {"action": "INSPECT", "payload": {"fact_id": "F2"}})}))
            current = store.commit(current, _fixture_attempts(current, cas, {"X17": world.encode(
                {"action": "TRACE", "payload": {"fact_id": "F2", "value": "cedar", "note": "fixture"}})}))
            current = store.commit(current, _fixture_attempts(current, cas, {"X17": world.encode(
                {"action": "REUSE", "payload": {"trace_id": current["traces"][0]["id"]}})}))
            current = store.commit(current, _fixture_attempts(current, cas, {"X17": world.encode(
                {"action": "SUBMIT", "payload": {"answer": "F1=amber|F2=cedar"}})}))
            submission = current["submissions"][-1]
            assert submission["correct"] is True and submission["verified"] is True
            assert store.replay(state["run_id"]) == current
            chains.append({"condition": condition, "status": "PASS", "trace_id": current["traces"][0]["id"]})
        finally:
            store.close()
    return {"status": "PASS", "chains": chains}


def affordance_qualification() -> dict:
    """Check conditional language and references without model behavior."""
    records = []
    for condition in ("A", "B", "C"):
        state = world.initial_state("QUAL-003-" + condition, condition)
        desc = afford.affordance(state, "X17")
        records.append({"state": condition + "_initial", "actions": list(desc["actions"]),
                        "refs": desc["visible_refs"], "grammar_sha256": desc["grammar_sha256"]})
        assert "REUSE" not in desc["actions"]
        assert "SUBMIT" not in desc["actions"]
        assert "TRACE" not in desc["actions"]
        assert "INSPECT" in desc["actions"]
        assert "TCTRL" not in desc["grammar"]
        scanned = copy.deepcopy(state)
        scanned["scans"]["X17"]["F2"] = "cedar"
        scan_desc = afford.affordance(scanned, "X17")
        if condition in ("B", "C"):
            assert scan_desc["actions"]["TRACE"]["fact_ids"] == ["F2"]
        else:
            assert "TRACE" not in scan_desc["actions"]
        if condition == "C":
            assert scan_desc["actions"]["COMMIT"]["fact_ids"] == ["F1", "F2"]
            afford.validate_candidate({"action": "COMMIT", "payload": {"fact_id": "F2", "value": "cedar"}}, scan_desc)
        records.append({"state": condition + "_active_scan", "actions": list(scan_desc["actions"]),
                        "refs": scan_desc["visible_refs"], "grammar_sha256": scan_desc["grammar_sha256"]})
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
        windowed = copy.deepcopy(state)
        windowed["tick"] = state["submission_tick"]
        window_desc = afford.affordance(windowed, "X17")
        assert list(window_desc["actions"]) == ["WAIT", "SUBMIT"]
        assert window_desc["actions"]["SUBMIT"]["answer"] == "F1=value|F2=value"
        assert window_desc["actions"]["SUBMIT"]["values"] == ["amber"]
        assert '"amber"' in window_desc["grammar"] and '"cedar"' not in window_desc["grammar"]
        afford.validate_candidate({"action": "SUBMIT", "payload": {"answer": "F1=amber|F2=cedar"}}, window_desc)
        try:
            afford.validate_candidate({"action": "INSPECT", "payload": {"fact_id": "F2"}}, window_desc)
        except ValueError:
            pass
        else:
            raise AssertionError("INSPECT was afforded inside the submission window")
        records.append({"state": condition + "_submission_window", "actions": list(window_desc["actions"]),
                        "refs": window_desc["visible_refs"], "grammar_sha256": window_desc["grammar_sha256"]})
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
    command = [sys.executable, "-m", "pytest", "tests/test_retention_persistence.py",
               "tests/test_instrumental_persistence.py", "tests/test_stigmergy.py",
               "tests/test_action_codec.py", "tests/test_action_affordance.py", "-q"]
    run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    qualification = affordance_qualification()
    chains = capability_chain(output / "capability")
    if run.returncode or qualification["status"] != "PASS" or chains["status"] != "PASS" or frozen != sources():
        raise RuntimeError("EXP-STIG-003 deterministic gate failed: " + run.stdout + run.stderr)
    write_new(output / "validation.json", seal({
        "status": "PASS", "phase": "DETERMINISTIC_FAULT_REPLAY_AND_AFFORDANCE_GATE",
        "sources": frozen, "config_digest": world.digest(config), "qualification": qualification,
        "capability": chains,
        "command": "python -m pytest tests/test_retention_persistence.py tests/test_instrumental_persistence.py tests/test_stigmergy.py tests/test_action_codec.py tests/test_action_affordance.py -q",
        "stdout": run.stdout, "stderr": run.stderr, "python": sys.version,
    }))
    print(json.dumps({"gate": "PASS", "tests": run.stdout.strip(), "affordance": "PASS"}), flush=True)


def seed_for(condition: str, tick: int, actor: str) -> int:
    return int(world.digest(["EXP-STIG-003-PILOT", condition, tick, actor])[:8], 16) & 0x7fffffff


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


def _missing_of(actor: str) -> list[str]:
    return [fact for fact in world.OBJECTIVES[actor]["fact_ids"] if fact not in world.INITIAL_KNOWLEDGE[actor]]


def _classify(output: Path, store: world.RetentionStore, jobs_by_tick: dict[int, list[dict]], failures: dict[tuple[str, int, str], str]):
    counts = Counter()
    actions = Counter()
    observations = []
    submitted = []
    p1_models = set()
    p3_models = set()
    relay_messages = []
    for condition in ("A", "B", "C"):
        run_id = f"EXP-STIG-003-PILOT-V3-{condition}"
        state = world.initial_state(run_id, condition)
        for tick in range(4):
            jobs = {(j["run_id"], j["actor"]): j for j in jobs_by_tick[tick] if j["run_id"] == run_id}
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
                    if action == "SUBMIT" and tick < state["submission_tick"]:
                        counts["premature_submit_attempts"] += 1
                    observations.append(record)
                    continue
                if event["gateway"] == "PASS":
                    counts["gateway_valid_intents"] += 1
                    counts["committed_actions"] += 1
                    model_index = jobs[(run_id, actor)]["model_index"]
                    if action in ("TRACE", "COMMIT") and event.get("fact_id") in _missing_of(actor):
                        counts["objective_persistence_acts"] += 1
                        p1_models.add(model_index)
                    if action == "REUSE":
                        counts["trace_reuse"] += 1
                    if action == "INSPECT":
                        counts["scans_created"] += 1
                    if action == "SEND" and any(value in candidate["payload"]["body"] for value in SCAN_ONLY_VALUES):
                        relay_messages.append({"run_id": run_id, "tick": tick, "actor": actor,
                                               "target": candidate["payload"]["target"]})
                        counts["relay_messages"] += 1
                    if action == "SUBMIT":
                        provenance = event.get("provenance", {})
                        # Every missing fact is either mapped above or already
                        # internalized via REUSE, so an empty map is
                        # environmental by construction.
                        environmental = all(v in ENVIRONMENTAL for v in provenance.values())
                        entry = {"condition": condition, "actor": actor, "model_index": model_index,
                                 "correct": event.get("correct", False), "verified": event.get("verified", False),
                                 "provenance": provenance,
                                 "environmental": bool(event.get("correct")) and environmental,
                                 "exploration_cost": event.get("exploration_cost", 0)}
                        submitted.append(entry)
                        if entry["correct"]:
                            counts["correct_submissions"] += 1
                            if entry["environmental"]:
                                counts["environmental_completions"] += 1
                                p3_models.add(model_index)
                            if "unexplained" in provenance.values():
                                counts["unexplained_correct_submissions"] += 1
                else:
                    if event["status"] == "CONFLICT":
                        counts["kernel_conflict"] += 1
                    else:
                        counts["semantic_rejection"] += 1
                record["action"] = action
                record["candidate"] = candidate
                observations.append(record)
            state = json.loads(store.history(run_id)[tick]["state"])
    counts["generation_opportunities"] = 36
    counts["generation_completed"] = 36 - sum(v for k, v in counts.items() if k in {
        "inference_timeout", "transport_runtime_failure", "model_load_failure"})
    return dict(counts), dict(actions), observations, submitted, p1_models, p3_models, relay_messages


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
        "assignment": config["profile"]["model_assignment"], "seeds": "SHA256(EXP-STIG-003-PILOT,condition,tick,actor)",
        "phase": "REAL_MODEL_PILOT_V3_36_OPPORTUNITIES", "large_run_authorized": False,
    })
    write_new(output / "planned.json", planned)
    cas = FileSystemArtifactStore(output / "cas")
    store = world.RetentionStore(output / "world.sqlite", cas)
    runs = {condition: f"EXP-STIG-003-PILOT-V3-{condition}" for condition in ("A", "B", "C")}
    for condition, run_id in runs.items():
        store.create(world.initial_state(run_id, condition))
    jobs_by_tick = defaultdict(list)
    failures: dict[tuple[str, int, str], str] = {}
    costs, loads = [], []
    started = time.monotonic()
    try:
        for tick in range(4):
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
        counts, actions, observations, submissions, p1_models, p3_models, relay_messages = _classify(
            output, store, jobs_by_tick, failures)
        metrics = {run_id: world.metrics(store, run_id) for run_id in runs.values()}
        result = {
            "status": "PILOT_COMPLETE", "planned_digest": planned["manifest_digest"],
            "worlds": metrics, "outcome_counts": counts, "action_counts": actions,
            "submissions": submissions, "relay_messages": relay_messages,
            "requests": len(costs), "primary_requests": len(costs),
            "tokens_prompt": sum(c["timings"].get("prompt_n", 0) for c in costs),
            "tokens_generated": sum(c["timings"].get("predicted_n", 0) for c in costs),
            "prompt_bytes": sum(c["prompt_bytes"] for c in costs), "raw_bytes": sum(c["raw_bytes"] for c in costs),
            "wall_seconds": time.monotonic() - started,
            "pre_registered": {"P0": counts.get("objective_persistence_acts", 0) == 0,
                               "P1": counts.get("objective_persistence_acts", 0) > 0,
                               "P2": counts.get("trace_reuse", 0) > 0,
                               "P3": counts.get("environmental_completions", 0) > 0,
                               "P4": len(p1_models) == 2 and len(p3_models) == 2},
            "pilot_signal": counts.get("objective_persistence_acts", 0) > 0,
            "large_run": "NOT_RUN_BY_PREREGISTERED_STOP_RULE",
            "evidence_hashes": {},
            "limits": ["pilot only: one world per condition", "three persistent identities, four ticks",
                        "no population estimate or cross-world replication",
                        "condition A can complete only via peer relay, which is counted separately",
                        "unexplained correct submissions void the affected world pending audit"],
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
        print(json.dumps({"run": "COMPLETE", "requests": len(costs),
                          "objective_persistence_acts": counts.get("objective_persistence_acts", 0),
                          "environmental_completions": counts.get("environmental_completions", 0),
                          "result": result["manifest_digest"]}), flush=True)
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
    store = world.RetentionStore(output / "world.sqlite", cas)
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
    parser.add_argument("--port", type=int, default=18873)
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
