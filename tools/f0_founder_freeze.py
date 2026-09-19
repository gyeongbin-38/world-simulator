#!/usr/bin/env python3
"""Commit the terminal FOUNDER_FREEZE result record for a candidate.

The record is pre-registered by ``specs/experiments/founder-freeze-record-v1.yaml``.
This tool verifies the frozen record schema, resolves all four gate evidence
manifests, checks each gate verdict, binds the candidate identity across the
founder eval manifests, and writes the record once via the canonical
write-once evidence helper.  It never infers a verdict, never mutates
canonical state, and never promotes the adapter.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
from typing import Any, Mapping

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))
sys.path.insert(0, str(REPOSITORY_ROOT))

from tools import f0_foundation_ab_gate as gate  # noqa: E402

RECORD_SPEC_PATH = (
    REPOSITORY_ROOT / "specs/experiments/founder-freeze-record-v1.yaml"
)
RECORD_SCHEMA_ID = "FOUNDER_FREEZE_RECORD_V1"
ADMISSION_ID = "FOUNDER_MODEL_ADMISSION_V1"
EVAL_ID = "F0_FOUNDATION_AB_EVAL_V1"


class FreezeAbort(RuntimeError):
    """A required frozen invariant failed closed before the record commit."""


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _record_spec_audit() -> None:
    spec = _read_json(RECORD_SPEC_PATH)
    if (
        spec.get("record_schema_id") != RECORD_SCHEMA_ID
        or spec.get("status") != "FROZEN"
        or spec.get("admission_id") != ADMISSION_ID
    ):
        raise FreezeAbort("founder freeze record schema identity mismatch")
    if "FOUNDATION_ADAPTER_SELECTION" not in (spec.get("sealed_from") or ()):
        raise FreezeAbort("founder freeze record selection firewall missing")
    gate_fields = (spec.get("required_fields") or {}).get("gate_evidence") or {}
    if set(gate_fields) != {"C0", "C20", "MOTOR", "AUTONOMOUS"}:
        raise FreezeAbort("founder freeze record gate set drifted")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _founder_eval_gate(manifest_path: Path, suite: str) -> dict[str, Any]:
    """Verify one founder eval manifest and read its suite verdict."""

    if not manifest_path.is_file():
        raise FreezeAbort(f"gate evidence missing: {manifest_path}")
    digest = _digest(manifest_path)
    manifest = _read_json(manifest_path)
    if manifest.get("eval_id") != EVAL_ID:
        raise FreezeAbort(f"{suite} evidence is not an F0 eval manifest")
    if suite not in (manifest.get("suites") or ()):
        raise FreezeAbort(f"{suite} suite absent from eval manifest")
    summary_path = manifest_path.parent / "summaries.json"
    if not summary_path.is_file():
        raise FreezeAbort(f"{suite} summaries missing: {summary_path}")
    recorded = (manifest.get("artifact_hashes") or {}).get("summaries")
    if recorded is None or _digest(summary_path) != recorded:
        raise FreezeAbort(f"{suite} summaries digest mismatch")
    summaries = _read_json(summary_path)
    body = summaries.get(suite) or {}
    if body.get("post_selection_only") is not True:
        raise FreezeAbort(f"{suite} summary missing post-selection marker")
    verdict = str(body.get("verdict"))
    if verdict not in {"ADMISSION_PASS", "ADMISSION_FAIL"}:
        raise FreezeAbort(f"{suite} verdict missing or malformed")
    return {
        "manifest_sha256": digest,
        "verdict": verdict,
        "candidate_adapter_sha256": manifest.get("adapter_sha256"),
        "treatment_id": manifest.get("treatment_id"),
        "seed": manifest.get("seed"),
    }


def _a0_gate(manifest_path: Path, gate_name: str) -> dict[str, Any]:
    """Verify one A0 protocol evidence manifest and read the gate verdict."""

    if not manifest_path.is_file():
        raise FreezeAbort(f"gate evidence missing: {manifest_path}")
    digest = _digest(manifest_path)
    manifest = _read_json(manifest_path)
    if manifest.get("status") != "COMPLETE":
        raise FreezeAbort(f"{gate_name} A0 manifest is not COMPLETE")
    result = manifest.get("result") or {}
    if str(result.get("status")) not in {"ADMISSION_PASS", "ADMISSION_FAIL"}:
        raise FreezeAbort(f"{gate_name} A0 result status malformed")
    if gate_name == "MOTOR":
        passed = result.get("minimal_motor_treatment") is not None
    else:
        passed = (
            str(result.get("status")) == "ADMISSION_PASS"
            and result.get("selected_treatment") is not None
        )
    return {
        "manifest_sha256": digest,
        "verdict": "ADMISSION_PASS" if passed else "ADMISSION_FAIL",
        "minimal_motor_treatment": result.get("minimal_motor_treatment"),
        "selected_treatment": result.get("selected_treatment"),
    }


def _freeze_record(
    *,
    c0: Mapping[str, Any],
    c20: Mapping[str, Any],
    motor: Mapping[str, Any],
    autonomous: Mapping[str, Any],
    adapter_sha256: str | None,
    recorded_at_utc: str,
) -> dict[str, Any]:
    """Pure record assembly; verdict is computed, never inferred."""

    for label, gate_body in (("C0", c0), ("C20", c20)):
        if gate_body["candidate_adapter_sha256"] != adapter_sha256:
            raise FreezeAbort(
                f"{label} candidate identity does not match record candidate"
            )
    gates = {"C0": c0, "C20": c20, "MOTOR": motor, "AUTONOMOUS": autonomous}
    admitted = all(
        body["verdict"] == "ADMISSION_PASS" for body in gates.values()
    )
    return {
        "record_schema_id": RECORD_SCHEMA_ID,
        "admission_id": ADMISSION_ID,
        "candidate": {
            "adapter_artifact_sha256": adapter_sha256,
        },
        "gate_evidence": {
            name: {
                "manifest_sha256": body["manifest_sha256"],
                "verdict": body["verdict"],
            }
            for name, body in gates.items()
        },
        "verdict": "FOUNDER_ADMITTED" if admitted else "FOUNDER_REJECTED",
        "recorded_at_utc": recorded_at_utc,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--c0-manifest", type=Path, default=None)
    parser.add_argument("--c20-manifest", type=Path, default=None)
    parser.add_argument("--motor-manifest", type=Path, default=None)
    parser.add_argument("--autonomous-manifest", type=Path, default=None)
    identity = parser.add_mutually_exclusive_group()
    identity.add_argument("--adapter-sha256", type=str, default=None)
    identity.add_argument("--base-only", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        _record_spec_audit()
        if args.validate_only:
            print(
                json.dumps(
                    {
                        "status": "VALIDATE_ONLY_PASS",
                        "record_schema_id": RECORD_SCHEMA_ID,
                        "gate_set": ["C0", "C20", "MOTOR", "AUTONOMOUS"],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        required = {
            "--c0-manifest": args.c0_manifest,
            "--c20-manifest": args.c20_manifest,
            "--motor-manifest": args.motor_manifest,
            "--autonomous-manifest": args.autonomous_manifest,
            "--output": args.output,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            raise FreezeAbort(f"missing required arguments: {missing}")
        if not args.base_only and not args.adapter_sha256:
            raise FreezeAbort(
                "candidate identity required: --adapter-sha256 or --base-only"
            )
        adapter_sha256 = None if args.base_only else args.adapter_sha256

        c0 = _founder_eval_gate(args.c0_manifest, "founder_c0_v2")
        c20 = _founder_eval_gate(args.c20_manifest, "founder_c20_v1")
        motor = _a0_gate(args.motor_manifest, "MOTOR")
        autonomous = _a0_gate(args.autonomous_manifest, "AUTONOMOUS")
        record = _freeze_record(
            c0=c0,
            c20=c20,
            motor=motor,
            autonomous=autonomous,
            adapter_sha256=adapter_sha256,
            recorded_at_utc=datetime.now(timezone.utc).isoformat(),
        )
        record["recorder"] = "f0_founder_freeze"
        record["environment"] = {
            "packages": gate.package_versions(),
            "platform": platform.platform(),
        }
        record["git"] = gate.git_state()
        gate._write_new_evidence(args.output, record)
        print(json.dumps(record, indent=2, sort_keys=True))
        return 0
    except (FreezeAbort, RuntimeError, ValueError, TypeError, OSError) as error:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "reason": f"{type(error).__name__}: {error}",
                }
            )
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
