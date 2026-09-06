from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import world_exp000_live_multiagent_pilot as pilot


def _args(tmp_path: Path):
    return SimpleNamespace(
        base_model_dir=tmp_path / "base",
        adapter_path=tmp_path / "adapter",
        d1_details=tmp_path / "d1.json",
        smoke_manifest=tmp_path / "smoke.json",
        smoke_archive=tmp_path / "smoke.tar.gz",
        output_root=tmp_path / "out",
        expected_git_commit="a" * 40,
    )


def test_pilot_config_matches_preregistered_boundary() -> None:
    config = pilot.pilot_config()

    assert config.run_id == "WORLD_EXP000_LIVE_PILOT_V1_R1"
    assert config.founders == (
        "EXP000_FOUNDER_A",
        "EXP000_FOUNDER_B",
        "EXP000_FOUNDER_C",
    )
    assert config.horizon_ticks == 20
    assert config.lifespan_ticks == 20
    assert config.maturity_delay_ticks == 0
    assert config.refractory_interval_ticks == 0
    assert config.population_capacity == 6


def test_write_json_once_is_immutable(tmp_path: Path) -> None:
    target = tmp_path / "evidence" / "tick.json"
    pilot._write_json_once(target, {"b": 2, "a": 1})

    first = target.read_bytes()
    assert first.endswith(b"\n")
    assert json.loads(first) == {"a": 1, "b": 2}

    with pytest.raises(pilot.LivePilotError, match="overwrite"):
        pilot._write_json_once(target, {"a": 9})
    assert target.read_bytes() == first


def test_verify_smoke_sources_requires_frozen_semantics(tmp_path: Path, monkeypatch) -> None:
    manifest = tmp_path / "manifest.json"
    archive = tmp_path / "archive.tar.gz"
    payload = {
        "status": "INFRASTRUCTURE_PASS",
        "result_digest": "result",
        "selector": {"selected_action": "SEND"},
        "integrity": {"simulation_state_commits": 0, "weight_updates": 0},
    }
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    archive.write_bytes(b"archive")

    monkeypatch.setattr(pilot, "SMOKE_MANIFEST_SHA256", hashlib.sha256(manifest.read_bytes()).hexdigest())
    monkeypatch.setattr(pilot, "SMOKE_ARCHIVE_SHA256", hashlib.sha256(archive.read_bytes()).hexdigest())
    monkeypatch.setattr(pilot, "SMOKE_RESULT_DIGEST", "result")

    verified = pilot._verify_smoke_sources(manifest, archive)
    assert verified["status"] == "INFRASTRUCTURE_PASS"
    assert verified["result_digest"] == "result"

    payload["selector"]["selected_action"] = "WAIT"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(pilot, "SMOKE_MANIFEST_SHA256", hashlib.sha256(manifest.read_bytes()).hexdigest())
    with pytest.raises(pilot.LivePilotError, match="semantic identity"):
        pilot._verify_smoke_sources(manifest, archive)


def test_static_preflight_is_model_free_and_freezes_selector_contract(tmp_path: Path, monkeypatch) -> None:
    args = _args(tmp_path)
    args.d1_details.write_bytes(b"d1")

    monkeypatch.setattr(pilot, "_git_head", lambda: args.expected_git_commit)
    monkeypatch.setattr(pilot, "_git_clean", lambda: True)
    monkeypatch.setattr(
        pilot,
        "_sha256_file",
        lambda path: pilot.D1_DETAILS_SHA256 if path == args.d1_details else "unused",
    )
    monkeypatch.setattr(
        pilot,
        "_verify_smoke_sources",
        lambda *_: {
            "manifest_sha256": pilot.SMOKE_MANIFEST_SHA256,
            "archive_sha256": pilot.SMOKE_ARCHIVE_SHA256,
            "result_digest": pilot.SMOKE_RESULT_DIGEST,
            "status": "INFRASTRUCTURE_PASS",
        },
    )
    monkeypatch.setattr(
        pilot,
        "_runtime_freeze_sha256",
        lambda: (pilot.PIP_FREEZE_SHA256, pilot.RUNTIME_PACKAGE_COUNT),
    )
    monkeypatch.setattr(
        pilot,
        "verify_static_deployment",
        lambda *args, **kwargs: {"status": "STATIC_PREFLIGHT_OK"},
    )

    static = pilot.static_preflight(args)

    assert static["status"] == "STATIC_PREFLIGHT_OK"
    assert static["model_loaded"] is False
    assert static["generation"] is False
    assert static["simulation_state_commit"] is False
    assert static["selector"] == {
        "phase": "C10_FA_PREFILL_BASE_SELECTOR",
        "temperature": 1.0,
        "legality_mask": False,
        "retry": False,
        "fallback": False,
        "repair": False,
        "batching": False,
    }


def test_static_preflight_refuses_existing_output_root(tmp_path: Path, monkeypatch) -> None:
    args = _args(tmp_path)
    args.output_root.mkdir()
    monkeypatch.setattr(pilot, "_git_head", lambda: args.expected_git_commit)
    monkeypatch.setattr(pilot, "_git_clean", lambda: True)

    with pytest.raises(pilot.LivePilotError, match="output root already exists"):
        pilot.static_preflight(args)


def test_summarize_trajectory_reports_actions_lineage_and_population() -> None:
    records = [
        {
            "tick": 0,
            "population_before": 3,
            "opportunities": 3,
            "cognition": [
                {
                    "agent_id": "EXP000_FOUNDER_A",
                    "selected_action": "PROPOSE",
                    "gateway_intent": {"kind": "PROPOSE"},
                    "law_admitted": True,
                    "rejection": None,
                },
                {
                    "agent_id": "EXP000_FOUNDER_B",
                    "selected_action": "SEND",
                    "gateway_intent": {"kind": "SEND"},
                    "law_admitted": True,
                    "rejection": None,
                },
                {
                    "agent_id": "EXP000_FOUNDER_C",
                    "selected_action": "WAIT",
                    "gateway_intent": {"kind": "WAIT"},
                    "law_admitted": True,
                    "rejection": None,
                },
            ],
            "fragments": [
                {
                    "kind": "MESSAGE",
                    "message": {"message_id": "m", "body": "hello"},
                },
                {
                    "kind": "PROPOSAL_CREATED",
                    "proposal": {
                        "proposal_id": "p",
                        "proposer_id": "EXP000_FOUNDER_A",
                        "target_id": "EXP000_FOUNDER_B",
                    },
                },
                {
                    "kind": "BIRTH",
                    "birth": {
                        "proposal_id": "p",
                        "child_id": "child",
                        "parent_ids": ["EXP000_FOUNDER_A", "EXP000_FOUNDER_B"],
                    },
                },
            ],
            "commit": {"population_after": 4},
        }
    ]
    final = SimpleNamespace(
        agents=[SimpleNamespace(agent_id=SimpleNamespace(value="child"))],
        tick=20,
        state_version=20,
        status=SimpleNamespace(value="COMPLETED"),
        state_hash=lambda: "f" * 64,
    )

    summary = pilot.summarize_trajectory(records, final)

    assert summary["selected_action_distribution"] == {
        "PROPOSE": 1,
        "SEND": 1,
        "WAIT": 1,
    }
    assert summary["generation_depth"]["child"] == 1
    assert summary["max_generation_depth"] == 1
    assert summary["final_population"] == 1
    assert len(summary["messages"]) == 1
    assert len(summary["proposals_created"]) == 1
    assert len(summary["births"]) == 1


def test_preregistration_identity_is_frozen() -> None:
    assert pilot.STUDY_ID == "WORLD_EXP000_LIVE_MULTIAGENT_PILOT_V1"
    assert pilot.PREREG_COMMIT == "0aa0fdbeb4f9c0a04a52bdff54d0d751febacb1c"
    assert pilot.D1_DETAILS_SHA256 == "0e5e62709d58168c9922645c1d05d54a7f5c417b68b3f461b4558d3706ca3b17"
    assert pilot.SMOKE_RESULT_DIGEST == "7e69dbc2c40509f0cc6f10906a5482cc4cc2d01a8a114e66cb836e72ff95a912"
