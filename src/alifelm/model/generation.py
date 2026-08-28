"""Generation policy, request, and raw-result contracts."""

from __future__ import annotations

from dataclasses import dataclass
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
        if self.seed_id is not None:
            _opaque(self.seed_id, "seed_id")
        if self.stop_policy_id is not None:
            _opaque(self.stop_policy_id, "stop_policy_id")


StopHook = Callable[[str], bool]


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """One explicit request from a compiled context to a model adapter.

    ``generator`` and ``stop_hooks`` are runtime injection points.  They are
    not part of canonical state or model-facing text and are intentionally
    absent from the machine contract.
    """

    opportunity_id: OpportunityId
    context_pack_id: str
    context_hash: str
    rendered_input: bytes
    model_profile: ModelProfile
    generation_policy: GenerationPolicy
    generation_seed_id: str
    generation_seed: int | None
    generator: Any | None
    stop_hooks: tuple[StopHook, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.opportunity_id, OpportunityId):
            raise TypeError("opportunity_id must be an OpportunityId")
        _opaque(self.context_pack_id, "context_pack_id")
        _digest(self.context_hash, "context_hash")
        if not isinstance(self.rendered_input, bytes):
            raise TypeError("rendered_input must be bytes")
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


@dataclass(frozen=True, slots=True)
class RawGenerationResult:
    """Immutable raw model evidence, before parsing or Gateway binding."""

    opportunity_id: OpportunityId
    context_pack_id: str
    context_hash: str
    raw_text: str
    token_ids: tuple[int, ...] | None
    model_profile_id: str
    generation_policy_id: str
    generation_policy_version: str
    generation_seed_id: str | None
    finish_reason: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.opportunity_id, OpportunityId):
            raise TypeError("opportunity_id must be an OpportunityId")
        _opaque(self.context_pack_id, "context_pack_id")
        _digest(self.context_hash, "context_hash")
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
        if self.finish_reason is not None and (
            not isinstance(self.finish_reason, str) or not self.finish_reason
        ):
            raise ValueError("finish_reason must be a non-empty string or None")
