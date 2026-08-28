"""Explicit model and generation configuration for the real-model boundary.

These values are infrastructure configuration.  They are intentionally kept
outside the dependency-free canonical domain package and are never rendered
into an EXP-000 ContextPack.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from alifelm.domain import ArtifactRef


_OPAQUE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_DTYPES = frozenset({"auto", "float32", "float16", "bfloat16"})


def _opaque(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not _OPAQUE_ID.fullmatch(value):
        raise ValueError(f"{field_name} must be an opaque identifier")


def _version(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not _VERSION.fullmatch(value):
        raise ValueError(f"{field_name} must be a semantic version")


def _nullable_digest(value: str | None, field_name: str) -> None:
    if value is not None and (not isinstance(value, str) or not _DIGEST.fullmatch(value)):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest or None")


@dataclass(frozen=True, slots=True)
class ModelProfile:
    """A fully explicit reference-backend model loading profile.

    ``model_identifier`` and ``tokenizer_identifier`` may be local paths or
    hub identifiers.  Their meaning is infrastructure-only.  A nullable
    digest means the caller does not yet have a verified digest; it does not
    permit the backend to invent one.
    """

    profile_id: str
    profile_version: str
    model_identifier: str
    model_revision: str | None
    model_digest: str | None
    tokenizer_identifier: str
    tokenizer_digest: str | None
    model_class: str
    generation_policy_id: str
    device: str
    dtype: str
    adapter_ref: ArtifactRef | None
    trust_remote_code: bool

    def __post_init__(self) -> None:
        _opaque(self.profile_id, "profile_id")
        _version(self.profile_version, "profile_version")
        if not isinstance(self.model_identifier, str) or not self.model_identifier:
            raise ValueError("model_identifier must be a non-empty identifier or path")
        if self.model_revision is not None and (
            not isinstance(self.model_revision, str) or not self.model_revision
        ):
            raise ValueError("model_revision must be a non-empty string or None")
        _nullable_digest(self.model_digest, "model_digest")
        if not isinstance(self.tokenizer_identifier, str) or not self.tokenizer_identifier:
            raise ValueError("tokenizer_identifier must be explicit and non-empty")
        _nullable_digest(self.tokenizer_digest, "tokenizer_digest")
        if not isinstance(self.model_class, str) or not self.model_class:
            raise ValueError("model_class must be a non-empty profile value")
        _opaque(self.generation_policy_id, "generation_policy_id")
        if not isinstance(self.device, str) or not self.device:
            raise ValueError("device must be an explicit non-empty device setting")
        if self.dtype not in _DTYPES:
            raise ValueError(f"dtype must be one of {sorted(_DTYPES)}")
        if self.adapter_ref is not None and not isinstance(self.adapter_ref, ArtifactRef):
            raise TypeError("adapter_ref must be an ArtifactRef or None")
        if type(self.trust_remote_code) is not bool:
            raise TypeError("trust_remote_code must be a boolean")

