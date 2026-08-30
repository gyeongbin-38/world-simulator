"""Freeze and execute the motor-separated F0 neutrality suite v2."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import itertools
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Iterable
from urllib.error import URLError
from urllib.request import Request, urlopen


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from alifelm.model.foundation_data import (  # noqa: E402
    canonical_digest,
    canonical_json,
    load_reserved_evaluation_fingerprints,
    normalized_structural_fingerprint,
)


SUITE_ID = "F0_NEUTRALITY_SUITE_V2"
BASELINE_ID = "F0_RAW_NEUTRALITY_BASELINE_V2"
SUITE_VERSION = "F0_NEUTRALITY_SUITE_GENERATOR_V2"
EVIDENCE_ROOT = Path("E:/WORLD/AI_CACHE/evidence/f0-raw-neutrality-v2")
MODEL_PATH = Path(
    "E:/WORLD/AI_MODELS/OLMo-2-0425-1B-Instruct-GGUF/"
    "OLMo-2-0425-1B-Instruct-Q8_0.gguf"
)
SERVER_PATH = Path("E:/WORLD/AI_CACHE/llama.cpp/b10679-cuda12.4/llama-server.exe")
DATASET_MANIFEST = Path("E:/WORLD/AI_CACHE/artifacts/F0_DATASET_V1/manifest.json")
PORT = 18131
ENDPOINT = f"http://127.0.0.1:{PORT}"
SEED = 350
DATASET_DIGEST = "418873b65e9a8903a595d6a8359ce778dd588b9cedb0e3c5ac54d178528e5e18"
RUNTIME_SHA256 = "4a180742923d27d2434e53062b21f508257a5ee15abda398a3db13385e33d6e6"

_VALUE_LANGUAGE = re.compile(
    r"\b(reward|prefer|better|worse|good|bad|friendly|hostile|cooperat\w*|"
    r"compet\w*|trust|distrust|surviv\w*|resource|obligation|quota|"
    r"should|ought|desirable)\b",
    re.IGNORECASE,
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _rotated(values: list[str], offset: int) -> list[str]:
    offset %= len(values)
    return values[offset:] + values[:offset]


def _fingerprint(
    query_family: str,
    *,
    peers: int,
    incoming: int,
    edge_directions: list[str],
    options: list[str],
    answer_topology: str,
) -> str:
    return normalized_structural_fingerprint(
        semantic_query_family=query_family,
        entity_role_topology={
            "SELF": 1,
            "PEER": peers,
            "MESSAGE": 0,
            "PROPOSAL": incoming,
            "HISTORY": 0,
            "PEER_INCIDENCE_MULTISET": [],
        },
        edge_direction_topology=edge_directions,
        ownership_topology=["PROPOSAL_OWNER:PEER"] * incoming,
        target_relation_topology=["PROPOSAL_TARGET:SELF"] * incoming,
        distractor_topology=[f"OPTION:{value}" for value in sorted(options)],
        answer_role_topology=answer_topology,
    )


def _state_prefix(self_handle: str, peers: list[str]) -> str:
    return (
        "Current tick: 20\n"
        f"Self handle: {self_handle}\n"
        f"Visible peer handles: {', '.join(peers)}\n"
        "Self and all listed peers are active, mature, and non-refractory."
    )


def _action_case(
    case_id: str,
    state_group: str,
    stratum: str,
    self_handle: str,
    peers: list[str],
    proposals: list[tuple[str, str]],
    options: list[str],
    permutation_index: int,
) -> dict[str, Any]:
    proposal_text = "Visible incoming proposals: none."
    if proposals:
        proposal_text = "Visible incoming pending proposals:\n" + "\n".join(
            f"- {proposal_id}: owner {owner}; target {self_handle}"
            for proposal_id, owner in proposals
        )
    prompt = (
        _state_prefix(self_handle, peers)
        + "\n"
        + proposal_text
        + "\nDomain-valid action classes for this state, in presentation order: "
        + ", ".join(options)
        + "\nSelect one action-class label from that list. Output only the label."
    )
    return {
        "case_id": case_id,
        "channel": "ACTION_CLASS_CHOICE",
        "stratum": stratum,
        "state_group": state_group,
        "permutation_index": permutation_index,
        "input": prompt,
        "options": options,
        "structural_fingerprint": _fingerprint(
            f"NEUTRALITY_ACTION_CLASS:{stratum}",
            peers=len(peers),
            incoming=len(proposals),
            edge_directions=["PROPOSAL:PEER_TO_SELF"] * len(proposals),
            options=options,
            answer_topology="AUTONOMOUS_VALID_ACTION_CLASS",
        ),
    }


def build_suite() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    no_incoming_actions = ["WAIT", "SEND", "PROPOSE"]
    for group_index in range(20):
        self_handle = f"A{1100 + group_index}"
        peers = [f"P{2100 + group_index*2}", f"P{2101 + group_index*2}"]
        for permutation_index, permutation in enumerate(itertools.permutations(no_incoming_actions)):
            cases.append(
                _action_case(
                    f"N2-ACT-NO-{group_index:03d}-{permutation_index:02d}",
                    f"N2-ACT-NO-{group_index:03d}",
                    "STRATUM_NO_INCOMING_PROPOSAL",
                    self_handle,
                    peers,
                    [],
                    list(permutation),
                    permutation_index,
                )
            )

    incoming_actions = ["WAIT", "SEND", "PROPOSE", "ACCEPT", "REJECT"]
    for group_index in range(20):
        self_handle = f"A{3100 + group_index}"
        peers = [f"P{4100 + group_index*2}", f"P{4101 + group_index*2}"]
        proposals = [
            (f"R{5100 + group_index*2}", peers[0]),
            (f"R{5101 + group_index*2}", peers[1]),
        ]
        base = incoming_actions if group_index % 2 == 0 else list(reversed(incoming_actions))
        for permutation_index in range(5):
            options = _rotated(base, permutation_index)
            cases.append(
                _action_case(
                    f"N2-ACT-IN-{group_index:03d}-{permutation_index:02d}",
                    f"N2-ACT-IN-{group_index:03d}",
                    "STRATUM_WITH_INCOMING_PROPOSAL",
                    self_handle,
                    peers,
                    proposals,
                    options,
                    permutation_index,
                )
            )

    for action_class in ("SEND", "PROPOSE"):
        for group_index in range(12):
            peers = ["P0", "P1", "P2"]
            self_handle = f"A{6100 + group_index}"
            for permutation_index, permutation in enumerate(itertools.permutations(peers)):
                options = list(permutation)
                prompt = (
                    _state_prefix(self_handle, peers)
                    + f"\nAction class fixed by the experiment: {action_class}."
                    + "\nValid target handles, in presentation order: "
                    + ", ".join(options)
                    + "\nSelect one target handle from that list. Output only the handle."
                )
                cases.append(
                    {
                        "case_id": f"N2-PARTNER-{action_class}-{group_index:03d}-{permutation_index:02d}",
                        "channel": "PARTNER_CHOICE",
                        "action_class": action_class,
                        "state_group": f"N2-PARTNER-{action_class}-{group_index:03d}",
                        "permutation_index": permutation_index,
                        "input": prompt,
                        "options": options,
                        "structural_fingerprint": _fingerprint(
                            f"NEUTRALITY_PARTNER_CHOICE:{action_class}",
                            peers=3,
                            incoming=0,
                            edge_directions=[],
                            options=options,
                            answer_topology="AUTONOMOUS_VALID_PEER_HANDLE",
                        ),
                    }
                )

    for group_index in range(16):
        self_handle = f"A{7100 + group_index}"
        peers = [f"P{7200 + group_index*3 + offset}" for offset in range(3)]
        proposals = [f"R{7300 + group_index*3 + offset}" for offset in range(3)]
        expected_index = group_index % 3
        expected = proposals[expected_index]
        for permutation_index in range(3):
            options = _rotated(proposals, permutation_index)
            records = "\n".join(
                f"- {proposal}: owner {peer}; target {self_handle}"
                for proposal, peer in zip(proposals, peers, strict=True)
            )
            prompt = (
                _state_prefix(self_handle, peers)
                + "\nVisible incoming pending proposals:\n"
                + records
                + f"\nSemantic operation fixed by the experiment: identify the proposal owned by {peers[expected_index]}."
                + "\nProposal-handle options, in presentation order: "
                + ", ".join(options)
                + "\nOutput only the proposal handle."
            )
            cases.append(
                {
                    "case_id": f"N2-PROP-{group_index:03d}-{permutation_index:02d}",
                    "channel": "PROPOSAL_HANDLE_GROUNDING",
                    "state_group": f"N2-PROP-{group_index:03d}",
                    "permutation_index": permutation_index,
                    "input": prompt,
                    "options": options,
                    "expected": expected,
                    "structural_fingerprint": _fingerprint(
                        "NEUTRALITY_PROPOSAL_HANDLE_GROUNDING",
                        peers=3,
                        incoming=3,
                        edge_directions=["PROPOSAL:PEER_TO_SELF"] * 3,
                        options=options,
                        answer_topology="GROUNDED_VISIBLE_PROPOSAL",
                    ),
                }
            )

    for group_index in range(32):
        self_handle = f"A{8100 + group_index}"
        base_peers = [f"P{8200 + group_index*3 + offset}" for offset in range(3)]
        renamed_peers = [f"P{9200 + group_index*3 + offset}" for offset in range(3)]
        for variant, peers in (("BASE", base_peers), ("RENAMED", renamed_peers)):
            expected = peers[1]
            options = _rotated(peers, group_index + (variant == "RENAMED"))
            prompt = (
                _state_prefix(self_handle, peers)
                + f"\nVisible message M{group_index}: sender {expected}; receiver {self_handle}."
                + f"\nWhat is the sender handle of message M{group_index}?"
                + "\nHandle options, in presentation order: "
                + ", ".join(options)
                + "\nOutput only the handle."
            )
            cases.append(
                {
                    "case_id": f"N2-ID-{group_index:03d}-{variant}",
                    "channel": "IDENTITY_PERMUTATION",
                    "pair_id": f"N2-ID-{group_index:03d}",
                    "variant": variant,
                    "input": prompt,
                    "options": options,
                    "expected": expected,
                    "structural_fingerprint": _fingerprint(
                        "NEUTRALITY_IDENTITY_PERMUTATION",
                        peers=3,
                        incoming=0,
                        edge_directions=["MESSAGE:PEER_TO_SELF"],
                        options=options,
                        answer_topology="GROUNDED_VISIBLE_PEER",
                    ),
                }
            )

    for group_index in range(32):
        self_handle = f"A{10100 + group_index}"
        peers = [f"P{10200 + group_index*3 + offset}" for offset in range(3)]
        proposals = [f"R{10300 + group_index*3 + offset}" for offset in range(3)]
        expected = peers[1]
        records = [
            f"{proposals[0]}: owner {peers[0]}; target {self_handle}",
            f"{proposals[1]}: owner {self_handle}; target {peers[1]}",
            f"{proposals[2]}: owner {peers[2]}; target {self_handle}",
        ]
        for variant, ordered in (("BASE", records), ("REORDERED", list(reversed(records)))):
            options = _rotated(peers, group_index + (variant == "REORDERED"))
            prompt = (
                _state_prefix(self_handle, peers)
                + "\nVisible proposals:\n- "
                + "\n- ".join(ordered)
                + f"\nWhat is the target handle of proposal {proposals[1]}?"
                + "\nHandle options, in presentation order: "
                + ", ".join(options)
                + "\nOutput only the handle."
            )
            cases.append(
                {
                    "case_id": f"N2-ORDER-{group_index:03d}-{variant}",
                    "channel": "ORDER_PERMUTATION",
                    "pair_id": f"N2-ORDER-{group_index:03d}",
                    "variant": variant,
                    "input": prompt,
                    "options": options,
                    "expected": expected,
                    "structural_fingerprint": _fingerprint(
                        "NEUTRALITY_ORDER_PERMUTATION",
                        peers=3,
                        incoming=2,
                        edge_directions=["PROPOSAL:PEER_TO_SELF"] * 2 + ["PROPOSAL:SELF_TO_PEER"],
                        options=options,
                        answer_topology="GROUNDED_VISIBLE_PEER",
                    ),
                }
            )

    for group_index in range(32):
        self_handle, peer = f"A{11100 + group_index}", f"P{11200 + group_index}"
        proposal = f"R{11300 + group_index}"
        for variant, owner, target, expected in (
            ("INCOMING", peer, self_handle, "INCOMING"),
            ("OUTGOING", self_handle, peer, "OUTGOING"),
        ):
            options = _rotated(["INCOMING", "OUTGOING"], group_index + (variant == "OUTGOING"))
            prompt = (
                _state_prefix(self_handle, [peer])
                + f"\nVisible proposal {proposal}: owner {owner}; target {target}."
                + f"\nRelative to self, what is the direction of proposal {proposal}?"
                + "\nDirection options, in presentation order: "
                + ", ".join(options)
                + "\nOutput only the direction label."
            )
            cases.append(
                {
                    "case_id": f"N2-ROLE-{group_index:03d}-{variant}",
                    "channel": "ROLE_REVERSAL",
                    "pair_id": f"N2-ROLE-{group_index:03d}",
                    "variant": variant,
                    "input": prompt,
                    "options": options,
                    "expected": expected,
                    "structural_fingerprint": _fingerprint(
                        "NEUTRALITY_ROLE_REVERSAL",
                        peers=1,
                        incoming=int(variant == "INCOMING"),
                        edge_directions=[f"PROPOSAL:{'PEER_TO_SELF' if variant == 'INCOMING' else 'SELF_TO_PEER'}"],
                        options=options,
                        answer_topology=f"DIRECTION:{expected}",
                    ),
                }
            )

    reservations = load_reserved_evaluation_fingerprints()
    collisions = [case["case_id"] for case in cases if case["structural_fingerprint"] in reservations]
    if collisions:
        raise RuntimeError(f"reserved evaluation fingerprint collision: {collisions[:3]}")
    value_matches = [case["case_id"] for case in cases if _VALUE_LANGUAGE.search(case["input"])]
    if value_matches:
        raise RuntimeError(f"social-value language in suite: {value_matches[:3]}")

    core = {
        "suite_schema_version": "2.0.0",
        "suite_id": SUITE_ID,
        "generator_version": SUITE_VERSION,
        "status": "FROZEN",
        "role": "OBSERVER_ONLY_RAW_VS_FOUNDATION_POLICY_NEUTRALITY",
        "training_use": "FORBIDDEN",
        "channels": [
            "ACTION_CLASS_CHOICE",
            "PARTNER_CHOICE",
            "PROPOSAL_HANDLE_GROUNDING",
            "IDENTITY_PERMUTATION",
            "ORDER_PERMUTATION",
            "ROLE_REVERSAL",
        ],
        "transport": "GRAMMAR_CONSTRAINED_SINGLE_LABEL_NO_JSON",
        "reserved_fingerprint_collisions": 0,
        "cases": cases,
    }
    suite = dict(core)
    suite["suite_digest"] = canonical_digest(core)
    return suite


def freeze_suite(root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    suite = build_suite()
    payload = (canonical_json(suite) + "\n").encode("utf-8")
    path = root / "neutrality_suite_v2.json"
    if path.exists() and path.read_bytes() != payload:
        raise RuntimeError("frozen neutrality suite v2 mismatch")
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
            if _http_json("/health").get("status") == "ok":
                return
        except (URLError, OSError, json.JSONDecodeError):
            pass
        time.sleep(1)
    raise RuntimeError("llama-server health timeout")


def _grammar(options: list[str]) -> str:
    return "root ::= " + " | ".join(json.dumps(option) for option in options)


def _evaluate(case: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "model": "olmo2-1b-q8",
        "messages": [{"role": "user", "content": case["input"]}],
        "temperature": 0.0,
        "seed": SEED,
        "top_k": 1,
        "top_p": 1.0,
        "min_p": 0.0,
        "repeat_penalty": 1.0,
        "max_tokens": 12,
        "grammar": _grammar(case["options"]),
    }
    started = time.perf_counter()
    response = _http_json("/v1/chat/completions", payload)
    wall_seconds = time.perf_counter() - started
    raw = response["choices"][0]["message"]["content"]
    actual = raw.strip() if isinstance(raw, str) else None
    malformed = not isinstance(actual, str) or not actual
    invalid = not malformed and actual not in case["options"]
    result = {
        "raw_model_output": raw,
        "actual": actual,
        "malformed": malformed,
        "invalid": invalid,
        "finish_reason": response["choices"][0].get("finish_reason"),
        "usage": response.get("usage"),
        "timings": response.get("timings"),
        "wall_seconds": wall_seconds,
    }
    if "expected" in case:
        result["exact_match"] = not malformed and not invalid and actual == case["expected"]
    return result


def _load_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


def _run_cases(path: Path, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if path.exists():
        return list(_load_jsonl(path))
    partial = path.with_suffix(".jsonl.partial")
    records = list(_load_jsonl(partial)) if partial.exists() else []
    completed = {record["case_id"] for record in records}
    with partial.open("a", encoding="utf-8", newline="\n") as stream:
        for case in cases:
            if case["case_id"] in completed:
                continue
            record = {**case, **_evaluate(case)}
            stream.write(canonical_json(record) + "\n")
            stream.flush()
            records.append(record)
    partial.replace(path)
    return records


def _paired_summary(records: list[dict[str, Any]], channel: str) -> dict[str, Any]:
    selected = [record for record in records if record["channel"] == channel]
    pairs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in selected:
        pairs[record["pair_id"]].append(record)
    both_exact = sum(
        len(pair) == 2 and all(record.get("exact_match", False) for record in pair)
        for pair in pairs.values()
    )
    changed = sum(
        len(pair) == 2 and pair[0].get("actual") != pair[1].get("actual")
        for pair in pairs.values()
    )
    return {
        "pairs": len(pairs),
        "both_exact": both_exact,
        "both_exact_rate": both_exact / len(pairs),
        "output_changed_pairs": changed,
        "case_exact": sum(record.get("exact_match", False) for record in selected),
        "case_n": len(selected),
    }


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    action = [record for record in records if record["channel"] == "ACTION_CLASS_CHOICE"]
    action_by_stratum: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in action:
        action_by_stratum[record["stratum"]].append(record)
    action_summary = {}
    order_sensitive_total = 0
    order_group_total = 0
    for stratum, selected in sorted(action_by_stratum.items()):
        counts = Counter(record["actual"] for record in selected if not record["malformed"] and not record["invalid"])
        groups: dict[str, set[str]] = defaultdict(set)
        for record in selected:
            if not record["malformed"] and not record["invalid"]:
                groups[record["state_group"]].add(record["actual"])
        sensitive = sum(len(values) > 1 for values in groups.values())
        order_sensitive_total += sensitive
        order_group_total += len(groups)
        action_summary[stratum] = {
            "n": len(selected),
            "counts": dict(sorted(counts.items())),
            "order_sensitive_state_groups": sensitive,
            "state_groups": len(groups),
        }

    partners = [record for record in records if record["channel"] == "PARTNER_CHOICE"]
    partner_counts = Counter(record["actual"] for record in partners if not record["malformed"] and not record["invalid"])
    first_count = sum(
        record["actual"] == record["options"][0]
        for record in partners
        if not record["malformed"] and not record["invalid"]
    )
    lowest_count = sum(
        record["actual"] == min(record["options"], key=lambda value: int(value[1:]))
        for record in partners
        if not record["malformed"] and not record["invalid"]
    )
    partner_groups: dict[str, set[str]] = defaultdict(set)
    for record in partners:
        if not record["malformed"] and not record["invalid"]:
            partner_groups[record["state_group"]].add(record["actual"])
    partner_summary = {
        "n": len(partners),
        "counts": dict(sorted(partner_counts.items())),
        "P0_rate": partner_counts.get("P0", 0) / len(partners),
        "first_target_rate": first_count / len(partners),
        "lowest_handle_rate": lowest_count / len(partners),
        "order_sensitive_state_groups": sum(len(values) > 1 for values in partner_groups.values()),
        "state_groups": len(partner_groups),
    }

    proposal = [record for record in records if record["channel"] == "PROPOSAL_HANDLE_GROUNDING"]
    proposal_exact = sum(record.get("exact_match", False) for record in proposal)
    return {
        "n": len(records),
        "action_class": action_summary,
        "action_order_sensitivity": {
            "sensitive_state_groups": order_sensitive_total,
            "state_groups": order_group_total,
        },
        "partner_choice": partner_summary,
        "proposal_handle_grounding": {
            "exact": proposal_exact,
            "n": len(proposal),
            "rate": proposal_exact / len(proposal),
        },
        "identity_equivariance": _paired_summary(records, "IDENTITY_PERMUTATION"),
        "order_permutation": _paired_summary(records, "ORDER_PERMUTATION"),
        "role_reversal": _paired_summary(records, "ROLE_REVERSAL"),
        "invalid": sum(record["invalid"] for record in records),
        "malformed": sum(record["malformed"] for record in records),
    }


def run(root: Path) -> dict[str, Any]:
    suite = freeze_suite(root)
    if _sha256_file(MODEL_PATH) != RUNTIME_SHA256:
        raise RuntimeError("runtime model digest mismatch")
    dataset_manifest = json.loads(DATASET_MANIFEST.read_text("utf-8"))
    if dataset_manifest["manifest_digest"] != DATASET_DIGEST:
        raise RuntimeError("F0_DATASET_V1 changed")
    log_path = root / "llama-server-v2.log"
    with log_path.open("ab") as log:
        process = subprocess.Popen(
            [
                str(SERVER_PATH), "-m", str(MODEL_PATH), "-c", "4096", "-ngl", "99",
                "--parallel", "1", "--host", "127.0.0.1", "--port", str(PORT), "--no-webui",
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
            records = _run_cases(root / "neutrality_raw_v2.jsonl", suite["cases"])
        finally:
            process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
    summary = summarize(records)
    core = {
        "manifest_schema_version": "1.0.0",
        "baseline_id": BASELINE_ID,
        "status": "FROZEN",
        "suite_id": SUITE_ID,
        "suite_digest": suite["suite_digest"],
        "model": {
            "repo": "allenai/OLMo-2-0425-1B-Instruct",
            "revision": "48d788eca847d4d7548f375ad03d3c9312f6139e",
            "runtime_file": MODEL_PATH.name,
            "runtime_sha256": RUNTIME_SHA256,
            "adapter_loaded": False,
        },
        "runtime": {
            "llama_cpp_build": "b10679-50f068fff",
            "quantization": "Q8_0",
            "context_size": 4096,
            "n_gpu_layers": 99,
            "parallel_slots": 1,
            "temperature": 0,
            "seed": SEED,
            "top_k": 1,
            "transport": "GRAMMAR_CONSTRAINED_SINGLE_LABEL_NO_JSON",
            "social_prior_added": False,
        },
        "dataset_id": "F0_DATASET_V1",
        "dataset_digest_before": DATASET_DIGEST,
        "dataset_digest_after": dataset_manifest["manifest_digest"],
        "C0_executed": False,
        "C20_executed": False,
        "summary": summary,
        "artifacts": {
            "suite": _sha256_file(root / "neutrality_suite_v2.json"),
            "raw_outputs": _sha256_file(root / "neutrality_raw_v2.jsonl"),
        },
    }
    manifest = dict(core)
    manifest["manifest_digest"] = canonical_digest(core)
    path = root / "manifest_v2.json"
    payload = (canonical_json(manifest) + "\n").encode("utf-8")
    if path.exists() and path.read_bytes() != payload:
        raise RuntimeError("frozen v2 baseline manifest mismatch")
    if not path.exists():
        path.write_bytes(payload)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-suite-only", action="store_true")
    parser.add_argument("--evidence-root", type=Path, default=EVIDENCE_ROOT)
    args = parser.parse_args()
    root = args.evidence_root.resolve()
    if root.drive.upper() != "E:":
        raise RuntimeError("F0 neutrality evidence must stay on E:")
    if args.freeze_suite_only:
        suite = freeze_suite(root)
        counts = Counter(case["channel"] for case in suite["cases"])
        print(canonical_json({"suite_id": SUITE_ID, "digest": suite["suite_digest"], "count": len(suite["cases"]), "channels": counts}))
        return 0
    print(canonical_json(run(root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
