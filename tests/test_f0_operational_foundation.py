from __future__ import annotations

import json
from pathlib import Path


def _load(root: Path, name: str) -> dict:
    return json.loads((root / "specs" / "experiments" / name).read_text(encoding="utf-8"))


def test_post_stage0_amendment_preserves_boundary_and_derived_metric(repository_root: Path) -> None:
    amendment = (repository_root / "docs/research/foundation/ALIFELM_FOUNDATION_TUNING_STUDY_V1_AMENDMENT_01.md").read_text(encoding="utf-8")
    assert "POST-STAGE-0 ARCHITECTURAL BOUNDARY CORRECTION" in amendment
    assert "3128 / 3136 = 0.9974489795918368" in amendment
    assert "PROPOSAL_OWNER" in amendment
    assert "historical preregistered" in amendment


def test_artifact_acceptance_binds_stage0_and_keeps_recipe_unpromoted(repository_root: Path) -> None:
    record = _load(repository_root, "F0-foundation-artifact-acceptance-v1.yaml")
    assert record["status"] == "FOUNDATION_ARTIFACT_OPERATIONAL_ACCEPTANCE"
    assert record["artifact_status"] == "ACCEPTED_FOR_WORLD_V0_EXPERIMENTAL_USE"
    assert record["training_recipe_formal_promotion"] == "NOT_ESTABLISHED"
    assert record["artifact"]["adapter_sha256"] == "46917511362243be67e0783ddb7411a96f26613c1083bc4f95117d910d0998ec"
    assert record["stage0_evidence"]["manifest_digest"] == "f46dda9d18ece93fb9c3045ea963eba5d1474d6ad99bc253fe497852227fa3d9"
    assert record["operational_metrics"]["neural_grounding_nga"] == 0.9974489795918368
    assert record["operational_metrics"]["sensor_correctness"] == 1.0
    assert record["operational_metrics"]["evaluator_failures"] == 0


def test_stage0_result_is_append_only_and_historical_fail_is_unchanged(repository_root: Path) -> None:
    record = _load(repository_root, "F0-foundation-stage0-result-v1.yaml")
    assert record["execution"]["git_commit"] == "874abe147c5129ec9209ab06e96c9f6d77875aad"
    assert record["historical_comparison"]["historical_result"] == {
        "correct": 3524,
        "total": 3584,
        "value": 0.9832589285714286,
        "status": "FAIL_SYNTHETIC_HIDDEN_ADMISSION",
    }
    assert record["historical_comparison"]["historical_status_rewritten"] is False
    assert record["sealing"]["hidden_case_contents_in_repository"] is False


def test_live_bridge_design_preserves_model_proposal_and_commit_boundaries(repository_root: Path) -> None:
    design = (repository_root / "docs/research/foundation/WORLD_V0_LIVE_MODEL_BRIDGE_V1.md").read_text(encoding="utf-8")
    required = (
        "P3 compiles every context",
        "ModelActionCandidate",
        "CognitionGateway",
        "malformed",
        "never silently become `WAIT`",
        "completion order",
        "raw generation result",
        "ArtifactStore",
        "typed_codec",
        "action_diagnostics",
        "motor_diagnostics",
        "No constrained-decoding mechanism is selected",
    )
    for phrase in required:
        assert phrase in design
