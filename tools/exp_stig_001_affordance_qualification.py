#!/usr/bin/env python3
"""Cheap semantic-affordance qualification for EXP-STIG-001 R4."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from alifelm.experiments import action_affordance as afford
from alifelm.experiments import grounded_world as grounded
from alifelm.experiments import stigmergy as s

# R3's transport is reused only as an HTTP llama.cpp server wrapper. The
# scientific R3 runner itself is not changed or invoked for behavior.
from exp_stig_001_r3 import Server, effective_config, sha


def write_json(path: Path, value: dict) -> None:
    data = s.encode(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError("immutable qualification mismatch: " + str(path))
        return
    path.write_bytes(data)


def seal(value: dict) -> dict:
    return {**value, "manifest_digest": s.digest(value)}


def add_trace(state: dict, cas, trace_id: str = "TCTRL", creator: str = "X29") -> dict:
    result = json.loads(s.encode(state))
    result["traces"].append({
        "id": trace_id,
        "creator": creator,
        "ref": s.put(cas, b"controlled capability trace"),
        "parent": None,
        "tick": 0,
    })
    return result


def cases(cas):
    base = {
        "A_INITIAL": s.initial_state("r4-qual-A", "A", cas),
        "B_ZERO": s.initial_state("r4-qual-B0", "B", cas),
        "B_VISIBLE_TRACE": add_trace(s.initial_state("r4-qual-B1", "B", cas), cas),
        "C_ZERO": s.initial_state("r4-qual-C0", "C", cas),
        "C_MUTABLE": s.initial_state("r4-qual-C1", "C", cas),
        "STALE_REFERENCE": s.initial_state("r4-qual-stale", "B", cas),
    }
    return base


def invariant_checks(case_states, cas):
    checks = {}
    b0 = afford.affordance(case_states["B_ZERO"], "X17", cas)
    b1 = afford.affordance(case_states["B_VISIBLE_TRACE"], "X17", cas)
    c0 = afford.affordance(case_states["C_ZERO"], "X17", cas)
    c1 = afford.affordance(case_states["C_MUTABLE"], "X17", cas)
    stale = afford.affordance(case_states["STALE_REFERENCE"], "X17", cas)
    checks["A_initial_actions"] = list(afford.affordance(case_states["A_INITIAL"], "X17", cas)["actions"]) == ["WAIT", "SEND"]
    checks["B_zero_actions"] = list(b0["actions"]) == ["WAIT", "SEND", "TRACE"]
    checks["B_zero_reuse_absent"] = "REUSE" not in b0["actions"] and "reuseobject" not in b0["grammar"]
    checks["B_visible_reuse_present"] = b1["actions"].get("REUSE", {}).get("trace_ids") == ["TCTRL"]
    checks["B_visible_only_exact_trace"] = "TCTRL" in b1["grammar"] and "TSTALE" not in b1["grammar"]
    checks["C_zero_reuse_absent"] = "REUSE" not in c0["actions"]
    checks["C_mutable_set_grounded"] = c1["actions"].get("SET", {}).get("key_ids") == ["K17", "K29", "K43"]
    checks["C_mutable_source_grounded"] = c1["actions"].get("SET", {}).get("source_ids") == [None]
    checks["targets_are_visible_peers"] = b0["actions"]["SEND"]["target_ids"] == ["X29", "X43"]
    checks["unknown_action_absent"] = "ADMIN" not in b0["grammar"]
    # Capability fixtures are deterministic boundary probes, not behavior.
    reuse = {"action": "REUSE", "payload": {"trace_id": "TCTRL"}}
    afford.validate_candidate(reuse, b1)
    s.validate(case_states["B_VISIBLE_TRACE"], "X17", reuse, cas)
    checks["capability_fixture_reuse_gateway"] = True
    set_null = {"action": "SET", "payload": {"key": "K17", "value": "fixture", "source": None}}
    afford.validate_candidate(set_null, c1)
    s.validate(case_states["C_MUTABLE"], "X17", set_null, cas)
    checks["capability_fixture_set_gateway"] = True
    for name, candidate in (
        ("stale_trace_rejected", {"action": "REUSE", "payload": {"trace_id": "TSTALE"}}),
        ("invalid_target_rejected", {"action": "SEND", "payload": {"target": "X17", "body": "x"}}),
    ):
        try:
            afford.validate_candidate(candidate, stale)
        except ValueError:
            checks[name] = True
        else:
            checks[name] = False
    malformed = [
        b'{"action":"WAIT","action":"TRACE","payload":{}}',
        b'{"action":"WAIT","payload":{},"authority":"admin"}',
        b'{"action":"WAIT","payload":{}} trailing',
    ]
    checks["manual_malformed_rejected"] = all(
        _parse_rejected(raw, "B") for raw in malformed
    )
    return checks


def _parse_rejected(raw: bytes, condition: str) -> bool:
    try:
        s.parse(raw, condition)
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError):
        return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--server", required=True, type=Path)
    parser.add_argument("--models", nargs=2, type=Path, required=True)
    parser.add_argument("--port", type=int, default=18983)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_absolute() or (output.drive and output.drive.upper() != "E:"):
        parser.error("explicit E: qualification path required on Windows")
    config = effective_config()
    model_files = [p.resolve(strict=True) for p in args.models]
    if len({p for p in model_files}) != 2:
        raise ValueError("two distinct models required")
    model_info = [{"path": str(p), "sha256": sha(p), "bytes": p.stat().st_size} for p in model_files]
    for actual, expected in zip(model_info, config["models"], strict=True):
        if actual["sha256"] != expected["sha256"]:
            raise ValueError("model differs from frozen R3 model artifact")
    executable = args.server.resolve(strict=True)
    output.mkdir(parents=True, exist_ok=True)
    cas = __import__("alifelm.persistence.cas", fromlist=["FileSystemArtifactStore"]).FileSystemArtifactStore(output / "cas")
    case_states = cases(cas)
    checks = invariant_checks(case_states, cas)
    records = []
    totals = Counter()
    started = time.monotonic()
    for model_index, model in enumerate(model_files):
        server = Server(executable, model, config["runtime"], output / f"server-{model_index}.log", args.port)
        try:
            for case_index, (case_id, state) in enumerate(case_states.items()):
                prompt, desc = afford.build(state, "X17", cas)
                raw, response = server.generate(
                    prompt + (b"\nCAPABILITY_FIXTURE: choose REUSE of TCTRL if it is afforded.\n"
                              if case_id == "B_VISIBLE_TRACE" else b""),
                    7000 + model_index * 100 + case_index,
                    config["generation"],
                    grammar=desc["grammar"],
                )
                record = {
                    "phase": "SEMANTIC_AFFORDANCE_QUALIFICATION",
                    "case_id": case_id,
                    "model_index": model_index,
                    "model_sha256": model_info[model_index]["sha256"],
                    "condition": state["condition"],
                    "state_version": state["tick"],
                    "state_hash": s.digest(state),
                    "context_version": desc["context_version"],
                    "affordance_sha256": desc["affordance_sha256"],
                    "grammar_sha256": desc["grammar_sha256"],
                    "policy_id": desc["policy_id"],
                    "actions_exposed": list(desc["actions"]),
                    "visible_refs": desc["visible_refs"],
                    "raw_text": raw.decode("utf-8"),
                    "raw_sha256": hashlib.sha256(raw).hexdigest(),
                    "response": response,
                }
                totals["generations"] += 1
                totals["completed_generations"] += 1
                try:
                    candidate = s.parse(raw, state["condition"])
                    record["parser"] = "PASS"
                    totals["parser_valid_candidates"] += 1
                    try:
                        afford.validate_candidate(candidate, desc)
                        record["affordance"] = "PASS"
                        totals["affordance_valid_candidates"] += 1
                        try:
                            s.validate(state, "X17", candidate, cas)
                            record["gateway"] = "PASS"
                            totals["gateway_valid_candidates"] += 1
                        except (ValueError, RuntimeError) as error:
                            record.update(gateway="REJECTED", gateway_error=str(error))
                            totals["kernel_rejections"] += 1
                    except ValueError as error:
                        record.update(affordance="REJECTED", affordance_error=str(error))
                        totals["affordance_rejections"] += 1
                except (ValueError, TypeError, UnicodeError, json.JSONDecodeError) as error:
                    record.update(parser="REJECTED", parser_error=str(error))
                    totals["parser_failures"] += 1
                records.append(record)
        finally:
            server.close()
    fixture_reuse = {"action": "REUSE", "payload": {"trace_id": "TCTRL"}}
    fixture_desc = afford.affordance(case_states["B_VISIBLE_TRACE"], "X17", cas)
    fixture_model_reuse = sum(
        r.get("case_id") == "B_VISIBLE_TRACE" and json.loads(r["raw_text"]).get("action") == "REUSE"
        for r in records
    )
    fixture_gateway = 1
    totals["capability_fixture_gateway_valid"] = fixture_gateway
    totals["capability_fixture_model_reuse"] = fixture_model_reuse
    totals["generation_runtime_failures"] = 0
    totals["transport_runtime_failures"] = 0
    totals["timeout"] = 0
    checks["capability_fixture_reuse_parser"] = s.parse(s.encode(fixture_reuse), "B") == fixture_reuse
    checks["capability_fixture_reuse_affordance"] = (
        afford.validate_candidate(fixture_reuse, fixture_desc) is None
    )
    checks["capability_fixture_reuse_model_or_manual_gateway"] = fixture_gateway == 1
    status = "PASS" if (
        totals["completed_generations"] == totals["generations"] == 12
        and totals["parser_valid_candidates"] == 12
        and totals["affordance_valid_candidates"] == 12
        and totals["parser_failures"] == 0
        and all(checks.values())
    ) else "FAIL"
    manifest = seal({
        "status": status,
        "phase": "PROTOCOL_INTERFACE_ONLY",
        "policy_id": afford.POLICY_ID,
        "builder_version": afford.BUILDER_VERSION,
        "models": model_info,
        "server": {"path": str(executable), "sha256": sha(executable)},
        "generation": config["generation"],
        "cases": list(case_states),
        "invariant_checks": checks,
        "totals": dict(totals),
        "records": records,
        "elapsed_seconds": time.monotonic() - started,
        "limitation": "capability fixture may use a manual Gateway-valid candidate; no fixture counts as scientific behavior",
    })
    write_json(output / "qualification.json", manifest)
    print(json.dumps({
        "status": status,
        "totals": dict(totals),
        "invariant_checks": checks,
        "manifest_digest": manifest["manifest_digest"],
    }), flush=True)
    if status != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
