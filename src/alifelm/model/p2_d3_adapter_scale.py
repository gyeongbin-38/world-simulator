"""Research-only temporary LoRA scaling for P2-D3.

The intervention multiplies PEFT LoRA scaling metadata for selected transformer
layers inside a context manager and restores the exact original values on exit.
Parameter tensors are never changed.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import re
from typing import Any, Iterator, Mapping

from .transformers_backend import GenerationError


_LAYER_RE = re.compile(r"(?:^|\.)(?:layers|h)\.(\d+)(?:\.|$)")


@dataclass(frozen=True, slots=True)
class LayerScaleApplication:
    layer_scales: tuple[tuple[int, float], ...]
    matched_module_names: tuple[str, ...]
    matched_modules_by_layer: tuple[tuple[int, int], ...]


def transformer_layer_id(module_name: str) -> int | None:
    if not isinstance(module_name, str):
        raise TypeError("module_name must be a string")
    match = _LAYER_RE.search(module_name)
    return None if match is None else int(match.group(1))


def _normalize_layer_scales(layer_scales: Mapping[int, float]) -> dict[int, float]:
    if not layer_scales:
        raise ValueError("P2-D3 requires at least one target layer")
    normalized: dict[int, float] = {}
    for layer, scale in layer_scales.items():
        if type(layer) is not int or not 0 <= layer <= 15:
            raise ValueError("P2-D3 layer IDs must be integers in 0..15")
        value = float(scale)
        if not 0.0 <= value <= 1.0:
            raise ValueError("P2-D3 scale multipliers must be in [0, 1]")
        normalized[layer] = value
    return dict(sorted(normalized.items()))


def _is_lora_scaling_module(module: Any) -> bool:
    scaling = getattr(module, "scaling", None)
    if not isinstance(scaling, dict) or not scaling:
        return False
    return hasattr(module, "lora_A") or hasattr(module, "lora_B")


@contextmanager
def lora_layer_scale(model: Any, layer_scales: Mapping[int, float]) -> Iterator[LayerScaleApplication]:
    """Temporarily multiply LoRA scaling in selected transformer layers.

    All LoRA adapter entries present in a matched module are scaled. Discovery
    happens before mutation, every requested layer must match at least one LoRA
    module, and all original scaling objects are restored even if inference
    raises.
    """

    named_modules = getattr(model, "named_modules", None)
    if not callable(named_modules):
        raise GenerationError("P2-D3 requires model.named_modules()")
    normalized = _normalize_layer_scales(layer_scales)

    targets: list[tuple[str, Any, int]] = []
    counts = {layer: 0 for layer in normalized}
    for name, module in named_modules():
        layer = transformer_layer_id(name)
        if layer not in normalized or not _is_lora_scaling_module(module):
            continue
        targets.append((name, module, layer))
        counts[layer] += 1

    missing = [layer for layer, count in counts.items() if count == 0]
    if missing:
        raise GenerationError(f"P2-D3 found no LoRA scaling modules for layers {missing}")

    originals: list[tuple[dict[str, Any], str, Any]] = []
    try:
        for _, module, layer in targets:
            scaling = module.scaling
            factor = normalized[layer]
            for adapter_name in tuple(scaling):
                original = scaling[adapter_name]
                originals.append((scaling, adapter_name, original))
                try:
                    scaling[adapter_name] = original * factor
                except Exception as error:
                    raise GenerationError("P2-D3 could not apply LoRA scale multiplier") from error
        yield LayerScaleApplication(
            layer_scales=tuple(normalized.items()),
            matched_module_names=tuple(name for name, _, _ in targets),
            matched_modules_by_layer=tuple((layer, counts[layer]) for layer in normalized),
        )
    finally:
        for scaling, adapter_name, original in reversed(originals):
            scaling[adapter_name] = original


__all__ = ["LayerScaleApplication", "lora_layer_scale", "transformer_layer_id"]
