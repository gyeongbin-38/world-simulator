from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "tools" / "world_p2_d4_kv_component_decomposition.py"
CONFIG = ROOT / "docs" / "research" / "world" / "WORLD_P2_D4_KV_COMPONENT_DECOMPOSITION_CONFIG_V1.json"


def test_runner_is_bound_to_frozen_d4_preregistration():
    text = RUNNER.read_text(encoding="utf-8")
    assert 'PREREG_COMMIT = "80e449ee464c8c682ae33f2cd026e88ea6fa351c"' in text
    assert 'STUDY_ID = "WORLD_P2_D4_KV_COMPONENT_DECOMPOSITION_V1"' in text
    assert 'TARGET_LAYERS = (9, 10)' in text
    for candidate in (
        '"L9_K"',
        '"L9_V"',
        '"L10_K"',
        '"L10_V"',
        '"L9_L10_K"',
        '"L9_L10_V"',
    ):
        assert candidate in text


def test_runner_freezes_stage0_component_controls():
    text = RUNNER.read_text(encoding="utf-8")
    assert "_run_stage0" in text
    assert "transplant_cache_components" in text
    assert "transplant_cache_layers" in text
    assert "component self-donor patch is not a no-op" in text
    assert "K/V composition differs from D2 full-KV transplant" in text
    assert "component patch changed a nonselected cache component" in text
    assert "Stage-0 mutated BASE source cache" in text
    assert "Stage-0 mutated FA source cache" in text


def test_runner_freezes_screen_then_full_confirmation_and_exact_repeat():
    text = RUNNER.read_text(encoding="utf-8")
    assert "_run_stage_a" in text
    assert "select_component_candidate" in text
    assert "_run_stage_b" in text
    assert "repeat=True" in text
    assert "_repeat_view(stage_b, selected) == repeat" in text
    assert "matching_d2_full_kv_reference" in text


def test_runner_has_no_state_or_weight_mutation_path():
    text = RUNNER.read_text(encoding="utf-8")
    assert '"action_intent_generation": False' in text
    assert '"simulation_state_commits": 0' in text
    assert '"weight_updates": 0' in text
    assert "optimizer" not in text.lower()
    assert ".backward(" not in text


def test_config_remains_preregistered_and_preservation_bound():
    text = CONFIG.read_text(encoding="utf-8")
    assert '"status": "PREREGISTERED_MECHANISTIC_DIAGNOSTIC"' in text
    assert '"off_machine_copy_required_before_next_study": true' in text
    assert '"destination_hash_verification_required_before_next_study": true' in text
