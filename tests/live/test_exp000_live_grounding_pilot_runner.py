from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from alifelm.context import ModelActionCandidate

from tools import world_exp000_live_grounding_pilot as runner


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_preregistered_identity_is_frozen():
    assert runner.STUDY_ID == "WORLD_EXP000_LIVE_GROUNDING_PILOT_V1"
    assert runner.RUN_ID == "WORLD_EXP000_LIVE_GROUNDING_PILOT_V1_R1"
    assert runner.PREREG_COMMIT == "76e666e5a51a93ea2c46bf10bda2ccf8c6f17b35"


def test_verify_grounding_smoke_requires_frozen_semantics(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.json"
    archive = tmp_path / "archive.tar.gz"
    sums = tmp_path / "SHA256SUMS"
    payload = {
        "status": "GROUNDING_SMOKE_PASS",
        "result_digest": runner.GROUNDING_SMOKE_RESULT_DIGEST,
        "gates": {
            "G0": True,
            "G1_source_context_identity": True,
            "G2_handle_mapping": True,
            "G3_phase_integrity": True,
            "G4_snapshot_unchanged": True,
        },
        "action_selector_rerun": False,
        "simulation_state_commits": 0,
        "weight_updates": 0,
        "retries": 0,
        "fallbacks": 0,
        "repairs": 0,
        "law_validator_admitted_descriptive_count": 2,
    }
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    archive.write_bytes(b"archive")
    sums.write_bytes(b"sums")
    monkeypatch.setattr(runner, "GROUNDING_SMOKE_MANIFEST_SHA256", _sha(manifest))
    monkeypatch.setattr(runner, "GROUNDING_SMOKE_ARCHIVE_SHA256", _sha(archive))
    monkeypatch.setattr(runner, "GROUNDING_SMOKE_SEAL_SUMS_SHA256", _sha(sums))
    args = SimpleNamespace(
        grounding_manifest=manifest,
        grounding_archive=archive,
        grounding_seal_sums=sums,
    )
    result = runner._verify_grounding_smoke(args)
    assert result["status"] == "GROUNDING_SMOKE_PASS"
    assert result["off_machine_hash_verified"] is True


def test_tick_record_preserves_handle_and_canonical_mapping(monkeypatch):
    candidate_raw = ModelActionCandidate(
        "CONFIRM_BILATERAL_REQUEST", (("proposal_id", "R0"),)
    )
    candidate_mapped = ModelActionCandidate(
        "CONFIRM_BILATERAL_REQUEST", (("proposal_id", "canonical-1"),)
    )
    oid = SimpleNamespace(value="oid-1")
    result = SimpleNamespace(opportunities=(SimpleNamespace(opportunity_id=oid),))
    base = {
        "tick": 3,
        "cognition": [
            {
                "opportunity_id": "oid-1",
                "agent_id": "A",
                "selected_action": "ACCEPT",
                "candidate": {
                    "action_label": "CONFIRM_BILATERAL_REQUEST",
                    "payload": {"proposal_id": "canonical-1"},
                },
                "gateway_intent": {
                    "payload": {"proposal_id": "canonical-1"}
                },
                "law_admitted": True,
            }
        ],
    }
    monkeypatch.setattr(runner, "_BASE_TICK_RECORD", lambda result, runtime: base)
    grounding = SimpleNamespace(
        mode="PROPOSAL_HANDLE_VISIBLE_REFERENCE_DOMAIN",
        treatment_id="treatment-v1",
        handle_map=SimpleNamespace(canonical_to_handle=(("canonical-1", "R0"),)),
        raw_handle_candidate=candidate_raw,
        mapped_candidate=candidate_mapped,
    )
    runtime = SimpleNamespace(
        payload_provider=SimpleNamespace(grounding_for=lambda value: grounding)
    )
    record = runner._grounding_tick_record(result, runtime)
    observed = record["cognition"][0]["proposal_grounding"]
    assert observed["handle_map"] == [
        {"canonical_proposal_id": "canonical-1", "handle": "R0"}
    ]
    assert observed["raw_handle_candidate"]["payload"]["proposal_id"] == "R0"
    assert observed["mapped_canonical_candidate"]["payload"]["proposal_id"] == "canonical-1"


def test_handle_gate_accepts_treated_and_no_visible_baseline(tmp_path):
    ticks = tmp_path / "ticks"
    ticks.mkdir()
    record = {
        "tick": 0,
        "cognition": [
            {
                "agent_id": "A",
                "selected_action": "ACCEPT",
                "candidate": {
                    "action_label": "CONFIRM_BILATERAL_REQUEST",
                    "payload": {"proposal_id": "canonical-1"},
                },
                "gateway_intent": {"payload": {"proposal_id": "canonical-1"}},
                "proposal_grounding": {
                    "mode": "PROPOSAL_HANDLE_VISIBLE_REFERENCE_DOMAIN",
                    "handle_map": [
                        {"canonical_proposal_id": "canonical-1", "handle": "R0"}
                    ],
                    "raw_handle_candidate": {
                        "action_label": "CONFIRM_BILATERAL_REQUEST",
                        "payload": {"proposal_id": "R0"},
                    },
                    "mapped_canonical_candidate": {
                        "action_label": "CONFIRM_BILATERAL_REQUEST",
                        "payload": {"proposal_id": "canonical-1"},
                    },
                },
            },
            {
                "agent_id": "B",
                "selected_action": "REJECT",
                "candidate": None,
                "gateway_intent": None,
                "proposal_grounding": {
                    "mode": "BASELINE_NO_VISIBLE_PROPOSAL_REFERENCE",
                    "handle_map": [],
                    "raw_handle_candidate": None,
                    "mapped_canonical_candidate": None,
                },
            },
        ],
    }
    (ticks / "tick_0000.json").write_text(json.dumps(record), encoding="utf-8")
    ok, details = runner._handle_gate_from_tick_records(tmp_path)
    assert ok is True
    assert details["treated_attempts"] == 1
    assert details["baseline_no_visible_reference_attempts"] == 1
    assert details["invalid"] == []


def test_handle_gate_rejects_binding_mismatch(tmp_path):
    ticks = tmp_path / "ticks"
    ticks.mkdir()
    record = {
        "tick": 4,
        "cognition": [
            {
                "agent_id": "A",
                "selected_action": "ACCEPT",
                "candidate": {
                    "action_label": "CONFIRM_BILATERAL_REQUEST",
                    "payload": {"proposal_id": "canonical-2"},
                },
                "gateway_intent": {"payload": {"proposal_id": "canonical-2"}},
                "proposal_grounding": {
                    "mode": "PROPOSAL_HANDLE_VISIBLE_REFERENCE_DOMAIN",
                    "handle_map": [
                        {"canonical_proposal_id": "canonical-1", "handle": "R0"}
                    ],
                    "raw_handle_candidate": {
                        "action_label": "CONFIRM_BILATERAL_REQUEST",
                        "payload": {"proposal_id": "R0"},
                    },
                    "mapped_canonical_candidate": {
                        "action_label": "CONFIRM_BILATERAL_REQUEST",
                        "payload": {"proposal_id": "canonical-1"},
                    },
                },
            }
        ],
    }
    (ticks / "tick_0004.json").write_text(json.dumps(record), encoding="utf-8")
    ok, details = runner._handle_gate_from_tick_records(tmp_path)
    assert ok is False
    assert details["invalid"][0]["reason"] == "HANDLE_CANONICAL_BINDING_MISMATCH"
