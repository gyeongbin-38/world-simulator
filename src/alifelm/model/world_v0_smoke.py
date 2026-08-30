"""Contracts and execution helpers for the first WORLD v0 A40 smoke.

This module is deployment tooling, not a second simulator.  Static checks are
dependency-light and run before importing PyTorch.  The execute path wires the
existing kernel, context pipeline, live candidate runtime, Gateway, validator,
and filesystem CAS together after those checks pass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from importlib import metadata as importlib_metadata
import json
from pathlib import Path, PureWindowsPath
import platform
import subprocess
from typing import Any, Mapping

from alifelm.context import (
    ContextCognitionPipeline,
    ContextPolicy,
    DEFAULT_ACTION_PRESENTATION,
    OrderingPolicy,
    action_presentation_digest,
    context_policy_digest,
)
from alifelm.domain import AgentId, ArtifactId, ArtifactRef, Duration, RunId
from alifelm.kernel import DeterministicKernel, SimulationRun
from alifelm.persistence import FileSystemArtifactStore

from .generation import GenerationPolicy
from .live_runtime import LiveCandidateRuntime, WORLD_V0_FA_V1_IDENTITY
from .peft_runtime import PeftTransformersLoader
from .profile import ModelProfile
from .treatments import I0_STRICT_FREE_GENERATION


WORLD_V0_SMOKE_ID = "WORLD_V0_A40_SMOKE_V1"
WORLD_V0_SMOKE_SCHEMA = "1.0.0"
BASE_MODEL_REPO = WORLD_V0_FA_V1_IDENTITY.base_model_repo
BASE_MODEL_REVISION = WORLD_V0_FA_V1_IDENTITY.base_model_revision
BASE_CHECKPOINT_SHA256 = WORLD_V0_FA_V1_IDENTITY.base_checkpoint_sha256
TOKENIZER_REVISION = WORLD_V0_FA_V1_IDENTITY.tokenizer_revision
TOKENIZER_DIGEST = WORLD_V0_FA_V1_IDENTITY.tokenizer_digest
ADAPTER_SHA256 = WORLD_V0_FA_V1_IDENTITY.adapter_sha256
ADAPTER_CONFIG_SHA256 = "687100a0b6340b6096ca1e86066d3c13224b3c8e14ce9fb1b0cf78a52a8bdb7d"
EXPECTED_BOS_TOKEN_ID = 100257
EXPECTED_EOS_TOKEN_ID = 100257
EXPECTED_PAD_TOKEN_ID = 100277
EXPECTED_TARGET_MODULES = ("q_proj", "k_proj", "v_proj", "o_proj")
FORBIDDEN_TARGET_MODULES = ("gate_proj", "up_proj", "down_proj", "lm_head")
TOKENIZER_FILE_HASHES = {
    "tokenizer.json": "73fd5254624f39a88e3faac6a8e11300fc3c735ed37880d4f4f08db898eaecca",
    "tokenizer_config.json": "50c412c57d832057a3d5db42064c741f751e570f7c8788f037bfb0d2dd6e5f49",
    "special_tokens_map.json": "78afb564e81264029b25f9caf24bda2521d5bdaeff5cd3fdbc01d3da2e8ce2f2",
    "vocab.json": "9e14712c91b37c7aab74b1306baa46ac342d620637a4b44523cdc3aec7d24195",
    "merges.txt": "b6fe424e334903f7fb84d3a106d9730455f4744b9fe3c21ee136d97a00e72502",
}
MODEL_CONFIG_FILE_HASHES = {
    "config.json": "0d15ebb6cb8d998513b46ef337214176a6fd59fe5f16b30387c70d5f87795a9c",
    "generation_config.json": "437b97826bb4430c205083a0986fbe31f4959cffbe445e47fb7c5192fdcb8d58",
}
MODEL_CONFIG_AGGREGATE_SHA256 = "eeed26d20a24ad35479aa33b690b196096c5f98fee8bc43d816c3bd314987c38"
FOUNDERS = ("A40_FOUNDER_000", "A40_FOUNDER_001", "A40_FOUNDER_002")
SMOKE_TICKS = 2
SMOKE_GENERATION_SEED = 35020260831
SMOKE_GENERATION_SEED_ID = "WORLD_V0_A40_SMOKE_SEED_V1"
SMOKE_GENERATION_POLICY_ID = "WORLD_V0_A40_SMOKE_GREEDY_V1"
SMOKE_PROFILE_ID = "WORLD_V0_FA_V1_BF16"
SMOKE_CONTEXT_POLICY_ID = "exp000-context"


class SmokePreflightError(RuntimeError):
    """A deployment or scientific identity check failed closed."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise SmokePreflightError(f"required deployment file is missing: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_absolute_deployment_path(value: Path | str) -> bool:
    """Accept native absolute paths and Windows drive paths on any host."""

    text = str(value)
    # ``Path`` on Windows treats ``/workspace`` as drive-relative even though
    # it is an absolute POSIX deployment path on the Linux A40 host.  Keep the
    # cross-platform root check explicit so historical PEFT paths are metadata
    # rather than mistaken hub identifiers.
    return (
        text.startswith("/")
        or Path(text).is_absolute()
        or PureWindowsPath(text).is_absolute()
    )


@dataclass(frozen=True, slots=True)
class DeploymentPaths:
    base_model_dir: Path
    adapter_path: Path
    output_root: Path
    base_checkpoint_file: Path | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "base_model_dir", Path(self.base_model_dir))
        object.__setattr__(self, "adapter_path", Path(self.adapter_path))
        object.__setattr__(self, "output_root", Path(self.output_root))
        if self.base_checkpoint_file is not None:
            object.__setattr__(self, "base_checkpoint_file", Path(self.base_checkpoint_file))
        for value, name in (
            (self.base_model_dir, "base_model_dir"),
            (self.adapter_path, "adapter_path"),
            (self.output_root, "output_root"),
        ):
            if not is_absolute_deployment_path(value):
                raise ValueError(f"{name} must be an absolute deployment path")
        if self.base_checkpoint_file is not None and not is_absolute_deployment_path(
            self.base_checkpoint_file
        ):
            raise ValueError("base_checkpoint_file must be an absolute deployment path")

    @property
    def base_checkpoint(self) -> Path:
        return self.base_checkpoint_file or (self.base_model_dir / "model.safetensors")

    @property
    def adapter_dir(self) -> Path:
        return self.adapter_path.parent if self.adapter_path.suffix == ".safetensors" else self.adapter_path

    @property
    def adapter_file(self) -> Path:
        return self.adapter_path if self.adapter_path.suffix == ".safetensors" else self.adapter_path / "adapter_model.safetensors"

    @property
    def adapter_config(self) -> Path:
        return self.adapter_dir / "adapter_config.json"


@dataclass(frozen=True, slots=True)
class DeploymentExpectations:
    base_checkpoint_sha256: str = BASE_CHECKPOINT_SHA256
    adapter_sha256: str = ADAPTER_SHA256
    adapter_config_sha256: str = ADAPTER_CONFIG_SHA256
    tokenizer_digest: str = TOKENIZER_DIGEST
    tokenizer_file_hashes: Mapping[str, str] = field(
        default_factory=lambda: dict(TOKENIZER_FILE_HASHES)
    )
    config_file_hashes: Mapping[str, str] = field(
        default_factory=lambda: dict(MODEL_CONFIG_FILE_HASHES)
    )
    config_aggregate_sha256: str = MODEL_CONFIG_AGGREGATE_SHA256
    bos_token_id: int = EXPECTED_BOS_TOKEN_ID
    eos_token_id: int = EXPECTED_EOS_TOKEN_ID
    pad_token_id: int = EXPECTED_PAD_TOKEN_ID


DEFAULT_EXPECTATIONS = DeploymentExpectations()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SmokePreflightError(f"invalid JSON deployment file: {path}") from error
    if not isinstance(value, dict):
        raise SmokePreflightError(f"deployment JSON must be an object: {path}")
    return value


def _file_digest_map(root: Path, expected: Mapping[str, str]) -> dict[str, str]:
    actual = {name: sha256_file(root / name) for name in sorted(expected)}
    if actual != dict(expected):
        raise SmokePreflightError(f"deployment file hash mismatch under {root}")
    return actual


def _aggregate_file_digest(hashes: Mapping[str, str]) -> str:
    return canonical_digest({name: hashes[name] for name in sorted(hashes)})


def _validate_adapter_base_provenance(value: Any) -> str:
    """Validate hub provenance without treating serialized local paths as source IDs."""

    if not isinstance(value, str) or not value:
        raise SmokePreflightError("adapter base model provenance is missing")
    if is_absolute_deployment_path(value):
        return value
    if value != BASE_MODEL_REPO:
        raise SmokePreflightError("adapter base model source identifier does not match accepted source")
    return value


def _verify_tokenizer_metadata(root: Path, expectations: DeploymentExpectations) -> dict[str, Any]:
    config = _read_json(root / "tokenizer_config.json")
    added = config.get("added_tokens_decoder")
    if not isinstance(added, dict):
        raise SmokePreflightError("tokenizer added_tokens_decoder metadata is missing")
    expected_tokens = {
        str(expectations.bos_token_id): "<|endoftext|>",
        str(expectations.eos_token_id): "<|endoftext|>",
        str(expectations.pad_token_id): "<|pad|>",
    }
    for token_id, content in expected_tokens.items():
        item = added.get(token_id)
        if not isinstance(item, dict) or item.get("content") != content:
            raise SmokePreflightError(f"tokenizer token metadata mismatch for {token_id}")
    if config.get("bos_token") != "<|endoftext|>" or config.get("eos_token") != "<|endoftext|>":
        raise SmokePreflightError("tokenizer BOS/EOS token metadata mismatch")
    if config.get("pad_token") != "<|pad|>":
        raise SmokePreflightError("tokenizer PAD token metadata mismatch")
    return {
        "bos_token_id": expectations.bos_token_id,
        "eos_token_id": expectations.eos_token_id,
        "pad_token_id": expectations.pad_token_id,
        "chat_template_applied": False,
        "add_special_tokens": True,
    }


def verify_static_deployment(
    paths: DeploymentPaths,
    *,
    expectations: DeploymentExpectations = DEFAULT_EXPECTATIONS,
    expected_git_commit: str | None = None,
    repository_root: Path | None = None,
) -> dict[str, Any]:
    """Verify deployment bytes and planned-output immutability before loading torch."""

    for directory, name in ((paths.base_model_dir, "base model"), (paths.adapter_dir, "adapter")):
        if not directory.is_dir():
            raise SmokePreflightError(f"{name} directory is missing: {directory}")
    base_hash = sha256_file(paths.base_checkpoint)
    if base_hash != expectations.base_checkpoint_sha256:
        raise SmokePreflightError("base checkpoint SHA-256 mismatch")
    adapter_hash = sha256_file(paths.adapter_file)
    if adapter_hash != expectations.adapter_sha256:
        raise SmokePreflightError("adapter SHA-256 mismatch")
    config_hash = sha256_file(paths.adapter_config)
    if config_hash != expectations.adapter_config_sha256:
        raise SmokePreflightError("adapter config SHA-256 mismatch")
    adapter_config = _read_json(paths.adapter_config)
    if adapter_config.get("peft_type") != "LORA":
        raise SmokePreflightError("accepted adapter must be PEFT LoRA")
    base_name = _validate_adapter_base_provenance(adapter_config.get("base_model_name_or_path"))
    targets = adapter_config.get("target_modules")
    if set(targets or ()) != set(EXPECTED_TARGET_MODULES) or set(targets or ()) & set(FORBIDDEN_TARGET_MODULES):
        raise SmokePreflightError("adapter target modules do not match accepted FA-v1")

    tokenizer_hashes = _file_digest_map(paths.base_model_dir, expectations.tokenizer_file_hashes)
    config_hashes = _file_digest_map(paths.base_model_dir, expectations.config_file_hashes)
    tokenizer_digest = _aggregate_file_digest(tokenizer_hashes)
    config_digest = _aggregate_file_digest(config_hashes)
    if tokenizer_digest != expectations.tokenizer_digest:
        raise SmokePreflightError("tokenizer aggregate digest mismatch")
    if config_digest != expectations.config_aggregate_sha256:
        raise SmokePreflightError("model config aggregate digest mismatch")
    tokenizer_metadata = _verify_tokenizer_metadata(paths.base_model_dir, expectations)

    commit = expected_git_commit
    if repository_root is not None:
        try:
            actual_commit = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repository_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError) as error:
            raise SmokePreflightError("cannot resolve repository commit") from error
        if commit is not None and actual_commit != commit:
            raise SmokePreflightError("repository commit mismatch")
        commit = actual_commit

    planned = build_smoke_manifest(
        paths=paths,
        git_commit=commit or "UNPINNED",
        tokenizer_hashes=tokenizer_hashes,
        config_hashes=config_hashes,
        adapter_config_sha256=config_hash,
    )
    existing_status = inspect_existing_manifest(paths.output_root, planned["manifest_identity_digest"])
    return {
        "status": "STATIC_PREFLIGHT_OK",
        "run_id": WORLD_V0_SMOKE_ID,
        "schema_version": WORLD_V0_SMOKE_SCHEMA,
        "paths": {
            "base_model_dir": str(paths.base_model_dir),
            "adapter_path": str(paths.adapter_path),
            "output_root": str(paths.output_root),
        },
        "base_checkpoint_sha256": base_hash,
        "adapter_sha256": adapter_hash,
        "adapter_config_sha256": config_hash,
        "adapter_base_model_name_or_path": base_name,
        "tokenizer_revision": TOKENIZER_REVISION,
        "tokenizer_digest": tokenizer_digest,
        "tokenizer_file_hashes": tokenizer_hashes,
        "config_file_hashes": config_hashes,
        "config_aggregate_sha256": config_digest,
        "tokenizer_metadata": tokenizer_metadata,
        "git_commit": commit,
        "planned_manifest_identity_digest": planned["manifest_identity_digest"],
        "existing_manifest_status": existing_status,
    }


def inspect_existing_manifest(output_root: Path, planned_identity_digest: str) -> str | None:
    manifest_path = output_root / "manifest.json"
    if not manifest_path.exists():
        return None
    existing = _read_json(manifest_path)
    if existing.get("manifest_identity_digest") != planned_identity_digest:
        raise SmokePreflightError("existing output manifest has a mismatching identity")
    own = dict(existing)
    recorded = own.pop("manifest_digest", None)
    if not isinstance(recorded, str) or canonical_digest(own) != recorded:
        raise SmokePreflightError("existing output manifest self-digest is invalid")
    status = existing.get("status")
    if status == "COMPLETE":
        return "ALREADY_COMPLETE"
    raise SmokePreflightError("existing output manifest is incomplete and immutable")


def build_generation_policy() -> GenerationPolicy:
    return GenerationPolicy(
        policy_id=SMOKE_GENERATION_POLICY_ID,
        version="1.0.0",
        max_new_tokens=128,
        do_sample=False,
        temperature=None,
        top_p=None,
        top_k=None,
        repetition_penalty=1.0,
        seed_id=SMOKE_GENERATION_SEED_ID,
        stop_policy_id=None,
    )


def build_model_profile(base_model_dir: Path, *, device: str = "cuda:0") -> ModelProfile:
    return ModelProfile(
        profile_id=SMOKE_PROFILE_ID,
        profile_version="1.0.0",
        model_identifier=str(base_model_dir),
        model_revision=BASE_MODEL_REVISION,
        model_digest=BASE_CHECKPOINT_SHA256,
        tokenizer_identifier=str(base_model_dir),
        tokenizer_revision=TOKENIZER_REVISION,
        tokenizer_digest=TOKENIZER_DIGEST,
        model_class="AUTO_CAUSAL_LM",
        generation_policy_id=SMOKE_GENERATION_POLICY_ID,
        device=device,
        dtype="bfloat16",
        adapter_ref=ArtifactRef(ArtifactId("F0_FA_V1_FORMAL"), ADAPTER_SHA256),
        trust_remote_code=False,
        add_special_tokens=True,
    )


def build_context_policy() -> ContextPolicy:
    return ContextPolicy.exp000(
        max_prior_visible_records=2,
        ordering=OrderingPolicy(
            policy_version="1.0.0",
            unordered_collection_algorithm="ALIFELM_CONTEXT_ORDER_V1",
            digest_algorithm="sha256",
            ordering_seed_id="world-v0-order",
            ordering_seed_digest="2" * 64,
            cross_tick_order="COMMITTED_TICK_CHRONOLOGICAL",
            tie_breaker="FULL_STABLE_ITEM_KEY",
        ),
        action_presentation_digest=action_presentation_digest(DEFAULT_ACTION_PRESENTATION),
    )


def build_smoke_manifest(
    *,
    paths: DeploymentPaths,
    git_commit: str,
    tokenizer_hashes: Mapping[str, str] | None = None,
    config_hashes: Mapping[str, str] | None = None,
    adapter_config_sha256: str = ADAPTER_CONFIG_SHA256,
) -> dict[str, Any]:
    profile = build_model_profile(paths.base_model_dir)
    policy = build_generation_policy()
    context_policy = build_context_policy()
    identity_material = {
        "run_id": WORLD_V0_SMOKE_ID,
        "schema_version": WORLD_V0_SMOKE_SCHEMA,
        "scientific_identity": {
            "base_model_repo": BASE_MODEL_REPO,
            "base_model_revision": BASE_MODEL_REVISION,
            "base_checkpoint_sha256": BASE_CHECKPOINT_SHA256,
            "tokenizer_revision": TOKENIZER_REVISION,
            "tokenizer_digest": TOKENIZER_DIGEST,
            "adapter_sha256": ADAPTER_SHA256,
            "adapter_config_sha256": adapter_config_sha256,
        },
        "model_profile": {
            "profile_id": profile.profile_id,
            "profile_version": profile.profile_version,
            "model_revision": profile.model_revision,
            "model_digest": profile.model_digest,
            "tokenizer_revision": profile.tokenizer_revision,
            "tokenizer_digest": profile.tokenizer_digest,
            "model_class": profile.model_class,
            "device": profile.device,
            "dtype": profile.dtype,
            "adapter_digest": ADAPTER_SHA256,
        },
        "generation_policy": {
            "policy_id": policy.policy_id,
            "version": policy.version,
            "max_new_tokens": policy.max_new_tokens,
            "do_sample": policy.do_sample,
            "temperature": policy.temperature,
            "top_p": policy.top_p,
            "top_k": policy.top_k,
            "repetition_penalty": policy.repetition_penalty,
            "seed_id": policy.seed_id,
            "seed": SMOKE_GENERATION_SEED,
        },
        "interface_treatment": {
            "id": I0_STRICT_FREE_GENERATION.treatment_id,
            "version": I0_STRICT_FREE_GENERATION.version,
            "digest": I0_STRICT_FREE_GENERATION.digest,
        },
        "context_policy": {
            "id": SMOKE_CONTEXT_POLICY_ID,
            "version": "1.0.0",
            "digest": context_policy_digest(context_policy),
        },
        "founders": list(FOUNDERS),
        "ticks": SMOKE_TICKS,
        "lifecycle": {"lifespan_ticks": 20, "maturity_delay_ticks": 0, "refractory_interval_ticks": 0},
        "flags": {
            "resources": False,
            "batching": False,
            "retry": False,
            "fallback": False,
            "repair": False,
            "constrained_decoding": False,
            "social_priors": False,
            "neural_heredity": False,
        },
        "dataset": {"id": "EXP-000_RUNTIME_CONTEXT_ONLY", "training": False},
        "git_commit": git_commit,
    }
    manifest = {
        "schema_version": WORLD_V0_SMOKE_SCHEMA,
        "run_id": WORLD_V0_SMOKE_ID,
        "status": "PLANNED",
        "manifest_identity": identity_material,
        "manifest_identity_digest": canonical_digest(identity_material),
        "deployment": {
            "base_model_dir": str(paths.base_model_dir),
            "adapter_path": str(paths.adapter_path),
            "output_root": str(paths.output_root),
            "tokenizer_file_hashes": dict(sorted((tokenizer_hashes or TOKENIZER_FILE_HASHES).items())),
            "config_file_hashes": dict(sorted((config_hashes or MODEL_CONFIG_FILE_HASHES).items())),
        },
        "evidence_policy": {
            "raw_model_text": "CAS_ONLY",
            "canonical_state_contains_raw_text": False,
            "one_attempt_per_opportunity": True,
            "malformed_output": "TYPED_REJECTION_NO_INTENT",
            "infrastructure_failure": "ABORT_FAIL_CLOSED",
        },
    }
    return manifest


def ensure_execute_environment(*, torch_module: Any | None = None) -> dict[str, Any]:
    try:
        if torch_module is None:
            import torch as torch_module  # type: ignore[import-not-found]
    except ImportError as error:
        raise SmokePreflightError("PyTorch is required in execute mode") from error
    cuda = getattr(torch_module, "cuda", None)
    if cuda is None or not bool(cuda.is_available()):
        raise SmokePreflightError("CUDA is unavailable in execute mode")
    driver = "unknown"
    try:
        driver = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip().splitlines()[0]
    except (OSError, IndexError, subprocess.CalledProcessError):
        pass
    packages: dict[str, str] = {}
    for package in ("transformers", "peft", "accelerate", "safetensors", "bitsandbytes"):
        try:
            packages[package] = importlib_metadata.version(package)
        except importlib_metadata.PackageNotFoundError:
            packages[package] = "not-installed"
    return {
        "cuda": True,
        "gpu": str(cuda.get_device_name(0)) if hasattr(cuda, "get_device_name") else "unknown",
        "device_count": int(cuda.device_count()) if hasattr(cuda, "device_count") else None,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "torch": str(getattr(torch_module, "__version__", "unknown")),
        "torch_cuda": str(getattr(getattr(torch_module, "version", None), "cuda", "unknown")),
        "driver": driver,
        "packages": packages,
    }


def manifest_with_result(planned: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    final = dict(planned)
    final["status"] = "COMPLETE"
    final["result"] = result
    final["manifest_digest"] = canonical_digest(final)
    return final


def write_immutable_manifest(output_root: Path, manifest: Mapping[str, Any]) -> str:
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / "manifest.json"
    payload = dict(manifest)
    recorded = payload.get("manifest_digest")
    if not isinstance(recorded, str) or canonical_digest({k: v for k, v in payload.items() if k != "manifest_digest"}) != recorded:
        raise SmokePreflightError("manifest self-digest is invalid")
    if path.exists():
        existing = _read_json(path)
        if existing != payload:
            raise SmokePreflightError("refusing to overwrite a mismatching output manifest")
        return "ALREADY_COMPLETE"
    path.write_bytes(canonical_bytes(payload) + b"\n")
    return "WRITTEN"


def run_headless_smoke(
    *,
    paths: DeploymentPaths,
    git_commit: str,
    environment: Mapping[str, Any],
) -> dict[str, Any]:
    """Run the real existing kernel/pipeline after the loader has been admitted."""

    profile = build_model_profile(paths.base_model_dir)
    policy = build_generation_policy()
    identity = WORLD_V0_FA_V1_IDENTITY
    store = FileSystemArtifactStore(paths.output_root / "cas")
    pipeline = ContextCognitionPipeline(
        build_context_policy(),
        model_profile_id=profile.profile_id,
        generation_policy_id=policy.policy_id,
        generation_seed_id=SMOKE_GENERATION_SEED_ID,
        artifact_store=store,
    )
    loader = PeftTransformersLoader(
        base_model_dir=paths.base_model_dir,
        adapter_path=paths.adapter_path,
    )
    runtime = LiveCandidateRuntime.from_loader(
        loader,
        profile=profile,
        generation_policy=policy,
        artifact_store=store,
        identity=identity,
        generation_seed=SMOKE_GENERATION_SEED,
        interface_treatment=I0_STRICT_FREE_GENERATION,
    )
    run = SimulationRun.bootstrap(
        RunId(WORLD_V0_SMOKE_ID),
        lifespan_ticks=Duration(20),
        maturity_delay_ticks=Duration(0),
        refractory_interval_ticks=Duration(0),
        founder_ids=tuple(AgentId(value) for value in FOUNDERS),
    )
    kernel = DeterministicKernel(run, runtime, context_pipeline=pipeline)
    tick_records: list[dict[str, Any]] = []
    for _ in range(SMOKE_TICKS):
        result = kernel.run_tick()
        attempts = result.cognition_attempts
        rejected = [
            getattr(getattr(item, "parse_status", None), "value", getattr(item, "parse_status", None))
            for item in attempts
            if item.candidate is None
        ]
        tick_records.append(
            {
                "tick": int(result.snapshot_before.tick),
                "snapshot_before": result.snapshot_before.state_hash(),
                "opportunities": len(result.opportunities),
                "attempts": len(attempts),
                "valid_intents": len(result.intent_batch.intents),
                "rejected_attempts": rejected,
                "validated_intents": len(result.validated_intents),
                "fragment_kinds": [fragment.kind.value for fragment in result.fragments],
                "fragment_count": len(result.fragments),
                "snapshot_after": result.commit_result.snapshot.state_hash(),
                "artifact_refs": [
                    {"artifact_id": ref.artifact_id.value, "digest": ref.digest}
                    for ref in result.context_artifact_refs
                ],
                "state_version": int(result.commit_result.snapshot.state_version),
            }
        )
    return {
        "status": "INFRASTRUCTURE_PASS",
        "environment": dict(environment),
        "ticks": tick_records,
        "final_snapshot_hash": run.snapshot.state_hash(),
        "final_state_version": int(run.snapshot.state_version),
    }


__all__ = [
    "ADAPTER_CONFIG_SHA256",
    "ADAPTER_SHA256",
    "BASE_CHECKPOINT_SHA256",
    "BASE_MODEL_REPO",
    "BASE_MODEL_REVISION",
    "DeploymentExpectations",
    "DeploymentPaths",
    "FOUNDERS",
    "MODEL_CONFIG_FILE_HASHES",
    "SMOKE_TICKS",
    "SmokePreflightError",
    "TOKENIZER_DIGEST",
    "TOKENIZER_FILE_HASHES",
    "TOKENIZER_REVISION",
    "WORLD_V0_SMOKE_ID",
    "build_generation_policy",
    "build_model_profile",
    "build_smoke_manifest",
    "ensure_execute_environment",
    "inspect_existing_manifest",
    "is_absolute_deployment_path",
    "manifest_with_result",
    "run_headless_smoke",
    "verify_static_deployment",
    "write_immutable_manifest",
]
