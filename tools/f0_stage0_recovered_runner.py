"""Prepare and run the recovered FA-v1 Foundation Stage 0 evaluation.

The runner is deliberately fail-closed.  It does not reconstruct a historical
adapter, change the evaluator, or copy the sealed F0_DATASET_V1 hidden union
into ordinary evidence.  On the A40 host, explicit paths to the recovered
artifacts are supplied and every recovered hash is checked before model load.

``--validate-only`` performs repository-side contract and dataset checks without
loading a model.  ``--execute`` is the only mode that loads the canonical BF16
base and the recovered PEFT adapter and evaluates the four frozen holdout
splits.  GPU execution is intentionally not attempted by this repository-side
validation pass.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable, Mapping


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from alifelm.domain import ArtifactId, ArtifactRef, OpportunityId  # noqa: E402
from alifelm.model.foundation_data import (  # noqa: E402
    SemanticFamily,
    canonical_digest,
    canonical_json,
)
from alifelm.model.foundation_eval import (  # noqa: E402
    FOUNDATION_EVALUATOR_ID,
    FOUNDATION_EVALUATOR_VERSION,
    FoundationSerializationEvaluation,
    evaluate_foundation_scalar_record,
    evaluate_foundation_serialization_text,
)
from alifelm.model.foundation_sensor import (  # noqa: E402
    SENSOR_NORMALIZER_ID,
    SENSOR_NORMALIZER_VERSION,
    deterministic_sensor_answer,
)
from alifelm.model.generation import (  # noqa: E402
    GenerationPolicy,
    GenerationRequest,
    generation_identity,
)
from alifelm.model.profile import ModelProfile  # noqa: E402
from alifelm.model.treatments import I0_STRICT_FREE_GENERATION  # noqa: E402
from alifelm.model.transformers_backend import GenerationError  # noqa: E402


RECOVERY_RECORD_ID = "F0_HISTORICAL_FA_V1_RECOVERY_V1"
STAGE0_RUN_ID = "F0_FOUNDATION_STAGE0_EVAL_V2_V1"
DATASET_ID = "F0_DATASET_V1"
DATASET_MANIFEST_DIGEST = (
    "418873b65e9a8903a595d6a8359ce778dd588b9cedb0e3c5ac54d178528e5e18"
)
BASE_REPO = "allenai/OLMo-2-0425-1B-Instruct"
BASE_REVISION = "48d788eca847d4d7548f375ad03d3c9312f6139e"
BASE_CHECKPOINT_SHA256 = (
    "36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f"
)
ADAPTER_SHA256 = "46917511362243be67e0783ddb7411a96f26613c1083bc4f95117d910d0998ec"
TRAINING_EVIDENCE_SHA256 = (
    "e4033811f2916f955896dc561355d5e69d86c7c85dc308cdc256f7d2e80720b4"
)
HIDDEN_EVIDENCE_SHA256 = (
    "7882747b8f9a04fe53d7b24d9e8dcd7e4a31d077916de61135d1043608a1d5c7"
)
HIDDEN_PREDICTIONS_SHA256 = (
    "91557a8d49da011f12367f374788487aa68a816afde1ee77a797080bb6919daa"
)
HISTORICAL_EXACT = {"numerator": 3524, "denominator": 3584}
HISTORICAL_NEURAL_DIAGNOSTIC = {"numerator": 3344, "denominator": 3360}

HIDDEN_SPLITS = (
    "STRUCTURAL_HOLDOUT",
    "TEMPLATE_HOLDOUT",
    "DOUBLE_HOLDOUT",
    "ADVERSARIAL_HOLDOUT",
)
ALL_SPLITS = (
    "TRAIN",
    "DEV",
    "STRUCTURAL_HOLDOUT",
    "TEMPLATE_HOLDOUT",
    "DOUBLE_HOLDOUT",
    "ADVERSARIAL_HOLDOUT",
)

TOKENIZER_REVISION = BASE_REVISION
TOKENIZER_EXPECTED = {
    "bos_token_id": 100257,
    "eos_token_id": 100257,
    "pad_token_id": 100277,
    "tokenizer_digest": "c448b9e69576a2af5fccdb905c4d6c9f6c0d06509b15d2459a3bc92bb33d42ff",
    "config_digest": "eeed26d20a24ad35479aa33b690b196096c5f98fee8bc43d816c3bd314987c38",
    "tokenizer_files": {
        "tokenizer.json": "73fd5254624f39a88e3faac6a8e11300fc3c735ed37880d4f4f08db898eaecca",
        "tokenizer_config.json": "50c412c57d832057a3d5db42064c741f751e570f7c8788f037bfb0d2dd6e5f49",
        "special_tokens_map.json": "78afb564e81264029b25f9caf24bda2521d5bdaeff5cd3fdbc01d3da2e8ce2f2",
        "vocab.json": "9e14712c91b37c7aab74b1306baa46ac342d620637a4b44523cdc3aec7d24195",
        "merges.txt": "b6fe424e334903f7fb84d3a106d9730455f4744b9fe3c21ee136d97a00e72502",
    },
    "config_files": {
        "config.json": "0d15ebb6cb8d998513b46ef337214176a6fd59fe5f16b30387c70d5f87795a9c",
        "generation_config.json": "437b97826bb4430c205083a0986fbe31f4959cffbe445e47fb7c5192fdcb8d58",
    },
}
NEURAL_FAMILIES = tuple(
    family.value
    for family in SemanticFamily
    if family is not SemanticFamily.VISIBLE_PEER_COUNT
)
SERIALIZATION_FAMILY = SemanticFamily.ALREADY_SELECTED_ACTION_SERIALIZATION.value
VISIBLE_COUNT_FAMILY = SemanticFamily.VISIBLE_PEER_COUNT.value
EXPECTED_TARGET_MODULES = ("q_proj", "k_proj", "v_proj", "o_proj")
FORBIDDEN_TARGET_MODULES = ("gate_proj", "up_proj", "down_proj", "lm_head")


class Stage0ValidationError(RuntimeError):
    """A required historical or evaluator invariant failed closed."""


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise Stage0ValidationError(f"required file is missing: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise Stage0ValidationError(f"required JSON artifact is missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise Stage0ValidationError(f"invalid JSON artifact: {path}") from error
    if not isinstance(value, dict):
        raise Stage0ValidationError(f"JSON artifact must be an object: {path}")
    return value


def _canonical_file_digest(paths: Mapping[str, Path]) -> tuple[str, dict[str, str]]:
    hashes = {name: sha256_file(path) for name, path in sorted(paths.items())}
    return canonical_digest(hashes), hashes


def _load_repository_dataset_manifest() -> dict[str, Any]:
    path = REPOSITORY_ROOT / "specs/experiments/F0-dataset-v1-manifest.yaml"
    manifest = _read_json(path)
    if manifest.get("dataset_id") != DATASET_ID:
        raise Stage0ValidationError("repository F0_DATASET_V1 manifest identity mismatch")
    if manifest.get("manifest_digest") != DATASET_MANIFEST_DIGEST:
        raise Stage0ValidationError("repository F0_DATASET_V1 manifest digest mismatch")
    return manifest


def verify_dataset(dataset_root: Path) -> dict[str, Any]:
    """Verify the exact V1 manifest and sealed hidden-union file hashes."""

    repository_manifest = _load_repository_dataset_manifest()
    artifact_manifest_path = dataset_root / "manifest.json"
    artifact_manifest = _read_json(artifact_manifest_path)
    if artifact_manifest.get("dataset_id") != DATASET_ID:
        raise Stage0ValidationError("artifact dataset identity mismatch")
    if artifact_manifest.get("manifest_digest") != DATASET_MANIFEST_DIGEST:
        raise Stage0ValidationError("artifact dataset manifest digest mismatch")
    manifest_core = dict(artifact_manifest)
    manifest_core.pop("manifest_digest", None)
    if canonical_digest(manifest_core) != DATASET_MANIFEST_DIGEST:
        raise Stage0ValidationError("artifact dataset canonical digest law failed")

    split_info: dict[str, Any] = {}
    hidden_records = 0
    for split in ALL_SPLITS:
        repo_split = repository_manifest["splits"].get(split)
        artifact_split = artifact_manifest["splits"].get(split)
        if not isinstance(repo_split, dict) or not isinstance(artifact_split, dict):
            raise Stage0ValidationError(f"missing {split} manifest entry")
        filename = str(repo_split["file"])
        path = dataset_root / filename
        actual_hash = sha256_file(path)
        expected_hash = str(repo_split["file_sha256"])
        expected_aggregate = str(repo_split["aggregate_split_digest"])
        expected_count = int(repo_split["count"])
        if actual_hash != expected_hash:
            raise Stage0ValidationError(f"{split} file SHA-256 mismatch")
        if artifact_split.get("file_sha256") != expected_hash:
            raise Stage0ValidationError(f"{split} manifest file SHA-256 mismatch")
        if artifact_split.get("aggregate_split_digest") != expected_aggregate:
            raise Stage0ValidationError(f"{split} aggregate digest mismatch")
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) != expected_count:
            raise Stage0ValidationError(f"{split} count mismatch")
        if split in HIDDEN_SPLITS:
            hidden_records += len(lines)
        split_info[split] = {
            "file": filename,
            "count": len(lines),
            "file_sha256": actual_hash,
            "aggregate_split_digest": expected_aggregate,
        }

    if hidden_records != HISTORICAL_EXACT["denominator"]:
        raise Stage0ValidationError("historical hidden union count mismatch")
    return {
        "dataset_id": DATASET_ID,
        "manifest_digest": DATASET_MANIFEST_DIGEST,
        "manifest_file": str(artifact_manifest_path),
        "manifest_file_sha256": sha256_file(artifact_manifest_path),
        "hidden_union_splits": list(HIDDEN_SPLITS),
        "hidden_union_count": hidden_records,
        "splits": split_info,
    }


def verify_recovered_files(
    *,
    base_checkpoint: Path,
    adapter_file: Path,
    training_evidence: Path,
    hidden_evidence: Path,
    hidden_predictions: Path,
) -> dict[str, Any]:
    """Verify every recovered artifact before any model/evaluator work."""

    if adapter_file.name != "adapter_model.safetensors":
        raise Stage0ValidationError(
            "recovered FA-v1 adapter must be adapter_model.safetensors"
        )
    expected = {
        "base_checkpoint": (base_checkpoint, BASE_CHECKPOINT_SHA256),
        "adapter": (adapter_file, ADAPTER_SHA256),
        "training_evidence": (training_evidence, TRAINING_EVIDENCE_SHA256),
        "hidden_evidence": (hidden_evidence, HIDDEN_EVIDENCE_SHA256),
        "hidden_predictions": (hidden_predictions, HIDDEN_PREDICTIONS_SHA256),
    }
    actual: dict[str, Any] = {}
    for label, (path, expected_hash) in expected.items():
        observed = sha256_file(path)
        if observed != expected_hash:
            raise Stage0ValidationError(
                f"{label} SHA-256 mismatch: expected {expected_hash}, got {observed}"
            )
        actual[label] = {"path": str(path), "sha256": observed}

    config_path = adapter_file.parent / "adapter_config.json"
    adapter_config = _read_json(config_path)
    if adapter_config.get("peft_type") != "LORA":
        raise Stage0ValidationError("recovered adapter is not a PEFT LoRA adapter")
    target_modules = adapter_config.get("target_modules")
    if not isinstance(target_modules, list) or set(target_modules) != set(EXPECTED_TARGET_MODULES):
        raise Stage0ValidationError("recovered adapter target modules do not match FA-v1")
    if set(target_modules) & set(FORBIDDEN_TARGET_MODULES):
        raise Stage0ValidationError("recovered adapter includes forbidden target modules")
    base_name = adapter_config.get("base_model_name_or_path")
    if not isinstance(base_name, str) or "OLMo-2-0425-1B-Instruct" not in base_name:
        raise Stage0ValidationError("recovered adapter base identity is not OLMo-2-0425-1B-Instruct")
    actual["adapter_config"] = {
        "path": str(config_path),
        "peft_type": adapter_config.get("peft_type"),
        "base_model_name_or_path": base_name,
        "r": adapter_config.get("r"),
        "lora_alpha": adapter_config.get("lora_alpha"),
        "target_modules": sorted(target_modules),
        "bias": adapter_config.get("bias"),
    }
    return actual


def audit_tokenizer(tokenizer_root: Path, tokenizer: Any | None = None) -> dict[str, Any]:
    """Verify pinned tokenizer bytes and direct-completion semantics."""

    tokenizer_files = {
        name: tokenizer_root / name for name in TOKENIZER_EXPECTED["tokenizer_files"]
    }
    config_files = {
        name: tokenizer_root / name for name in TOKENIZER_EXPECTED["config_files"]
    }
    tokenizer_digest, tokenizer_hashes = _canonical_file_digest(tokenizer_files)
    config_digest, config_hashes = _canonical_file_digest(config_files)
    if tokenizer_hashes != TOKENIZER_EXPECTED["tokenizer_files"]:
        raise Stage0ValidationError("tokenizer file digest mismatch")
    if config_hashes != TOKENIZER_EXPECTED["config_files"]:
        raise Stage0ValidationError("model config file digest mismatch")
    if tokenizer_digest != TOKENIZER_EXPECTED["tokenizer_digest"]:
        raise Stage0ValidationError("tokenizer aggregate digest mismatch")
    if config_digest != TOKENIZER_EXPECTED["config_digest"]:
        raise Stage0ValidationError("model config aggregate digest mismatch")

    result: dict[str, Any] = {
        "revision": TOKENIZER_REVISION,
        "tokenizer_digest": tokenizer_digest,
        "config_digest": config_digest,
        "bos_token_id": TOKENIZER_EXPECTED["bos_token_id"],
        "eos_token_id": TOKENIZER_EXPECTED["eos_token_id"],
        "pad_token_id": TOKENIZER_EXPECTED["pad_token_id"],
        "add_special_tokens": True,
        "chat_template_applied": False,
        "foundation_completion_path": "DIRECT_COMPLETION_NO_CHAT_TEMPLATE",
    }
    if tokenizer is None:
        return result
    if not bool(getattr(tokenizer, "is_fast", False)):
        raise Stage0ValidationError("slow tokenizer is not permitted for Stage 0")
    for name, expected_value in (
        ("bos_token_id", 100257),
        ("eos_token_id", 100257),
        ("pad_token_id", 100277),
    ):
        if getattr(tokenizer, name, None) != expected_value:
            raise Stage0ValidationError(f"tokenizer {name} mismatch")
    sample = "Canonical visible state follows.\nSelf handle: A1\n"
    without = tokenizer.encode(sample, add_special_tokens=False)
    with_special = tokenizer.encode(sample, add_special_tokens=True)
    if list(without) != list(with_special):
        raise Stage0ValidationError("direct completion tokenizer unexpectedly inserts special tokens")
    if list(without)[:1] == [100257]:
        raise Stage0ValidationError("direct completion tokenizer unexpectedly inserts BOS")
    result.update(
        {
            "class": type(tokenizer).__name__,
            "is_fast": True,
            "direct_ids_equal_with_and_without_special_tokens": True,
            "direct_encode_adds_bos": False,
            "chat_template_present_but_unused": bool(getattr(tokenizer, "chat_template", None)),
        }
    )
    return result


def verify_contract(dataset_root: Path) -> dict[str, Any]:
    """Repository-side validation that does not require recovered A40 files."""

    dataset = verify_dataset(dataset_root)
    recovery = _read_json(
        REPOSITORY_ROOT / "specs/experiments/F0-historical-fa-v1-recovery.yaml"
    )
    if recovery.get("record_id") != RECOVERY_RECORD_ID:
        raise Stage0ValidationError("recovery record identity mismatch")
    if recovery.get("status") != "RECOVERED_FORMAL_PROVENANCE":
        raise Stage0ValidationError("recovery record status mismatch")
    expected_record_bindings = {
        "base": {"checkpoint_sha256": BASE_CHECKPOINT_SHA256},
        "adapter": {"artifact_sha256": ADAPTER_SHA256},
        "training_evidence": {"artifact_sha256": TRAINING_EVIDENCE_SHA256},
        "historical_hidden_evaluation": {
            "evidence_sha256": HIDDEN_EVIDENCE_SHA256,
            "predictions_sha256": HIDDEN_PREDICTIONS_SHA256,
            "dataset_id": DATASET_ID,
            "dataset_manifest_digest": DATASET_MANIFEST_DIGEST,
            "union_count": HISTORICAL_EXACT["denominator"],
        },
    }
    for section, bindings in expected_record_bindings.items():
        section_document = recovery.get(section, {})
        if not isinstance(section_document, dict):
            raise Stage0ValidationError(f"recovery record {section} is not an object")
        for key, value in bindings.items():
            if section_document.get(key) != value:
                raise Stage0ValidationError(
                    f"recovery record {section}.{key} binding mismatch"
                )
    if recovery.get("historical_result") != {
        "numerator": 3524,
        "denominator": 3584,
        "exact": 0.9832589285714286,
        "status": "FAIL_SYNTHETIC_HIDDEN_ADMISSION",
        "evaluator": "GREEDY_DIRECT_ANSWER",
        "evaluation_precision": "BF16",
        "quantization": "NONE",
        "choices_in_prompt": False,
    }:
        raise Stage0ValidationError("historical fail result was altered")
    if recovery.get("historical_hidden_evaluation", {}).get("dataset_manifest_digest") != DATASET_MANIFEST_DIGEST:
        raise Stage0ValidationError("recovery record dataset binding mismatch")
    return {
        "stage0_run_id": STAGE0_RUN_ID,
        "dataset": dataset,
        "recovery_record": str(
            REPOSITORY_ROOT / "specs/experiments/F0-historical-fa-v1-recovery.yaml"
        ),
        "evaluator": {
            "id": FOUNDATION_EVALUATOR_ID,
            "version": FOUNDATION_EVALUATOR_VERSION,
            "candidate_scoring": "TEACHER_FORCED_MEAN_TOKEN_LOG_PROBABILITY",
            "serialization": "GENERATIVE_SCHEMA_AND_SEMANTIC_SEPARATION",
        },
        "sensor": {
            "id": SENSOR_NORMALIZER_ID,
            "version": SENSOR_NORMALIZER_VERSION,
            "visible_peer_count_excluded_from_neural_nga": True,
        },
        "neural_families": list(NEURAL_FAMILIES),
    }


def _git_state() -> dict[str, Any]:
    def run(*args: str) -> str:
        return subprocess.check_output(
            ("git", *args), cwd=REPOSITORY_ROOT, text=True
        ).strip()

    return {
        "commit": run("rev-parse", "HEAD"),
        "status": run("status", "--porcelain"),
    }


def _load_runtime(
    *,
    base_model: Path,
    adapter_file: Path | None,
) -> tuple[Any, Any, ModelProfile, dict[str, Any]]:
    """Load canonical BF16 OLMo and optionally the exact recovered adapter."""

    try:
        import torch
        import transformers
        from peft import PeftModel
    except ImportError as error:
        raise Stage0ValidationError("Stage 0 execution requires torch, transformers, and peft") from error

    if not torch.cuda.is_available():
        raise Stage0ValidationError("Stage 0 execution requires the A40 CUDA runtime")
    tokenizer = transformers.AutoTokenizer.from_pretrained(
        base_model,
        revision=TOKENIZER_REVISION,
        local_files_only=True,
        use_fast=True,
    )
    tokenizer_audit = audit_tokenizer(base_model, tokenizer)
    model = transformers.AutoModelForCausalLM.from_pretrained(
        base_model,
        revision=BASE_REVISION,
        local_files_only=True,
        dtype=torch.bfloat16,
    )
    if getattr(model.config, "model_type", None) != "olmo2":
        raise Stage0ValidationError("loaded base is not the canonical OLMo-2 architecture")
    if adapter_file is not None:
        model = PeftModel.from_pretrained(
            model,
            adapter_file.parent,
            is_trainable=False,
            local_files_only=True,
        )
    model = model.to("cuda")
    model.eval()
    adapter_ref = None
    if adapter_file is not None:
        adapter_ref = ArtifactRef(
            artifact_id=ArtifactId("FA-V1-ADAPTER"), digest=ADAPTER_SHA256
        )
    profile = ModelProfile(
        profile_id="F0Stage0FAv1BF16",
        profile_version="1.0.0",
        model_identifier=str(base_model),
        model_revision=BASE_REVISION,
        model_digest=BASE_CHECKPOINT_SHA256,
        tokenizer_identifier=str(base_model),
        tokenizer_revision=TOKENIZER_REVISION,
        tokenizer_digest=tokenizer_audit["tokenizer_digest"],
        model_class=type(model).__name__,
        generation_policy_id="F0Stage0Serialization",
        device="cuda",
        dtype="bfloat16",
        adapter_ref=adapter_ref,
        trust_remote_code=False,
        add_special_tokens=True,
    )
    return (
        TransformersRuntimeShim(profile, tokenizer, model, torch),
        tokenizer,
        profile,
        tokenizer_audit,
    )


class TransformersRuntimeShim:
    """Small protocol-compatible holder avoiding eager optional imports."""

    def __init__(self, profile: ModelProfile, tokenizer: Any, model: Any, torch_module: Any):
        from alifelm.model.transformers_backend import TransformersModelRuntime

        self.runtime = TransformersModelRuntime.from_components(
            profile, tokenizer=tokenizer, model=model, torch_module=torch_module
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self.runtime, name)


def _generation_request(profile: ModelProfile, record: Mapping[str, Any], index: int) -> GenerationRequest:
    rendered = str(record["input"]).encode("utf-8")
    rendered_hash = hashlib.sha256(rendered).hexdigest()
    context_hash = canonical_digest(
        {"dataset_id": DATASET_ID, "example_id": str(record["example_id"])}
    )
    policy = GenerationPolicy(
        policy_id="F0Stage0Serialization",
        version="1.0.0",
        max_new_tokens=128,
        do_sample=False,
        temperature=None,
        top_p=None,
        top_k=1,
        repetition_penalty=1.0,
        seed_id="F0Stage0Seed",
        stop_policy_id=None,
    )
    generation_id = generation_identity(
        context_hash=context_hash,
        profile=profile,
        policy=policy,
        generation_seed_id="F0Stage0Seed",
        generation_seed=0,
        rendered_input_hash=rendered_hash,
        interface_treatment_id=I0_STRICT_FREE_GENERATION.treatment_id,
        interface_treatment_version=I0_STRICT_FREE_GENERATION.version,
        interface_treatment_digest=I0_STRICT_FREE_GENERATION.digest,
        constraint_policy_id=None,
    )
    return GenerationRequest(
        opportunity_id=OpportunityId(f"F0STAGE0-{index:06d}"),
        generation_id=generation_id,
        context_pack_id=f"F0STAGE0-{index:06d}",
        context_hash=context_hash,
        rendered_input_hash=rendered_hash,
        rendered_input=rendered,
        interface_treatment_id=I0_STRICT_FREE_GENERATION.treatment_id,
        interface_treatment_version=I0_STRICT_FREE_GENERATION.version,
        interface_treatment_digest=I0_STRICT_FREE_GENERATION.digest,
        constraint_policy_id=None,
        model_profile=profile,
        generation_policy=policy,
        generation_seed_id="F0Stage0Seed",
        generation_seed=0,
        generator=None,
        stop_hooks=(),
        prefix_allowed_tokens_fn=None,
    )


def _iter_hidden_records(dataset_root: Path) -> Iterable[dict[str, Any]]:
    for split in HIDDEN_SPLITS:
        path = dataset_root / f"{split.lower()}.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise Stage0ValidationError("hidden record is not an object")
            yield value


def _run_condition(
    *,
    condition: str,
    dataset_root: Path,
    runtime: Any,
    profile: ModelProfile,
    sensor_active: bool,
) -> dict[str, Any]:
    family_counts: Counter[str] = Counter()
    family_correct: Counter[str] = Counter()
    sensor_total = sensor_correct = sensor_model_correct = 0
    serialization_total = serialization_schema_valid = serialization_semantic_correct = 0
    candidate_ties = tokenization_boundary_failures = evaluator_failures = malformed = 0

    for index, record in enumerate(_iter_hidden_records(dataset_root)):
        family = str(record["semantic_family"])
        if family == VISIBLE_COUNT_FAMILY:
            sensor_total += 1
            if sensor_active:
                answer = deterministic_sensor_answer(record)
                if answer is None:
                    raise Stage0ValidationError("sensor-active condition lacked deterministic count answer")
                sensor_correct += int(answer == str(record["ground_truth"]))
                continue
            try:
                result = evaluate_foundation_scalar_record(runtime, record)
                sensor_model_correct += int(result.exact_match)
                candidate_ties += int(
                    sum(score.mean_log_probability == result.scores[0].mean_log_probability for score in result.scores)
                    > 1
                )
            except GenerationError as error:
                evaluator_failures += 1
                tokenization_boundary_failures += int("prefix-stable" in str(error))
            continue

        family_counts[family] += 1
        if family == SERIALIZATION_FAMILY:
            serialization_total += 1
            try:
                generated = runtime.generate(_generation_request(profile, record, index))
                result = evaluate_foundation_serialization_text(record, generated.raw_text)
                if not isinstance(result, FoundationSerializationEvaluation):
                    raise Stage0ValidationError("serialization evaluator returned wrong result type")
                serialization_schema_valid += int(result.schema_valid)
                serialization_semantic_correct += int(result.semantic_correct)
                family_correct[family] += int(result.semantic_correct)
                malformed += int(not result.schema_valid)
            except GenerationError as error:
                evaluator_failures += 1
                tokenization_boundary_failures += int("prefix-stable" in str(error))
            continue

        try:
            result = evaluate_foundation_scalar_record(runtime, record)
            family_correct[family] += int(result.exact_match)
            candidate_ties += int(
                sum(score.mean_log_probability == result.scores[0].mean_log_probability for score in result.scores)
                > 1
            )
        except GenerationError as error:
            evaluator_failures += 1
            tokenization_boundary_failures += int("prefix-stable" in str(error))

    if set(family_counts) != set(NEURAL_FAMILIES):
        missing = sorted(set(NEURAL_FAMILIES) - set(family_counts))
        raise Stage0ValidationError(f"hidden union lacks neural families: {missing}")
    family_accuracy = {
        family: family_correct[family] / family_counts[family]
        for family in NEURAL_FAMILIES
    }
    macro = sum(family_accuracy.values()) / len(family_accuracy)
    neural_total = sum(family_counts.values())
    neural_correct = sum(family_correct.values())
    sensor_result = None if not sensor_active else sensor_correct / sensor_total
    return {
        "condition": condition,
        "primary_metric": "15_FAMILY_MACRO_NGA_EXCLUDING_VISIBLE_PEER_COUNT",
        "macro_nga": macro,
        "micro_neural_accuracy": neural_correct / neural_total,
        "neural_correct": neural_correct,
        "neural_total": neural_total,
        "family_accuracy": family_accuracy,
        "worst_family": min(family_accuracy, key=family_accuracy.get),
        "worst_family_accuracy": min(family_accuracy.values()),
        "serialization": {
            "schema_validity": (
                serialization_schema_valid / serialization_total
                if serialization_total
                else None
            ),
            "semantic_correctness": (
                serialization_semantic_correct / serialization_total
                if serialization_total
                else None
            ),
            "count": serialization_total,
        },
        "sensor": {
            "active": sensor_active,
            "deterministic_correctness": sensor_result,
            "count": sensor_total,
            "model_diagnostic_correctness": (
                sensor_model_correct / sensor_total if not sensor_active and sensor_total else None
            ),
        },
        "candidate_ties": candidate_ties,
        "tokenization_boundary_failures": tokenization_boundary_failures,
        "evaluator_failures": evaluator_failures,
        "malformed": malformed,
    }


def execute_stage0(
    *,
    dataset_root: Path,
    base_model: Path,
    adapter_file: Path,
    training_evidence: Path,
    hidden_evidence: Path,
    hidden_predictions: Path,
    output_root: Path,
    condition: str,
) -> dict[str, Any]:
    """Execute S0-A/B/C on the A40 host after all preflight checks."""

    contract = verify_contract(dataset_root)
    recovered = verify_recovered_files(
        base_checkpoint=base_model / "model.safetensors",
        adapter_file=adapter_file,
        training_evidence=training_evidence,
        hidden_evidence=hidden_evidence,
        hidden_predictions=hidden_predictions,
    )
    tokenizer_static = audit_tokenizer(base_model)
    selected = ("S0-A", "S0-B", "S0-C") if condition == "all" else (condition,)
    results: dict[str, Any] = {}
    for current in selected:
        runtime, _, profile, tokenizer_runtime = _load_runtime(
            base_model=base_model,
            adapter_file=None if current == "S0-A" else adapter_file,
        )
        if any(
            tokenizer_runtime.get(key) != value
            for key, value in tokenizer_static.items()
        ):
            raise Stage0ValidationError("runtime tokenizer audit differs from static tokenizer audit")
        results[current] = _run_condition(
            condition=current,
            dataset_root=dataset_root,
            runtime=runtime,
            profile=profile,
            sensor_active=current == "S0-C",
        )
        if sha256_file(base_model / "model.safetensors") != BASE_CHECKPOINT_SHA256:
            raise Stage0ValidationError("canonical base changed during Stage 0 evaluation")

    output_root = output_root.resolve()
    if output_root.drive.upper() != "E:":
        raise Stage0ValidationError("Stage 0 evidence must be stored on E:")
    output_root.mkdir(parents=True, exist_ok=True)
    core = {
        "run_id": STAGE0_RUN_ID,
        "status": "COMPLETE",
        "git": _git_state(),
        "dataset": contract["dataset"],
        "recovered_artifacts": recovered,
        "base_model": {
            "repo": BASE_REPO,
            "revision": BASE_REVISION,
            "checkpoint_sha256": BASE_CHECKPOINT_SHA256,
            "evaluation_precision": "BF16",
            "quantized_evaluation": False,
        },
        "tokenizer": tokenizer_static,
        "evaluator": contract["evaluator"],
        "sensor": contract["sensor"],
        "historical_comparison": {
            "old_exact": HISTORICAL_EXACT,
            "old_exact_rate": HISTORICAL_EXACT["numerator"] / HISTORICAL_EXACT["denominator"],
            "old_neural_diagnostic": HISTORICAL_NEURAL_DIAGNOSTIC,
            "old_neural_diagnostic_rate": HISTORICAL_NEURAL_DIAGNOSTIC["numerator"] / HISTORICAL_NEURAL_DIAGNOSTIC["denominator"],
        },
        "conditions": results,
        "hidden_cases_copied": False,
    }
    manifest = dict(core)
    manifest["manifest_digest"] = canonical_digest(core)
    payload = (canonical_json(manifest) + "\n").encode("utf-8")
    manifest_path = output_root / "manifest.json"
    if manifest_path.exists() and manifest_path.read_bytes() != payload:
        raise Stage0ValidationError("existing Stage 0 manifest differs; refusing overwrite")
    if not manifest_path.exists():
        manifest_path.write_bytes(payload)
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--base-model", type=Path)
    parser.add_argument("--adapter-file", type=Path)
    parser.add_argument("--training-evidence", type=Path)
    parser.add_argument("--hidden-evidence", type=Path)
    parser.add_argument("--hidden-predictions", type=Path)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("E:/WORLD/AI_CACHE/evidence/F0_FOUNDATION_STAGE0_EVAL_V2_V1"),
    )
    parser.add_argument("--condition", choices=("S0-A", "S0-B", "S0-C", "all"), default="all")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--execute", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.validate_only == args.execute:
        raise SystemExit("choose exactly one of --validate-only or --execute")
    dataset_root = args.dataset_root.resolve()
    if args.validate_only:
        print(canonical_json(verify_contract(dataset_root)))
        return 0
    required = {
        "--base-model": args.base_model,
        "--adapter-file": args.adapter_file,
        "--training-evidence": args.training_evidence,
        "--hidden-evidence": args.hidden_evidence,
        "--hidden-predictions": args.hidden_predictions,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise SystemExit("--execute requires " + ", ".join(missing))
    manifest = execute_stage0(
        dataset_root=dataset_root,
        base_model=args.base_model.resolve(),
        adapter_file=args.adapter_file.resolve(),
        training_evidence=args.training_evidence.resolve(),
        hidden_evidence=args.hidden_evidence.resolve(),
        hidden_predictions=args.hidden_predictions.resolve(),
        output_root=args.output_root,
        condition=args.condition,
    )
    print(canonical_json({"run_id": STAGE0_RUN_ID, "manifest_digest": manifest["manifest_digest"], "status": manifest["status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
