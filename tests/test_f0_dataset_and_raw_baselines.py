from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from alifelm.model.foundation_data import (
    FORMAL_HOLDOUT_TEMPLATE_IDS,
    FORMAL_TRAIN_TEMPLATE_IDS,
    SemanticFamily,
    generate_formal_example,
    load_reserved_evaluation_fingerprints,
    solve,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DATASET_ROOT = Path("E:/WORLD/AI_CACHE/artifacts/F0_DATASET_V1")
BASELINE_ROOT = Path("E:/WORLD/AI_CACHE/evidence/f0-raw-baselines-v1")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_repo_spec(name: str) -> dict:
    return json.loads((REPOSITORY_ROOT / "specs/experiments" / name).read_text("utf-8"))


def test_formal_profile_generation_is_deterministic_and_symbolic() -> None:
    """F0-GENERATOR-003; F0-UNIQUE-ANSWER-002; F0-VISIBILITY-002."""

    reservations = load_reserved_evaluation_fingerprints()
    kwargs = {
        "topology_profile": "HOLDOUT_I3O2",
        "template_id": "F0_EXPLICIT_HOLDOUT_V2",
        "reserved_eval_fingerprints": reservations,
    }
    first = generate_formal_example(82917, SemanticFamily.PROPOSAL_TARGET, **kwargs)
    second = generate_formal_example(82917, SemanticFamily.PROPOSAL_TARGET, **kwargs)
    assert first == second
    assert first.answer == solve(first.state, first.query)
    assert first.choices.count(first.answer) == 1
    assert first.structural_fingerprint not in reservations


def test_template_and_structural_controls_are_disjoint() -> None:
    """F0-SPLIT-002; F0-FINGERPRINT-003."""

    assert set(FORMAL_TRAIN_TEMPLATE_IDS).isdisjoint(FORMAL_HOLDOUT_TEMPLATE_IDS)
    train = {
        generate_formal_example(
            700 + index,
            SemanticFamily.MESSAGE_DIRECTION,
            topology_profile=profile,
            template_id=FORMAL_TRAIN_TEMPLATE_IDS[0],
        ).structural_fingerprint
        for index, profile in enumerate(("BASE_I2O1", "BASE_I1O2", "BASE_I2O2"))
    }
    structural = {
        generate_formal_example(
            800 + index,
            SemanticFamily.MESSAGE_DIRECTION,
            topology_profile=profile,
            template_id=FORMAL_TRAIN_TEMPLATE_IDS[0],
        ).structural_fingerprint
        for index, profile in enumerate(("HOLDOUT_I3O1", "HOLDOUT_I1O3", "HOLDOUT_I3O2"))
    }
    assert train.isdisjoint(structural)


@pytest.mark.skipif(not (DATASET_ROOT / "manifest.json").exists(), reason="external F0 artifact unavailable")
def test_frozen_dataset_counts_hashes_and_isolation() -> None:
    """F0-DATASET-001; F0-CONTAMINATION-002; F0-SPLIT-003."""

    repo_manifest = _load_repo_spec("F0-dataset-v1-manifest.yaml")
    artifact_manifest = json.loads((DATASET_ROOT / "manifest.json").read_text("utf-8"))
    assert repo_manifest["manifest_digest"] == artifact_manifest["manifest_digest"]
    assert artifact_manifest["validation"] == {
        "ambiguous": 0,
        "cross_split_violations": 0,
        "exact_text_duplicates": 0,
        "examples_total": 8192,
        "policy_examples": 0,
        "regeneration_count": 0,
        "reserved_collision_regenerations": 0,
        "reserved_collisions_final": 0,
        "template_violations": 0,
    }
    for split, expected in repo_manifest["splits"].items():
        path = DATASET_ROOT / expected["file"]
        assert sum(1 for _ in path.open("r", encoding="utf-8")) == expected["count"]
        assert _sha256(path) == expected["file_sha256"]
        assert artifact_manifest["splits"][split]["aggregate_split_digest"] == expected["aggregate_split_digest"]


def test_neutrality_suite_is_frozen_and_policy_neutral() -> None:
    """F0-NEUTRALITY-003."""

    spec = _load_repo_spec("F0-neutrality-suite-v1.yaml")
    suite_path = Path(spec["artifact"])
    if not suite_path.exists():
        pytest.skip("external neutrality suite unavailable")
    suite = json.loads(suite_path.read_text("utf-8"))
    assert suite["suite_id"] == spec["suite_id"]
    assert suite["suite_digest"] == spec["suite_digest"]
    assert len(suite["cases"]) == spec["case_count"] == 356
    assert suite["social_prior_added"] is False
    assert suite["required_action_distribution"] is None


@pytest.mark.skipif(not (BASELINE_ROOT / "manifest.json").exists(), reason="RAW baselines not frozen yet")
def test_raw_baseline_provenance_and_sealed_evaluation_nonexecution() -> None:
    """F0-BASELINE-001; F0-CONTAMINATION-003."""

    manifest = json.loads((BASELINE_ROOT / "manifest.json").read_text("utf-8"))
    assert manifest["status"] == "FROZEN"
    assert manifest["model"]["adapter_loaded"] is False
    assert manifest["C0_executed"] is False
    assert manifest["C20_executed"] is False
    assert manifest["sealed_evaluation_access"] == "FINGERPRINTS_ONLY_DURING_DATASET_GENERATION"
    assert manifest["hidden"]["n"] == 3584
    assert manifest["retention"]["n"] == 60
    assert manifest["neutrality"]["free_action_distribution"]["n"] == 100
