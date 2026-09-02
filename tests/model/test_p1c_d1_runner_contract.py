from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "tools" / "world_p1c_d1_equivalence_localization.py"
CONFIG_PATH = ROOT / "docs" / "research" / "world" / "WORLD_P1C_D1_EQUIVALENCE_LOCALIZATION_CONFIG_V1.json"


def _runner_module():
    spec = spec_from_file_location("world_p1c_d1_runner_contract", RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_d1_runner_loads_frozen_config_without_drift():
    runner = _runner_module()
    config, digest = runner._load_config(CONFIG_PATH)
    assert config["study_id"] == runner.D1_STUDY_ID
    assert config["protocol_commit"] == runner.D1_PROTOCOL_COMMIT
    assert len(digest) == 64


def test_d1_runner_paths_match_frozen_protocol():
    runner = _runner_module()
    assert runner.D1_BF16_PATHS == (
        "E0_BARE_FULL_BF16",
        "E1_BARE_CACHED_BF16",
        "E2_PEFT_DISABLED_FULL_BF16",
        "E3_PEFT_DISABLED_CACHED_BF16",
    )
    assert runner.D1_FP32_PATHS == (
        "F0_BARE_FULL_FP32",
        "F1_BARE_CACHED_FP32",
    )


def test_d1_planned_document_is_diagnostic_only(tmp_path):
    runner = _runner_module()
    from alifelm.model.world_v0_smoke import DeploymentPaths

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
    assert planned["bf16_score_sets"] == 640
    assert planned["fp32_score_sets"] == 40
    assert planned["repeat_score_sets"] == 6
    assert planned["generation"] is False
    assert planned["state_commit"] is False
    assert planned["weight_update"] is False
    assert planned["source_p1c_mutation"] is False


def test_d1_profiles_define_only_frozen_dtype_paths(tmp_path):
    runner = _runner_module()
    bf16 = runner._profile(tmp_path, dtype="bfloat16", adapter=False)
    fp32 = runner._profile(tmp_path, dtype="float32", adapter=False)
    peft = runner._profile(tmp_path, dtype="bfloat16", adapter=True)
    assert bf16.model_digest == fp32.model_digest == peft.model_digest == runner.D1_BASE_CHECKPOINT_SHA256
    assert bf16.tokenizer_digest == fp32.tokenizer_digest == peft.tokenizer_digest == runner.D1_TOKENIZER_DIGEST
    assert bf16.adapter_ref is None
    assert fp32.adapter_ref is None
    assert peft.adapter_ref is not None
    assert peft.adapter_ref.digest == runner.D1_ADAPTER_SHA256
