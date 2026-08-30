#!/usr/bin/env python3
"""Audit and resource-test the controlled F0 NF4-vs-BF16 experiment.

This tool never performs an optimizer step and never saves an adapter. It may
write researcher-only gate evidence under E:/WORLD/AI_CACHE/evidence.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from typing import Any, Mapping


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from alifelm.model.foundation_data import canonical_digest, canonical_json  # noqa: E402
from alifelm.model.foundation_eval import (  # noqa: E402
    FOUNDATION_EVALUATOR_ID,
    FOUNDATION_EVALUATOR_VERSION,
    foundation_scoring_prompt,
)
from alifelm.model.foundation_sensor import (  # noqa: E402
    SENSOR_NORMALIZER_ID,
    SENSOR_NORMALIZER_VERSION,
    sensor_invariant_bytes,
)


EXPERIMENT_ID = "F0_FOUNDATION_AB_V1"
GATE_ID = "F0_FOUNDATION_AB_RESOURCE_GATE_V1"
DATASET_ID = "F0_DATASET_V2"
DATASET_DIGEST = "4ed8f67689e312fc2b37976d82a4b5f6d9c4ce1a38df808d6f562a9c19b259dd"
DATASET_ROOT = Path("E:/WORLD/AI_CACHE/artifacts/F0_DATASET_V2")
MODEL_REPO = "allenai/OLMo-2-0425-1B-Instruct"
MODEL_REVISION = "48d788eca847d4d7548f375ad03d3c9312f6139e"
MODEL_ROOT = Path("E:/WORLD/AI_MODELS/OLMo-2-0425-1B-Instruct-BF16")
CHECKPOINT_PATH = MODEL_ROOT / "model.safetensors"
CHECKPOINT_SHA256 = "36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f"
EVIDENCE_ROOT = Path("E:/WORLD/AI_CACHE/evidence/f0-foundation-ab-gate-v1")
TARGET_MODULES = ("q_proj", "k_proj", "v_proj", "o_proj")
FORBIDDEN_TARGET_MODULES = ("gate_proj", "up_proj", "down_proj", "lm_head")
SEQUENCE_LENGTH = 256
SEED = 292255390
EXPECTED_SPLIT_HASHES = {
    "train.jsonl": "9e23b2dbb5cdf0ca866c854f9450d8d5eabaefc4211c107ffbe9f1416f0b91da",
    "dev.jsonl": "08ad4fa2decde3864c7f049b577f8630d4c1171fa5d1c987b55d4176a0180d1d",
    "structural_holdout.jsonl": "392bacd5ee492f41bfc91259e94d87c91d924acc00c2e2ad0422584797c64c0e",
    "template_holdout.jsonl": "dbb311d78739ab902dabac86d9a55921ba530d7da55e5e082243406ba2bd1f7e",
    "double_holdout.jsonl": "588841b262ce1cc6db99d2a5b7661260784d31ba1dff52a9a154f5572259a260",
    "adversarial_holdout.jsonl": "ef3d2d00c7d6d9992c9a16fb1819edd71fdd0e84ba7da30975be7965fbd95978",
    "screening_train.jsonl": "f83520cd675368a99796bcb9227eff465ccec6b0d62d07d8579985324de4c52a",
    "screening_dev.jsonl": "24c8bfba0119bba959e05d543053e4d35fbd7dc69e53ffb9a1e464256ae4253e",
    "sensor_invariants.jsonl": "82551f554cf75d0456953d7b7806270e0568db8edbe18d5f7cdd928d380f7d2a",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_file_digest(paths: Mapping[str, Path]) -> tuple[str, dict[str, str]]:
    hashes = {name: sha256_file(path) for name, path in sorted(paths.items())}
    return canonical_digest(hashes), hashes


def package_versions() -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for name in (
        "python",
        "torch",
        "transformers",
        "peft",
        "bitsandbytes",
        "accelerate",
        "safetensors",
    ):
        if name == "python":
            result[name] = sys.version.split()[0]
            continue
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = None
    return result


def git_state() -> dict[str, Any]:
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPOSITORY_ROOT, text=True
    ).strip()
    status = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=REPOSITORY_ROOT, text=True
    )
    return {"commit": head, "worktree_clean": not bool(status), "status": status.splitlines()}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _write_new_evidence(path: Path, document: dict[str, Any]) -> None:
    core = dict(document)
    core.pop("evidence_digest", None)
    document = dict(core)
    document["evidence_digest"] = canonical_digest(core)
    payload = (canonical_json(document) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise RuntimeError(f"existing evidence differs: {path}")
        return
    path.write_bytes(payload)


def _dataset_audit() -> dict[str, Any]:
    manifest_path = DATASET_ROOT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("manifest_digest") != DATASET_DIGEST:
        raise RuntimeError("F0_DATASET_V2 manifest digest mismatch")
    core = dict(manifest)
    core.pop("manifest_digest")
    if canonical_digest(core) != DATASET_DIGEST:
        raise RuntimeError("F0_DATASET_V2 canonical digest law failed")
    actual_hashes = {
        name: sha256_file(DATASET_ROOT / name) for name in EXPECTED_SPLIT_HASHES
    }
    if actual_hashes != EXPECTED_SPLIT_HASHES:
        raise RuntimeError("F0_DATASET_V2 split digest mismatch")
    train = _load_jsonl(DATASET_ROOT / "train.jsonl")
    peer_count_targets = sum(
        record["semantic_family"] == "VISIBLE_PEER_COUNT" for record in train
    )
    if len(train) != 4096 or peer_count_targets:
        raise RuntimeError("F0_DATASET_V2 neural training boundary failed")
    return {
        "dataset_id": manifest["dataset_id"],
        "manifest_digest": manifest["manifest_digest"],
        "manifest_file_sha256": sha256_file(manifest_path),
        "split_hashes": actual_hashes,
        "train_count": len(train),
        "visible_peer_count_gradient_targets": peer_count_targets,
    }


def _sensor_audit() -> dict[str, Any]:
    records = _load_jsonl(DATASET_ROOT / "sensor_invariants.jsonl")
    correct = 0
    artifact_hashes: list[str] = []
    for record in records:
        artifact = sensor_invariant_bytes(record)
        document = json.loads(artifact)
        correct += int(document["ground_truth_agrees"])
        artifact_hashes.append(hashlib.sha256(artifact).hexdigest())
    if len(records) != 512 or correct != len(records):
        raise RuntimeError("deterministic sensor invariant failure")
    return {
        "normalizer_id": SENSOR_NORMALIZER_ID,
        "normalizer_version": SENSOR_NORMALIZER_VERSION,
        "count": len(records),
        "correct": correct,
        "accuracy": correct / len(records),
        "gradient_target": False,
        "result_digest": canonical_digest(artifact_hashes),
    }


def _module_audit() -> dict[str, Any]:
    from safetensors import safe_open

    with safe_open(CHECKPOINT_PATH, framework="pt", device="cpu") as stream:
        keys = tuple(stream.keys())
    matched = {
        suffix: sorted(
            key
            for key in keys
            if key.endswith(f".self_attn.{suffix}.weight")
        )
        for suffix in TARGET_MODULES
    }
    counts = {suffix: len(values) for suffix, values in matched.items()}
    if counts != {suffix: 16 for suffix in TARGET_MODULES}:
        raise RuntimeError(f"unexpected OLMo attention module tree: {counts}")
    forbidden = sorted(
        key
        for key in keys
        if any(key.endswith(f".{suffix}.weight") for suffix in FORBIDDEN_TARGET_MODULES)
    )
    return {
        "target_modules": list(TARGET_MODULES),
        "matched_counts": counts,
        "matched_paths": matched,
        "forbidden_target_modules": list(FORBIDDEN_TARGET_MODULES),
        "forbidden_modules_present_in_base_but_not_targeted": forbidden,
    }


def run_audit(evidence_path: Path) -> dict[str, Any]:
    import torch
    from transformers import AutoConfig, AutoTokenizer

    checkpoint_digest = sha256_file(CHECKPOINT_PATH)
    if checkpoint_digest != CHECKPOINT_SHA256:
        raise RuntimeError("canonical base checkpoint digest mismatch")
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_ROOT, local_files_only=True, use_fast=True
    )
    config = AutoConfig.from_pretrained(MODEL_ROOT, local_files_only=True)
    sample = "Canonical visible state follows.\nSelf handle: A1\n"
    ids_without = tokenizer.encode(sample, add_special_tokens=False)
    ids_with = tokenizer.encode(sample, add_special_tokens=True)
    rendered_chat = tokenizer.apply_chat_template(
        [{"role": "user", "content": sample}],
        tokenize=False,
        add_generation_prompt=True,
    )
    tokenizer_files = {
        name: MODEL_ROOT / name
        for name in (
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "vocab.json",
            "merges.txt",
        )
    }
    tokenizer_digest, tokenizer_hashes = canonical_file_digest(tokenizer_files)
    config_digest, config_hashes = canonical_file_digest(
        {
            "config.json": MODEL_ROOT / "config.json",
            "generation_config.json": MODEL_ROOT / "generation_config.json",
        }
    )
    free_bytes = total_bytes = None
    if torch.cuda.is_available():
        free_bytes, total_bytes = torch.cuda.mem_get_info(0)
    document = {
        "evidence_schema": "alifelm-f0-foundation-ab-audit-v1",
        "experiment_id": EXPERIMENT_ID,
        "gate_id": GATE_ID,
        "status": "PASS",
        "git": git_state(),
        "dataset": _dataset_audit(),
        "base": {
            "repo": MODEL_REPO,
            "revision": MODEL_REVISION,
            "path": str(MODEL_ROOT),
            "checkpoint": str(CHECKPOINT_PATH),
            "checkpoint_sha256": checkpoint_digest,
            "architecture": config.architectures[0],
            "model_type": config.model_type,
            "torch_dtype": str(config.torch_dtype),
            "hidden_size": config.hidden_size,
            "layer_count": config.num_hidden_layers,
            "attention_heads": config.num_attention_heads,
        },
        "tokenizer": {
            "revision": MODEL_REVISION,
            "class": type(tokenizer).__name__,
            "is_fast": tokenizer.is_fast,
            "tokenizer_files": tokenizer_hashes,
            "tokenizer_digest": tokenizer_digest,
            "config_files": config_hashes,
            "config_digest": config_digest,
            "bos_token": tokenizer.bos_token,
            "bos_token_id": tokenizer.bos_token_id,
            "eos_token": tokenizer.eos_token,
            "eos_token_id": tokenizer.eos_token_id,
            "pad_token": tokenizer.pad_token,
            "pad_token_id": tokenizer.pad_token_id,
            "add_special_tokens": True,
            "direct_encode_adds_bos": ids_with[:1] == [tokenizer.bos_token_id]
            and ids_without[:1] != [tokenizer.bos_token_id],
            "direct_ids_equal_with_and_without_special_tokens": ids_with == ids_without,
            "chat_template_applied_for_foundation_completion": False,
            "chat_template_sha256": hashlib.sha256(
                tokenizer.chat_template.encode("utf-8")
            ).hexdigest(),
            "chat_render_sample_sha256": hashlib.sha256(
                rendered_chat.encode("utf-8")
            ).hexdigest(),
            "chat_render_starts_with_bos": rendered_chat.startswith(
                tokenizer.bos_token
            ),
            "completion_answer_boundary": foundation_scoring_prompt(sample).decode(
                "utf-8"
            )[-9:],
        },
        "evaluator": {
            "id": FOUNDATION_EVALUATOR_ID,
            "version": FOUNDATION_EVALUATOR_VERSION,
            "ranking": "MEAN_TOKEN_LOG_PROBABILITY",
        },
        "sensor": _sensor_audit(),
        "modules": _module_audit(),
        "environment": {
            "packages": package_versions(),
            "cuda_build": torch.version.cuda,
            "cuda_available": torch.cuda.is_available(),
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "compute_capability": list(torch.cuda.get_device_capability(0))
            if torch.cuda.is_available()
            else None,
            "vram_total_bytes": total_bytes,
            "vram_free_bytes": free_bytes,
        },
        "path_safety": {"evidence_root": str(EVIDENCE_ROOT), "E_only": True},
    }
    _write_new_evidence(evidence_path, document)
    return document


def _training_record(tokenizer: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    record = _load_jsonl(DATASET_ROOT / "train.jsonl")[0]
    if record["semantic_family"] == "VISIBLE_PEER_COUNT":
        raise RuntimeError("sensor-owned target selected for neural smoke")
    prompt = foundation_scoring_prompt(record["input"]).decode("utf-8")
    prompt_ids = tokenizer.encode(prompt, add_special_tokens=True)
    answer_ids = tokenizer.encode(
        record["ground_truth"] + tokenizer.eos_token,
        add_special_tokens=False,
    )
    used = prompt_ids + answer_ids
    if len(used) > SEQUENCE_LENGTH:
        raise RuntimeError("selected formal training record exceeds sequence length")
    padding = SEQUENCE_LENGTH - len(used)
    batch = {
        "input_ids": used + [tokenizer.pad_token_id] * padding,
        "attention_mask": [1] * len(used) + [0] * padding,
        "labels": [-100] * len(prompt_ids) + answer_ids + [-100] * padding,
    }
    metadata = {
        "example_id": record["example_id"],
        "semantic_family": record["semantic_family"],
        "prompt_token_count": len(prompt_ids),
        "active_target_token_count": len(answer_ids),
        "sequence_length": SEQUENCE_LENGTH,
        "example_digest": record["exact_instance_digest"],
    }
    return batch, metadata


def classify_failure(error: BaseException) -> str:
    message = f"{type(error).__name__}: {error}".lower()
    if "out of memory" in message or "memory allocation" in message:
        return "CUDA_OOM"
    if "bfloat16" in message or "not implemented" in message or "unsupported" in message:
        return "BACKEND_UNSUPPORTED"
    return "OTHER"


def run_smoke(treatment: str, evidence_path: Path) -> dict[str, Any]:
    import psutil
    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    if treatment not in {"A_NF4_QLORA", "B_BF16_LORA"}:
        raise ValueError("unknown treatment")
    before_digest = sha256_file(CHECKPOINT_PATH)
    if before_digest != CHECKPOINT_SHA256:
        raise RuntimeError("canonical checkpoint digest mismatch before smoke")
    started = time.perf_counter()
    process = psutil.Process()
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    free_before, total_bytes = torch.cuda.mem_get_info(0)
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_ROOT, local_files_only=True, use_fast=True
    )
    raw_batch, record_metadata = _training_record(tokenizer)
    document: dict[str, Any] = {
        "evidence_schema": "alifelm-f0-foundation-ab-resource-smoke-v1",
        "experiment_id": EXPERIMENT_ID,
        "gate_id": GATE_ID,
        "treatment": treatment,
        "classification": ["NON_TRAINING", "FORWARD_BACKWARD_ONLY", "NO_ADAPTER_SAVED"],
        "git": git_state(),
        "dataset_id": DATASET_ID,
        "dataset_manifest_digest": DATASET_DIGEST,
        "base_revision": MODEL_REVISION,
        "checkpoint_sha256_before": before_digest,
        "seed": SEED,
        "record": record_metadata,
        "config": {
            "sequence_length": SEQUENCE_LENGTH,
            "microbatch": 1,
            "gradient_accumulation_for_formal_run": 8,
            "gradient_checkpointing": True,
            "optimizer_step_performed": False,
            "lora_r": 16,
            "lora_alpha": 32,
            "lora_dropout": 0.0,
            "lora_bias": "none",
            "target_modules": list(TARGET_MODULES),
        },
        "environment": {
            "packages": package_versions(),
            "cuda_build": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0),
            "compute_capability": list(torch.cuda.get_device_capability(0)),
            "vram_total_bytes": total_bytes,
            "vram_free_before_bytes": free_before,
        },
        "result": {"status": "NOT_RUN"},
    }
    model = None
    try:
        if treatment == "A_NF4_QLORA":
            quantization = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.float16,
            )
            model = AutoModelForCausalLM.from_pretrained(
                MODEL_ROOT,
                local_files_only=True,
                quantization_config=quantization,
                device_map={"": 0},
                low_cpu_mem_usage=True,
                dtype=torch.float16,
            )
            model = prepare_model_for_kbit_training(
                model, use_gradient_checkpointing=True
            )
            precision = {
                "base_quantization": "NF4_4BIT",
                "double_quantization": True,
                "compute_dtype": "FP16",
            }
        else:
            model = AutoModelForCausalLM.from_pretrained(
                MODEL_ROOT,
                local_files_only=True,
                device_map={"": 0},
                low_cpu_mem_usage=True,
                dtype=torch.bfloat16,
            )
            model.gradient_checkpointing_enable()
            model.enable_input_require_grads()
            precision = {
                "base_quantization": None,
                "base_dtype": "BF16",
                "compute_dtype": "BF16",
            }
        model.config.use_cache = False
        lora_config = LoraConfig(
            r=16,
            lora_alpha=32,
            lora_dropout=0.0,
            bias="none",
            target_modules=list(TARGET_MODULES),
            task_type="CAUSAL_LM",
            use_dora=False,
            use_rslora=False,
            init_lora_weights=True,
        )
        model = get_peft_model(model, lora_config)
        model.train()
        trainable = [
            (name, parameter)
            for name, parameter in model.named_parameters()
            if parameter.requires_grad
        ]
        wrong = [
            name
            for name, _ in trainable
            if ("lora_A" not in name and "lora_B" not in name)
            or ".self_attn." not in name
            or not any(f".{target}." in name for target in TARGET_MODULES)
        ]
        if wrong:
            raise RuntimeError(f"trainability firewall failed: {wrong}")
        if any(
            parameter.requires_grad
            for name, parameter in model.named_parameters()
            if "lora_" not in name
        ):
            raise RuntimeError("canonical base parameter remains trainable")
        batch = {
            key: torch.tensor([value], dtype=torch.long, device="cuda:0")
            for key, value in raw_batch.items()
        }
        step_started = time.perf_counter()
        output = model(**batch)
        loss = output.loss
        loss_value = float(loss.detach().float().cpu())
        if not math.isfinite(loss_value):
            raise RuntimeError("non-finite smoke loss")
        loss.backward()
        torch.cuda.synchronize()
        nonzero_gradients = sum(
            parameter.grad is not None
            and bool(torch.count_nonzero(parameter.grad).detach().cpu())
            for _, parameter in trainable
        )
        if not nonzero_gradients:
            raise RuntimeError("LoRA gradients remained zero")
        free_after, _ = torch.cuda.mem_get_info(0)
        document["precision"] = precision
        document["result"] = {
            "status": "PASS",
            "forward": True,
            "backward": True,
            "loss": loss_value,
            "loss_finite": True,
            "base_frozen": True,
            "only_lora_trainable": True,
            "trainable_parameter_count": sum(p.numel() for _, p in trainable),
            "trainable_tensor_count": len(trainable),
            "nonzero_gradient_tensor_count": nonzero_gradients,
            "peak_vram_allocated_bytes": torch.cuda.max_memory_allocated(),
            "peak_vram_reserved_bytes": torch.cuda.max_memory_reserved(),
            "vram_free_after_bytes": free_after,
            "process_ram_bytes": process.memory_info().rss,
            "forward_backward_seconds": time.perf_counter() - step_started,
            "total_seconds": time.perf_counter() - started,
        }
    except BaseException as error:
        document["result"] = {
            "status": "FAIL",
            "failure_class": classify_failure(error),
            "exception_type": type(error).__name__,
            "exception": str(error),
            "traceback": traceback.format_exc(),
            "peak_vram_allocated_bytes": torch.cuda.max_memory_allocated(),
            "peak_vram_reserved_bytes": torch.cuda.max_memory_reserved(),
            "process_ram_bytes": process.memory_info().rss,
            "total_seconds": time.perf_counter() - started,
        }
    finally:
        del model
        gc.collect()
        torch.cuda.empty_cache()
        after_digest = sha256_file(CHECKPOINT_PATH)
        document["checkpoint_sha256_after"] = after_digest
        document["checkpoint_unchanged"] = (
            before_digest == after_digest == CHECKPOINT_SHA256
        )
        document["adapter_saved"] = False
        _write_new_evidence(evidence_path, document)
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", action="store_true")
    parser.add_argument(
        "--smoke-treatment", choices=("A_NF4_QLORA", "B_BF16_LORA")
    )
    parser.add_argument("--evidence-root", type=Path, default=EVIDENCE_ROOT)
    args = parser.parse_args()
    root = args.evidence_root.resolve()
    if root.drive.upper() != "E:":
        raise SystemExit("evidence root must remain on E:")
    if args.audit == (args.smoke_treatment is not None):
        raise SystemExit("select exactly one of --audit or --smoke-treatment")
    if args.audit:
        result = run_audit(root / "environment-tokenizer-sensor.json")
    else:
        treatment = str(args.smoke_treatment)
        result = run_smoke(treatment, root / f"smoke-{treatment.lower()}.json")
    print(canonical_json(result["result"] if "result" in result else {"status": result["status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
