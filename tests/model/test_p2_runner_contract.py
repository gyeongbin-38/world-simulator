import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "tools" / "world_p2_phase_decoupled_behavioral_admission.py"
CONFIG = ROOT / "docs" / "research" / "world" / "WORLD_P2_PHASE_DECOUPLED_BEHAVIORAL_ADMISSION_CONFIG_V1.json"


def _module():
    spec = importlib.util.spec_from_file_location("world_p2_runner_contract", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_p2_runner_frozen_identity_and_fresh_cohort():
    module = _module()
    assert module.PROTOCOL_COMMIT == "299b5ff29a14aef92b977ee53d0cf8e792067f11"
    assert module.SOURCE_RESULTS_COMMIT == "1059b03e28668e2b8563c4aa81d39e1a2e65576f"
    assert module.CONFIG_SHA256 == "c53bb0d0f037e70df0553cbd17d181b3402cc825812dd8ba1e481f096588e92b"
    assert (module.CASE_START, module.CASE_END) == (4000, 4031)
    assert module.PHASE_CONDITIONS == (
        ("C00", False, False),
        ("C01", False, True),
        ("C10", True, False),
        ("C11", True, True),
    )


def test_p2_config_freezes_i3_and_no_behavior_frequency_target():
    payload = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert payload["interface"]["mode"] == "I3"
    assert payload["interface"]["treatment_id"] == "i05r2-i3-conditional-typed-codec"
    assert payload["interface"]["semantic_payload_narrowing"] is False
    assert payload["generation"]["action_frequency_target"] is None
    assert payload["generation"]["retry"] is False
    assert payload["generation"]["fallback"] is False
    assert payload["generation"]["repair"] is False
    assert payload["ordinary_full_sequence_primary_generation_calls"] == 0
    assert payload["simulation_state_commit"] is False
    assert payload["weight_update"] is False
    assert payload["founder_freeze"] == "NOT_ESTABLISHED"


def test_p2_runner_conditional_branch_audit_and_bounded_promotion():
    source = RUNNER.read_text(encoding="utf-8")
    assert "if g0_pre_audit and g1 and g2:" in source
    assert "evaluate_i3_branch_order_audit" in source
    assert "C10_PHASE_DECOUPLED_BEHAVIORAL_ADMISSION_PASS" in source
    assert '"ordinary_full_sequence_primary_generation_calls": 0' in source
    assert '"simulation_state_commits": 0' in source
    assert '"weight_updates": 0' in source
    assert '"founder_freeze": "NOT_ESTABLISHED"' in source
