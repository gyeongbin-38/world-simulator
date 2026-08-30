from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from alifelm.model import PeftTransformersLoader
from alifelm.model.world_v0_smoke import (
    DeploymentExpectations,
    DeploymentPaths,
    MODEL_CONFIG_AGGREGATE_SHA256,
    MODEL_CONFIG_FILE_HASHES,
    SmokePreflightError,
    TOKENIZER_DIGEST,
    TOKENIZER_FILE_HASHES,
    build_model_profile,
    canonical_digest,
    ensure_execute_environment,
    verify_static_deployment,
)

RECOVERED_LOCAL_BASE = "/workspace/alifelm/models/OLMo-2-0425-1B-Instruct"


def test_recovered_tokenizer_hash_map_and_aggregate_are_frozen():
    assert TOKENIZER_FILE_HASHES == {
        "tokenizer.json": "73fd5254624f39a88e3faac6a8e11300fc3c735ed37880d4f4f08db898eaecca",
        "tokenizer_config.json": "50c412c57d832057a3d5db42064c741f751e570f7c8788f037bfb0d2dd6e5f49",
        "special_tokens_map.json": "78afb564e81264029b25f9caf24bda2521d5bdaeff5cd3fdbc01d3da2e8ce2f2",
        "vocab.json": "9e14712c91b37c7aab74b1306baa46ac342d620637a4b44523cdc3aec7d24195",
        "merges.txt": "b6fe424e334903f7fb84d3a106d9730455f4744b9fe3c21ee136d97a00e72502",
    }
    assert canonical_digest(TOKENIZER_FILE_HASHES) == (
        "c448b9e69576a2af5fccdb905c4d6c9f6c0d06509b15d2459a3bc92bb33d42ff"
    )
    assert canonical_digest(MODEL_CONFIG_FILE_HASHES) == MODEL_CONFIG_AGGREGATE_SHA256


def _write_deployment(
    tmp_path: Path,
    *,
    base_model_name_or_path: str = RECOVERED_LOCAL_BASE,
) -> tuple[DeploymentPaths, DeploymentExpectations]:
    base = tmp_path / "base"
    adapter = tmp_path / "adapter"
    output = tmp_path / "evidence"
    base.mkdir()
    adapter.mkdir()
    (base / "model.safetensors").write_bytes(b"base")
    (adapter / "adapter_model.safetensors").write_bytes(b"adapter")
    adapter_config = {
        "peft_type": "LORA",
        "base_model_name_or_path": base_model_name_or_path,
        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
    }
    (adapter / "adapter_config.json").write_text(
        json.dumps(adapter_config, separators=(",", ":")), encoding="utf-8"
    )
    tokenizer_config = {
        "added_tokens_decoder": {
            "100257": {"content": "<|endoftext|>"},
            "100277": {"content": "<|pad|>"},
        },
        "bos_token": "<|endoftext|>",
        "eos_token": "<|endoftext|>",
        "pad_token": "<|pad|>",
    }
    files = {
        "tokenizer.json": b"tokenizer",
        "tokenizer_config.json": json.dumps(tokenizer_config, separators=(",", ":")).encode(),
        "special_tokens_map.json": b"{}",
        "vocab.json": b"vocab",
        "merges.txt": b"merges",
        "config.json": b"config",
        "generation_config.json": b"generation",
    }
    for name, content in files.items():
        (base / name).write_bytes(content)
    digest = lambda content: hashlib.sha256(content).hexdigest()
    tokenizer_hashes = {
        name: digest(files[name]) for name in TOKENIZER_FILE_HASHES
    }
    config_hashes = {
        name: digest(files[name]) for name in ("config.json", "generation_config.json")
    }
    canonical = lambda value: hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    expectations = DeploymentExpectations(
        base_checkpoint_sha256=digest(b"base"),
        adapter_sha256=digest(b"adapter"),
        adapter_config_sha256=digest(
            json.dumps(adapter_config, separators=(",", ":")).encode()
        ),
        tokenizer_digest=canonical(tokenizer_hashes),
        tokenizer_file_hashes=tokenizer_hashes,
        config_file_hashes=config_hashes,
        config_aggregate_sha256=canonical(config_hashes),
    )
    return DeploymentPaths(base, adapter, output), expectations


def test_validate_static_deployment_never_loads_model(tmp_path, monkeypatch):
    paths, expectations = _write_deployment(tmp_path)
    calls = []
    monkeypatch.setattr(
        PeftTransformersLoader,
        "__call__",
        lambda self, profile: calls.append(profile),
    )
    result = verify_static_deployment(paths, expectations=expectations, expected_git_commit="abc")
    assert result["status"] == "STATIC_PREFLIGHT_OK"
    assert calls == []


def test_recovered_local_base_path_is_metadata_only(tmp_path):
    paths, expectations = _write_deployment(tmp_path)
    result = verify_static_deployment(
        paths,
        expectations=expectations,
        expected_git_commit="abc",
    )
    assert result["adapter_base_model_name_or_path"] == RECOVERED_LOCAL_BASE


def test_accepted_hub_base_identifier_passes(tmp_path):
    paths, expectations = _write_deployment(
        tmp_path,
        base_model_name_or_path="allenai/OLMo-2-0425-1B-Instruct",
    )
    result = verify_static_deployment(paths, expectations=expectations, expected_git_commit="abc")
    assert result["adapter_base_model_name_or_path"] == "allenai/OLMo-2-0425-1B-Instruct"


def test_unrelated_hub_base_identifier_fails_closed(tmp_path):
    paths, expectations = _write_deployment(
        tmp_path,
        base_model_name_or_path="other-org/other-model",
    )
    with pytest.raises(SmokePreflightError, match="source identifier"):
        verify_static_deployment(paths, expectations=expectations)


def test_bad_static_hash_fails_before_any_loader(tmp_path):
    paths, expectations = _write_deployment(tmp_path)
    bad = DeploymentExpectations(
        base_checkpoint_sha256="0" * 64,
        adapter_sha256=expectations.adapter_sha256,
        adapter_config_sha256=expectations.adapter_config_sha256,
        tokenizer_digest=expectations.tokenizer_digest,
        tokenizer_file_hashes=expectations.tokenizer_file_hashes,
        config_file_hashes=expectations.config_file_hashes,
        config_aggregate_sha256=expectations.config_aggregate_sha256,
    )
    with pytest.raises(SmokePreflightError, match="base checkpoint"):
        verify_static_deployment(paths, expectations=bad)


@pytest.mark.parametrize(
    ("field", "message"),
    (("adapter_sha256", "adapter SHA"), ("tokenizer_digest", "tokenizer aggregate"), ("adapter_config_sha256", "adapter config")),
)
def test_static_identity_failures_happen_before_loader(tmp_path, field, message):
    paths, expectations = _write_deployment(tmp_path)
    values = {
        "base_checkpoint_sha256": expectations.base_checkpoint_sha256,
        "adapter_sha256": expectations.adapter_sha256,
        "adapter_config_sha256": expectations.adapter_config_sha256,
        "tokenizer_digest": expectations.tokenizer_digest,
        "tokenizer_file_hashes": expectations.tokenizer_file_hashes,
        "config_file_hashes": expectations.config_file_hashes,
        "config_aggregate_sha256": expectations.config_aggregate_sha256,
    }
    values[field] = "0" * 64
    bad = DeploymentExpectations(**values)
    with pytest.raises(SmokePreflightError, match=message):
        verify_static_deployment(paths, expectations=bad)


def test_target_module_mismatch_still_fails_after_config_hash_update(tmp_path):
    paths, expectations = _write_deployment(tmp_path)
    config = json.loads(paths.adapter_config.read_text(encoding="utf-8"))
    config["target_modules"] = ["q_proj", "k_proj", "v_proj", "gate_proj"]
    paths.adapter_config.write_text(json.dumps(config, separators=(",", ":")), encoding="utf-8")
    updated = replace(
        expectations,
        adapter_config_sha256=hashlib.sha256(paths.adapter_config.read_bytes()).hexdigest(),
    )
    with pytest.raises(SmokePreflightError, match="target modules"):
        verify_static_deployment(paths, expectations=updated)


def test_output_manifest_mismatch_refuses_overwrite(tmp_path):
    paths, expectations = _write_deployment(tmp_path)
    paths.output_root.mkdir()
    (paths.output_root / "manifest.json").write_text(
        json.dumps({"manifest_identity_digest": "wrong"}), encoding="utf-8"
    )
    with pytest.raises(SmokePreflightError, match="mismatching identity"):
        verify_static_deployment(paths, expectations=expectations, expected_git_commit="abc")


def test_manifest_digest_is_reproducible(tmp_path):
    paths, expectations = _write_deployment(tmp_path)
    first = verify_static_deployment(paths, expectations=expectations, expected_git_commit="abc")
    second = verify_static_deployment(paths, expectations=expectations, expected_git_commit="abc")
    assert first["planned_manifest_identity_digest"] == second["planned_manifest_identity_digest"]


def test_windows_style_absolute_deployment_paths_are_accepted():
    paths = DeploymentPaths(
        Path(r"E:\WORLD\models\olmo"),
        Path(r"E:\WORLD\artifacts\fa"),
        Path(r"E:\WORLD\evidence\smoke"),
    )
    assert paths.output_root == Path(r"E:\WORLD\evidence\smoke")


def test_execute_requires_cuda_without_loading_model():
    fake_torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
    with pytest.raises(SmokePreflightError, match="CUDA"):
        ensure_execute_environment(torch_module=fake_torch)


def test_peft_loader_loads_base_tokenizer_and_adapter_once(tmp_path):
    base = tmp_path / "base"
    adapter = tmp_path / "adapter"
    base.mkdir()
    adapter.mkdir()
    profile = build_model_profile(base, device="cpu")
    counts = {"tokenizer": 0, "base": 0, "adapter": 0, "to": 0}

    class Parameter:
        requires_grad = False

        def requires_grad_(self, value):
            self.requires_grad = value
            return self

    class Model:
        training = True

        def __init__(self):
            self.parameters_seen = [Parameter()]

        def to(self, device):
            counts["to"] += 1
            return self

        def eval(self):
            self.training = False
            return self

        def parameters(self):
            return iter(self.parameters_seen)

        def generate(self, **kwargs):
            return [[1]]

    class AutoTokenizer:
        @staticmethod
        def from_pretrained(*args, **kwargs):
            counts["tokenizer"] += 1
            return SimpleNamespace(
                bos_token_id=100257,
                eos_token_id=100257,
                pad_token_id=100277,
                is_fast=True,
                encode=lambda text, add_special_tokens=False: [1, 2],
            )

    class AutoModel:
        @staticmethod
        def from_pretrained(*args, **kwargs):
            counts["base"] += 1
            return Model()

    class PeftModel:
        @staticmethod
        def from_pretrained(model, *args, **kwargs):
            counts["adapter"] += 1
            return model

    fake_torch = SimpleNamespace(bfloat16="bf16")
    fake_transformers = SimpleNamespace(
        __version__="4.45.0", AutoTokenizer=AutoTokenizer, AutoModelForCausalLM=AutoModel
    )
    fake_peft = SimpleNamespace(PeftModel=PeftModel)
    runtime = PeftTransformersLoader(
        base_model_dir=base,
        adapter_path=adapter,
        torch_module=fake_torch,
        transformers_module=fake_transformers,
        peft_module=fake_peft,
    )(profile)
    assert runtime.profile == profile
    assert counts == {"tokenizer": 1, "base": 1, "adapter": 1, "to": 1}


def test_smoke_spec_has_no_behavioral_admission_gate():
    spec = json.loads(
        Path(__file__).parents[2].joinpath(
            "specs/experiments/WORLD-v0-a40-smoke-v1.yaml"
        ).read_text(encoding="utf-8")
    )
    assert spec["run"]["founders"] == [
        "A40_FOUNDER_000",
        "A40_FOUNDER_001",
        "A40_FOUNDER_002",
    ]
    assert spec["run"]["ticks"] == 2
    assert spec["run"]["behavioral_admission_gate"] is False
