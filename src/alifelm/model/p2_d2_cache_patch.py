"""Protocol-bound KV-cache transplant utilities for WORLD P2-D2."""

from __future__ import annotations

import copy
from typing import Any, Iterable

from .transformers_backend import GenerationError


D2_EXPECTED_CACHE_LAYERS = 16


def _tensor_signature(value: Any) -> tuple[Any, ...]:
    shape = tuple(getattr(value, "shape", ()))
    dtype = str(getattr(value, "dtype", None))
    device = str(getattr(value, "device", None))
    if not shape:
        raise GenerationError("D2 cache tensor has no usable shape")
    return shape, dtype, device


def _clone_tensor(value: Any) -> Any:
    clone = getattr(value, "clone", None)
    if not callable(clone):
        raise GenerationError("D2 cache entry is not cloneable")
    return clone()


def _layer_object_pairs(cache: Any) -> tuple[tuple[Any, Any], ...] | None:
    """Expose Transformers v5 Cache.layers K/V tensors without mutating cache state."""

    raw_layers = getattr(cache, "layers", None)
    if not isinstance(raw_layers, (tuple, list)):
        return None
    layers: list[tuple[Any, Any]] = []
    for layer in raw_layers:
        key = getattr(layer, "keys", None)
        value = getattr(layer, "values", None)
        if key is None or value is None:
            return None
        layers.append((key, value))
    return tuple(layers)


def _legacy_cache(cache: Any) -> tuple[tuple[tuple[Any, Any], ...], str, type[Any] | None]:
    """Normalize supported legacy and modern HF cache representations to K/V pairs."""

    converter = getattr(cache, "to_legacy_cache", None)
    if callable(converter):
        raw = converter()
        kind = "CACHE_CLASS"
        cache_type: type[Any] | None = type(cache)
    elif isinstance(cache, tuple):
        raw = cache
        kind = "LEGACY_TUPLE"
        cache_type = None
    elif isinstance(cache, list):
        raw = cache
        kind = "LEGACY_LIST"
        cache_type = None
    else:
        layer_pairs = _layer_object_pairs(cache)
        if layer_pairs is None:
            raise GenerationError("D2 unsupported past_key_values representation")
        raw = layer_pairs
        kind = "LAYER_OBJECT_CACHE"
        cache_type = type(cache)

    if not isinstance(raw, (tuple, list)):
        raise GenerationError("D2 cache conversion did not produce a sequence")
    layers: list[tuple[Any, Any]] = []
    for layer in raw:
        if not isinstance(layer, (tuple, list)) or len(layer) != 2:
            raise GenerationError("D2 requires exactly one key/value pair per cache layer")
        layers.append((layer[0], layer[1]))
    return tuple(layers), kind, cache_type


def _rebuild_cache(
    layers: tuple[tuple[Any, Any], ...],
    kind: str,
    cache_type: type[Any] | None,
    *,
    template: Any | None = None,
) -> Any:
    if kind == "LEGACY_TUPLE":
        return tuple(layers)
    if kind == "LEGACY_LIST":
        return list(layers)
    if kind == "LAYER_OBJECT_CACHE":
        if template is None or cache_type is None or type(template) is not cache_type:
            raise GenerationError("D2 modern cache rebuild requires the exact target cache type")
        try:
            rebuilt = copy.deepcopy(template)
        except Exception as error:
            raise GenerationError("D2 failed to clone modern cache representation") from error
        rebuilt_layers = getattr(rebuilt, "layers", None)
        if not isinstance(rebuilt_layers, (tuple, list)) or len(rebuilt_layers) != len(layers):
            raise GenerationError("D2 modern cache clone changed layer structure")
        for layer, (key, value) in zip(rebuilt_layers, layers):
            if not hasattr(layer, "keys") or not hasattr(layer, "values"):
                raise GenerationError("D2 modern cache layer does not expose mutable keys/values")
            layer.keys = key
            layer.values = value
        return rebuilt
    if kind != "CACHE_CLASS" or cache_type is None:
        raise GenerationError("D2 cannot rebuild cache representation")
    builder = getattr(cache_type, "from_legacy_cache", None)
    if not callable(builder):
        raise GenerationError("D2 cache class lacks from_legacy_cache()")
    try:
        return builder(tuple(layers))
    except Exception as error:
        raise GenerationError("D2 failed to rebuild cache class from legacy K/V tensors") from error


def cache_signature(cache: Any, expected_layers: int = D2_EXPECTED_CACHE_LAYERS) -> tuple[tuple[Any, ...], ...]:
    layers, _, _ = _legacy_cache(cache)
    if len(layers) != expected_layers:
        raise GenerationError(f"D2 expected {expected_layers} cache layers but observed {len(layers)}")
    return tuple((_tensor_signature(key), _tensor_signature(value)) for key, value in layers)


def validate_cache_pair(base_cache: Any, fa_cache: Any, expected_layers: int = D2_EXPECTED_CACHE_LAYERS) -> tuple[tuple[Any, ...], ...]:
    base_layers, base_kind, base_type = _legacy_cache(base_cache)
    fa_layers, fa_kind, fa_type = _legacy_cache(fa_cache)
    if base_kind != fa_kind or base_type is not fa_type:
        raise GenerationError("D2 BASE/FA cache representations differ")
    if len(base_layers) != expected_layers or len(fa_layers) != expected_layers:
        raise GenerationError("D2 BASE/FA cache layer count differs from preregistration")
    signatures: list[tuple[Any, ...]] = []
    for index, ((base_key, base_value), (fa_key, fa_value)) in enumerate(zip(base_layers, fa_layers)):
        base_sig = (_tensor_signature(base_key), _tensor_signature(base_value))
        fa_sig = (_tensor_signature(fa_key), _tensor_signature(fa_value))
        if base_sig != fa_sig:
            raise GenerationError(f"D2 BASE/FA cache signature mismatch at layer {index}")
        signatures.append(base_sig)
    return tuple(signatures)


def transplant_cache_layers(target_cache: Any, donor_cache: Any, layer_indices: Iterable[int], expected_layers: int = D2_EXPECTED_CACHE_LAYERS) -> Any:
    """Return a new target cache with selected full-layer K/V pairs from donor."""

    target_layers, target_kind, target_type = _legacy_cache(target_cache)
    donor_layers, donor_kind, donor_type = _legacy_cache(donor_cache)
    if target_kind != donor_kind or target_type is not donor_type:
        raise GenerationError("D2 target/donor cache representations differ")
    if len(target_layers) != expected_layers or len(donor_layers) != expected_layers:
        raise GenerationError("D2 target/donor cache layer count differs from preregistration")

    selected = tuple(sorted(set(layer_indices)))
    if not selected or any(type(index) is not int for index in selected):
        raise ValueError("D2 patch requires at least one integer layer index")
    if selected[0] < 0 or selected[-1] >= expected_layers:
        raise ValueError("D2 patch layer index is outside the frozen range")

    validate_cache_pair(target_cache, donor_cache, expected_layers)
    selected_set = set(selected)
    rebuilt: list[tuple[Any, Any]] = []
    for index in range(expected_layers):
        key, value = donor_layers[index] if index in selected_set else target_layers[index]
        rebuilt.append((_clone_tensor(key), _clone_tensor(value)))
    return _rebuild_cache(tuple(rebuilt), target_kind, target_type, template=target_cache)


__all__ = [
    "D2_EXPECTED_CACHE_LAYERS",
    "cache_signature",
    "validate_cache_pair",
    "transplant_cache_layers",
]
