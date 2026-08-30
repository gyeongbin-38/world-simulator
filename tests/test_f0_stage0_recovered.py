from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/f0_stage0_recovered_runner.py"
RECOVERY = ROOT / "specs/experiments/F0-historical-fa-v1-recovery.yaml"
DATASET_ROOT = Path("E:/WORLD/AI_CACHE/artifacts/F0_DATASET_V1")
BASE_ROOT = Path("E:/WORLD/AI_MODELS/OLMo-2-0425-1B-Instruct-BF16")


def _module():
    spec = importlib.util.spec_from_file_location("f0_stage0_recovered_runner", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_recovery_record_is_append_only_and_preserves_historical_fail() -> None:
    record = json.loads(RECOVERY.read_text(encoding="utf-8"))
    assert record["record_id"] == "F0_HISTORICAL_FA_V1_RECOVERY_V1"
    assert record["status"] == "RECOVERED_FORMAL_PROVENANCE"
    assert record["adapter"]["artifact_sha256"] == (
        "46917511362243be67e0783ddb7411a96f26613c1083bc4f95117d910d0998ec"
    )
    assert record["historical_result"]["status"] == "FAIL_SYNTHETIC_HIDDEN_ADMISSION"
    assert record["historical_result"]["exact"] == 0.9832589285714286
    assert record["historical_result"]["choices_in_prompt"] is False
    assert record["chronology"]["prior_record_rewritten"] is False


def test_stage0_contract_verifies_frozen_hidden_union() -> None:
    module = _module()
    contract = module.verify_contract(DATASET_ROOT)
    assert contract["dataset"]["manifest_digest"] == module.DATASET_MANIFEST_DIGEST
    assert contract["dataset"]["hidden_union_count"] == 3584
    assert contract["dataset"]["hidden_union_splits"] == [
        "DEV",
        "STRUCTURAL_HOLDOUT",
        "TEMPLATE_HOLDOUT",
        "DOUBLE_HOLDOUT",
    ]
    assert "DEV" in contract["dataset"]["hidden_union_splits"]
    assert "ADVERSARIAL_HOLDOUT" not in contract["dataset"]["hidden_union_splits"]
    assert set(contract["dataset"]["splits"]) == set(module.ALL_SPLITS)
    assert len(contract["neural_families"]) == 15
    assert module.VISIBLE_COUNT_FAMILY not in contract["neural_families"]
    assert module.SERIALIZATION_FAMILY in contract["neural_families"]


def test_tokenizer_static_audit_matches_pinned_olmo_semantics() -> None:
    module = _module()
    audit = module.audit_tokenizer(BASE_ROOT)
    assert audit["revision"] == module.BASE_REVISION
    assert audit["tokenizer_digest"] == module.TOKENIZER_EXPECTED["tokenizer_digest"]
    assert audit["config_digest"] == module.TOKENIZER_EXPECTED["config_digest"]
    assert audit["foundation_completion_path"] == "DIRECT_COMPLETION_NO_CHAT_TEMPLATE"


def test_recovered_artifact_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    module = _module()
    paths = []
    for name in ("base", "adapter", "training", "hidden", "predictions"):
        path = tmp_path / (
            "adapter_model.safetensors" if name == "adapter" else name
        )
        path.write_text(name, encoding="utf-8")
        paths.append(path)
    with pytest.raises(module.Stage0ValidationError, match="SHA-256 mismatch"):
        module.verify_recovered_files(
            base_checkpoint=paths[0],
            adapter_file=paths[1],
            training_evidence=paths[2],
            hidden_evidence=paths[3],
            hidden_predictions=paths[4],
        )


def test_stage0_source_does_not_write_hidden_cases_to_evidence() -> None:
    source = TOOL.read_text(encoding="utf-8")
    assert '"hidden_cases_copied": False' in source
    assert '"hidden_union_splits"' in source


def test_linux_absolute_evidence_root_is_accepted() -> None:
    module = _module()
    accepted = module.validate_evidence_root(
        "/workspace/alifelm/evidence/F0_FOUNDATION_STAGE0_EVAL_V2_V1",
        system="Linux",
    )
    assert accepted.as_posix().startswith("/workspace/")


def test_linux_relative_evidence_root_is_rejected() -> None:
    module = _module()
    with pytest.raises(module.Stage0ValidationError, match="absolute"):
        module.validate_evidence_root("evidence/stage0", system="Linux")


def test_windows_e_drive_evidence_root_is_accepted() -> None:
    module = _module()
    assert str(
        module.validate_evidence_root(
            "E:/WORLD/AI_CACHE/evidence/stage0", system="Windows"
        )
    ).startswith("E:")


def test_existing_mismatching_manifest_refuses_overwrite(tmp_path: Path) -> None:
    module = _module()
    root = tmp_path / "evidence"
    manifest = {"status": "COMPLETE", "manifest_digest": "a" * 64}
    module.write_immutable_manifest(root, manifest, system="Linux")
    with pytest.raises(module.Stage0ValidationError, match="refusing overwrite"):
        module.write_immutable_manifest(
            root,
            {"status": "COMPLETE", "manifest_digest": "b" * 64},
            system="Linux",
        )
