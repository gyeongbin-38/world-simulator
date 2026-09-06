from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import world_exp000_proposal_handle_grounding_smoke as smoke


def test_target_cases_match_preregistered_source_failures() -> None:
    assert smoke.TARGET_CASES == (
        (2, "EXP000_FOUNDER_A", "ACCEPT"),
        (8, "EXP000_FOUNDER_A", "ACCEPT"),
        (14, "EXP000_FOUNDER_C", "REJECT"),
    )


def test_write_json_once_is_immutable(tmp_path: Path) -> None:
    target = tmp_path / "evidence" / "case.json"
    smoke._write_json_once(target, {"b": 2, "a": 1})
    first = target.read_bytes()
    assert first.endswith(b"\n")
    assert json.loads(first) == {"a": 1, "b": 2}

    with pytest.raises(smoke.GroundingSmokeError, match="overwrite"):
        smoke._write_json_once(target, {"a": 9})
    assert target.read_bytes() == first


def test_verify_source_seal_checks_all_listed_files(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "seal"
    evidence = root / "evidence"
    evidence.mkdir(parents=True)
    manifest = evidence / "manifest.json"
    manifest_payload = {
        "status": "LIVE_PILOT_COMPLETE",
        "result_digest": "result",
        "gates": {"G0": True, "G1": True, "G2": True, "G3": True},
    }
    manifest.write_text(json.dumps(manifest_payload), encoding="utf-8")
    other = evidence / "tick.json"
    other.write_bytes(b"tick")

    sums = root / "SHA256SUMS"
    sums.write_text(
        f"{hashlib.sha256(manifest.read_bytes()).hexdigest()}  evidence/manifest.json\n"
        f"{hashlib.sha256(other.read_bytes()).hexdigest()}  evidence/tick.json\n",
        encoding="utf-8",
    )
    archive = tmp_path / "archive.tar.gz"
    archive.write_bytes(b"archive")

    monkeypatch.setattr(smoke, "SOURCE_SEAL_SUMS_SHA256", hashlib.sha256(sums.read_bytes()).hexdigest())
    monkeypatch.setattr(smoke, "SOURCE_ARCHIVE_SHA256", hashlib.sha256(archive.read_bytes()).hexdigest())
    monkeypatch.setattr(smoke, "SOURCE_MANIFEST_SHA256", hashlib.sha256(manifest.read_bytes()).hexdigest())
    monkeypatch.setattr(smoke, "SOURCE_RESULT_DIGEST", "result")

    result = smoke._verify_source_seal(root, archive)
    assert result["verified_file_count"] == 2
    assert result["status"] if "status" in result else True

    other.write_bytes(b"changed")
    with pytest.raises(smoke.GroundingSmokeError, match="hash drift"):
        smoke._verify_source_seal(root, archive)


def test_cas_bytes_rejects_digest_drift(tmp_path: Path) -> None:
    root = tmp_path / "evidence"
    digest = hashlib.sha256(b"expected").hexdigest()
    path = root / "cas" / digest[:2] / digest
    path.parent.mkdir(parents=True)
    path.write_bytes(b"wrong")

    with pytest.raises(smoke.GroundingSmokeError, match="digest mismatch"):
        smoke._cas_bytes(root, {"artifact_id": "x", "digest": digest})


def test_static_preflight_blocks_existing_output_before_model_use(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "out"
    output.mkdir()
    args = SimpleNamespace(
        base_model_dir=tmp_path / "base",
        adapter_path=tmp_path / "adapter",
        source_seal_root=tmp_path / "seal",
        source_archive=tmp_path / "archive.tar.gz",
        output_root=output,
        expected_git_commit="a" * 40,
    )
    monkeypatch.setattr(smoke, "_git_head", lambda: args.expected_git_commit)
    monkeypatch.setattr(smoke, "_git_clean", lambda: True)

    with pytest.raises(smoke.GroundingSmokeError, match="output root already exists"):
        smoke.static_preflight(args)
