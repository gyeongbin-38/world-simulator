"""Unit tests for the founder freeze record tool.

The gate-verification helpers are exercised against fabricated eval/A0
manifests written into tmp dirs; no model stack is required.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))
sys.path.insert(0, str(REPOSITORY_ROOT / "tools"))

import f0_founder_freeze as freeze  # noqa: E402


ADAPTER = "aa" * 32


def _write(path: Path, doc: dict) -> str:
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8"
    )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _eval_dir(tmp_path: Path, suite: str, verdict: str) -> Path:
    eval_dir = tmp_path / "run" / "eval"
    eval_dir.mkdir(parents=True)
    summaries = {
        suite: {
            "verdict": verdict,
            "post_selection_only": True,
            "selection_input": False,
        }
    }
    summaries_path = eval_dir / "summaries.json"
    summaries_digest = _write(summaries_path, summaries)
    manifest = {
        "eval_id": "F0_FOUNDATION_AB_EVAL_V1",
        "suites": [suite],
        "artifact_hashes": {"summaries": summaries_digest},
        "adapter_sha256": ADAPTER,
        "treatment_id": "F0_AB_A_NF4_QLORA",
        "seed": 292255390,
    }
    _write(eval_dir / "eval_manifest.json", manifest)
    return eval_dir / "eval_manifest.json"


def _a0_manifest(
    tmp_path: Path,
    name: str = "a0",
    *,
    status: str = "ADMISSION_PASS",
    motor: str | None = "I1",
    selected: str | None = "I2",
) -> Path:
    manifest = {
        "status": "COMPLETE",
        "result": {
            "status": status,
            "minimal_motor_treatment": motor,
            "selected_treatment": selected,
        },
    }
    path = tmp_path / name / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    _write(path, manifest)
    return path


def _gate(verdict: str = "ADMISSION_PASS", adapter: str = ADAPTER) -> dict:
    return {
        "manifest_sha256": "bb" * 32,
        "verdict": verdict,
        "candidate_adapter_sha256": adapter,
    }


def test_freeze_record_admitted_only_when_all_gates_pass() -> None:
    record = freeze._freeze_record(
        c0=_gate(),
        c20=_gate(),
        motor={"manifest_sha256": "cc" * 32, "verdict": "ADMISSION_PASS"},
        autonomous={
            "manifest_sha256": "dd" * 32,
            "verdict": "ADMISSION_PASS",
        },
        adapter_sha256=ADAPTER,
        recorded_at_utc="2026-01-01T00:00:00+00:00",
    )
    assert record["verdict"] == "FOUNDER_ADMITTED"
    assert record["record_schema_id"] == "FOUNDER_FREEZE_RECORD_V1"
    assert set(record["gate_evidence"]) == {
        "C0",
        "C20",
        "MOTOR",
        "AUTONOMOUS",
    }

    record = freeze._freeze_record(
        c0=_gate(),
        c20=_gate(verdict="ADMISSION_FAIL"),
        motor={"manifest_sha256": "cc" * 32, "verdict": "ADMISSION_PASS"},
        autonomous={
            "manifest_sha256": "dd" * 32,
            "verdict": "ADMISSION_PASS",
        },
        adapter_sha256=ADAPTER,
        recorded_at_utc="2026-01-01T00:00:00+00:00",
    )
    assert record["verdict"] == "FOUNDER_REJECTED"


def test_freeze_record_candidate_identity_must_match() -> None:
    with pytest.raises(freeze.FreezeAbort):
        freeze._freeze_record(
            c0=_gate(adapter="ee" * 32),
            c20=_gate(),
            motor={
                "manifest_sha256": "cc" * 32,
                "verdict": "ADMISSION_PASS",
            },
            autonomous={
                "manifest_sha256": "dd" * 32,
                "verdict": "ADMISSION_PASS",
            },
            adapter_sha256=ADAPTER,
            recorded_at_utc="2026-01-01T00:00:00+00:00",
        )


def test_founder_eval_gate_verifies_suite_and_digest(tmp_path: Path) -> None:
    manifest_path = _eval_dir(tmp_path, "founder_c0_v2", "ADMISSION_PASS")
    body = freeze._founder_eval_gate(manifest_path, "founder_c0_v2")
    assert body["verdict"] == "ADMISSION_PASS"
    assert body["candidate_adapter_sha256"] == ADAPTER

    with pytest.raises(freeze.FreezeAbort):
        freeze._founder_eval_gate(manifest_path, "founder_c20_v1")


def test_founder_eval_gate_rejects_summary_digest_drift(
    tmp_path: Path,
) -> None:
    manifest_path = _eval_dir(tmp_path, "founder_c20_v1", "ADMISSION_FAIL")
    summaries_path = manifest_path.parent / "summaries.json"
    _write(
        summaries_path,
        {
            "founder_c20_v1": {
                "verdict": "ADMISSION_PASS",
                "post_selection_only": True,
            }
        },
    )
    with pytest.raises(freeze.FreezeAbort):
        freeze._founder_eval_gate(manifest_path, "founder_c20_v1")


def test_a0_gate_verdict_fields(tmp_path: Path) -> None:
    passing = _a0_manifest(tmp_path)
    motor = freeze._a0_gate(passing, "MOTOR")
    assert motor["verdict"] == "ADMISSION_PASS"
    autonomous = freeze._a0_gate(passing, "AUTONOMOUS")
    assert autonomous["verdict"] == "ADMISSION_PASS"

    # MOTOR can pass while AUTONOMOUS fails.
    partial = _a0_manifest(
        tmp_path, "a0_partial", status="ADMISSION_FAIL", selected=None
    )
    assert freeze._a0_gate(partial, "MOTOR")["verdict"] == "ADMISSION_PASS"
    assert (
        freeze._a0_gate(partial, "AUTONOMOUS")["verdict"] == "ADMISSION_FAIL"
    )

    incomplete = tmp_path / "a0bad" / "manifest.json"
    incomplete.parent.mkdir(parents=True)
    _write(incomplete, {"status": "PLANNED", "result": {}})
    with pytest.raises(freeze.FreezeAbort):
        freeze._a0_gate(incomplete, "MOTOR")


def test_record_spec_audit_passes_against_frozen_spec() -> None:
    freeze._record_spec_audit()
