#!/usr/bin/env python3
"""Bounded EXP-STIG-001 gate, local inference, counterfactuals and replay audit."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from alifelm.experiments import stigmergy as s
from alifelm.experiments import action_codec as codec
from alifelm.persistence.cas import FileSystemArtifactStore

SPEC = ROOT / "specs/experiments/EXP-STIG-001-v1.yaml"
R3_PROFILE = ROOT / "specs/experiments/EXP-STIG-001-execution-r3.yaml"
BOUND = [SPEC, R3_PROFILE, Path(__file__),
         ROOT / "src/alifelm/experiments/stigmergy.py", ROOT / "src/alifelm/experiments/action_codec.py",
         ROOT / "tests/test_stigmergy.py", ROOT / "tests/test_action_codec.py",
         ROOT / "src/alifelm/persistence/cas.py", ROOT / "src/alifelm/persistence/migrations.py"]


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
    if config["generation"] != {"temperature": 0.0, "top_k": 1, "top_p": 1.0,
            "min_p": 0.0, "repeat_penalty": 1.0, "n_predict": 128, "cache_prompt": False, "stream": False}:
        raise ValueError("generation freeze mismatch")


def effective_config():
    config = json.loads(SPEC.read_bytes())
    profile = json.loads(R3_PROFILE.read_bytes())
    if sha(SPEC) != profile["scientific_config_sha256"]:
        raise ValueError("R3 scientific configuration mismatch")
    expected = {
        "execution_id": "EXP-STIG-001-R3",
        "qualification_status": "PASS",
        "request_timeout_seconds": 900,
        "model_load_timeout_seconds": 600,
        "maximum_operational_replications": 1,
        "reuse_previous_responses": False,
        "scientific_treatment_changes": False,
        "treatment_definitions_unchanged": True,
        "generation_policy_unchanged": True,
    }
    if any(profile.get(key) != value for key, value in expected.items()):
        raise ValueError("unregistered R3 qualification profile")
    if profile["constraint_policy_id"] != codec.POLICY_ID:
        raise ValueError("constraint policy mismatch")
    if set(profile["constraint_policy_hashes"]) != {"A", "B", "C"}:
        raise ValueError("constraint condition coverage mismatch")
    for condition in ("A", "B", "C"):
        if profile["constraint_policy_hashes"][condition] != codec.policy(condition)["grammar_sha256"]:
            raise ValueError("constraint grammar hash mismatch")
    config["execution_id"] = profile["execution_id"]
    config["runtime"]["request_timeout_seconds"] = profile["request_timeout_seconds"]
    config["runtime"]["model_load_timeout_seconds"] = profile["model_load_timeout_seconds"]
    config["operational_r3"] = profile
    validate_config(config)
    return config

def validation_gate(output):
    config = effective_config()
    frozen = sources()
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    run = subprocess.run([sys.executable, "-m", "pytest", "tests/test_stigmergy.py",
                          "tests/test_action_codec.py", "-q"],
                         cwd=ROOT, env=env, capture_output=True, text=True)
    if run.returncode or frozen != sources():
        raise RuntimeError("R3 deterministic/codec gate failed: " + run.stdout + run.stderr)
    write_new(output / "validation.json", seal({"status": "PASS", "sources": frozen,
              "config_digest": s.digest(config),
              "command": "python -m pytest tests/test_stigmergy.py tests/test_action_codec.py -q",
              "stdout": run.stdout, "stderr": run.stderr, "python": sys.version}))
    print(json.dumps({"gate": "PASS", "tests": run.stdout.strip()}), flush=True)

class Server:
    """One local Q8 file at a time. No semantic retries or prompt repair."""
    def __init__(self, executable, model, config, log, port):
        with socket.socket() as check:
            check.bind(("127.0.0.1", port))
        self.command = [str(executable), "-m", str(model), "-c", str(config["context"]),
            "-ngl", str(config["gpu_layers"]), "-t", str(config["threads"]), "--parallel", "1",
            "--host", "127.0.0.1", "--port", str(port), "--no-webui"]
        self.log = log.open("xb")
        env = {k: v for k, v in os.environ.items() if not k.startswith("LLAMA_ARG_")}
        self.process = subprocess.Popen(self.command, stdout=self.log, stderr=subprocess.STDOUT, env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.url = "http://127.0.0.1:" + str(port)
        self.timeout = config["request_timeout_seconds"]
        started = time.monotonic()
        try:
            while time.monotonic() - started < config.get("model_load_timeout_seconds", 180):
                if self.process.poll() is not None:
                    raise RuntimeError("local model server exited; inspect " + str(log))
                try:
                    with urllib.request.urlopen(self.url + "/health", timeout=2) as response:
                        if json.load(response).get("status") == "ok":
                            self.load_seconds = time.monotonic() - started
                            return
                except (OSError, ValueError):
                    pass
                time.sleep(0.5)
            raise RuntimeError("local model load timeout")
        except BaseException:
            self.close()
            raise

    def generate(self, prompt, seed, generation, *, grammar=None):
        started = time.monotonic()
        payload = {**generation, "prompt": prompt.decode("utf-8"), "seed": seed}
        if grammar is not None:
            payload["grammar"] = grammar
        request = urllib.request.Request(self.url + "/completion", data=s.encode(payload),
                                        headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            result = json.load(response)
        if not isinstance(result.get("content"), str) or result.get("truncated", False):
            raise RuntimeError("invalid runtime response or context truncation")
        result["observed_wall_seconds"] = time.monotonic() - started
        return result["content"].encode(), result

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        self.log.close()



def seed_for(block, tick, actor):
    # Identical across matched conditions; run condition never enters generation seed.
    return int(s.digest(["STIG_SEED_V1", block, tick, actor])[:8], 16) & 0x7fffffff


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
    store = s.StigStore(output / "world.sqlite", cas)
    try:
        for run_id, expected in result["worlds"].items():
            if s.metrics(store, run_id) != expected:
                raise ValueError("analysis/replay mismatch")
        for cost in json.loads((output / "costs.json").read_bytes()):
            if "response_ref" in cost:
                s.resolve(cas, cost["response_ref"])
        for probe in json.loads((output / "counterfactuals.json").read_bytes()):
            for key in ("intact_prompt_ref", "ablated_prompt_ref", "primary_raw_ref", "repeat_raw_ref", "ablated_raw_ref",
                        "repeat_response_ref", "ablated_response_ref"):
                s.resolve(cas, probe[key])
            history = store.history(probe["run_id"])
            before = json.loads(history[probe["tick"]-1]["state"]) if probe["tick"] else json.loads(
                store.db.execute("SELECT initial FROM stig_runs WHERE id=?", (probe["run_id"],)).fetchone()[0])
            if s.resolve(cas, probe["intact_prompt_ref"]) != s.render(before, probe["actor"], cas):
                raise ValueError("counterfactual intact context mismatch")
            if s.resolve(cas, probe["ablated_prompt_ref"]) != s.render(before, probe["actor"], cas, remove_traces=True):
                raise ValueError("counterfactual changed more than trace visibility")
            primary = next(a for a in json.loads(history[probe["tick"]]["request"])["attempts"] if a["actor"] == probe["actor"])
            if primary["attempt_id"] != probe["attempt_id"] or primary["raw_ref"] != probe["primary_raw_ref"] or primary["seed"] != probe["seed"]:
                raise ValueError("counterfactual/primary binding mismatch")
            recalculated = s.attribution(before, probe["actor"], s.resolve(cas, probe["primary_raw_ref"]),
                s.resolve(cas, probe["repeat_raw_ref"]), s.resolve(cas, probe["ablated_raw_ref"]), cas)
            event = next(e for e in json.loads(history[probe["tick"]]["events"]) if e["actor"] == probe["actor"])
            if event["status"] != "ACCEPTED":
                recalculated["attributable"] = False
            if recalculated != probe["attribution"]:
                raise ValueError("causal attribution mismatch")
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
    run_prefix = config.get("execution_id", "EXP-STIG-001")
    model_files = [p.resolve(strict=True) for p in args.models]
    if len(model_files) != 2 or len(set(model_files)) != 2:
        raise ValueError("exactly two distinct model artifacts required")
    model_info = [{"path": str(p), "sha256": sha(p), "bytes": p.stat().st_size} for p in model_files]
    for actual, expected in zip(model_info, config["models"], strict=True):
        if actual["sha256"] != expected["sha256"]:
            raise ValueError("model artifact differs from frozen provenance")
    if len({m["sha256"] for m in model_info}) != 2:
        raise ValueError("heterogeneous artifact hashes required")
    executable = args.server.resolve(strict=True)
    git = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    gpu = subprocess.check_output(["nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.free",
                                   "--format=csv,noheader"], text=True).strip()
    planned = seal({"experiment": s.VERSION, "config": config, "sources": sources(), "git_commit": git,
        "worktree": dirty, "models": model_info, "server": {"path": str(executable), "sha256": sha(executable),
            "library_hashes": {p.name: sha(p) for p in sorted(executable.parent.glob("*.dll"))}},
        "validation_digest": receipt["manifest_digest"], "python": sys.version, "platform": platform.platform(), "gpu": gpu,
        "inference": "LOCAL_LLAMA_CPP_DIRECT_COMPLETION_Q8_CONSTRAINED",
        "constraint_policy_id": codec.POLICY_ID,
        "constraint_policy_hashes": {c: codec.policy(c)["grammar_sha256"] for c in config["conditions"]},
        "constraint_transport": "llama.cpp_completion_grammar",
        "phase": "EXPLORATORY_NOT_FOUNDER_ADMISSION", "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    write_new(output / "planned.json", planned)
    cas = FileSystemArtifactStore(output / "cas")
    store = s.StigStore(output / "world.sqlite", cas)
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
            # Full P3 compile/persist barrier before any P4 inference in this tick.
            jobs = []
            for run_id, block, assignment in worlds:
                state = store.state(run_id)
                for index, actor in enumerate(s.AGENTS):
                    prompt = s.render(state, actor, cas)
                    s.put(cas, prompt)
                    jobs.append({"run_id": run_id, "state": state, "actor": actor,
                        "condition": state["condition"], "model_index": assignment[index],
                        "seed": seed_for(block, tick, actor), "prompt": prompt})
            completed = {run_id: [] for run_id, _, _ in worlds}
            for model_index, path in enumerate(model_files):
                server = Server(executable, path, config["runtime"], output / f"server-primary-{tick}-{model_index}.log", args.port)
                loads.append({"phase": "primary", "tick": tick, "model": model_index,
                              "seconds": server.load_seconds, "command": server.command})
                try:
                    for job in [j for j in jobs if j["model_index"] == model_index]:
                        raw, response = server.generate(job["prompt"], job["seed"], config["generation"],
                                                        grammar=codec.grammar_for(job["condition"]))
                        item = s.attempt(job["state"], job["actor"], model_info[model_index]["sha256"], job["seed"],
                                         job["prompt"], raw, response, cas)
                        completed[job["run_id"]].append(item)
                        costs.append({"phase": "primary", "run_id": job["run_id"], "tick": tick,
                            "actor": job["actor"], "model": model_index, "timings": response.get("timings", {}),
                            "seconds": response["observed_wall_seconds"], "response_ref": s.put(cas, s.encode(response))})
                        key = (job["run_id"], job["actor"])
                        if key not in exposed and any(t["creator"] != job["actor"] for t in job["state"]["traces"]):
                            exposed.add(key)
                            probes.append({**job, "primary_raw_ref": item["raw_ref"], "attempt_id": item["attempt_id"]})
                        print(json.dumps({"phase": "primary", "tick": tick, "run": job["run_id"], "actor": job["actor"],
                                          "request_complete": True}), flush=True)
                finally:
                    server.close()
            for run_id, _, _ in worlds:
                store.commit(store.state(run_id), completed[run_id])
            write_new(output / f"tick-{tick}.json", {run_id: s.digest(store.replay(run_id)) for run_id, _, _ in worlds})
        probe_evidence = []
        for model_index, path in enumerate(model_files):
            selected = [j for j in probes if j["model_index"] == model_index]
            if not selected:
                continue
            server = Server(executable, path, config["runtime"], output / f"server-counterfactual-{model_index}.log", args.port)
            loads.append({"phase": "counterfactual", "model": model_index, "seconds": server.load_seconds, "command": server.command})
            try:
                for job in selected:
                    intact = job["prompt"]
                    ablated_prompt = s.render(job["state"], job["actor"], cas, remove_traces=True)
                    repeat, repeat_response = server.generate(intact, job["seed"], config["generation"],
                                                               grammar=codec.grammar_for(job["condition"]))
                    ablated, ablated_response = server.generate(ablated_prompt, job["seed"], config["generation"],
                                                                grammar=codec.grammar_for(job["condition"]))
                    record = {"run_id": job["run_id"], "tick": job["state"]["tick"], "actor": job["actor"],
                        "model": model_index, "seed": job["seed"], "attempt_id": job["attempt_id"],
                        "intact_prompt_ref": s.put(cas, intact), "ablated_prompt_ref": s.put(cas, ablated_prompt),
                        "primary_raw_ref": job["primary_raw_ref"], "repeat_raw_ref": s.put(cas, repeat),
                        "ablated_raw_ref": s.put(cas, ablated), "repeat_response_ref": s.put(cas, s.encode(repeat_response)),
                        "ablated_response_ref": s.put(cas, s.encode(ablated_response))}
                    record["attribution"] = s.attribution(job["state"], job["actor"],
                        s.resolve(cas, job["primary_raw_ref"]), repeat, ablated, cas)
                    row = store.history(job["run_id"])[job["state"]["tick"]]
                    event = next(e for e in json.loads(row["events"]) if e["actor"] == job["actor"])
                    if event["status"] != "ACCEPTED":
                        record["attribution"]["attributable"] = False
                    probe_evidence.append(record)
                    for response in (repeat_response, ablated_response):
                        costs.append({"phase": "counterfactual", "model": model_index, "run_id": job["run_id"],
                                      "seconds": response["observed_wall_seconds"], "timings": response.get("timings", {})})
            finally:
                server.close()
        write_new(output / "counterfactuals.json", probe_evidence)
        write_new(output / "costs.json", costs)
        write_new(output / "loads.json", loads)
        results = {run_id: s.metrics(store, run_id) for run_id, _, _ in worlds}
        deltas = []
        for block in config["blocks"]:
            a, b, c = [results[f"{run_prefix}-{block}-{x}"] for x in "ABC"]
            deltas.append({"block": block, "B_minus_A_use_rate": b["environment_use_rate"]-a["environment_use_rate"],
                           "C_minus_B_use_rate": c["environment_use_rate"]-b["environment_use_rate"]})
        chains = [p for p in probe_evidence if p["attribution"]["attributable"]]
        s1 = all(d["B_minus_A_use_rate"] > 0 for d in deltas) and any(p["run_id"].endswith("-B") for p in chains)
        s2 = all(d["C_minus_B_use_rate"] > 0 for d in deltas) and any(p["run_id"].endswith("-C") and p["attribution"]["register_change"] for p in chains)
        s3 = (s1 or s2) and len({p["model"] for p in chains}) == 2 and len({p["run_id"].split("-")[-2] for p in chains}) >= 2
        interpretation = "S3" if s3 else "S2" if s2 else "S1" if s1 else "S0"
        # Classify every primary model opportunity without merging protocol,
        # semantic, kernel, or runtime outcomes.
        outcome_counts = Counter()
        action_counts = Counter()
        for run_id, _, _ in worlds:
            for row in store.history(run_id):
                request = json.loads(row["request"])
                events = {event["actor"]: event for event in json.loads(row["events"])}
                for item in request["attempts"]:
                    actor = item["actor"]
                    event = events[actor]
                    raw = s.resolve(cas, item["raw_ref"])
                    try:
                        candidate = s.parse(raw, item.get("condition", run_id.rsplit("-", 1)[-1]))
                    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError):
                        outcome_counts["protocol_rejection"] += 1
                        continue
                    action = candidate["action"]
                    outcome_counts["valid_model_action_intent"] += 1
                    action_counts[action] += 1
                    if action == "WAIT":
                        outcome_counts["semantic_WAIT"] += 1
                    elif action == "SEND":
                        outcome_counts["SEND"] += 1
                    elif action == "TRACE":
                        outcome_counts["TRACE"] += 1
                    elif action == "REUSE":
                        outcome_counts["REUSE"] += 1
                    elif action == "SET":
                        outcome_counts["SET"] += 1
                    if event["status"] in ("REJECTED", "CONFLICT"):
                        outcome_counts["gateway_kernel_rejection"] += 1
        outcome_counts["inference_timeout"] = 0
        outcome_counts["model_load_failure"] = 0
        outcome_counts["transport_runtime_failure"] = 0
        outcome_counts["primary_opportunities"] = len(config["blocks"]) * len(config["conditions"]) * len(s.AGENTS) * config["ticks"]
        store.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        store.close()
        store = None
        evidence = {p.name: sha(p) for p in output.iterdir() if p.is_file() and p.suffix not in ("-wal", "-shm")
                    and p.name not in ("result.json", "REPORT.md") and not p.name.endswith(("-wal", "-shm"))}
        final = seal({"status": "COMPLETE", "planned_digest": planned["manifest_digest"], "worlds": results,
            "paired_differences": deltas, "attributable_chains": len(chains), "counterfactual_exposures": len(probes),
            "S1": bool(s1), "S2": bool(s2), "S3": bool(s3), "interpretation": interpretation,
            "outcome_counts": dict(outcome_counts), "action_counts": dict(action_counts),
            "requests": len(costs), "primary_requests": sum(c["phase"] == "primary" for c in costs),
            "tokens_prompt": sum(c["timings"].get("prompt_n", 0) for c in costs),
            "tokens_generated": sum(c["timings"].get("predicted_n", 0) for c in costs),
            "wall_seconds": time.monotonic()-started, "evidence_hashes": evidence,
            "limits": ["bounded exploratory assay; no population inference", "no equivalence claim from S0",
                       "general utility and specialization not identifiable from four ticks", "no scientific fitness"]})
        if sources() != planned["sources"]:
            raise ValueError("source/protocol changed during execution")
        audit(output, candidate=final)
        write_new(output / "result.json", final)
    except BaseException as error:
        if store is not None:
            store.close()
        write_new(output / "failure.json", {"status": "INCOMPLETE_INVALID", "error": repr(error),
                  "no_semantic_retry": True, "planned_digest": planned["manifest_digest"]})
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
    parser.add_argument("--port", type=int, default=18871)
    parser.add_argument("--recovery", action="store_true", help="use the frozen, one-time R2 deadline overlay")
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
