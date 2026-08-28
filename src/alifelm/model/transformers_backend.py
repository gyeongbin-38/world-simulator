"""Lazy Transformers/PyTorch reference backend.

The backend is intentionally a small adapter.  It does not select a model,
freeze sampling semantics, batch agents, or write canonical state.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import nullcontext
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
            }
            transformers_major = int(
                str(getattr(transformers_module, "__version__", "4")).split(".", 1)[0]
            )
            dtype_key = "dtype" if transformers_major >= 5 else "torch_dtype"
            model_kwargs[dtype_key] = _dtype_value(torch_module, profile.dtype)
            if profile.model_revision is not None:
                model_kwargs["revision"] = profile.model_revision
            if profile.tokenizer_revision is not None:
                tokenizer_kwargs["revision"] = profile.tokenizer_revision
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

    def _rng_context(self, request: GenerationRequest) -> Any:
        if request.generator is not None:
            raise GenerationError(
                "external generator objects are not supported by the reference backend; "
                "use the explicit generation_seed request field"
            )
        if request.generation_seed is None:
            return nullcontext()
        if self._torch is None or not hasattr(self._torch, "random"):
            raise GenerationError(
                "a generation seed was supplied but PyTorch RNG isolation is unavailable"
            )

        torch_module = self._torch
        device = request.model_profile.device

        class _ForkedSeed:
            def __enter__(self):
                devices = []
                device_type = "cuda"
                if device.startswith("cuda"):
                    device_index = 0
                    if ":" in device:
                        device_index = int(device.split(":", 1)[1])
                    devices = [device_index]
                self._fork = torch_module.random.fork_rng(
                    devices=devices, device_type=device_type
                )
                self._fork.__enter__()
                torch_module.manual_seed(request.generation_seed)
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return self._fork.__exit__(exc_type, exc_value, traceback)

        return _ForkedSeed()

    def generate(self, request: GenerationRequest) -> RawGenerationResult:
        if not isinstance(request, GenerationRequest):
            raise TypeError("request must be a GenerationRequest")
        if request.model_profile != self.profile:
            raise ValueError("request profile does not match the loaded runtime")
        if request.stop_hooks:
            raise GenerationError(
                "stop hooks are not implemented by the reference backend; "
                "a post-generation check must not masquerade as a generation stop"
            )
        try:
            text_input = request.rendered_input.decode("utf-8")
            encoded = self.tokenizer(
                text_input,
                return_tensors="pt",
                add_special_tokens=self.profile.add_special_tokens,
            )
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
                "repetition_penalty": request.generation_policy.repetition_penalty,
            }
            if request.generation_policy.temperature is not None:
                generation_kwargs["temperature"] = request.generation_policy.temperature
            if request.generation_policy.top_p is not None:
                generation_kwargs["top_p"] = request.generation_policy.top_p
            if request.generation_policy.top_k is not None:
                generation_kwargs["top_k"] = request.generation_policy.top_k
            if request.prefix_allowed_tokens_fn is not None:
                generation_kwargs["prefix_allowed_tokens_fn"] = (
                    request.prefix_allowed_tokens_fn
                )
            inference_context = (
                self._torch.inference_mode()
                if self._torch is not None and hasattr(self._torch, "inference_mode")
                else nullcontext()
            )
            with self._rng_context(request):
                with inference_context:
                    outputs = self.model.generate(**model_inputs, **generation_kwargs)
            sequence = _to_int_tuple(_first_sequence(outputs))
            generated_ids = sequence[_input_length(input_ids) :]
            raw_text = self.tokenizer.decode(
                list(generated_ids), skip_special_tokens=True
            )
            generation_config = getattr(self.model, "generation_config", None)
            eos_ids = getattr(generation_config, "eos_token_id", None)
            if isinstance(eos_ids, int):
                eos_ids = (eos_ids,)
            elif eos_ids is None:
                eos_ids = ()
            else:
                eos_ids = tuple(eos_ids)
            if generated_ids and generated_ids[-1] in eos_ids:
                finish_reason = "eos_token"
            elif len(generated_ids) >= request.generation_policy.max_new_tokens:
                finish_reason = "length"
            else:
                finish_reason = "completed"
        except GenerationError:
            raise
        except Exception as error:
            raise GenerationError(
                f"generation failed for model profile {self.profile.profile_id!r}"
            ) from error
        return RawGenerationResult(
            opportunity_id=request.opportunity_id,
            generation_id=request.generation_id,
            context_pack_id=request.context_pack_id,
            context_hash=request.context_hash,
            rendered_input_hash=request.rendered_input_hash,
            interface_treatment_id=request.interface_treatment_id,
            interface_treatment_version=request.interface_treatment_version,
            interface_treatment_digest=request.interface_treatment_digest,
            constraint_policy_id=request.constraint_policy_id,
            raw_text=raw_text,
            token_ids=generated_ids,
            model_profile_id=self.profile.profile_id,
            generation_policy_id=request.generation_policy.policy_id,
            generation_policy_version=request.generation_policy.version,
            generation_seed_id=request.generation_seed_id,
            generation_seed=request.generation_seed,
            finish_reason=finish_reason,
        )
