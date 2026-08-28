"""Lazy Transformers/PyTorch reference backend.

The backend is intentionally a small adapter.  It does not select a model,
freeze sampling semantics, batch agents, or write canonical state.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .generation import GenerationRequest, RawGenerationResult
from .profile import ModelProfile


class ModelLoadError(RuntimeError):
    """The reference backend could not load the explicitly requested profile."""


class GenerationError(RuntimeError):
    """The reference backend could not produce a raw result."""


def _load_optional_modules(torch_module: Any | None, transformers_module: Any | None) -> tuple[Any, Any]:
    if torch_module is None:
        try:
            import torch as torch_module  # type: ignore[import-not-found]
        except ImportError as error:
            raise ModelLoadError(
                "PyTorch is required for the Transformers reference backend; "
                "install the optional 'model' dependency extra"
            ) from error
    if transformers_module is None:
        try:
            import transformers as transformers_module  # type: ignore[import-not-found]
        except ImportError as error:
            raise ModelLoadError(
                "Transformers is required for the reference backend; "
                "install the optional 'model' dependency extra"
            ) from error
    return torch_module, transformers_module


def _dtype_value(torch_module: Any, dtype: str) -> Any:
    if dtype == "auto":
        return "auto"
    try:
        return getattr(torch_module, dtype)
    except AttributeError as error:
        raise ModelLoadError(f"PyTorch does not provide configured dtype {dtype!r}") from error


def _first_sequence(outputs: Any) -> Any:
    sequences = getattr(outputs, "sequences", outputs)
    try:
        return sequences[0]
    except (IndexError, KeyError, TypeError) as error:
        raise GenerationError("model generation returned no sequence") from error


def _to_int_tuple(sequence: Any) -> tuple[int, ...]:
    if hasattr(sequence, "detach"):
        sequence = sequence.detach()
    if hasattr(sequence, "cpu"):
        sequence = sequence.cpu()
    if hasattr(sequence, "tolist"):
        sequence = sequence.tolist()
    if not isinstance(sequence, (list, tuple)):
        raise GenerationError("generated sequence is not a token collection")
    if any(type(token_id) is not int for token_id in sequence):
        raise GenerationError("generated sequence contains a non-integer token")
    return tuple(sequence)


def _input_length(input_ids: Any) -> int:
    if hasattr(input_ids, "shape") and len(input_ids.shape) >= 2:
        return int(input_ids.shape[-1])
    if hasattr(input_ids, "tolist"):
        values = input_ids.tolist()
    else:
        values = input_ids
    if isinstance(values, (list, tuple)) and values and isinstance(values[0], (list, tuple)):
        return len(values[0])
    if isinstance(values, (list, tuple)):
        return len(values)
    raise GenerationError("tokenizer input_ids has no usable sequence length")


class TransformersModelRuntime:
    """Reference single-request runtime backed by explicit HF components."""

    def __init__(
        self,
        profile: ModelProfile,
        *,
        tokenizer: Any,
        model: Any,
        torch_module: Any | None = None,
    ) -> None:
        if not isinstance(profile, ModelProfile):
            raise TypeError("profile must be a ModelProfile")
        self.profile = profile
        self.tokenizer = tokenizer
        self.model = model
        self._torch = torch_module

    @classmethod
    def load(
        cls,
        profile: ModelProfile,
        *,
        torch_module: Any | None = None,
        transformers_module: Any | None = None,
    ) -> TransformersModelRuntime:
        if not isinstance(profile, ModelProfile):
            raise TypeError("profile must be a ModelProfile")
        torch_module, transformers_module = _load_optional_modules(
            torch_module, transformers_module
        )
        try:
            tokenizer_loader = transformers_module.AutoTokenizer
            model_loader = transformers_module.AutoModelForCausalLM
            tokenizer_kwargs: dict[str, Any] = {
                "trust_remote_code": profile.trust_remote_code,
            }
            model_kwargs: dict[str, Any] = {
                "trust_remote_code": profile.trust_remote_code,
                "torch_dtype": _dtype_value(torch_module, profile.dtype),
            }
            if profile.model_revision is not None:
                tokenizer_kwargs["revision"] = profile.model_revision
                model_kwargs["revision"] = profile.model_revision
            tokenizer = tokenizer_loader.from_pretrained(
                profile.tokenizer_identifier, **tokenizer_kwargs
            )
            model = model_loader.from_pretrained(
                profile.model_identifier, **model_kwargs
            )
            if profile.device != "auto":
                model = model.to(profile.device)
            model.eval()
        except Exception as error:
            raise ModelLoadError(
                f"failed to load model profile {profile.profile_id!r} "
                f"from {profile.model_identifier!r}"
            ) from error
        return cls(profile, tokenizer=tokenizer, model=model, torch_module=torch_module)

    @classmethod
    def from_components(
        cls,
        profile: ModelProfile,
        *,
        tokenizer: Any,
        model: Any,
        torch_module: Any | None = None,
    ) -> TransformersModelRuntime:
        """Inject already-created components for fast adapter-level tests."""

        runtime = cls(
            profile,
            tokenizer=tokenizer,
            model=model,
            torch_module=torch_module,
        )
        if not hasattr(model, "generate"):
            raise TypeError("injected model must provide generate")
        return runtime

    def _make_generator(self, request: GenerationRequest) -> Any | None:
        if request.generator is not None:
            return request.generator
        if request.generation_seed is None:
            return None
        if self._torch is None or not hasattr(self._torch, "Generator"):
            raise GenerationError("a generation seed was supplied but PyTorch Generator is unavailable")
        device = request.model_profile.device
        try:
            generator = self._torch.Generator(device=device if device != "auto" else "cpu")
            return generator.manual_seed(request.generation_seed)
        except Exception as error:
            raise GenerationError("failed to construct the requested generation generator") from error

    def generate(self, request: GenerationRequest) -> RawGenerationResult:
        if not isinstance(request, GenerationRequest):
            raise TypeError("request must be a GenerationRequest")
        if request.model_profile != self.profile:
            raise ValueError("request profile does not match the loaded runtime")
        try:
            text_input = request.rendered_input.decode("utf-8")
            encoded = self.tokenizer(text_input, return_tensors="pt")
            if not isinstance(encoded, Mapping):
                raise GenerationError("tokenizer output must be a mapping")
            model_inputs = {
                key: value.to(self.profile.device)
                if hasattr(value, "to") and self.profile.device != "auto"
                else value
                for key, value in encoded.items()
            }
            input_ids = model_inputs.get("input_ids")
            if input_ids is None:
                raise GenerationError("tokenizer output does not contain input_ids")
            generation_kwargs: dict[str, Any] = {
                "max_new_tokens": request.generation_policy.max_new_tokens,
                "do_sample": request.generation_policy.do_sample,
            }
            if request.generation_policy.temperature is not None:
                generation_kwargs["temperature"] = request.generation_policy.temperature
            if request.generation_policy.top_p is not None:
                generation_kwargs["top_p"] = request.generation_policy.top_p
            if request.generation_policy.top_k is not None:
                generation_kwargs["top_k"] = request.generation_policy.top_k
            generator = self._make_generator(request)
            if generator is not None:
                generation_kwargs["generator"] = generator
            outputs = self.model.generate(**model_inputs, **generation_kwargs)
            sequence = _to_int_tuple(_first_sequence(outputs))
            generated_ids = sequence[_input_length(input_ids) :]
            raw_text = self.tokenizer.decode(
                list(generated_ids), skip_special_tokens=False
            )
            finish_reason = None
            for hook in request.stop_hooks:
                if hook(raw_text):
                    finish_reason = "stop_hook"
                    break
        except GenerationError:
            raise
        except Exception as error:
            raise GenerationError(
                f"generation failed for model profile {self.profile.profile_id!r}"
            ) from error
        return RawGenerationResult(
            opportunity_id=request.opportunity_id,
            context_pack_id=request.context_pack_id,
            context_hash=request.context_hash,
            raw_text=raw_text,
            token_ids=generated_ids,
            model_profile_id=self.profile.profile_id,
            generation_policy_id=request.generation_policy.policy_id,
            generation_policy_version=request.generation_policy.version,
            generation_seed_id=request.generation_seed_id,
            finish_reason=finish_reason,
        )
