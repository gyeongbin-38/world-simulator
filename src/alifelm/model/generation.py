"""Generation policy, request, and raw-result contracts."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Callable
import re

from alifelm.domain import OpportunityId

from .profile import ModelProfile


_OPAQUE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_DIGEST = re.compile(r"^[a-f0-9]{64}$")


def _opaque(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not _OPAQUE_ID.fullmatch(value):
        raise ValueError(f"{field_name} must be an opaque identifier")


def _version(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not _VERSION.fullmatch(value):
        raise ValueError(f"{field_name} must be a semantic version")


def _digest(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True)
class GenerationPolicy:
    """Explicit generation controls; no sampling defaults are frozen here."""

    policy_id: str
    version: str
    max_new_tokens: int
    do_sample: bool
    temperature: float | None
    top_p: float | None
    top_k: int | None
    repetition_penalty: float
    seed_id: str | None
    stop_policy_id: str | None

    def __post_init__(self) -> None:
        _opaque(self.policy_id, "policy_id")
        _version(self.version, "version")
        if type(self.max_new_tokens) is not int or self.max_new_tokens < 1:
            raise ValueError("max_new_tokens must be a positive integer")
        if type(self.do_sample) is not bool:
            raise TypeError("do_sample must be a boolean")
        if self.temperature is not None and (
            isinstance(self.temperature, bool)
            or not isinstance(self.temperature, (int, float))
            or self.temperature <= 0
        ):
            raise ValueError("temperature must be positive or None")
        if self.top_p is not None and (
            isinstance(self.top_p, bool)
            or not isinstance(self.top_p, (int, float))
            or self.top_p <= 0
            or self.top_p > 1
        ):
            raise ValueError("top_p must be in (0, 1] or None")
        if self.top_k is not None and (
            type(self.top_k) is not int or self.top_k < 0
        ):
            raise ValueError("top_k must be a non-negative integer or None")
        if (
            isinstance(self.repetition_penalty, bool)
            or not isinstance(self.repetition_penalty, (int, float))
            or self.repetition_penalty <= 0
        ):
            raise ValueError("repetition_penalty must be positive")
        if self.seed_id is not None:
            _opaque(self.seed_id, "seed_id")
        if self.stop_policy_id is not None:
            _opaque(self.stop_policy_id, "stop_policy_id")


StopHook = Callable[[str], bool]
PrefixAllowedTokensFn = Callable[[int, Any], list[int]]


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """One explicit request from a compiled context to a model adapter.

    ``generator`` and ``stop_hooks`` are runtime injection points.  They are
    not part of canonical state or model-facing text and are intentionally
    absent from the machine contract.
    """

    opportunity_id: OpportunityId
    generation_id: str
    context_pack_id: str
    context_hash: str
    rendered_input_hash: str
    rendered_input: bytes
    interface_treatment_id: str
    interface_treatment_version: str
    interface_treatment_digest: str
    constraint_policy_id: str | None
    model_profile: ModelProfile
    generation_policy: GenerationPolicy
    generation_seed_id: str
    generation_seed: int | None
    generator: Any | None
    stop_hooks: tuple[StopHook, ...]
    prefix_allowed_tokens_fn: PrefixAllowedTokensFn | None

    def __post_init__(self) -> None:
        if not isinstance(self.opportunity_id, OpportunityId):
            raise TypeError("opportunity_id must be an OpportunityId")
        _digest(self.generation_id, "generation_id")
        _opaque(self.context_pack_id, "context_pack_id")
        _digest(self.context_hash, "context_hash")
        _digest(self.rendered_input_hash, "rendered_input_hash")
        if not isinstance(self.rendered_input, bytes):
            raise TypeError("rendered_input must be bytes")
        if hashlib.sha256(self.rendered_input).hexdigest() != self.rendered_input_hash:
            raise ValueError("rendered_input_hash does not match rendered_input bytes")
        _opaque(self.interface_treatment_id, "interface_treatment_id")
        _version(self.interface_treatment_version, "interface_treatment_version")
        _digest(self.interface_treatment_digest, "interface_treatment_digest")
        if self.constraint_policy_id is not None:
            _opaque(self.constraint_policy_id, "constraint_policy_id")
        if not isinstance(self.model_profile, ModelProfile):
            raise TypeError("model_profile must be a ModelProfile")
        if not isinstance(self.generation_policy, GenerationPolicy):
            raise TypeError("generation_policy must be a GenerationPolicy")
        _opaque(self.generation_seed_id, "generation_seed_id")
        if (
            self.generation_policy.seed_id is not None
            and self.generation_policy.seed_id != self.generation_seed_id
        ):
            raise ValueError("generation seed identity does not match the generation policy")
        if self.generation_seed is not None and (
            type(self.generation_seed) is not int or self.generation_seed < 0
        ):
            raise ValueError("generation_seed must be a non-negative integer or None")
        if not isinstance(self.stop_hooks, tuple) or any(
            not callable(hook) for hook in self.stop_hooks
        ):
            raise TypeError("stop_hooks must be a tuple of callables")
        if self.prefix_allowed_tokens_fn is not None and not callable(
            self.prefix_allowed_tokens_fn
        ):
            raise TypeError("prefix_allowed_tokens_fn must be callable or None")


@dataclass(frozen=True, slots=True)
class RawGenerationResult:
    """Immutable raw model evidence, before parsing or Gateway binding."""

    opportunity_id: OpportunityId
    generation_id: str
    context_pack_id: str
    context_hash: str
    rendered_input_hash: str
    interface_treatment_id: str
    interface_treatment_version: str
    interface_treatment_digest: str
    constraint_policy_id: str | None
    raw_text: str
    token_ids: tuple[int, ...] | None
    model_profile_id: str
    generation_policy_id: str
    generation_policy_version: str
    generation_seed_id: str | None
    generation_seed: int | None
    finish_reason: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.opportunity_id, OpportunityId):
            raise TypeError("opportunity_id must be an OpportunityId")
        _digest(self.generation_id, "generation_id")
        _opaque(self.context_pack_id, "context_pack_id")
        _digest(self.context_hash, "context_hash")
        _digest(self.rendered_input_hash, "rendered_input_hash")
        _opaque(self.interface_treatment_id, "interface_treatment_id")
        _version(self.interface_treatment_version, "interface_treatment_version")
        _digest(self.interface_treatment_digest, "interface_treatment_digest")
        if self.constraint_policy_id is not None:
            _opaque(self.constraint_policy_id, "constraint_policy_id")
        if not isinstance(self.raw_text, str):
            raise TypeError("raw_text must be a string")
        if self.token_ids is not None:
            if not isinstance(self.token_ids, tuple) or any(
                type(token_id) is not int for token_id in self.token_ids
            ):
                raise TypeError("token_ids must be an immutable tuple of integers or None")
        _opaque(self.model_profile_id, "model_profile_id")
        _opaque(self.generation_policy_id, "generation_policy_id")
        _version(self.generation_policy_version, "generation_policy_version")
        if self.generation_seed_id is not None:
            _opaque(self.generation_seed_id, "generation_seed_id")
        if self.generation_seed is not None and (
            type(self.generation_seed) is not int or self.generation_seed < 0
        ):
            raise ValueError("generation_seed must be a non-negative integer or None")
        if self.finish_reason is not None and (
            not isinstance(self.finish_reason, str) or not self.finish_reason
        ):
            raise ValueError("finish_reason must be a non-empty string or None")


def generation_identity(
    *,
    context_hash: str,
    profile: ModelProfile,
    policy: GenerationPolicy,
    generation_seed_id: str,
    generation_seed: int | None,
    rendered_input_hash: str,
    interface_treatment_id: str,
    interface_treatment_version: str,
    interface_treatment_digest: str,
    constraint_policy_id: str | None,
) -> str:
    """Stable request identity excluding timing, retry, and completion order."""

    _digest(context_hash, "context_hash")
    _opaque(generation_seed_id, "generation_seed_id")
    _digest(rendered_input_hash, "rendered_input_hash")
    _opaque(interface_treatment_id, "interface_treatment_id")
    _version(interface_treatment_version, "interface_treatment_version")
    _digest(interface_treatment_digest, "interface_treatment_digest")
    if constraint_policy_id is not None:
        _opaque(constraint_policy_id, "constraint_policy_id")
    artifact = profile.adapter_ref
    value = {
        "domain": "ALIFELM_GENERATION_ID_V1",
        "context_hash": context_hash,
        "rendered_input_hash": rendered_input_hash,
        "interface": {
            "treatment_id": interface_treatment_id,
            "version": interface_treatment_version,
            "digest": interface_treatment_digest,
            "constraint_policy_id": constraint_policy_id,
        },
        "model_profile": {
            "profile_id": profile.profile_id,
            "profile_version": profile.profile_version,
            # Deployment paths are intentionally excluded.  Scientific model
            # identity is bound by revisions/digests and the live runtime
            # identity verifier; a path must not change causal request IDs.
            "model_revision": profile.model_revision,
            "model_digest": profile.model_digest,
            "tokenizer_revision": profile.tokenizer_revision,
            "tokenizer_digest": profile.tokenizer_digest,
            "model_class": profile.model_class,
            "device": profile.device,
            "dtype": profile.dtype,
            "adapter_ref": (
                {"artifact_id": artifact.artifact_id.value, "digest": artifact.digest}
                if artifact is not None
                else None
            ),
            "trust_remote_code": profile.trust_remote_code,
            "add_special_tokens": profile.add_special_tokens,
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
            "stop_policy_id": policy.stop_policy_id,
        },
        "generation_seed_id": generation_seed_id,
        "generation_seed": generation_seed,
    }
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
