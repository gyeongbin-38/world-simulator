"""Run-scoped live cognition bridge for the WORLD model proposal path.

This module owns no canonical state.  It adapts one already-loaded model and
adapter to the P4 candidate outcome contract while durable raw evidence is
written through the existing evidence/CAS implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from alifelm.context import CognitionAttempt, CompiledContext, ModelActionParser
from alifelm.persistence import ArtifactStore

from .adapter import ModelRuntime
from .evidence import (
    prepare_cognition_evidence,
    finalize_cognition_evidence,
)
from .generation import GenerationPolicy
from .profile import ModelProfile
from .treatments import I0_STRICT_FREE_GENERATION, InterfaceTreatment
from .transformers_backend import ModelLoadError


@dataclass(frozen=True, slots=True)
class LiveRuntimeIdentity:
    """Scientific identity required before a runtime can enter P4."""

    base_model_repo: str
    base_model_revision: str
    base_checkpoint_sha256: str
    adapter_sha256: str

    def __post_init__(self) -> None:
        if not self.base_model_repo or not self.base_model_revision:
            raise ValueError("base model repository and revision are required")
        for value, name in (
            (self.base_checkpoint_sha256, "base_checkpoint_sha256"),
            (self.adapter_sha256, "adapter_sha256"),
        ):
            if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
                raise ValueError(f"{name} must be a lowercase SHA-256 digest")


WORLD_V0_FA_V1_IDENTITY = LiveRuntimeIdentity(
    base_model_repo="allenai/OLMo-2-0425-1B-Instruct",
    base_model_revision="48d788eca847d4d7548f375ad03d3c9312f6139e",
    base_checkpoint_sha256="36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f",
    adapter_sha256="46917511362243be67e0783ddb7411a96f26613c1083bc4f95117d910d0998ec",
)


class RuntimeLoader(Protocol):
    """Deployment loader invoked exactly once by ``from_loader``."""

    def __call__(self, profile: ModelProfile) -> ModelRuntime: ...


def validate_live_runtime_identity(
    profile: ModelProfile,
    identity: LiveRuntimeIdentity,
) -> None:
    """Verify adapter/base identities before admission to the live path."""

    if profile.model_revision != identity.base_model_revision:
        raise ModelLoadError("loaded base revision does not match live runtime identity")
    if profile.model_digest != identity.base_checkpoint_sha256:
        raise ModelLoadError("loaded base checkpoint digest does not match live runtime identity")
    if profile.adapter_ref is None:
        raise ModelLoadError("live runtime requires a bound adapter ArtifactRef")
    if profile.adapter_ref.digest != identity.adapter_sha256:
        raise ModelLoadError("loaded adapter digest does not match live runtime identity")


class LiveCandidateRuntime:
    """One immutable, run-scoped candidate runtime.

    ``from_loader`` performs all loading before any ``infer`` call.  The
    loader is deliberately injected so deployment paths can use a local
    cache, while the scientific identity remains hash/revision based.
    """

    def __init__(
        self,
        runtime: ModelRuntime,
        *,
        profile: ModelProfile,
        generation_policy: GenerationPolicy,
        artifact_store: ArtifactStore,
        identity: LiveRuntimeIdentity,
        generation_seed: int | None = None,
        parser: ModelActionParser | None = None,
        interface_treatment: InterfaceTreatment = I0_STRICT_FREE_GENERATION,
        prefix_allowed_tokens_fn=None,
    ) -> None:
        if not isinstance(profile, ModelProfile):
            raise TypeError("profile must be a ModelProfile")
        if not isinstance(generation_policy, GenerationPolicy):
            raise TypeError("generation_policy must be a GenerationPolicy")
        if not isinstance(identity, LiveRuntimeIdentity):
            raise TypeError("identity must be a LiveRuntimeIdentity")
        if not hasattr(runtime, "generate"):
            raise TypeError("runtime must provide generate(request)")
        loaded_profile = getattr(runtime, "profile", profile)
        if loaded_profile != profile:
            raise ModelLoadError("loaded runtime profile does not match configured profile")
        validate_live_runtime_identity(profile, identity)
        model = getattr(runtime, "model", None)
        if model is not None and hasattr(model, "eval"):
            model.eval()
        if model is not None and hasattr(model, "parameters"):
            for parameter in model.parameters():
                if hasattr(parameter, "requires_grad_"):
                    parameter.requires_grad_(False)
                elif hasattr(parameter, "requires_grad"):
                    parameter.requires_grad = False
        if model is not None and getattr(model, "training", False):
            raise ModelLoadError("live cognition runtime must be in eval mode")
        if model is not None and hasattr(model, "parameters"):
            if any(getattr(parameter, "requires_grad", False) for parameter in model.parameters()):
                raise ModelLoadError("live cognition runtime parameters must be frozen")
        self.runtime = runtime
        self.profile = profile
        self.generation_policy = generation_policy
        self.artifact_store = artifact_store
        self.identity = identity
        self.generation_seed = generation_seed
        self.parser = parser or ModelActionParser()
        self.interface_treatment = interface_treatment
        self.prefix_allowed_tokens_fn = prefix_allowed_tokens_fn

    @classmethod
    def from_loader(
        cls,
        loader: RuntimeLoader,
        *,
        profile: ModelProfile,
        generation_policy: GenerationPolicy,
        artifact_store: ArtifactStore,
        identity: LiveRuntimeIdentity,
        generation_seed: int | None = None,
        parser: ModelActionParser | None = None,
        interface_treatment: InterfaceTreatment = I0_STRICT_FREE_GENERATION,
        prefix_allowed_tokens_fn=None,
    ) -> "LiveCandidateRuntime":
        if not callable(loader):
            raise TypeError("loader must be callable")
        # This is the only load call.  ``infer`` never invokes the loader.
        runtime = loader(profile)
        return cls(
            runtime,
            profile=profile,
            generation_policy=generation_policy,
            artifact_store=artifact_store,
            identity=identity,
            generation_seed=generation_seed,
            parser=parser,
            interface_treatment=interface_treatment,
            prefix_allowed_tokens_fn=prefix_allowed_tokens_fn,
        )

    def infer(self, compiled: CompiledContext) -> CognitionAttempt:
        """Produce exactly one candidate/rejection outcome for one context."""

        preparation = prepare_cognition_evidence(
            compiled,
            self.runtime,
            self.profile,
            self.generation_policy,
            self.artifact_store,
            generation_seed=self.generation_seed,
            parser=self.parser,
            interface_treatment=self.interface_treatment,
            prefix_allowed_tokens_fn=self.prefix_allowed_tokens_fn,
        )

        def finalize(action_intent, rejection):
            return finalize_cognition_evidence(
                preparation,
                self.profile,
                self.generation_policy,
                self.artifact_store,
                action_intent=action_intent,
                rejection=rejection,
            )

        return CognitionAttempt(
            opportunity_id=compiled.opportunity.opportunity_id,
            candidate=preparation.candidate,
            evidence_ref=None,
            parse_status=preparation.parse_status,
            generation_id=preparation.raw_generation.generation_id,
            rejection=preparation.rejection,
            evidence_finalizer=finalize,
        )
