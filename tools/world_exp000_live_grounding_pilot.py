#!/usr/bin/env python3
"""Validate or execute the preregistered WORLD EXP-000 live grounding pilot.

This runner reuses the admitted LIVE EXP-000 controller/trajectory machinery and
changes only the non-WAIT payload provider: already-selected ACCEPT/REJECT
payloads may use the preregistered proposal-handle grounding layer.  The action
selector, Gateway, LawValidator, kernel, SQLite/CAS persistence, and replay
boundaries remain unchanged.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))
sys.path.insert(0, str(REPOSITORY_ROOT))

from alifelm.model.proposal_handle_grounding import (  # noqa: E402
    build_c10_score_selected_proposal_handle_runtime,
)
from alifelm.model.world_v0_smoke import canonical_bytes, canonical_digest  # noqa: E402
from tools import world_exp000_live_multiagent_pilot as parent  # noqa: E402


STUDY_ID = "WORLD_EXP000_LIVE_GROUNDING_PILOT_V1"
RUN_ID = "WORLD_EXP000_LIVE_GROUNDING_PILOT_V1_R1"
SCHEMA_VERSION = "1.0.0"
PREREG_COMMIT = "76e666e5a51a93ea2c46bf10bda2ccf8c6f17b35"
GROUNDING_SMOKE_RESULT_DIGEST = "bbbca1f5c278ea21fcc4ec203e3ceacbe4a1087806f89dfb629105214d74f5d5"
GROUNDING_SMOKE_MANIFEST_SHA256 = "aedfa2f58c9b127ff9c04e5d79bebe7c7b9e892c831fa5ffac385abcff505260"
GROUNDING_SMOKE_ARCHIVE_SHA256 = "ca3ae00fb89dfbb628254410189328381ae0901b8bb7d502f93fe6026e918dd3"
GROUNDING_SMOKE_SEAL_SUMS_SHA256 = "31ff48bfe03e256e95f70c6c82a1028b51f3f5f5c0e19af11854555d44b35675"

_BASE_TICK_RECORD = parent.tick_record
_BASE_SUMMARIZE = parent.summarize_trajectory


class LiveGroundingPilotError(RuntimeError):
    """Fail-closed contract error for the grounding-integrated LIVE pilot."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--base-model-dir", required=True, type=Path)
    parser.add_argument("--adapter-path", required=True, type=Path)
    parser.add_argument("--d1-details", required=True, type=Path)
    parser.add_argument("--smoke-manifest", required=True, type=Path)
    parser.add_argument("--smoke-archive", required=True, type=Path)
    parser.add_argument("--grounding-manifest", required=True, type=Path)
    parser.add_argument("--grounding-archive", required=True, type=Path)
    parser.add_argument("--grounding-seal-sums", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--expected-git-commit", required=True)
    return parser


def _sha256_file(path: Path) -> str:
    if not path.is_file():
        raise LiveGroundingPilotError(f"required source file is missing: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _candidate_dict(candidate) -> dict[str, Any] | None:
    if candidate is None:
        return None
    return {"action_label": candidate.action_label, "payload": candidate.payload_dict()}


def _configure_parent() -> None:
    parent.STUDY_ID = STUDY_ID
    parent.RUN_ID = RUN_ID
    parent.PREREG_COMMIT = PREREG_COMMIT
    parent.build_c10_score_selected_runtime = build_c10_score_selected_proposal_handle_runtime
    parent.tick_record = _grounding_tick_record
    parent.summarize_trajectory = _grounding_summary


def _verify_grounding_smoke(args) -> dict[str, Any]:
    manifest_sha = _sha256_file(args.grounding_manifest)
    archive_sha = _sha256_file(args.grounding_archive)
    sums_sha = _sha256_file(args.grounding_seal_sums)
    if manifest_sha != GROUNDING_SMOKE_MANIFEST_SHA256:
        raise LiveGroundingPilotError("grounding smoke manifest SHA-256 drift")
    if archive_sha != GROUNDING_SMOKE_ARCHIVE_SHA256:
        raise LiveGroundingPilotError("grounding smoke canonical archive SHA-256 drift")
    if sums_sha != GROUNDING_SMOKE_SEAL_SUMS_SHA256:
        raise LiveGroundingPilotError("grounding smoke seal SHA256SUMS identity drift")
    try:
        manifest = json.loads(args.grounding_manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LiveGroundingPilotError("grounding smoke manifest is invalid JSON") from error
    expected_gates = {
        "G0": True,
        "G1_source_context_identity": True,
        "G2_handle_mapping": True,
        "G3_phase_integrity": True,
        "G4_snapshot_unchanged": True,
    }
    if (
        manifest.get("status") != "GROUNDING_SMOKE_PASS"
        or manifest.get("result_digest") != GROUNDING_SMOKE_RESULT_DIGEST
        or manifest.get("gates") != expected_gates
        or manifest.get("action_selector_rerun") is not False
        or manifest.get("simulation_state_commits") != 0
        or manifest.get("weight_updates") != 0
        or manifest.get("retries") != 0
        or manifest.get("fallbacks") != 0
        or manifest.get("repairs") != 0
    ):
        raise LiveGroundingPilotError("grounding smoke semantic identity drift")
    return {
        "status": manifest["status"],
        "result_digest": manifest["result_digest"],
        "manifest_sha256": manifest_sha,
        "archive_sha256": archive_sha,
        "seal_sums_sha256": sums_sha,
        "law_validator_admitted_descriptive_count": manifest.get(
            "law_validator_admitted_descriptive_count"
        ),
        "off_machine_hash_verified": True,
    }


def static_preflight(args) -> dict[str, Any]:
    _configure_parent()
    static = parent.static_preflight(args)
    grounding = _verify_grounding_smoke(args)
    static = dict(static)
    static["study_id"] = STUDY_ID
    static["schema_version"] = SCHEMA_VERSION
    static["prereg_commit"] = PREREG_COMMIT
    static["grounding_smoke_source"] = grounding
    static["proposal_handle_grounding"] = {
        "enabled": True,
        "actions": ["ACCEPT", "REJECT"],
        "handle_domain": "ALL_VISIBLE_PROPOSAL_REFERENCES",
        "law_eligibility_filter": False,
        "action_availability_mask": False,
        "agent_id_aliasing": False,
        "fallback_when_no_visible_reference": "BASELINE_PAYLOAD_PATH",
    }
    return static


def _grounding_tick_record(result, score_runtime) -> dict[str, Any]:
    record = _BASE_TICK_RECORD(result, score_runtime)
    opportunity_ids = {
        item.opportunity_id.value: item.opportunity_id for item in result.opportunities
    }
    for cognition in record.get("cognition", []):
        if cognition.get("selected_action") not in {"ACCEPT", "REJECT"}:
            cognition["proposal_grounding"] = None
            continue
        oid = opportunity_ids[cognition["opportunity_id"]]
        try:
            grounding = score_runtime.payload_provider.grounding_for(oid)
        except KeyError:
            cognition["proposal_grounding"] = {"integrity_error": "MISSING_GROUNDING_RECORD"}
            continue
        cognition["proposal_grounding"] = {
            "mode": grounding.mode,
            "treatment_id": grounding.treatment_id,
            "handle_map": [
                {"canonical_proposal_id": canonical, "handle": handle}
                for canonical, handle in grounding.handle_map.canonical_to_handle
            ],
            "raw_handle_candidate": _candidate_dict(grounding.raw_handle_candidate),
            "mapped_canonical_candidate": _candidate_dict(grounding.mapped_candidate),
        }
    return record


def _grounding_summary(records: list[dict[str, Any]], final_snapshot) -> dict[str, Any]:
    summary = _BASE_SUMMARIZE(records, final_snapshot)
    modes = Counter()
    grounded = []
    for tick_record in records:
        for cognition in tick_record.get("cognition", []):
            grounding = cognition.get("proposal_grounding")
            if not grounding:
                continue
            if "integrity_error" in grounding:
                modes[grounding["integrity_error"]] += 1
            else:
                modes[grounding["mode"]] += 1
            grounded.append(
                {
                    "tick": tick_record["tick"],
                    "agent_id": cognition["agent_id"],
                    "selected_action": cognition["selected_action"],
                    "law_admitted": cognition["law_admitted"],
                    "proposal_grounding": grounding,
                }
            )
    summary["proposal_grounding"] = {
        "mode_counts": dict(sorted(modes.items())),
        "attempts": grounded,
    }
    return summary


def _handle_gate_from_tick_records(output_root: Path) -> tuple[bool, dict[str, Any]]:
    treated = 0
    baseline_no_visible = 0
    missing = 0
    invalid = []
    for path in sorted((output_root / "ticks").glob("tick_*.json")):
        tick = json.loads(path.read_text(encoding="utf-8"))
        for cognition in tick.get("cognition", []):
            if cognition.get("selected_action") not in {"ACCEPT", "REJECT"}:
                continue
            grounding = cognition.get("proposal_grounding")
            if not grounding or "integrity_error" in grounding:
                missing += 1
                invalid.append(
                    {"tick": tick["tick"], "agent_id": cognition["agent_id"], "reason": "MISSING_GROUNDING_RECORD"}
                )
                continue
            mode = grounding["mode"]
            if mode == "BASELINE_NO_VISIBLE_PROPOSAL_REFERENCE":
                baseline_no_visible += 1
                continue
            if mode != "PROPOSAL_HANDLE_VISIBLE_REFERENCE_DOMAIN":
                invalid.append(
                    {"tick": tick["tick"], "agent_id": cognition["agent_id"], "reason": f"UNKNOWN_MODE:{mode}"}
                )
                continue
            treated += 1
            raw = grounding.get("raw_handle_candidate")
            mapped = grounding.get("mapped_canonical_candidate")
            mapping = {
                item["handle"]: item["canonical_proposal_id"]
                for item in grounding.get("handle_map", [])
            }
            raw_id = None if raw is None else raw.get("payload", {}).get("proposal_id")
            mapped_id = None if mapped is None else mapped.get("payload", {}).get("proposal_id")
            gateway_id = (
                None
                if cognition.get("gateway_intent") is None
                else cognition["gateway_intent"].get("payload", {}).get("proposal_id")
            )
            if (
                raw_id not in mapping
                or mapping.get(raw_id) != mapped_id
                or gateway_id != mapped_id
                or cognition.get("candidate") != mapped
            ):
                invalid.append(
                    {
                        "tick": tick["tick"],
                        "agent_id": cognition["agent_id"],
                        "reason": "HANDLE_CANONICAL_BINDING_MISMATCH",
                        "raw_id": raw_id,
                        "mapped_id": mapped_id,
                        "gateway_id": gateway_id,
                    }
                )
    details = {
        "treated_attempts": treated,
        "baseline_no_visible_reference_attempts": baseline_no_visible,
        "missing_grounding_records": missing,
        "invalid": invalid,
    }
    return not invalid and missing == 0, details


def _write_json_once(path: Path, value: Any) -> None:
    if path.exists():
        raise LiveGroundingPilotError(f"refusing to overwrite immutable evidence: {path}")
    data = canonical_bytes(value) + b"\n"
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        import os

        os.fsync(stream.fileno())


def execute(args, static: dict[str, Any]) -> dict[str, Any]:
    _configure_parent()
    parent_result = parent.execute(args, static)
    handle_ok, handle_details = _handle_gate_from_tick_records(args.output_root)
    parent_gates = parent_result.get("gates", {})
    gates = {
        "G0": bool(parent_gates.get("G0")),
        "G1_cognition_integrity": bool(parent_gates.get("G1")),
        "G2_proposal_handle_integrity": handle_ok,
        "G3_canonical_commit_integrity": bool(parent_gates.get("G2")),
        "G4_persistence_replay_integrity": bool(parent_gates.get("G3")),
    }
    result = {
        "status": (
            "LIVE_GROUNDING_PILOT_COMPLETE"
            if parent_result.get("status") == "LIVE_PILOT_COMPLETE" and all(gates.values())
            else "LIVE_GROUNDING_PILOT_INTEGRITY_FAIL"
        ),
        "study_id": STUDY_ID,
        "run_id": RUN_ID,
        "schema_version": SCHEMA_VERSION,
        "git_commit": parent_result.get("git_commit"),
        "prereg_commit": PREREG_COMMIT,
        "gates": gates,
        "proposal_handle_integrity": handle_details,
        "parent_manifest_sha256": _sha256_file(args.output_root / "manifest.json"),
        "parent_result_digest": parent_result.get("result_digest"),
        "trajectory": parent_result.get("trajectory"),
        "action_selector_rerun": False,
        "action_availability_mask": False,
        "law_eligibility_filter": False,
        "agent_id_aliasing": False,
        "weight_updates": 0,
        "retries": 0,
        "fallbacks": 0,
        "repairs": 0,
    }
    result["result_digest"] = canonical_digest(result)
    _write_json_once(args.output_root / "grounding_manifest.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        static = static_preflight(args)
        if args.validate_only:
            print(json.dumps(static, ensure_ascii=False, sort_keys=True))
            return 0
        result = execute(args, static)
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "gates": result["gates"],
                    "proposal_handle_integrity": result["proposal_handle_integrity"],
                    "result_digest": result["result_digest"],
                    "manifest": str(args.output_root / "grounding_manifest.json"),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0 if result["status"] == "LIVE_GROUNDING_PILOT_COMPLETE" else 2
    except (
        LiveGroundingPilotError,
        parent.LivePilotError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        subprocess.CalledProcessError,
    ) as error:
        print(
            json.dumps(
                {"status": "BLOCKED", "error_type": type(error).__name__, "error": str(error)},
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
