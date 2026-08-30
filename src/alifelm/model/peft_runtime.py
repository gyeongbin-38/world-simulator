"""Deployment-side loader for an immutable PEFT adapter runtime.

The loader is deliberately separate from the scientific model contracts.  It
accepts deployment paths, performs one load of the tokenizer/base/adapter, and
returns the concrete :class:`TransformersModelRuntime` used by the live
bridge.  Static byte and provenance checks belong to the deployment preflight
and therefore happen before this loader is called.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .profile import ModelProfile
from .transformers_backend import (
    ModelLoadError,
    TransformersModelRuntime,
    _dtype_value,
)


def _verify_loaded_tokenizer(tokenizer: Any) -> None:
    """Recheck semantic tokenizer identities after local bytes are loaded."""

    for name, expected in (
        ("bos_token_id", 100257),
        ("eos_token_id", 100257),
        ("pad_token_id", 100277),
    ):
        if getattr(tokenizer, name, None) != expected:
            raise ModelLoadError(f"loaded tokenizer {name} does not match accepted identity")
    if not bool(getattr(tokenizer, "is_fast", False)):
        raise ModelLoadError("the accepted live runtime requires a fast tokenizer")
    encode = getattr(tokenizer, "encode", None)
    if callable(encode):
        sample = "Canonical visible state follows.\nSelf handle: A1\n"
        without = list(encode(sample, add_special_tokens=False))
        with_special = list(encode(sample, add_special_tokens=True))
        if without != with_special or (without and without[0] == 100257):
            raise ModelLoadError("loaded tokenizer violates direct-completion BOS semantics")


def _optional_modules(
    torch_module: Any | None,
    transformers_module: Any | None,
    peft_module: Any | None,
) -> tuple[Any, Any, Any]:
    if torch_module is None:
        try:
            import torch as torch_module  # type: ignore[import-not-found]
        except ImportError as error:
            raise ModelLoadError("PyTorch is required for the PEFT deployment loader") from error
    if transformers_module is None:
        try:
            import transformers as transformers_module  # type: ignore[import-not-found]
        except ImportError as error:
            raise ModelLoadError("Transformers is required for the PEFT deployment loader") from error
    if peft_module is None:
        try:
            import peft as peft_module  # type: ignore[import-not-found]
        except ImportError as error:
            raise ModelLoadError(
                "PEFT is required for the accepted live adapter; install the optional 'model' extra"
            ) from error
    return torch_module, transformers_module, peft_module


def _adapter_directory(adapter_path: Path) -> Path:
    """Resolve either an adapter directory or its safetensors file."""

    if adapter_path.suffix == ".safetensors":
        return adapter_path.parent
    return adapter_path


class PeftTransformersLoader:
    """Load one immutable BF16 base plus one PEFT adapter.

    ``__call__`` is intended for :meth:`LiveCandidateRuntime.from_loader` and
    is the only place where model components are loaded.  Tests may inject
    module-like fakes through the optional constructor arguments; production
    deployment leaves them unset and uses the installed packages.
    """

    def __init__(
        self,
        *,
        base_model_dir: Path | str,
        adapter_path: Path | str,
        torch_module: Any | None = None,
        transformers_module: Any | None = None,
        peft_module: Any | None = None,
    ) -> None:
        self.base_model_dir = Path(base_model_dir)
        self.adapter_path = Path(adapter_path)
        self.torch_module = torch_module
        self.transformers_module = transformers_module
        self.peft_module = peft_module

    def __call__(self, profile: ModelProfile) -> TransformersModelRuntime:
        if not isinstance(profile, ModelProfile):
            raise TypeError("profile must be a ModelProfile")
        if profile.dtype != "bfloat16":
            raise ModelLoadError("the WORLD v0 live loader requires BF16 inference")
        if not self.base_model_dir.is_dir():
            raise ModelLoadError(f"base model directory is missing: {self.base_model_dir}")
        if self.adapter_path.suffix == ".safetensors" and not self.adapter_path.is_file():
            raise ModelLoadError(f"adapter file is missing: {self.adapter_path}")
        adapter_directory = _adapter_directory(self.adapter_path)
        if not adapter_directory.is_dir():
            raise ModelLoadError(f"adapter directory is missing: {adapter_directory}")

        torch_module, transformers_module, peft_module = _optional_modules(
            self.torch_module,
            self.transformers_module,
            self.peft_module,
        )
        try:
            tokenizer = transformers_module.AutoTokenizer.from_pretrained(
                str(self.base_model_dir),
                local_files_only=True,
                trust_remote_code=False,
            )
            _verify_loaded_tokenizer(tokenizer)
            model_loader = transformers_module.AutoModelForCausalLM
            model_kwargs: dict[str, Any] = {
                "local_files_only": True,
                "trust_remote_code": False,
            }
            transformers_major = int(
                str(getattr(transformers_module, "__version__", "4")).split(".", 1)[0]
            )
            dtype_key = "dtype" if transformers_major >= 5 else "torch_dtype"
            model_kwargs[dtype_key] = _dtype_value(torch_module, "bfloat16")
            base_model = model_loader.from_pretrained(
                str(self.base_model_dir),
                **model_kwargs,
            )
            model = peft_module.PeftModel.from_pretrained(
                base_model,
                str(adapter_directory),
                is_trainable=False,
                local_files_only=True,
            )
            if profile.device != "auto":
                model = model.to(profile.device)
            model.eval()
            for parameter in model.parameters():
                if hasattr(parameter, "requires_grad_"):
                    parameter.requires_grad_(False)
                elif hasattr(parameter, "requires_grad"):
                    parameter.requires_grad = False
            if any(getattr(parameter, "requires_grad", False) for parameter in model.parameters()):
                raise ModelLoadError("PEFT live runtime parameters must be frozen")
        except ModelLoadError:
            raise
        except Exception as error:
            raise ModelLoadError(
                f"failed to load BF16 PEFT runtime from {self.base_model_dir!s}"
            ) from error
        return TransformersModelRuntime.from_components(
            profile,
            tokenizer=tokenizer,
            model=model,
            torch_module=torch_module,
        )


__all__ = ["PeftTransformersLoader"]
