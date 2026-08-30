from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "specs/experiments/F0-historical-fa-v1-legacy.yaml"
AB_SPEC = ROOT / "specs/experiments/F0-foundation-ab-v1.yaml"
RESOURCE_GATE = ROOT / "specs/experiments/F0-foundation-ab-resource-gate-v1.yaml"
TOOL = ROOT / "tools/f0_foundation_ab_gate.py"


def _document(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _tool_module():
    spec = importlib.util.spec_from_file_location("f0_foundation_ab_gate", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_historical_fa_v1_is_noncomparative_unverifiable_legacy() -> None:
    record = _document(LEGACY)
    assert record["status"] == "UNVERIFIABLE_LEGACY"
    assert record["rounded_historical_observation_pct"] == 98.33
    assert record["exact_98_3259_verified"] is False
    assert record["adapter_to_result_binding_available"] is False
    assert {
        "FORMAL_BASELINE",
        "PAIRED_COMPARISON",
        "IMPROVEMENT_OR_REGRESSION_EVIDENCE",
        "STATISTICAL_RESULT",
        "SUBSTITUTE_CHECKPOINT",
    } == set(record["prohibited_uses"])


def test_ab_treatments_hold_every_nonprecision_variable_constant() -> None:
    spec = _document(AB_SPEC)
    common = spec["common_training"]
    assert spec["independent_variable"] == (
        "BASE_WEIGHT_PRECISION_OR_QUANTIZATION_DURING_ADAPTATION"
    )
    assert common["epochs"] == 1
    assert common["sequence_length"] == 256
    assert common["microbatch"] == 1
    assert common["gradient_accumulation"] == 8
    assert common["effective_batch"] == 8
    assert common["optimizer"] == "torch.optim.AdamW"
    assert common["learning_rate"] == 2e-4
    assert common["weight_decay"] == 0
    assert common["warmup_steps"] == 0
    assert common["gradient_clipping"] is None
    assert common["lora"] == {
        "implementation": "PEFT_VANILLA_LORA",
        "r": 16,
        "alpha": 32,
        "dropout": 0.0,
        "bias": "none",
        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
        "forbidden_target_modules": ["gate_proj", "up_proj", "down_proj", "lm_head"],
        "forbidden_variants": [
            "EVA",
            "LORA_PLUS",
            "PISSA",
            "LORA_GA",
            "DORA",
            "RSLORA",
        ],
    }
    assert len(common["seeds"]) == 3
    assert set(spec["treatments"]) == {"A_NF4_QLORA", "B_BF16_LORA"}
    assert spec["training_authorized"] is False


def test_ab_gate_revalidates_frozen_dataset_and_sensor_boundary() -> None:
    module = _tool_module()
    dataset = module._dataset_audit()
    sensor = module._sensor_audit()
    assert dataset["manifest_digest"] == (
        "4ed8f67689e312fc2b37976d82a4b5f6d9c4ce1a38df808d6f562a9c19b259dd"
    )
    assert dataset["train_count"] == 4096
    assert dataset["visible_peer_count_gradient_targets"] == 0
    assert sensor["count"] == sensor["correct"] == 512
    assert sensor["accuracy"] == 1.0
    assert sensor["gradient_target"] is False


def test_resource_smoke_cannot_save_or_update_an_adapter() -> None:
    source = TOOL.read_text(encoding="utf-8")
    assert "optimizer.step(" not in source
    assert 'document["adapter_saved"] = False' in source
    assert "save_pretrained(" not in source


def test_resource_gate_fails_closed_on_bf16_vram_oversubscription() -> None:
    gate = _document(RESOURCE_GATE)
    assert gate["status"] == "BLOCKED_RESOURCE"
    assert gate["treatments"]["A_NF4_QLORA"]["safe_physical_vram_fit"] is True
    assert gate["treatments"]["B_BF16_LORA"]["safe_physical_vram_fit"] is False
    assert gate["resource_interpretation"]["treatments_locally_symmetric"] is False
    assert gate["resource_interpretation"]["automatic_asymmetric_fallback_allowed"] is False
    assert gate["clean_unadapted_baseline"]["metrics_available"] is False
    assert gate["training_authorized"] is False
