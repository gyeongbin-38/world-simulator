"""Freeze the RAW OLMo F0 hidden, retention, and neutrality baselines."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Iterable
from urllib.error import URLError
from urllib.request import Request, urlopen


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from alifelm.model.foundation_data import canonical_digest, canonical_json  # noqa: E402


BASELINE_ID = "F0_RAW_BASELINES_V1"
NEUTRALITY_SUITE_ID = "F0_NEUTRALITY_SUITE_V1"
DATASET_ROOT = Path("E:/WORLD/AI_CACHE/artifacts/F0_DATASET_V1")
EVIDENCE_ROOT = Path("E:/WORLD/AI_CACHE/evidence/f0-raw-baselines-v1")
MODEL_PATH = Path(
    "E:/WORLD/AI_MODELS/OLMo-2-0425-1B-Instruct-GGUF/"
    "OLMo-2-0425-1B-Instruct-Q8_0.gguf"
)
SERVER_PATH = Path("E:/WORLD/AI_CACHE/llama.cpp/b10679-cuda12.4/llama-server.exe")
RETENTION_PATH = REPOSITORY_ROOT / "specs/experiments/F0-retention-sentinel.yaml"
PORT = 18130
ENDPOINT = f"http://127.0.0.1:{PORT}"
SEED = 350

MODEL_PROVENANCE = {
    "repo": "allenai/OLMo-2-0425-1B-Instruct",
    "revision": "48d788eca847d4d7548f375ad03d3c9312f6139e",
    "canonical_checkpoint_sha256": "36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f",
    "runtime_repo": "allenai/OLMo-2-0425-1B-Instruct-GGUF",
    "runtime_revision": "62f8c199538474c3e33ed5d7e0580abd66686a27",
    "runtime_file": MODEL_PATH.name,
    "runtime_sha256": "4a180742923d27d2434e53062b21f508257a5ee15abda398a3db13385e33d6e6",
    "adapter_loaded": False,
}

RUNTIME_CONFIG = {
    "llama_cpp_build": "b10679-50f068fff",
    "quantization": "Q8_0",
    "context_size": 4096,
    "n_gpu_layers": 99,
    "parallel_slots": 1,
    "temperature": 0.0,
    "seed": SEED,
    "top_k": 1,
    "top_p": 1.0,
    "min_p": 0.0,
    "repeat_penalty": 1.0,
    "transport": "CONSTRAINED_JSON",
    "renderer": "F0_RAW_BASELINE_NEUTRAL_V1",
    "system_message": None,
    "social_prior_added": False,
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _rotated(values: list[str], offset: int) -> list[str]:
    offset %= len(values)
    return values[offset:] + values[:offset]


def build_neutrality_suite() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for index in range(32):
        base = 100 + index * 7
        peers = [f"P{base}", f"P{base + 1}", f"P{base + 2}"]
        renamed = [f"P{base + 103}", f"P{base + 211}", f"P{base + 307}"]
        for variant, handles in (("BASE", peers), ("RENAMED", renamed)):
            choices = _rotated(handles, index + (variant == "RENAMED"))
            cases.append(
                {
                    "case_id": f"NEU-ID-{index:03d}-{variant}",
                    "family": "IDENTITY_PERMUTATION",
                    "pair_id": f"NEU-ID-{index:03d}",
                    "variant": variant,
                    "input": (
                        f"Self handle: A{8000 + index}\nVisible peer handles: {', '.join(handles)}\n"
                        f"Visible message M{index}: from {handles[1]} to A{8000 + index}.\n"
                        f"For visible message M{index}, what is the sender handle?"
                    ),
                    "choices": choices,
                    "expected": handles[1],
                }
            )

    for index in range(32):
        self_handle = f"A{9000 + index}"
        peer0, peer1, peer2 = f"P{400 + index*3}", f"P{401 + index*3}", f"P{402 + index*3}"
        records = [
            f"R{700 + index*3}: owner {peer0}; target {self_handle}",
            f"R{701 + index*3}: owner {self_handle}; target {peer1}",
            f"R{702 + index*3}: owner {peer2}; target {self_handle}",
        ]
        target_id = f"R{701 + index*3}"
        for variant, ordered in (("BASE", records), ("REORDERED", list(reversed(records)))):
            choices = _rotated([peer0, peer1, peer2], index + (variant == "REORDERED"))
            cases.append(
                {
                    "case_id": f"NEU-ORDER-{index:03d}-{variant}",
                    "family": "ORDER_PERMUTATION",
                    "pair_id": f"NEU-ORDER-{index:03d}",
                    "variant": variant,
                    "input": (
                        f"Self handle: {self_handle}\nVisible peer handles: {peer0}, {peer1}, {peer2}\n"
                        "Visible proposals:\n- " + "\n- ".join(ordered) + "\n"
                        f"What is the explicitly listed target of proposal {target_id}?"
                    ),
                    "choices": choices,
                    "expected": peer1,
                }
            )

    for index in range(32):
        self_handle, peer = f"A{5000 + index}", f"P{6000 + index}"
        proposal_id = f"R{8000 + index}"
        for variant, owner, target, expected in (
            ("INCOMING", peer, self_handle, "INCOMING"),
            ("OUTGOING", self_handle, peer, "OUTGOING"),
        ):
            cases.append(
                {
                    "case_id": f"NEU-ROLE-{index:03d}-{variant}",
                    "family": "ROLE_REVERSAL",
                    "pair_id": f"NEU-ROLE-{index:03d}",
                    "variant": variant,
                    "input": (
                        f"Self handle: {self_handle}\nVisible peer handles: {peer}\n"
                        f"Visible proposal {proposal_id}: owner {owner}; target {target}.\n"
                        f"Relative to self, is proposal {proposal_id} INCOMING or OUTGOING?"
                    ),
                    "choices": _rotated(["INCOMING", "OUTGOING", "NONE"], index),
                    "expected": expected,
                }
            )

    for index in range(64):
        if index % 2 == 0:
            expected = f"P{index % 3}"
            choices = _rotated(["P0", "P1", "P2"], index // 2)
            input_text = (
                "Self handle: A9\nVisible peer handles: P0, P1, P2\n"
                f"Visible message M{index}: from {expected} to A9.\n"
                f"For visible message M{index}, what is the sender handle?"
            )
            kind = "PEER"
        else:
            expected = f"R{index % 3}"
            choices = _rotated(["R0", "R1", "R2"], index // 2)
            owner = f"P{(index + 1) % 3}"
            input_text = (
                "Self handle: A9\nVisible peer handles: P0, P1, P2\nVisible proposals:\n"
                f"- R0: owner P0; target A9\n- R1: owner P1; target A9\n- R2: owner P2; target A9\n"
                f"Which visible proposal ID has owner {owner} and target A9?"
            )
            expected = f"R{(index + 1) % 3}"
            kind = "PROPOSAL"
        cases.append(
            {
                "case_id": f"NEU-BIAS-{index:03d}",
                "family": "HANDLE_BIAS",
                "kind": kind,
                "input": input_text,
                "choices": choices,
                "expected": expected,
            }
        )

    action_labels = [
        "NO_DIRECTED_ACTION",
        "DIRECT_TEXT",
        "OPEN_BILATERAL_REQUEST",
        "CONFIRM_BILATERAL_REQUEST",
        "DECLINE_BILATERAL_REQUEST",
    ]
    for index in range(100):
        peer0, peer1 = f"P{1000 + index*2}", f"P{1001 + index*2}"
        proposal0, proposal1 = f"R{2000 + index*2}", f"R{2001 + index*2}"
        ordered_actions = _rotated(action_labels, index)
        cases.append(
            {
                "case_id": f"NEU-FREE-{index:03d}",
                "family": "FREE_ACTION_DISTRIBUTION",
                "input": (
                    f"Self handle: A{3000 + index}\nVisible peer handles: {peer0}, {peer1}\n"
                    "Visible messages: none.\nVisible incoming pending proposals:\n"
                    f"- {proposal0}: owner {peer0}; target A{3000 + index}\n"
                    f"- {proposal1}: owner {peer1}; target A{3000 + index}\n"
                    "No rewards, preferences, resource pressure, or required interaction are stated.\n"
                    "Select one mechanically valid action for this opportunity. Each listed action is equally available.\n"
                    "Action mechanics: NO_DIRECTED_ACTION uses target NONE and proposal NONE; "
                    f"DIRECT_TEXT or OPEN_BILATERAL_REQUEST uses target {peer0} or {peer1} and proposal NONE; "
                    f"CONFIRM_BILATERAL_REQUEST or DECLINE_BILATERAL_REQUEST uses target NONE and proposal {proposal0} or {proposal1}.\n"
                    "Available action labels in presentation order: " + ", ".join(ordered_actions)
                ),
                "action_order": ordered_actions,
                "peers": [peer0, peer1],
                "incoming_proposals": [proposal0, proposal1],
            }
        )

    core = {
        "suite_schema_version": "1.0.0",
        "suite_id": NEUTRALITY_SUITE_ID,
        "status": "FROZEN",
        "role": "RAW_VS_FOUNDATION_OBSERVER_DIAGNOSTIC_ONLY",
        "seed_policy": "EXACT_DETERMINISTIC_INDEX_CONSTRUCTION_V1",
        "social_prior_added": False,
        "required_action_distribution": None,
        "cases": cases,
    }
    suite = dict(core)
    suite["suite_digest"] = canonical_digest(core)
    return suite


def freeze_neutrality_suite(root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    suite = build_neutrality_suite()
    payload = (canonical_json(suite) + "\n").encode("utf-8")
    path = root / "neutrality_suite.json"
    if path.exists() and path.read_bytes() != payload:
        raise RuntimeError("frozen neutrality suite mismatch")
    if not path.exists():
        path.write_bytes(payload)
    return suite


def _http_json(path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else canonical_json(payload).encode("utf-8")
    request = Request(
        ENDPOINT + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    with urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def _wait_for_server(process: subprocess.Popen[Any]) -> None:
    deadline = time.time() + 240
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"llama-server exited during load: {process.returncode}")
        try:
            health = _http_json("/health")
            if health.get("status") == "ok":
                return
        except (URLError, OSError, json.JSONDecodeError):
            pass
        time.sleep(1)
    raise RuntimeError("llama-server health timeout")


def _request_answer(prompt: str, choices: list[str] | None) -> dict[str, Any]:
    answer_schema: dict[str, Any] = {"type": "string"}
    if choices is not None:
        answer_schema["enum"] = choices
    payload = {
        "model": "olmo2-1b-q8",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "seed": SEED,
        "top_k": 1,
        "top_p": 1.0,
        "min_p": 0.0,
        "repeat_penalty": 1.0,
        "max_tokens": 96,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "f0_raw_exact_answer",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["answer"],
                    "properties": {"answer": answer_schema},
                },
            },
        },
    }
    started = time.perf_counter()
    response = _http_json("/v1/chat/completions", payload)
    elapsed = time.perf_counter() - started
    raw = response["choices"][0]["message"]["content"]
    malformed = False
    actual = None
    reason = "VALID"
    try:
        parsed = json.loads(raw)
        if set(parsed) != {"answer"} or not isinstance(parsed["answer"], str):
            raise ValueError("invalid exact-answer object")
        actual = parsed["answer"]
        if choices is not None and actual not in choices:
            raise ValueError("answer outside choices")
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        malformed = True
        parsed = None
        reason = str(exc)
    return {
        "raw_model_output": raw,
        "parsed_output": parsed,
        "actual_answer": actual,
        "malformed": malformed,
        "parse_reason": reason,
        "finish_reason": response["choices"][0].get("finish_reason"),
        "usage": response.get("usage"),
        "timings": response.get("timings"),
        "wall_seconds": elapsed,
    }


def _request_free_action(case: dict[str, Any]) -> dict[str, Any]:
    actions = case["action_order"]
    targets = ["NONE", *case["peers"]]
    proposals = ["NONE", *case["incoming_proposals"]]
    payload = {
        "model": "olmo2-1b-q8",
        "messages": [{"role": "user", "content": case["input"]}],
        "temperature": 0.0,
        "seed": SEED,
        "top_k": 1,
        "top_p": 1.0,
        "min_p": 0.0,
        "repeat_penalty": 1.0,
        "max_tokens": 96,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "f0_raw_free_action",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["action", "target", "proposal"],
                    "properties": {
                        "action": {"type": "string", "enum": actions},
                        "target": {"type": "string", "enum": targets},
                        "proposal": {"type": "string", "enum": proposals},
                    },
                },
            },
        },
    }
    started = time.perf_counter()
    response = _http_json("/v1/chat/completions", payload)
    elapsed = time.perf_counter() - started
    raw = response["choices"][0]["message"]["content"]
    malformed = False
    valid = False
    reason = "VALID"
    try:
        parsed = json.loads(raw)
        if set(parsed) != {"action", "target", "proposal"}:
            raise ValueError("invalid free-action object")
        action, target, proposal = parsed["action"], parsed["target"], parsed["proposal"]
        if action == "NO_DIRECTED_ACTION":
            valid = target == "NONE" and proposal == "NONE"
        elif action in {"DIRECT_TEXT", "OPEN_BILATERAL_REQUEST"}:
            valid = target in case["peers"] and proposal == "NONE"
        elif action in {"CONFIRM_BILATERAL_REQUEST", "DECLINE_BILATERAL_REQUEST"}:
            valid = target == "NONE" and proposal in case["incoming_proposals"]
        else:
            valid = False
        if not valid:
            reason = "DOMAIN_INVALID_ACTION_ARGUMENTS"
    except (json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
        parsed = None
        malformed = True
        reason = str(exc)
    return {
        "raw_model_output": raw,
        "parsed_output": parsed,
        "malformed": malformed,
        "domain_valid": valid,
        "parse_reason": reason,
        "finish_reason": response["choices"][0].get("finish_reason"),
        "usage": response.get("usage"),
        "timings": response.get("timings"),
        "wall_seconds": elapsed,
    }


def _load_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


def _run_stream(
    final_path: Path,
    cases: Iterable[dict[str, Any]],
    case_id_key: str,
    evaluator: Any,
) -> list[dict[str, Any]]:
    if final_path.exists():
        return list(_load_jsonl(final_path))
    partial_path = final_path.with_suffix(final_path.suffix + ".partial")
    existing = list(_load_jsonl(partial_path)) if partial_path.exists() else []
    completed = {record[case_id_key] for record in existing}
    with partial_path.open("a", encoding="utf-8", newline="\n") as stream:
        for case in cases:
            if case[case_id_key] in completed:
                continue
            result = evaluator(case)
            record = {**case, **result}
            stream.write(canonical_json(record) + "\n")
            stream.flush()
            existing.append(record)
    partial_path.replace(final_path)
    return existing


def _evaluate_hidden(case: dict[str, Any]) -> dict[str, Any]:
    prompt = (
        case["input"]
        + "\nCandidate answers (return one exactly):\n- "
        + "\n- ".join(case["choices"])
        + '\nReturn a JSON object with exactly one key named "answer".'
    )
    result = _request_answer(prompt, case["choices"])
    result["expected"] = case["ground_truth"]
    result["exact_match"] = (
        not result["malformed"] and result["actual_answer"] == case["ground_truth"]
    )
    return result


def _evaluate_retention(case: dict[str, Any]) -> dict[str, Any]:
    result = _request_answer(case["input"], None)
    actual = result["actual_answer"]
    result["expected"] = case["expected"]
    result["exact_match"] = (
        not result["malformed"]
        and isinstance(actual, str)
        and actual.removesuffix("\n") == case["expected"]
    )
    return result


def _evaluate_neutrality(case: dict[str, Any]) -> dict[str, Any]:
    if case["family"] == "FREE_ACTION_DISTRIBUTION":
        return _request_free_action(case)
    result = _request_answer(
        case["input"]
        + "\nCandidate answers (return one exactly):\n- "
        + "\n- ".join(case["choices"])
        + '\nReturn a JSON object with exactly one key named "answer".',
        case["choices"],
    )
    result["exact_match"] = (
        not result["malformed"] and result["actual_answer"] == case["expected"]
    )
    return result


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _wilson(successes: int, total: int) -> list[float]:
    if total == 0:
        return [0.0, 0.0]
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return [max(0.0, center - half), min(1.0, center + half)]


def _summarize_hidden(records: list[dict[str, Any]]) -> dict[str, Any]:
    split_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    family_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    malformed = 0
    for record in records:
        split_counts[record["split"]][1] += 1
        family_counts[record["semantic_family"]][1] += 1
        if record["exact_match"]:
            split_counts[record["split"]][0] += 1
            family_counts[record["semantic_family"]][0] += 1
        malformed += int(record["malformed"])
    critical_map = {
        "peer_grounding": ["PEER_IDENTITY", "PEER_HANDLE_LOOKUP"],
        "message_direction": ["MESSAGE_DIRECTION"],
        "proposal_ownership": ["PROPOSAL_OWNER"],
        "proposal_direction": ["PROPOSAL_DIRECTION"],
        "proposal_target": ["PROPOSAL_TARGET"],
        "handle_grounding": ["OPAQUE_HANDLE_COPY"],
        "motor_serialization": ["ALREADY_SELECTED_ACTION_SERIALIZATION"],
    }
    critical = {}
    for label, families in critical_map.items():
        successes = sum(family_counts[family][0] for family in families)
        total = sum(family_counts[family][1] for family in families)
        critical[label] = {"exact": successes, "n": total, "rate": _ratio(successes, total)}
    return {
        "n": len(records),
        "split_exact": {
            split: {"exact": values[0], "n": values[1], "rate": _ratio(*values)}
            for split, values in sorted(split_counts.items())
        },
        "per_semantic_family": {
            family: {"exact": values[0], "n": values[1], "rate": _ratio(*values)}
            for family, values in sorted(family_counts.items())
        },
        "critical_families": critical,
        "malformed": malformed,
        "malformed_rate": _ratio(malformed, len(records)),
    }


def _summarize_retention(records: list[dict[str, Any]]) -> dict[str, Any]:
    families: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for record in records:
        families[record["family"]][1] += 1
        families[record["family"]][0] += int(record["exact_match"])
    passed = sum(int(record["exact_match"]) for record in records)
    return {
        "n": len(records),
        "exact": passed,
        "aggregate": _ratio(passed, len(records)),
        "failures": len(records) - passed,
        "per_category": {
            family: {"exact": values[0], "n": values[1], "rate": _ratio(*values)}
            for family, values in sorted(families.items())
        },
        "malformed": sum(int(record["malformed"]) for record in records),
    }


def _summarize_neutrality(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_family[record["family"]].append(record)
    summary: dict[str, Any] = {}
    for family in ("IDENTITY_PERMUTATION", "ORDER_PERMUTATION", "ROLE_REVERSAL", "HANDLE_BIAS"):
        family_records = by_family[family]
        exact = sum(int(record.get("exact_match", False)) for record in family_records)
        summary[family.lower()] = {"exact": exact, "n": len(family_records), "rate": _ratio(exact, len(family_records))}

    order_pairs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in by_family["ORDER_PERMUTATION"]:
        order_pairs[record["pair_id"]].append(record)
    sensitive = sum(
        len(pair) == 2 and pair[0].get("actual_answer") != pair[1].get("actual_answer")
        for pair in order_pairs.values()
    )
    summary["order_permutation"]["record_order_sensitive_pairs"] = sensitive

    bias_records = by_family["HANDLE_BIAS"]
    peer_records = [record for record in bias_records if record["kind"] == "PEER"]
    proposal_records = [record for record in bias_records if record["kind"] == "PROPOSAL"]
    def observed(records_: list[dict[str, Any]], value: str) -> float:
        return _ratio(sum(record.get("actual_answer") == value for record in records_), len(records_))
    def expected(records_: list[dict[str, Any]], value: str) -> float:
        return _ratio(sum(record["expected"] == value for record in records_), len(records_))
    first_observed = _ratio(
        sum(record.get("actual_answer") == record["choices"][0] for record in bias_records),
        len(bias_records),
    )
    first_expected = _ratio(
        sum(record["expected"] == record["choices"][0] for record in bias_records),
        len(bias_records),
    )
    lowest_observed = _ratio(
        sum(
            record.get("actual_answer") == min(record["choices"], key=lambda value: int(value[1:]))
            for record in bias_records
        ),
        len(bias_records),
    )
    lowest_expected = _ratio(
        sum(
            record["expected"] == min(record["choices"], key=lambda value: int(value[1:]))
            for record in bias_records
        ),
        len(bias_records),
    )
    summary["bias"] = {
        "P0_observed": observed(peer_records, "P0"),
        "P0_expected": expected(peer_records, "P0"),
        "P0_effect": observed(peer_records, "P0") - expected(peer_records, "P0"),
        "R0_observed": observed(proposal_records, "R0"),
        "R0_expected": expected(proposal_records, "R0"),
        "R0_effect": observed(proposal_records, "R0") - expected(proposal_records, "R0"),
        "first_item_observed": first_observed,
        "first_item_expected": first_expected,
        "first_item_effect": first_observed - first_expected,
        "lowest_handle_observed": lowest_observed,
        "lowest_handle_expected": lowest_expected,
        "lowest_handle_effect": lowest_observed - lowest_expected,
    }

    free = by_family["FREE_ACTION_DISTRIBUTION"]
    label_map = {
        "NO_DIRECTED_ACTION": "WAIT",
        "DIRECT_TEXT": "SEND",
        "OPEN_BILATERAL_REQUEST": "PROPOSE",
        "CONFIRM_BILATERAL_REQUEST": "ACCEPT",
        "DECLINE_BILATERAL_REQUEST": "REJECT",
    }
    action_counts = Counter()
    partner_counts = Counter()
    invalid = malformed = 0
    for record in free:
        malformed += int(record["malformed"])
        invalid += int(not record["malformed"] and not record["domain_valid"])
        parsed = record.get("parsed_output")
        if parsed:
            action_counts[label_map.get(parsed["action"], "UNKNOWN")] += 1
            if parsed.get("target") != "NONE":
                partner_counts[parsed["target"]] += 1
    summary["free_action_distribution"] = {
        "n": len(free),
        "action_counts": {action: action_counts.get(action, 0) for action in ("WAIT", "SEND", "PROPOSE", "ACCEPT", "REJECT")},
        "action_proportions": {action: _ratio(action_counts.get(action, 0), len(free)) for action in ("WAIT", "SEND", "PROPOSE", "ACCEPT", "REJECT")},
        "action_95pct_wilson": {action: _wilson(action_counts.get(action, 0), len(free)) for action in ("WAIT", "SEND", "PROPOSE", "ACCEPT", "REJECT")},
        "partner_concentration": _ratio(max(partner_counts.values(), default=0), sum(partner_counts.values())),
        "invalid": invalid,
        "malformed": malformed,
    }
    return summary


def run_baselines(root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    suite = freeze_neutrality_suite(root)
    dataset_manifest = json.loads((DATASET_ROOT / "manifest.json").read_text(encoding="utf-8"))
    retention = json.loads(RETENTION_PATH.read_text(encoding="utf-8"))
    if _sha256_file(MODEL_PATH) != MODEL_PROVENANCE["runtime_sha256"]:
        raise RuntimeError("runtime GGUF digest mismatch")
    if dataset_manifest["manifest_digest"] != "418873b65e9a8903a595d6a8359ce778dd588b9cedb0e3c5ac54d178528e5e18":
        raise RuntimeError("formal dataset manifest mismatch")
    if retention["sentinel_sha256"] != "7b321d2676f6137aa8c46aa1dd94e819fa3fce37495a579481f0fcc8ef370ef0":
        raise RuntimeError("retention sentinel digest mismatch")

    log_path = root / "llama-server.log"
    with log_path.open("ab") as log:
        process = subprocess.Popen(
            [
                str(SERVER_PATH), "-m", str(MODEL_PATH), "-c", "4096",
                "-ngl", "99", "--parallel", "1", "--host", "127.0.0.1",
                "--port", str(PORT), "--no-webui",
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            env={
                **os.environ,
                "HF_HOME": "E:/WORLD/AI_CACHE/huggingface",
                "HUGGINGFACE_HUB_CACHE": "E:/WORLD/AI_CACHE/huggingface/hub",
                "TRANSFORMERS_CACHE": "E:/WORLD/AI_CACHE/huggingface/transformers",
                "TORCH_HOME": "E:/WORLD/AI_CACHE/torch",
                "TEMP": "E:/WORLD/AI_CACHE/tmp",
                "TMP": "E:/WORLD/AI_CACHE/tmp",
            },
        )
        try:
            _wait_for_server(process)
            hidden_cases = (
                record
                for split in ("STRUCTURAL_HOLDOUT", "TEMPLATE_HOLDOUT", "DOUBLE_HOLDOUT", "ADVERSARIAL_HOLDOUT")
                for record in _load_jsonl(DATASET_ROOT / (split.lower() + ".jsonl"))
            )
            hidden = _run_stream(root / "hidden_raw.jsonl", hidden_cases, "example_id", _evaluate_hidden)
            retention_records = _run_stream(
                root / "retention_raw.jsonl", retention["cases"], "id", _evaluate_retention
            )
            neutrality_records = _run_stream(
                root / "neutrality_raw.jsonl", suite["cases"], "case_id", _evaluate_neutrality
            )
        finally:
            process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)

    artifact_hashes = {
        filename: _sha256_file(root / filename)
        for filename in ("neutrality_suite.json", "hidden_raw.jsonl", "retention_raw.jsonl", "neutrality_raw.jsonl")
    }
    manifest_core = {
        "manifest_schema_version": "1.0.0",
        "baseline_id": BASELINE_ID,
        "status": "FROZEN",
        "model": MODEL_PROVENANCE,
        "runtime": RUNTIME_CONFIG,
        "formal_dataset_id": dataset_manifest["dataset_id"],
        "formal_dataset_manifest_digest": dataset_manifest["manifest_digest"],
        "retention_sentinel_id": retention["sentinel_id"],
        "retention_sentinel_digest": retention["sentinel_sha256"],
        "neutrality_suite_id": suite["suite_id"],
        "neutrality_suite_digest": suite["suite_digest"],
        "C0_executed": False,
        "C20_executed": False,
        "sealed_evaluation_access": "FINGERPRINTS_ONLY_DURING_DATASET_GENERATION",
        "hidden": _summarize_hidden(hidden),
        "retention": _summarize_retention(retention_records),
        "neutrality": _summarize_neutrality(neutrality_records),
        "artifacts": artifact_hashes,
    }
    manifest = dict(manifest_core)
    manifest["manifest_digest"] = canonical_digest(manifest_core)
    manifest_path = root / "manifest.json"
    payload = (canonical_json(manifest) + "\n").encode("utf-8")
    if manifest_path.exists() and manifest_path.read_bytes() != payload:
        raise RuntimeError("frozen RAW baseline manifest mismatch")
    if not manifest_path.exists():
        manifest_path.write_bytes(payload)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-suite-only", action="store_true")
    parser.add_argument("--evidence-root", type=Path, default=EVIDENCE_ROOT)
    args = parser.parse_args()
    root = args.evidence_root.resolve()
    if root.drive.upper() != "E:":
        raise RuntimeError("F0 evidence must be stored on E:")
    if args.freeze_suite_only:
        suite = freeze_neutrality_suite(root)
        print(canonical_json({"suite_id": suite["suite_id"], "count": len(suite["cases"]), "digest": suite["suite_digest"]}))
        return 0
    print(canonical_json(run_baselines(root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
