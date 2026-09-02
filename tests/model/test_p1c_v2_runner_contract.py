import importlib.util
from pathlib import Path

from alifelm.model.p1b_metrics import ACTION_LABELS


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "tools" / "world_p1c_v2_common_topology_phase_ablation.py"
CONFIG = ROOT / "docs" / "research" / "world" / "WORLD_P1C_V2_COMMON_TOPOLOGY_PHASE_ABLATION_CONFIG_V1.json"


def _module():
    spec = importlib.util.spec_from_file_location("world_p1c_v2_runner", RUNNER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _score_rows(offset=0.0):
    return [
        {
            "model_label": label,
            "token_ids": [index + 1],
            "total_log_probability": -float(index) + offset,
            "mean_log_probability": -float(index) + offset,
            "rank": index + 1,
        }
        for index, label in enumerate(ACTION_LABELS)
    ]


def _record(case_index, offset=0.0):
    return {
        "context_class": "QUIET",
        "case_index": case_index,
        "rendered_sha256": "a" * 64,
        "context_token_ids": [1, 2],
        "prefix_token_ids": [3],
        "combined_token_ids": [1, 2, 3],
        "scores": _score_rows(offset),
    }


def test_runner_freezes_fresh_cohort_and_common_topology_conditions():
    module = _module()
    assert (module.CASE_START, module.CASE_END) == (3000, 3031)
    assert module.PHASE_CONDITIONS == (
        ("C00", False, False),
        ("C11", True, True),
        ("C10", True, False),
        ("C01", False, True),
    )


def test_runner_config_loads_frozen_protocol_without_mutation():
    module = _module()
    config, digest = module._load_config(CONFIG)
    assert config["protocol_commit"] == "9d6e7831c54c5aea3cb23f61c4dc26b5a2668a6f"
    assert config["phase_boundary"]["ordinary_full_sequence_primary_scoring"] is False
    assert len(digest) == 64


def test_planned_measurement_contract_has_no_full_sequence_primary_scores(tmp_path):
    module = _module()
    paths = module.DeploymentPaths(
        base_model_dir=tmp_path / "base",
        adapter_path=tmp_path / "adapter",
        output_root=tmp_path / "out",
    )
    planned = module._planned_document(paths=paths, config_sha256="0" * 64)
    assert planned["bare_cached_score_sets"] == 160
    assert planned["phase_score_sets"] == 640
    assert planned["repeat_score_sets"] == 5
    assert planned["ordinary_full_sequence_primary_score_sets"] == 0


def test_cached_wrapper_parity_requires_exact_numeric_equality():
    module = _module()
    bare = [_record(index) for index in range(160)]
    c00 = [_record(index) for index in range(160)]
    result = module._cached_parity(bare, c00)
    assert result["comparisons"] == 800
    assert result["posthoc_tolerance"] is None
    assert result["pass"] is True

    c00[10]["scores"][0]["total_log_probability"] += 1e-12
    assert module._cached_parity(bare, c00)["pass"] is False


def test_runner_source_hash_constants_match_frozen_results():
    module = _module()
    assert module.P1C_V1_ARCHIVE_SHA256 == "90eef02128d2caad16ef736170b28e1f8be76cb1331a53a2edb9e4d69bdff39d"
    assert module.D1_ARCHIVE_SHA256 == "300b064a9b29822c307655918cfa76cd63dd07f3a9382c2218bd0c9f0300eb9d"
    assert module.D1_SUMMARY_SHA256 == "b35075335a15f230d23e226644c09baae0020783ebfa389b74f8e62f11dc85b5"


def test_runner_cli_declares_validate_and_execute_modes():
    source = RUNNER.read_text(encoding="utf-8")
    assert 'mode.add_argument("--validate-only"' in source
    assert 'mode.add_argument("--execute"' in source
    assert 'parser.add_argument("--p1c-v1-archive"' in source
    assert 'parser.add_argument("--d1-archive"' in source
    assert 'ordinary_full_sequence_primary_score_sets": 0' in source
