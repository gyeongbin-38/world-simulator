from __future__ import annotations

from types import SimpleNamespace

import pytest

from alifelm.model.p2_d3_adapter_scale import lora_layer_scale, transformer_layer_id
from alifelm.model.transformers_backend import GenerationError


class FakeLora:
    def __init__(self, value: float):
        self.scaling = {"default": value}
        self.lora_A = {"default": object()}


class FakeModel:
    def __init__(self):
        self.l9 = FakeLora(2.0)
        self.l10 = FakeLora(3.0)
        self.l8 = FakeLora(5.0)
        self.other = SimpleNamespace(scaling={"default": 7.0})

    def named_modules(self):
        return iter((
            ("base_model.model.model.layers.9.self_attn.q_proj", self.l9),
            ("base_model.model.model.layers.10.mlp.down_proj", self.l10),
            ("base_model.model.model.layers.8.self_attn.q_proj", self.l8),
            ("base_model.model.model.layers.9.not_lora", self.other),
        ))


def test_transformer_layer_id_matches_olmo_style_names():
    assert transformer_layer_id("base_model.model.model.layers.9.self_attn.q_proj") == 9
    assert transformer_layer_id("transformer.h.10.attn") == 10
    assert transformer_layer_id("model.embed_tokens") is None


def test_layer_scale_changes_only_requested_lora_and_restores():
    model = FakeModel()
    with lora_layer_scale(model, {9: 0.5, 10: 0.0}) as applied:
        assert model.l9.scaling["default"] == 1.0
        assert model.l10.scaling["default"] == 0.0
        assert model.l8.scaling["default"] == 5.0
        assert model.other.scaling["default"] == 7.0
        assert applied.matched_modules_by_layer == ((9, 1), (10, 1))
    assert model.l9.scaling["default"] == 2.0
    assert model.l10.scaling["default"] == 3.0


def test_layer_scale_restores_after_exception():
    model = FakeModel()
    with pytest.raises(RuntimeError):
        with lora_layer_scale(model, {9: 0.25, 10: 0.75}):
            assert model.l9.scaling["default"] == 0.5
            assert model.l10.scaling["default"] == 2.25
            raise RuntimeError("boom")
    assert model.l9.scaling["default"] == 2.0
    assert model.l10.scaling["default"] == 3.0


def test_layer_scale_fails_closed_if_requested_layer_has_no_lora_modules():
    model = FakeModel()
    with pytest.raises(GenerationError):
        with lora_layer_scale(model, {9: 0.5, 11: 0.5}):
            pass
    assert model.l9.scaling["default"] == 2.0
