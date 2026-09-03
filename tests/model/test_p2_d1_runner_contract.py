from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "tools" / "world_p2_d1_decision_boundary_localization.py"
PROTOCOL = REPO / "docs" / "research" / "world" / "WORLD_P2_D1_DECISION_BOUNDARY_LOCALIZATION_V1.md"
CONFIG = REPO / "docs" / "research" / "world" / "WORLD_P2_D1_DECISION_BOUNDARY_LOCALIZATION_CONFIG_V1.json"


def test_d1_runner_is_diagnostic_only_and_uses_frozen_source_identity():
    text = RUNNER.read_text(encoding="utf-8")
    assert 'SOURCE_P2_RESULT_DIGEST = "4226c5909fd13d8d769436d344a221d6f0c1746b08466ff6f5eb03303c0be563"' in text
    assert 'SOURCE_P2_ARCHIVE_SHA256 = "61a19717cf089fb59b43e2b52efc31e28036449418e3aeba69c8dd0bbad17790"' in text
    assert 'SOURCE_P2_PROMOTION = "C10_NOT_BEHAVIORALLY_ADMITTED"' in text
    assert 'CONDITIONS = (("C00", False, False), ("C10", True, False))' in text
    assert '"action_intent_generation": False' in text
    assert '"simulation_state_commits": 0' in text
    assert '"weight_updates": 0' in text
    assert "score_i3_decision_boundary" in text


def test_d1_protocol_forbids_p2_relabel_and_posthoc_thresholds():
    protocol = PROTOCOL.read_text(encoding="utf-8")
    config = CONFIG.read_text(encoding="utf-8")
    assert "does not reopen or relabel P2" in protocol
    assert "No numerical sensitivity threshold may be invented after observing D1" in protocol
    assert '"posthoc_threshold_changes_forbidden": true' in config
    assert '"p2_relabel_forbidden": true' in config
