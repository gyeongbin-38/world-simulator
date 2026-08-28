"""Bounded real-model adapter foundation.

The package is infrastructure-only.  Canonical state remains owned by the
simulation kernel and all model output remains a candidate until it passes the
existing Cognition Gateway.
"""

from .adapter import (
    ContextModelRuntimeAdapter,
    ModelRuntime,
    generation_request_for,
    parse_raw_generation,
)
from .generation import GenerationPolicy, GenerationRequest, RawGenerationResult, StopHook
from .profile import ModelProfile
from .transformers_backend import GenerationError, ModelLoadError, TransformersModelRuntime

__all__ = [
    "ContextModelRuntimeAdapter",
    "GenerationError",
    "GenerationPolicy",
    "GenerationRequest",
    "ModelLoadError",
    "ModelProfile",
    "ModelRuntime",
    "RawGenerationResult",
    "StopHook",
    "TransformersModelRuntime",
    "generation_request_for",
    "parse_raw_generation",
]

