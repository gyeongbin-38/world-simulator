from dataclasses import dataclass

import pytest

from alifelm.model.p2_d2_cache_patch import (
    cache_signature,
    transplant_cache_layers,
    validate_cache_pair,
)
from alifelm.model.transformers_backend import GenerationError


@dataclass
class FakeTensor:
    value: int
    shape: tuple[int, ...] = (1, 2, 3, 4)
    dtype: str = "bfloat16"
    device: str = "cuda:0"

    def clone(self):
        return FakeTensor(self.value, self.shape, self.dtype, self.device)


class FakeCache:
    def __init__(self, layers):
        self.layers = tuple(tuple(layer) for layer in layers)

    def to_legacy_cache(self):
        return self.layers

    @classmethod
    def from_legacy_cache(cls, layers):
        return cls(layers)


class FakeModernLayer:
    def __init__(self, key, value, marker):
        self.keys = key
        self.values = value
        self.marker = marker


class FakeModernCache:
    """Minimal Transformers-v5-style Cache.layers representation."""

    def __init__(self, layers):
        self.layers = list(layers)
        self.cache_marker = "preserve-me"


def make_cache(offset: int, layers: int = 16):
    return FakeCache(
        tuple((FakeTensor(offset + i * 2), FakeTensor(offset + i * 2 + 1)) for i in range(layers))
    )


def make_modern_cache(offset: int, layers: int = 16):
    return FakeModernCache(
        [
            FakeModernLayer(
                FakeTensor(offset + i * 2),
                FakeTensor(offset + i * 2 + 1),
                marker=f"layer-{i}",
            )
            for i in range(layers)
        ]
    )


def values(cache):
    return tuple((key.value, value.value) for key, value in cache.to_legacy_cache())


def modern_values(cache):
    return tuple((layer.keys.value, layer.values.value) for layer in cache.layers)


def test_cache_pair_requires_frozen_16_layer_shape_identity():
    base = make_cache(0)
    fa = make_cache(100)
    signature = validate_cache_pair(base, fa)
    assert len(signature) == 16
    assert cache_signature(base) == cache_signature(fa)


def test_transplant_replaces_only_selected_full_kv_layers_without_source_mutation():
    base = make_cache(0)
    fa = make_cache(100)
    before_base = values(base)
    before_fa = values(fa)

    patched = transplant_cache_layers(fa, base, (1, 4, 9))
    patched_values = values(patched)

    for layer in range(16):
        expected = before_base[layer] if layer in {1, 4, 9} else before_fa[layer]
        assert patched_values[layer] == expected
    assert values(base) == before_base
    assert values(fa) == before_fa
    assert patched is not fa and patched is not base


def test_all_layer_transplant_is_value_equal_to_donor():
    base = make_cache(0)
    fa = make_cache(100)
    rescued = transplant_cache_layers(fa, base, range(16))
    induced = transplant_cache_layers(base, fa, range(16))
    assert values(rescued) == values(base)
    assert values(induced) == values(fa)


def test_self_patch_is_value_noop_but_returns_independent_cache():
    base = make_cache(0)
    patched = transplant_cache_layers(base, base, (3, 7))
    assert values(patched) == values(base)
    assert patched is not base


def test_modern_layer_object_cache_pair_and_transplant():
    base = make_modern_cache(0)
    fa = make_modern_cache(100)
    before_base = modern_values(base)
    before_fa = modern_values(fa)

    signature = validate_cache_pair(base, fa)
    assert len(signature) == 16
    assert cache_signature(base) == cache_signature(fa)

    patched = transplant_cache_layers(fa, base, (1, 4, 9))
    for layer in range(16):
        expected = before_base[layer] if layer in {1, 4, 9} else before_fa[layer]
        assert modern_values(patched)[layer] == expected

    assert modern_values(base) == before_base
    assert modern_values(fa) == before_fa
    assert patched is not base and patched is not fa
    assert patched.cache_marker == "preserve-me"
    assert [layer.marker for layer in patched.layers] == [f"layer-{i}" for i in range(16)]


def test_modern_all_layer_transplant_is_value_equal_to_donor():
    base = make_modern_cache(0)
    fa = make_modern_cache(100)
    rescued = transplant_cache_layers(fa, base, range(16))
    induced = transplant_cache_layers(base, fa, range(16))
    assert modern_values(rescued) == modern_values(base)
    assert modern_values(induced) == modern_values(fa)


def test_patch_rejects_layer_count_and_signature_drift():
    with pytest.raises(GenerationError):
        transplant_cache_layers(make_cache(0, 15), make_cache(100, 15), (0,))

    base = make_cache(0)
    fa = make_cache(100)
    fa.layers[3][0].shape = (1, 2, 9, 4)
    with pytest.raises(GenerationError):
        validate_cache_pair(base, fa)


def test_patch_rejects_invalid_layer_set():
    base = make_cache(0)
    fa = make_cache(100)
    with pytest.raises(ValueError):
        transplant_cache_layers(fa, base, ())
    with pytest.raises(ValueError):
        transplant_cache_layers(fa, base, (16,))
