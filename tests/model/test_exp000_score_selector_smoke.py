from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from alifelm.model.r3_fixtures import R3ContextClass, compile_r3_fixture
from alifelm.model.score_selector_smoke import (
    SMOKE_AGENT_ID,
    SMOKE_CASE_INDEX,
    SMOKE_CONTEXT_CLASS,
    SMOKE_OPPORTUNITY_ID,
    SMOKE_RUN_ID,
    SMOKE_SEED_DIGEST,
    SMOKE_SELECTED_ACTION,
    SMOKE_TICK,
    ScoreSelectorSmokeError,
    select_frozen_d1_row,
    verify_compiled_smoke_fixture,
)
from alifelm.model.world_v0_smoke import build_context_policy
from alifelm.persistence import FileSystemArtifactStore
from tools.world_p2_phase_decoupled_behavioral_admission import (
    GENERATION_SEED_ID,
    _policy,
    _profile,
)


def _compiled(tmp_path: Path):
    profile = _profile(Path("/tmp/exp000-smoke-model"))
    policy = _policy()
    store = FileSystemArtifactStore(tmp_path / "cas")
    return compile_r3_fixture(
        R3ContextClass.QUIET,
        SMOKE_CASE_INDEX,
        policy=build_context_policy(),
        model_profile_id=profile.profile_id,
        generation_policy_id=policy.policy_id,
        generation_seed_id=GENERATION_SEED_ID,
        artifact_store=store,
    )


def _source_row(compiled):
    return {
        "condition": "C10",
        "context_class": SMOKE_CONTEXT_CLASS,
        "case_index": SMOKE_CASE_INDEX,
        "rendered_context_sha256": hashlib.sha256(compiled.rendered_input).hexdigest(),
        "mean_scores": {
            "WAIT": 0.0,
            "SEND": -0.1,
            "PROPOSE": -10.0,
            "ACCEPT": -10.0,
            "REJECT": -10.0,
        },
    }


def test_frozen_r3_smoke_fixture_recompiles_to_exact_identity(tmp_path: Path) -> None:
    compiled = _compiled(tmp_path)
    opportunity = compiled.opportunity

    assert opportunity.run_id.value == SMOKE_RUN_ID
    assert int(opportunity.tick) == SMOKE_TICK
    assert opportunity.agent_id.value == SMOKE_AGENT_ID
    assert opportunity.opportunity_id.value == SMOKE_OPPORTUNITY_ID


def test_source_shaped_scores_reproduce_frozen_send_and_seed(tmp_path: Path) -> None:
    compiled = _compiled(tmp_path)
    decision = verify_compiled_smoke_fixture(compiled, _source_row(compiled))

    assert decision.selected_action == SMOKE_SELECTED_ACTION
    assert decision.seed_digest == SMOKE_SEED_DIGEST


def test_compiled_context_byte_drift_fails_closed(tmp_path: Path) -> None:
    compiled = _compiled(tmp_path)
    row = _source_row(compiled)
    row["rendered_context_sha256"] = "0" * 64

    with pytest.raises(ScoreSelectorSmokeError, match="context bytes"):
        verify_compiled_smoke_fixture(compiled, row)


def test_select_frozen_d1_row_requires_exact_unique_key() -> None:
    row = {
        "context_class": SMOKE_CONTEXT_CLASS,
        "case_index": SMOKE_CASE_INDEX,
        "mean_scores": {name: 0.0 for name in ("WAIT", "SEND", "PROPOSE", "ACCEPT", "REJECT")},
    }
    payload = {"primary": {"C10": [row]}}

    assert select_frozen_d1_row(payload) is row


def test_select_frozen_d1_row_rejects_duplicate_fixture_rows() -> None:
    row = {
        "context_class": SMOKE_CONTEXT_CLASS,
        "case_index": SMOKE_CASE_INDEX,
        "mean_scores": {name: 0.0 for name in ("WAIT", "SEND", "PROPOSE", "ACCEPT", "REJECT")},
    }

    with pytest.raises(ScoreSelectorSmokeError, match="not unique"):
        select_frozen_d1_row({"primary": {"C10": [row, dict(row)]}})


def test_select_frozen_d1_row_rejects_incomplete_action_vector() -> None:
    row = {
        "context_class": SMOKE_CONTEXT_CLASS,
        "case_index": SMOKE_CASE_INDEX,
        "mean_scores": {"WAIT": 0.0, "SEND": -0.1},
    }

    with pytest.raises(ScoreSelectorSmokeError, match="five D1 mean scores"):
        select_frozen_d1_row({"primary": {"C10": [row]}})
