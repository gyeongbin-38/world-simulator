#!/usr/bin/env python3
"""Run the bounded F0 FA-v0 local QLoRA feasibility smoke."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import traceback
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from alifelm.model.foundation_data import (  # noqa: E402
    SemanticFamily,
    canonical_digest,
    canonical_json,
    generate_example,
    load_reserved_evaluation_fingerprints,
)


EXECUTION_ID = "F0_FA_V0_QLORA_SMOKE_V1"
MODEL_PATH = Path("E:/WORLD/AI_MODELS/OLMo-2-0425-1B-Instruct-BF16")
CHECKPOINT_PATH = MODEL_PATH / "model.safetensors"
EVIDENCE_PATH = Path(
    "E:/WORLD/AI_CACHE/evidence/f0-qlora-smoke/F0_FA_V0_QLORA_SMOKE_V1.json"
)
EXPECTED_CHECKPOINT_SHA256 = (
    "36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f"
)
ROOT_SEED = 350
SMOKE_COUNT = 80
SEQUENCE_LADDER = (256, 192, 128)
TARGET_MODULES = ("q_proj", "k_proj", "v_proj", "o_proj")

GROUNDING_FAMILIES = (
    SemanticFamily.SELF_IDENTITY,
    SemanticFamily.PEER_IDENTITY,
    SemanticFamily.PEER_HANDLE_LOOKUP,
    SemanticFamily.VISIBLE_PEER_COUNT,
    SemanticFamily.MESSAGE_SENDER,
    SemanticFamily.MESSAGE_RECEIVER,
    SemanticFamily.MESSAGE_DIRECTION,
    SemanticFamily.PROPOSAL_ID,
    SemanticFamily.PROPOSAL_OWNER,
    SemanticFamily.PROPOSAL_DIRECTION,
    SemanticFamily.PROPOSAL_TARGET,
    SemanticFamily.INCOMING_PROPOSAL_IDENTIFICATION,
    SemanticFamily.OUTGOING_PROPOSAL_IDENTIFICATION,
    SemanticFamily.VISIBLE_VS_NOT_VISIBLE_FACT,
    SemanticFamily.OPAQUE_HANDLE_COPY,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def smoke_seed(index: int) -> int:
    material = f"F0_SMOKE_DATA_V1|{ROOT_SEED}|{index}".encode("ascii")
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")


def compact_prompt(example: Any) -> str:
    state = example.state
    question = example.rendered_input.split("\nQuestion:\n", 1)[1]
    return (
        "S(self):"
        + state.self_handle
        + "\nP(peer):"
        + ",".join(state.peer_handles)
        + "\nM(id:s>r):"
        + ";".join(
            f"{record.message_id}:{record.sender}>{record.receiver}"
            for record in state.messages
        )
        + "\nR(id:o>t):"
        + ";".join(
            f"{record.proposal_id}:{record.owner}>{record.target}"
            for record in state.proposals
        )
        + "\nQ:"
        + question
        + "\nC:"
        + canonical_json(list(example.choices))
    )


def build_smoke_data(tokenizer: Any) -> tuple[list[dict[str, Any]], str]:
    reservations = load_reserved_evaluation_fingerprints()
    records: list[dict[str, Any]] = []
    for index in range(SMOKE_COUNT):
        seed = smoke_seed(index)
        family = GROUNDING_FAMILIES[index % len(GROUNDING_FAMILIES)]
        example = generate_example(seed, family)
        if example.structural_fingerprint in reservations:
            raise RuntimeError("reserved evaluation collision escaped generator")
        prompt = compact_prompt(example)
        prompt_ids = tokenizer(prompt, add_special_tokens=True)["input_ids"]
        answer_ids = tokenizer(
            example.answer + tokenizer.eos_token,
            add_special_tokens=False,
        )["input_ids"]
        if len(prompt_ids) + len(answer_ids) > min(SEQUENCE_LADDER):
            raise RuntimeError(
                f"smoke example {index} exceeds sequence ladder minimum: "
                f"{len(prompt_ids) + len(answer_ids)}"
            )
        records.append(
            {
                "index": index,
                "seed": seed,
                "family": family.value,
                "fingerprint": example.structural_fingerprint,
                "prompt": prompt,
                "prompt_ids": prompt_ids,
                "answer": example.answer,
                "answer_ids": answer_ids,
            }
        )
    digest_payload = [
        {
            "index": record["index"],
            "seed": record["seed"],
            "family": record["family"],
            "fingerprint": record["fingerprint"],
            "prompt_sha256": hashlib.sha256(
                record["prompt"].encode("utf-8")
            ).hexdigest(),
            "answer_sha256": hashlib.sha256(
                record["answer"].encode("utf-8")
            ).hexdigest(),
        }
        for record in records
    ]
    return records, canonical_digest(digest_payload)


def padded_batch(record: dict[str, Any], sequence_length: int, pad_token_id: int) -> dict[str, Any]:
    import torch

    prompt_ids = list(record["prompt_ids"])
    answer_ids = list(record["answer_ids"])
    used = prompt_ids + answer_ids
    padding = sequence_length - len(used)
    if padding < 0:
        raise RuntimeError("prevalidated smoke record exceeds selected sequence length")
    input_ids = used + [pad_token_id] * padding
    attention_mask = [1] * len(used) + [0] * padding
    labels = [-100] * len(prompt_ids) + answer_ids + [-100] * padding
    return {
        "input_ids": torch.tensor([input_ids], dtype=torch.long, device="cuda"),
        "attention_mask": torch.tensor(
            [attention_mask], dtype=torch.long, device="cuda"
        ),
        "labels": torch.tensor([labels], dtype=torch.long, device="cuda"),
    }


def runtime_versions() -> dict[str, str | None]:
    import importlib.metadata as metadata

    result: dict[str, str | None] = {}
    for distribution in (
        "torch",
        "transformers",
        "peft",
        "bitsandbytes",
        "accelerate",
        "trl",
    ):
        try:
            result[distribution] = metadata.version(distribution)
        except metadata.PackageNotFoundError:
            result[distribution] = None
    return result


def classify_exception(exc: BaseException) -> str:
    message = f"{type(exc).__name__}: {exc}".lower()
    if "out of memory" in message or "cuda error: memory allocation" in message:
        return "CUDA_OOM"
    backend_markers = (
        "bitsandbytes",
        "4-bit",
        "4bit",
        "nf4",
        "quant_state",
        "no kernel image",
        "not compiled with cuda",
    )
    if any(marker in message for marker in backend_markers):
        return "BACKEND"
    return "OTHER"


def run_attempt(
    sequence_length: int,
    smoke_records: list[dict[str, Any]],
) -> dict[str, Any]:
    import psutil
    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig

    attempt_started = time.perf_counter()
    process = psutil.Process()
    peak_ram = process.memory_info().rss
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.float16,
    )
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH,
        local_files_only=True,
        quantization_config=quantization_config,
        device_map={"": 0},
        low_cpu_mem_usage=True,
        dtype=torch.float16,
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(
        model,
        use_gradient_checkpointing=True,
    )
    lora_config = LoraConfig(
        r=8,
        lora_alpha=16,
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

    trainable = [(name, parameter) for name, parameter in model.named_parameters() if parameter.requires_grad]
    unexpected_trainable = [
        name
        for name, _ in trainable
        if "lora_A" not in name and "lora_B" not in name
    ]
    wrong_scope = [
        name
        for name, _ in trainable
        if ".self_attn." not in name
        or not any(f".{target}." in name for target in TARGET_MODULES)
    ]
    if unexpected_trainable or wrong_scope:
        raise RuntimeError(
            f"trainability firewall failed: unexpected={unexpected_trainable}, scope={wrong_scope}"
        )
    if any(
        parameter.requires_grad
        for name, parameter in model.named_parameters()
        if "lora_" not in name
    ):
        raise RuntimeError("a canonical base parameter remains trainable")
    initial_lora = {
        name: parameter.detach().cpu().clone() for name, parameter in trainable
    }
    trainable_parameters = sum(parameter.numel() for _, parameter in trainable)
    canonical_base_parameters = 1_484_916_736
    total_parameters = canonical_base_parameters + trainable_parameters

    optimizer = torch.optim.AdamW(
        (parameter for _, parameter in trainable),
        lr=2e-4,
        weight_decay=0.0,
    )
    optimizer.zero_grad(set_to_none=True)
    initial_loss: float | None = None
    final_loss: float | None = None
    optimizer_step_times: list[float] = []
    microstep = 0
    for optimizer_step in range(10):
        step_started = time.perf_counter()
        for _ in range(8):
            record = smoke_records[microstep]
            batch = padded_batch(record, sequence_length, model.config.pad_token_id)
            outputs = model(**batch)
            scalar_loss = outputs.loss
            value = float(scalar_loss.detach().float().cpu())
            if initial_loss is None:
                initial_loss = value
            final_loss = value
            if not math.isfinite(value):
                raise RuntimeError(f"non-finite loss at microstep {microstep}: {value}")
            (scalar_loss / 8).backward()
            microstep += 1
            peak_ram = max(peak_ram, process.memory_info().rss)
        optimizer.step()
        optimizer.zero_grad(set_to_none=True)
        optimizer_step_times.append(time.perf_counter() - step_started)

    changed_names = [
        name
        for name, parameter in trainable
        if not torch.equal(initial_lora[name], parameter.detach().cpu())
    ]
    if not changed_names:
        raise RuntimeError("LoRA parameters did not change")
    loss_finite = initial_loss is not None and final_loss is not None and all(
        math.isfinite(value) for value in (initial_loss, final_loss)
    )
    result = {
        "sequence_length": sequence_length,
        "forward": True,
        "backward": True,
        "optimizer_steps": 10,
        "microsteps": microstep,
        "initial_loss": initial_loss,
        "final_loss": final_loss,
        "loss_finite": loss_finite,
        "peak_vram_bytes": torch.cuda.max_memory_allocated(),
        "peak_reserved_vram_bytes": torch.cuda.max_memory_reserved(),
        "peak_process_ram_bytes": peak_ram,
        "mean_optimizer_step_seconds": sum(optimizer_step_times)
        / len(optimizer_step_times),
        "optimizer_step_seconds": optimizer_step_times,
        "total_attempt_seconds": time.perf_counter() - attempt_started,
        "canonical_base_parameter_count": canonical_base_parameters,
        "trainable_parameter_count": trainable_parameters,
        "total_parameter_count_with_adapter": total_parameters,
        "trainable_percent_of_base_plus_adapter": 100
        * trainable_parameters
        / total_parameters,
        "base_frozen": True,
        "trainable_parameter_names": [name for name, _ in trainable],
        "lora_changed": True,
        "changed_lora_parameter_count": len(changed_names),
    }
    del optimizer, model, trainable, initial_lora
    gc.collect()
    torch.cuda.empty_cache()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE_PATH)
    args = parser.parse_args()

    required_environment = {
        "HF_HOME": "E:/WORLD/AI_CACHE/huggingface",
        "HUGGINGFACE_HUB_CACHE": "E:/WORLD/AI_CACHE/huggingface/hub",
        "TRANSFORMERS_CACHE": "E:/WORLD/AI_CACHE/huggingface/transformers",
        "TORCH_HOME": "E:/WORLD/AI_CACHE/torch",
        "TEMP": "E:/WORLD/AI_CACHE/tmp",
        "TMP": "E:/WORLD/AI_CACHE/tmp",
        "XDG_CACHE_HOME": "E:/WORLD/AI_CACHE/xdg",
        "CUDA_CACHE_PATH": "E:/WORLD/AI_CACHE/cuda",
        "TORCH_EXTENSIONS_DIR": "E:/WORLD/AI_CACHE/torch_extensions",
    }
    normalized_environment = {
        key: os.environ.get(key, "").replace("\\", "/")
        for key in required_environment
    }
    if normalized_environment != required_environment:
        raise SystemExit(
            "path safety precondition failed: "
            + canonical_json(normalized_environment)
        )
    if args.evidence.drive.upper() != "E:":
        raise SystemExit("evidence path must remain on E:")

    import torch
    from transformers import AutoTokenizer

    if not torch.cuda.is_available():
        raise SystemExit("PyTorch CUDA is unavailable")
    checkpoint_before = sha256_file(CHECKPOINT_PATH)
    if checkpoint_before != EXPECTED_CHECKPOINT_SHA256:
        raise SystemExit("canonical checkpoint digest mismatch before smoke")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, local_files_only=True)
    smoke_records, smoke_digest = build_smoke_data(tokenizer)
    reservations = load_reserved_evaluation_fingerprints()
    collisions = sorted(
        {record["fingerprint"] for record in smoke_records} & reservations
    )
    evidence: dict[str, Any] = {
        "evidence_schema": "alifelm-f0-qlora-smoke-evidence-v1",
        "execution_id": EXECUTION_ID,
        "classification": ["NON_ADMITTED", "SMOKE_ONLY", "DISPOSABLE"],
        "path_safety": {
            "required_environment": required_environment,
            "all_declared_writes_on_E": True,
            "C_project_model_cache_writes": 0,
        },
        "runtime": {
            "versions": runtime_versions(),
            "cuda_available": torch.cuda.is_available(),
            "cuda_build": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0),
            "compute_capability": list(torch.cuda.get_device_capability(0)),
        },
        "provenance": {
            "model_path": str(MODEL_PATH),
            "checkpoint_sha256_before": checkpoint_before,
            "checkpoint_sha256_expected": EXPECTED_CHECKPOINT_SHA256,
        },
        "smoke_data": {
            "count": len(smoke_records),
            "root_seed": ROOT_SEED,
            "digest": smoke_digest,
            "families": sorted({record["family"] for record in smoke_records}),
            "reserved_collision": collisions,
            "policy_examples": 0,
            "formal_F0_dataset": False,
        },
        "config": {
            "sequence_attempts": list(SEQUENCE_LADDER),
            "microbatch": 1,
            "gradient_accumulation": 8,
            "gradient_checkpointing": True,
            "optimizer": "torch.optim.AdamW",
            "quantization": "4_BIT_NF4",
            "double_quant": True,
            "compute_dtype": "FP16",
            "lora_r": 8,
            "lora_alpha": 16,
            "lora_dropout": 0,
            "lora_bias": "none",
            "target_modules": list(TARGET_MODULES),
        },
        "attempts": [],
        "result": {"status": "NOT_RUN"},
    }
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    exit_code = 1
    try:
        for sequence_length in SEQUENCE_LADDER:
            try:
                attempt = run_attempt(sequence_length, smoke_records)
                attempt["status"] = "PASS"
                evidence["attempts"].append(attempt)
                evidence["result"] = {
                    "sequence_selected": sequence_length,
                    **attempt,
                    "status": "PASS_LOCAL",
                }
                exit_code = 0
                break
            except BaseException as exc:  # evidence must survive backend/CUDA failures
                classification = classify_exception(exc)
                evidence["attempts"].append(
                    {
                        "sequence_length": sequence_length,
                        "status": "FAIL",
                        "failure_class": classification,
                        "exception_type": type(exc).__name__,
                        "exception": str(exc),
                        "traceback": traceback.format_exc(),
                    }
                )
                gc.collect()
                torch.cuda.empty_cache()
                if classification == "CUDA_OOM":
                    if sequence_length == min(SEQUENCE_LADDER):
                        evidence["result"] = {"status": "MEMORY_BLOCKED"}
                    continue
                evidence["result"] = {
                    "status": "BACKEND_BLOCKED"
                    if classification == "BACKEND"
                    else "OTHER_BLOCKED"
                }
                break
    finally:
        checkpoint_after = sha256_file(CHECKPOINT_PATH)
        evidence["provenance"]["checkpoint_sha256_after"] = checkpoint_after
        evidence["provenance"]["checkpoint_unchanged"] = (
            checkpoint_before == checkpoint_after == EXPECTED_CHECKPOINT_SHA256
        )
        args.evidence.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(canonical_json(evidence["result"]))
        print(str(args.evidence))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
