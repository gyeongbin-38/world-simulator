from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AB_SPEC = ROOT / "specs/experiments/F0-foundation-ab-v1.yaml"
TOOL = ROOT / "tools/f0_foundation_ab_train.py"
GATE_TOOL = ROOT / "tools/f0_foundation_ab_gate.py"


def _tool_module():
    spec = importlib.util.spec_from_file_location("f0_foundation_ab_train", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _document(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class _FakeTokenizer:
    """Deterministic char-level tokenizer for masking-law tests."""

    bos_token_id = 100257
    eos_token_id = 100257
    eos_token = "<eos>"
    pad_token_id = 100277

    def encode(self, text: str, *, add_special_tokens: bool = False) -> list[int]:
        ids = [ord(character) + 1000 for character in text]
        if add_special_tokens:
            return [self.bos_token_id] + ids
        return ids


def test_trainer_constants_match_frozen_spec() -> None:
    module = _tool_module()
    spec = _document(AB_SPEC)
    common = spec["common_training"]
    assert module.EPOCHS == common["epochs"] == 1
    assert module.SEQUENCE_LENGTH == common["sequence_length"] == 256
    assert module.MICROBATCH == common["microbatch"] == 1
    assert module.GRADIENT_ACCUMULATION == common["gradient_accumulation"] == 8
    assert module.EFFECTIVE_BATCH == common["effective_batch"] == 8
    assert module.LEARNING_RATE == common["learning_rate"] == 2e-4
    assert module.WEIGHT_DECAY == common["weight_decay"] == 0.0
    assert tuple(common["seeds"]) == module.SEEDS
    assert module.LORA_R == common["lora"]["r"] == 16
    assert module.LORA_ALPHA == common["lora"]["alpha"] == 32
    assert module.LORA_DROPOUT == common["lora"]["dropout"] == 0.0
    assert list(module.TARGET_MODULES) == common["lora"]["target_modules"]
    assert list(module.FORBIDDEN_TARGET_MODULES) == (
        common["lora"]["forbidden_target_modules"]
    )
    assert set(module.TREATMENTS) == set(spec["treatments"])
    for treatment, body in spec["treatments"].items():
        assert module.TREATMENT_IDS[treatment] == body["treatment_id"]
    assert spec["independent_variable"] == (
        "BASE_WEIGHT_PRECISION_OR_QUANTIZATION_DURING_ADAPTATION"
    )


def test_seed_derivation_law_matches_pinned_seeds() -> None:
    module = _tool_module()
    derived = [module.derive_seed(index) for index in range(len(module.SEEDS))]
    assert derived == list(module.SEEDS) == [
        292255390,
        1166218024,
        698950225,
    ]


def test_render_batch_masks_prompt_and_activates_answer() -> None:
    module = _tool_module()
    tokenizer = _FakeTokenizer()
    record = {
        "example_id": "X1",
        "semantic_family": "MESSAGE_DIRECTION",
        "input": "Self: A\nMessage: A->B",
        "ground_truth": "OUTGOING",
    }
    batch = module._render_batch(record, tokenizer)
    prompt = module.foundation_scoring_prompt(record["input"]).decode("utf-8")
    prompt_ids = tokenizer.encode(prompt, add_special_tokens=True)
    answer_ids = tokenizer.encode("OUTGOING" + tokenizer.eos_token)
    used = len(prompt_ids) + len(answer_ids)
    assert batch["labels"][: len(prompt_ids)] == [-100] * len(prompt_ids)
    assert batch["labels"][len(prompt_ids) : used] == answer_ids
    assert batch["labels"][used:] == [-100] * (256 - used)
    assert batch["attention_mask"] == [1] * used + [0] * (256 - used)


def test_render_batch_rejects_sensor_owned_and_overlength() -> None:
    module = _tool_module()
    tokenizer = _FakeTokenizer()
    with pytest.raises(module.TrainingAbort):
        module._render_batch(
            {
                "example_id": "S1",
                "semantic_family": "VISIBLE_PEER_COUNT",
                "input": "x",
                "ground_truth": "3",
            },
            tokenizer,
        )
    with pytest.raises(module.TrainingAbort):
        module._render_batch(
            {
                "example_id": "L1",
                "semantic_family": "MESSAGE_DIRECTION",
                "input": "y" * 400,
                "ground_truth": "OUTGOING",
            },
            tokenizer,
        )


def test_paired_ordering_is_deterministic_and_seed_separated() -> None:
    torch = pytest.importorskip("torch")
    module = _tool_module()

    def perm(seed: int, epoch: int) -> list[int]:
        generator = torch.Generator()
        generator.manual_seed(seed + epoch)
        return torch.randperm(4096, generator=generator).tolist()

    first = perm(module.SEEDS[0], 0)
    assert perm(module.SEEDS[0], 0) == first
    assert perm(module.SEEDS[1], 0) != first
    assert perm(module.SEEDS[0], 1) != first
    assert len(set(first)) == 4096


def test_validate_only_passes_repository_side_checks() -> None:
    module = _tool_module()
    pytest.importorskip("torch")
    document = module.validate_only()
    assert document["status"] == "VALIDATE_ONLY_PASS"
    assert all(document["checks"].values())
    assert document["detail"]["dataset"]["train_count"] == 4096
    assert document["detail"]["dataset"]["manifest_digest"] == (
        "4ed8f67689e312fc2b37976d82a4b5f6d9c4ce1a38df808d6f562a9c19b259dd"
    )
    assert document["detail"]["sensor"]["accuracy"] == 1.0
    assert document["detail"]["modules"]["matched_counts"] == {
        suffix: 16 for suffix in module.TARGET_MODULES
    }


def test_execute_refuses_existing_run_directory(tmp_path: Path) -> None:
    module = _tool_module()
    run_dir = tmp_path / "F0_AB_A_NF4_QLORA_SEED0"
    run_dir.mkdir(parents=True)
    with pytest.raises(module.TrainingAbort, match="already exists"):
        module.execute("A_NF4_QLORA", 0, tmp_path)


def test_execute_blocks_without_admitted_stack(tmp_path: Path) -> None:
    module = _tool_module()
    try:
        import transformers  # noqa: F401
        import peft  # noqa: F401
        import torch

        stack_ready = torch.cuda.is_available()
    except ImportError:
        stack_ready = False
    if stack_ready:
        pytest.skip("admitted GPU stack present; block test is vacuous")
    with pytest.raises(module.TrainingAbort):
        module.execute("B_BF16_LORA", 0, tmp_path)


def test_no_adapter_saved_after_training_abort() -> None:
    source = TOOL.read_text(encoding="utf-8")
    assert 'exit_status == "TRAIN_COMPLETE"' in source
    assert "save_pretrained" in source
    abort_index = source.index('exit_status = "TRAIN_ABORT"')
    save_index = source.index("model.save_pretrained")
    assert abort_index < save_index
    assert "if exit_status == \"TRAIN_COMPLETE\":" in source[abort_index:save_index]


def test_gate_tool_still_refuses_optimizer_steps() -> None:
    source = GATE_TOOL.read_text(encoding="utf-8")
    assert "optimizer.step(" not in source
    assert "save_pretrained(" not in source
