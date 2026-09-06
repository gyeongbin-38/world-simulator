from dataclasses import dataclass

import pytest

from alifelm.model.p2_d2_cache_patch import transplant_cache_layers
from alifelm.model.p2_d4_cache_component_patch import transplant_cache_components


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


def test_k_only_patch_replaces_key_and_preserves_target_value():
    base = make_cache(0)
    fa = make_cache(100)
    before_base = values(base)
    before_fa = values(fa)

    patched = transplant_cache_components(fa, base, (9, 10), "K")
    observed = values(patched)

    for layer in range(16):
        expected = (
            (before_base[layer][0], before_fa[layer][1])
            if layer in {9, 10}
            else before_fa[layer]
        )
        assert observed[layer] == expected

    assert values(base) == before_base
    assert values(fa) == before_fa
    assert patched is not base and patched is not fa


def test_v_only_patch_replaces_value_and_preserves_target_key():
    base = make_cache(0)
    fa = make_cache(100)
    before_base = values(base)
    before_fa = values(fa)

    patched = transplant_cache_components(fa, base, (9, 10), "V")
    observed = values(patched)

    for layer in range(16):
        expected = (
            (before_fa[layer][0], before_base[layer][1])
            if layer in {9, 10}
            else before_fa[layer]
        )
        assert observed[layer] == expected

    assert values(base) == before_base
    assert values(fa) == before_fa


def test_k_then_v_composition_matches_d2_full_kv_transplant():
    base = make_cache(0)
    fa = make_cache(100)

    k_only = transplant_cache_components(fa, base, (9, 10), "K")
    composed = transplant_cache_components(k_only, base, (9, 10), "V")
    full_kv = transplant_cache_layers(fa, base, (9, 10))

    assert values(composed) == values(full_kv)


def test_self_donor_component_patch_is_value_noop():
    base = make_cache(0)
    for component in ("K", "V"):
        patched = transplant_cache_components(base, base, (9, 10), component)
        assert values(patched) == values(base)
        assert patched is not base


def test_modern_component_patch_preserves_cache_metadata():
    base = make_modern_cache(0)
    fa = make_modern_cache(100)
    before_base = modern_values(base)
    before_fa = modern_values(fa)

    patched = transplant_cache_components(fa, base, (9,), "K")

    for layer in range(16):
        expected = (
            (before_base[layer][0], before_fa[layer][1])
            if layer == 9
            else before_fa[layer]
        )
        assert modern_values(patched)[layer] == expected

    assert patched.cache_marker == "preserve-me"
    assert [layer.marker for layer in patched.layers] == [f"layer-{i}" for i in range(16)]
    assert modern_values(base) == before_base
    assert modern_values(fa) == before_fa


def test_component_patch_rejects_invalid_component_and_layers():
    base = make_cache(0)
    fa = make_cache(100)

    with pytest.raises(ValueError):
        transplant_cache_components(fa, base, (9,), "KV")
    with pytest.raises(ValueError):
        transplant_cache_components(fa, base, (), "K")
    with pytest.raises(ValueError):
        transplant_cache_components(fa, base, (16,), "V")
