#!/usr/bin/env python3
"""Paired F0 Stage-1 trainer for the controlled NF4-vs-BF16 experiment.

Implements the frozen ``F0_FOUNDATION_AB_V1`` training contract: identical
dataset, ordering, masking, optimizer, LoRA scope, and seeds for both
treatments; only base-weight precision/quantization differs. The runner is
fail-closed: it verifies the frozen dataset, sensor boundary, tokenizer,
target-module firewall, checkpoint digest, and seed derivation before any
optimizer step, and refuses to save an adapter after a non-finite loss.

``--validate-only`` performs every repository-side check that does not
require loading the base model (dataset/sensor audits, spec identity, seed
derivation, ordering determinism). ``--execute`` performs one full
(treatment, seed) training run and then evaluates the saved adapter on the
allowed dev/holdout splits with Evaluator v2 teacher-forced ranking.
Serialization, retention, and neutrality audits belong to the separate
post-training evaluation stage and are not claimed here.

This tool requires a CUDA resource envelope admitted by
``F0_FOUNDATION_AB_RESOURCE_GATE_V1``; it performs no asymmetric fallback.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from tools import f0_foundation_ab_gate as gate  # noqa: E402
from alifelm.model.foundation_data import (  # noqa: E402
    SemanticFamily,
    canonical_digest,
    canonical_json,
)
from alifelm.model.foundation_eval import (  # noqa: E402
    FOUNDATION_EVALUATOR_ID,
    FOUNDATION_EVALUATOR_VERSION,
    SCALAR_FAMILIES,
    evaluate_foundation_scalar_record,
    foundation_scoring_prompt,
)
from alifelm.model.profile import ModelProfile  # noqa: E402
from alifelm.model.transformers_backend import TransformersModelRuntime  # noqa: E402

EXPERIMENT_ID = gate.EXPERIMENT_ID
SPEC_PATH = REPOSITORY_ROOT / "specs/experiments/F0-foundation-ab-v1.yaml"
TREATMENTS = ("A_NF4_QLORA", "B_BF16_LORA")
TREATMENT_IDS = {
    "A_NF4_QLORA": "F0_AB_A_NF4_QLORA",
    "B_BF16_LORA": "F0_AB_B_BF16_LORA",
}
SEED_NAMESPACE = "F0_FOUNDATION_AB_V1|35120260830|SEED"
SEEDS = (292255390, 1166218024, 698950225)
EPOCHS = 1
MICROBATCH = 1
GRADIENT_ACCUMULATION = 8
EFFECTIVE_BATCH = 8
LEARNING_RATE = 2e-4
WEIGHT_DECAY = 0.0
SEQUENCE_LENGTH = gate.SEQUENCE_LENGTH
TARGET_MODULES = gate.TARGET_MODULES
FORBIDDEN_TARGET_MODULES = gate.FORBIDDEN_TARGET_MODULES
LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.0
EVAL_SPLITS = (
    "dev.jsonl",
    "structural_holdout.jsonl",
    "template_holdout.jsonl",
    "double_holdout.jsonl",
    "adversarial_holdout.jsonl",
)
SELECTION_SPLIT = "dev.jsonl"
EVIDENCE_ROOT = Path("E:/WORLD/AI_CACHE/evidence/f0-foundation-ab-train-v1")


class TrainingAbort(RuntimeError):
    """Fail-closed training contract violation."""


def derive_seed(replicate_index: int) -> int:
    """First 31 bits of SHA-256(namespace|replicate_index)."""

    digest = hashlib.sha256(
        f"{SEED_NAMESPACE}|{replicate_index}".encode("utf-8")
    ).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def _load_spec() -> dict[str, Any]:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def _checkpoint_keys() -> tuple[str, ...]:
    """Enumerate tensor keys without requiring the safetensors package."""

    try:
        from safetensors import safe_open

        with safe_open(gate.CHECKPOINT_PATH, framework="pt", device="cpu") as stream:
            return tuple(stream.keys())
    except ImportError:
        import struct

        with gate.CHECKPOINT_PATH.open("rb") as stream:
            (header_length,) = struct.unpack("<Q", stream.read(8))
            header = json.loads(stream.read(header_length))
        return tuple(key for key in header if key != "__metadata__")


def _module_audit() -> dict[str, Any]:
    keys = _checkpoint_keys()
    matched = {
        suffix: sorted(
            key for key in keys if key.endswith(f".self_attn.{suffix}.weight")
        )
        for suffix in TARGET_MODULES
    }
    counts = {suffix: len(values) for suffix, values in matched.items()}
    if counts != {suffix: 16 for suffix in TARGET_MODULES}:
        raise TrainingAbort(f"unexpected OLMo attention module tree: {counts}")
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


def _spec_audit() -> dict[str, Any]:
    spec = _load_spec()
    if spec["experiment_id"] != EXPERIMENT_ID:
        raise TrainingAbort("A/B spec experiment_id mismatch")
    common = spec["common_training"]
    expectations = {
        "epochs": EPOCHS,
        "sequence_length": SEQUENCE_LENGTH,
        "microbatch": MICROBATCH,
        "gradient_accumulation": GRADIENT_ACCUMULATION,
        "effective_batch": EFFECTIVE_BATCH,
        "optimizer": "torch.optim.AdamW",
        "learning_rate": LEARNING_RATE,
        "weight_decay": WEIGHT_DECAY,
        "warmup_steps": 0,
        "scheduler": "CONSTANT",
        "gradient_clipping": None,
        "gradient_checkpointing": True,
    }
    for key, expected in expectations.items():
        if common.get(key) != expected:
            raise TrainingAbort(f"A/B spec common_training.{key} drifted")
    lora = common["lora"]
    if (
        lora["r"] != LORA_R
        or lora["alpha"] != LORA_ALPHA
        or lora["dropout"] != LORA_DROPOUT
        or lora["bias"] != "none"
        or lora["target_modules"] != list(TARGET_MODULES)
        or lora["forbidden_target_modules"] != list(FORBIDDEN_TARGET_MODULES)
        or lora["implementation"] != "PEFT_VANILLA_LORA"
    ):
        raise TrainingAbort("A/B spec LoRA scope drifted")
    if tuple(common["seeds"]) != SEEDS:
        raise TrainingAbort("A/B spec seed list drifted")
    if set(spec["treatments"]) != set(TREATMENTS):
        raise TrainingAbort("A/B spec treatment set drifted")
    for treatment, body in spec["treatments"].items():
        if body["treatment_id"] != TREATMENT_IDS[treatment]:
            raise TrainingAbort("A/B spec treatment identity drifted")
    if spec["dataset"]["manifest_digest"] != gate.DATASET_DIGEST:
        raise TrainingAbort("A/B spec dataset digest drifted")
    return {
        "experiment_id": spec["experiment_id"],
        "spec_file_sha256": gate.sha256_file(SPEC_PATH),
        "training_authorized": spec["training_authorized"],
        "authorization_rule": spec["authorization_rule"],
    }


def _seed_audit() -> dict[str, Any]:
    derived = [derive_seed(index) for index in range(len(SEEDS))]
    if derived != list(SEEDS):
        raise TrainingAbort("pinned seeds do not match the derivation law")
    return {"namespace": SEED_NAMESPACE, "seeds": derived}


def _ordering_audit() -> dict[str, Any]:
    import torch

    def perm(seed: int, epoch: int, count: int) -> list[int]:
        generator = torch.Generator()
        generator.manual_seed(seed + epoch)
        return torch.randperm(count, generator=generator).tolist()

    probe = perm(SEEDS[0], 0, 4096)
    if perm(SEEDS[0], 0, 4096) != probe:
        raise TrainingAbort("CPU-generator ordering is not deterministic")
    if perm(SEEDS[1], 0, 4096) == probe:
        raise TrainingAbort("paired seeds collide on identical order")
    if perm(SEEDS[0], 1, 4096) == probe:
        raise TrainingAbort("epoch reseed did not change order")
    return {
        "algorithm": "torch.randperm with a CPU torch.Generator",
        "reseed_each_epoch": "seed + epoch_index",
        "probe_first16": probe[:16],
    }


def _render_batch(record: dict[str, Any], tokenizer: Any) -> dict[str, Any]:
    """Render one training record per the frozen masking law."""

    if record["semantic_family"] == "VISIBLE_PEER_COUNT":
        raise TrainingAbort("sensor-owned target selected for neural training")
    prompt = foundation_scoring_prompt(record["input"]).decode("utf-8")
    prompt_ids = tokenizer.encode(prompt, add_special_tokens=True)
    answer_ids = tokenizer.encode(
        record["ground_truth"] + tokenizer.eos_token,
        add_special_tokens=False,
    )
    used = prompt_ids + answer_ids
    if len(used) > SEQUENCE_LENGTH:
        raise TrainingAbort(
            f"record {record['example_id']} exceeds sequence length: {len(used)}"
        )
    padding = SEQUENCE_LENGTH - len(used)
    return {
        "input_ids": used + [tokenizer.pad_token_id] * padding,
        "attention_mask": [1] * len(used) + [0] * padding,
        "labels": [-100] * len(prompt_ids) + answer_ids + [-100] * padding,
    }


def _build_model(treatment: str, torch: Any, transformers: Any, peft: Any):
    """Load the canonical base under one treatment precision; wrap in LoRA."""

    if treatment == "A_NF4_QLORA":
        quantization = transformers.BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.float16,
        )
        model = transformers.AutoModelForCausalLM.from_pretrained(
            gate.MODEL_ROOT,
            local_files_only=True,
            quantization_config=quantization,
            device_map={"": 0},
            low_cpu_mem_usage=True,
            dtype=torch.float16,
        )
        model = peft.prepare_model_for_kbit_training(
            model, use_gradient_checkpointing=True
        )
        precision = {
            "base_quantization": "NF4_4BIT",
            "double_quantization": True,
            "compute_dtype": "FP16",
        }
    else:
        model = transformers.AutoModelForCausalLM.from_pretrained(
            gate.MODEL_ROOT,
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
    lora_config = peft.LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        bias="none",
        target_modules=list(TARGET_MODULES),
        task_type="CAUSAL_LM",
        use_dora=False,
        use_rslora=False,
        init_lora_weights=True,
    )
    model = peft.get_peft_model(model, lora_config)
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
        raise TrainingAbort(f"trainability firewall failed: {wrong}")
    if any(
        parameter.requires_grad
        for name, parameter in model.named_parameters()
        if "lora_" not in name
    ):
        raise TrainingAbort("canonical base parameter remains trainable")
    return model, precision, trainable


def _evaluate_splits(
    runtime: TransformersModelRuntime,
    splits: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for split_name, records in splits.items():
        scalar_records = [
            record
            for record in records
            if SemanticFamily(str(record["semantic_family"])) in SCALAR_FAMILIES
        ]
        serialization_records = len(records) - len(scalar_records)
        correct = 0
        per_family: dict[str, list[int]] = {}
        for record in scalar_records:
            result = evaluate_foundation_scalar_record(runtime, record)
            correct += int(result.exact_match)
            per_family.setdefault(result.semantic_family, []).append(
                int(result.exact_match)
            )
        family_metrics = {
            family: {
                "correct": sum(values),
                "total": len(values),
                "accuracy": sum(values) / len(values),
            }
            for family, values in sorted(per_family.items())
        }
        metrics[split_name] = {
            "scalar_records": len(scalar_records),
            "serialization_records_deferred": serialization_records,
            "correct": correct,
            "nga": correct / len(scalar_records) if scalar_records else None,
            "families": family_metrics,
            "worst_family": min(
                family_metrics.items(), key=lambda item: item[1]["accuracy"]
            )[0]
            if family_metrics
            else None,
        }
    return metrics


def validate_only() -> dict[str, Any]:
    """Run every check that does not load the base model."""

    checks = {
        "spec": _spec_audit(),
        "seeds": _seed_audit(),
        "dataset": gate._dataset_audit(),
        "sensor": gate._sensor_audit(),
        "modules": _module_audit(),
        "ordering": _ordering_audit(),
    }
    document = {
        "status": "VALIDATE_ONLY_PASS",
        "experiment_id": EXPERIMENT_ID,
        "checks": {key: True for key in checks},
        "detail": checks,
        "git": gate.git_state(),
        "environment": gate.package_versions(),
        "training_authorized_note": checks["spec"]["training_authorized"] is False
        and "resource gate required before execution",
    }
    return document


def execute(
    treatment: str,
    seed_index: int,
    output_root: Path,
    *,
    evaluate: bool = True,
) -> dict[str, Any]:
    """Run one (treatment, seed) training + scalar-evaluation pass."""

    if treatment not in TREATMENTS:
        raise TrainingAbort(f"unknown treatment: {treatment}")
    if seed_index not in range(len(SEEDS)):
        raise TrainingAbort(f"unknown seed index: {seed_index}")
    seed = SEEDS[seed_index]
    run_id = f"{TREATMENT_IDS[treatment]}_SEED{seed_index}"
    run_dir = output_root / run_id
    if run_dir.exists():
        raise TrainingAbort(f"run directory already exists: {run_dir}")
    try:
        import torch
        import transformers
        import peft
    except ImportError as error:
        raise TrainingAbort(
            "model stack unavailable; execute requires the admitted "
            "transformers/peft/bitsandbytes environment"
        ) from error
    if not torch.cuda.is_available():
        raise TrainingAbort(
            "CUDA resource envelope required; the frozen contract admits no "
            "asymmetric or CPU fallback"
        )
    run_dir.mkdir(parents=True)

    spec = _spec_audit()
    dataset = gate._dataset_audit()
    sensor = gate._sensor_audit()
    modules = _module_audit()
    train_records = gate._load_jsonl(gate.DATASET_ROOT / "train.jsonl")
    eval_records = {
        name: gate._load_jsonl(gate.DATASET_ROOT / name) for name in EVAL_SPLITS
    }
    checkpoint_before = gate.sha256_file(gate.CHECKPOINT_PATH)
    if checkpoint_before != gate.CHECKPOINT_SHA256:
        raise TrainingAbort("canonical checkpoint digest mismatch before training")

    started_wall = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    started = time.perf_counter()
    tokenizer = transformers.AutoTokenizer.from_pretrained(
        gate.MODEL_ROOT, local_files_only=True, use_fast=True
    )
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    model, precision, trainable = _build_model(treatment, torch, transformers, peft)
    optimizer = torch.optim.AdamW(
        (parameter for _, parameter in trainable),
        lr=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
    )

    generator = torch.Generator()
    generator.manual_seed(seed + 0)
    order = torch.randperm(len(train_records), generator=generator).tolist()
    steps_per_epoch = len(train_records) // (
        MICROBATCH * GRADIENT_ACCUMULATION
    )
    if len(train_records) % (MICROBATCH * GRADIENT_ACCUMULATION):
        raise TrainingAbort("dataset size is not divisible by the effective batch")

    log_path = run_dir / "train_log.jsonl"
    model.train()
    trajectory: list[dict[str, Any]] = []
    optimizer_steps = 0
    exit_status = "TRAIN_COMPLETE"
    failure: str | None = None
    with log_path.open("x", encoding="utf-8") as log:
        try:
            for epoch in range(EPOCHS):
                if epoch:
                    generator.manual_seed(seed + epoch)
                    order = torch.randperm(
                        len(train_records), generator=generator
                    ).tolist()
                for step in range(steps_per_epoch):
                    micro_losses: list[float] = []
                    for offset in range(GRADIENT_ACCUMULATION):
                        record = train_records[
                            order[step * GRADIENT_ACCUMULATION + offset]
                        ]
                        batch = _render_batch(record, tokenizer)
                        tensor_batch = {
                            key: torch.tensor([value], dtype=torch.long, device="cuda:0")
                            for key, value in batch.items()
                        }
                        output = model(**tensor_batch)
                        loss_value = float(output.loss.detach().float().cpu())
                        if not math.isfinite(loss_value):
                            raise TrainingAbort(
                                f"non-finite loss at step {step} microbatch {offset}"
                            )
                        micro_losses.append(loss_value)
                        (output.loss / GRADIENT_ACCUMULATION).backward()
                    optimizer.step()
                    optimizer.zero_grad(set_to_none=True)
                    optimizer_steps += 1
                    entry = {
                        "epoch": epoch,
                        "step": step,
                        "seed": seed,
                        "example_ids": [
                            train_records[order[step * GRADIENT_ACCUMULATION + j]][
                                "example_id"
                            ]
                            for j in range(GRADIENT_ACCUMULATION)
                        ],
                        "microbatch_losses": micro_losses,
                        "mean_loss": sum(micro_losses) / len(micro_losses),
                    }
                    trajectory.append(entry)
                    log.write(canonical_json(entry) + "\n")
        except TrainingAbort as error:
            exit_status = "TRAIN_ABORT"
            failure = f"{type(error).__name__}: {error}"
    train_seconds = time.perf_counter() - started

    adapter_hashes: dict[str, str] = {}
    adapter_sha256: str | None = None
    if exit_status == "TRAIN_COMPLETE":
        adapter_dir = run_dir / "adapter"
        model.save_pretrained(adapter_dir)
        adapter_hashes = {
            path.name: gate.sha256_file(path)
            for path in sorted(adapter_dir.iterdir())
            if path.is_file()
        }
        weights = adapter_dir / "adapter_model.safetensors"
        adapter_sha256 = adapter_hashes.get(weights.name)

    eval_metrics: dict[str, Any] | None = None
    if evaluate and exit_status == "TRAIN_COMPLETE":
        model.eval()
        profile = ModelProfile(
            profile_id="f0-ab-train-eval",
            profile_version="1.0.0",
            model_identifier=str(gate.MODEL_ROOT),
            model_revision=gate.MODEL_REVISION,
            model_digest=gate.CHECKPOINT_SHA256,
            tokenizer_identifier=str(gate.MODEL_ROOT),
            tokenizer_revision=gate.MODEL_REVISION,
            tokenizer_digest=None,
            model_class=type(model).__name__,
            generation_policy_id="f0-ab-eval-teacher-forced",
            device="cuda:0",
            dtype="float16" if treatment == "A_NF4_QLORA" else "bfloat16",
            adapter_ref=None,
            trust_remote_code=False,
            add_special_tokens=True,
        )
        runtime = TransformersModelRuntime(
            profile, tokenizer=tokenizer, model=model, torch_module=torch
        )
        eval_metrics = _evaluate_splits(runtime, eval_records)
        (run_dir / "metrics_dev.json").write_text(
            canonical_json(
                {"evaluator": f"{FOUNDATION_EVALUATOR_ID}@{FOUNDATION_EVALUATOR_VERSION}",
                 "metrics": eval_metrics[SELECTION_SPLIT]}
            )
            + "\n",
            encoding="utf-8",
        )
        (run_dir / "metrics_holdouts.json").write_text(
            canonical_json(
                {name: eval_metrics[name] for name in eval_metrics if name != SELECTION_SPLIT}
            )
            + "\n",
            encoding="utf-8",
        )

    checkpoint_after = gate.sha256_file(gate.CHECKPOINT_PATH)
    if checkpoint_after != gate.CHECKPOINT_SHA256:
        raise TrainingAbort("canonical checkpoint digest changed during training")

    manifest = {
        "manifest_schema": "alifelm-f0-foundation-ab-train-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": run_id,
        "treatment": treatment,
        "treatment_id": TREATMENT_IDS[treatment],
        "status": exit_status,
        "failure": failure,
        "git": gate.git_state(),
        "dataset": dataset,
        "spec": spec,
        "base": {
            "repo": gate.MODEL_REPO,
            "revision": gate.MODEL_REVISION,
            "checkpoint_sha256": checkpoint_after,
        },
        "seed": {"index": seed_index, "value": seed, "derivation": _seed_audit()},
        "training_config": {
            "epochs": EPOCHS,
            "sequence_length": SEQUENCE_LENGTH,
            "microbatch": MICROBATCH,
            "gradient_accumulation": GRADIENT_ACCUMULATION,
            "effective_batch": EFFECTIVE_BATCH,
            "optimizer": "torch.optim.AdamW",
            "learning_rate": LEARNING_RATE,
            "weight_decay": WEIGHT_DECAY,
            "warmup_steps": 0,
            "scheduler": "CONSTANT",
            "gradient_clipping": None,
            "gradient_checkpointing": True,
            "shuffle": {
                "algorithm": "torch.randperm with a CPU torch.Generator",
                "reseed_each_epoch": "seed + epoch_index",
                "paired_order_identical_between_treatments": True,
            },
            "loss": {
                "renderer": "record.input.rstrip() + newline + Answer: + newline",
                "prompt_tokens": "MASKED_MINUS_100",
                "ground_truth_tokens": "ACTIVE",
                "eos_token": "ACTIVE",
                "chain_of_thought": False,
            },
            "lora": {
                "implementation": "PEFT_VANILLA_LORA",
                "r": LORA_R,
                "alpha": LORA_ALPHA,
                "dropout": LORA_DROPOUT,
                "bias": "none",
                "target_modules": list(TARGET_MODULES),
            },
            "precision": precision,
        },
        "modules": {
            "matched_counts": modules["matched_counts"],
            "trainable_parameters": sum(
                int(parameter.numel()) for _, parameter in trainable
            ),
        },
        "evaluator": {
            "id": FOUNDATION_EVALUATOR_ID,
            "version": FOUNDATION_EVALUATOR_VERSION,
            "splits_evaluated": list(eval_metrics) if eval_metrics else [],
            "deferred": [
                "serialization_generation",
                "retention_sentinel",
                "neutrality_suite_v2",
            ],
        },
        "sensor": sensor,
        "environment": {
            "packages": gate.package_versions(),
            "cuda_build": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0)
            if torch.cuda.is_available()
            else None,
        },
        "timestamps": {"start_utc": started_wall, "train_seconds": train_seconds},
        "optimizer_steps": optimizer_steps,
        "loss_trajectory": {
            "count": len(trajectory),
            "first_step_mean": trajectory[0]["mean_loss"] if trajectory else None,
            "final_step_mean": trajectory[-1]["mean_loss"] if trajectory else None,
            "min_step_mean": min(
                (item["mean_loss"] for item in trajectory), default=None
            ),
            "max_step_mean": max(
                (item["mean_loss"] for item in trajectory), default=None
            ),
            "log_file": "train_log.jsonl",
            "log_file_sha256": gate.sha256_file(log_path),
        },
        "adapter": {
            "saved": exit_status == "TRAIN_COMPLETE",
            "directory": "adapter/",
            "file_hashes": adapter_hashes,
            "adapter_model_safetensors_sha256": adapter_sha256,
        },
        "evaluation_metrics": eval_metrics,
        "checkpoint_unchanged": checkpoint_before == checkpoint_after,
    }
    manifest["manifest_digest"] = canonical_digest(
        {key: value for key, value in manifest.items() if key != "manifest_digest"}
    )
    gate._write_new_evidence(run_dir / "manifest.json", manifest)
    if exit_status == "TRAIN_COMPLETE":
        evidence_dir = EVIDENCE_ROOT / run_id
        gate._write_new_evidence(
            evidence_dir / "manifest.json",
            {"manifest": manifest["manifest_digest"], "run_dir": str(run_dir)},
        )
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--treatment", choices=TREATMENTS)
    parser.add_argument("--seed-index", type=int, choices=range(len(SEEDS)))
    parser.add_argument("--output-root", type=Path)
    parser.add_argument(
        "--no-evaluate",
        action="store_true",
        help="skip post-training scalar evaluation",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.validate_only:
            document = validate_only()
            print(canonical_json(document))
            return 0
        if args.treatment is None or args.seed_index is None or args.output_root is None:
            raise TrainingAbort(
                "--execute requires --treatment, --seed-index, --output-root"
            )
        manifest = execute(
            args.treatment,
            args.seed_index,
            args.output_root,
            evaluate=not args.no_evaluate,
        )
        print(
            canonical_json(
                {
                    "status": manifest["status"],
                    "run_id": manifest["run_id"],
                    "manifest_digest": manifest["manifest_digest"],
                    "adapter_sha256": manifest["adapter"][
                        "adapter_model_safetensors_sha256"
                    ],
                }
            )
        )
        return 0 if manifest["status"] == "TRAIN_COMPLETE" else 2
    except (TrainingAbort, OSError, RuntimeError, TypeError, ValueError) as error:
        print(
            canonical_json(
                {
                    "status": "BLOCKED",
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
