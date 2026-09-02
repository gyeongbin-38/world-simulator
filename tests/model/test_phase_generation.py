import pytest

from alifelm.model.phase_generation import phase_generation_boundary_token_ids
from alifelm.model.profile import ModelProfile
from alifelm.model.transformers_backend import GenerationError, TransformersModelRuntime
from alifelm.model.treatments import I3_CONDITIONAL_TYPED_CODEC


class _Tokenizer:
    def encode(self, text, *, add_special_tokens=False):
        del add_special_tokens
        return [ord(char) for char in text]


class _Model:
    def generate(self, **kwargs):
        raise AssertionError(kwargs)


def _runtime():
    profile = ModelProfile(
        profile_id="P2_TEST_PROFILE",
        profile_version="1.0.0",
        model_identifier="local-base",
        model_revision="revision",
        model_digest="0" * 64,
        tokenizer_identifier="local-tokenizer",
        tokenizer_revision="revision",
        tokenizer_digest="1" * 64,
        model_class="AUTO_CAUSAL_LM",
        generation_policy_id="P2_TEST_POLICY",
        device="auto",
        dtype="bfloat16",
        adapter_ref=None,
        trust_remote_code=False,
        add_special_tokens=True,
    )
    return TransformersModelRuntime.from_components(
        profile,
        tokenizer=_Tokenizer(),
        model=_Model(),
        torch_module=None,
    )


def test_p2_boundary_is_exact_i3_suffix_and_token_aligned():
    suffix = I3_CONDITIONAL_TYPED_CODEC.completion_suffix.encode("utf-8")
    context = b"Canonical visible state follows.\nSelf handle: A1\n"
    context_ids, prefix_ids, combined_ids = phase_generation_boundary_token_ids(
        _runtime(), context + suffix
    )
    assert combined_ids == context_ids + prefix_ids
    assert prefix_ids == tuple(ord(char) for char in suffix.decode("utf-8"))


def test_p2_boundary_fails_closed_without_exact_i3_suffix():
    with pytest.raises(GenerationError, match="frozen I3 phase boundary"):
        phase_generation_boundary_token_ids(_runtime(), b"context only")
