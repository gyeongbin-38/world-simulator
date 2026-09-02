from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from alifelm.model.p1c_metrics import P1C_CONDITIONS, P1C_STUDY_ID
from alifelm.model.world_v0_smoke import DeploymentPaths


ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "tools" / "world_p1c_foundation_policy_phase_ablation.py"
CONFIG_PATH = ROOT / "docs" / "research" / "world" / "WORLD_P1C_FOUNDATION_POLICY_PHASE_ABLATION_CONFIG_V1.json"


def _runner_module():
    spec = spec_from_file_location("world_p1c_runner_contract", RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_p1c_runner_loads_frozen_config_without_drift():
    runner = _runner_module()
    config, digest = runner._load_config(CONFIG_PATH)
    assert config["study_id"] == P1C_STUDY_ID
    assert config["preregistration_commit"] == runner.P1C_PREREG_COMMIT
    assert len(digest) == 64


def test_p1c_runner_phase_conditions_match_frozen_order_and_states():
    runner = _runner_module()
    assert tuple(name for name, _, _ in runner.PHASE_CONDITIONS) == P1C_CONDITIONS
    assert runner.PHASE_CONDITIONS == (
        ("C00", False, False),
        ("C11", True, True),
        ("C10", True, False),
        ("C01", False, True),
    )


def test_p1c_planned_document_has_only_diagnostic_measurements(tmp_path):
    runner = _runner_module()
    paths = DeploymentPaths(
        base_model_dir=tmp_path / "base",
        adapter_path=tmp_path / "adapter",
        output_root=tmp_path / "out",
    )
    planned = runner._planned_document(
        paths=paths,
        git_commit="a" * 40,
        config_sha256="b" * 64,
    )
    assert planned["ordinary_base_score_sets"] == 160
    assert planned["phase_score_sets"] == 640
    assert planned["phase_repeat_score_sets"] == 4
    assert planned["state_commit"] is False
    assert planned["weight_update"] is False
    assert planned["behavioral_admission"] is False


def test_p1c_profiles_share_exact_base_and_only_fa_profile_has_adapter(tmp_path):
    runner = _runner_module()
    base = runner._profile(tmp_path, adapter=False)
    fa = runner._profile(tmp_path, adapter=True)
    assert base.model_revision == fa.model_revision == runner.P1C_BASE_MODEL_REVISION
    assert base.model_digest == fa.model_digest == runner.P1C_BASE_CHECKPOINT_SHA256
    assert base.tokenizer_digest == fa.tokenizer_digest == runner.P1C_TOKENIZER_DIGEST
    assert base.adapter_ref is None
    assert fa.adapter_ref is not None
    assert fa.adapter_ref.digest == runner.P1C_ADAPTER_SHA256
