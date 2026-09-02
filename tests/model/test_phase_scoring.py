from contextlib import contextmanager
from types import SimpleNamespace

import torch

from alifelm.model.action_diagnostics import ACTION_SCORE_PREFIX
from alifelm.model.p1b_metrics import ACTION_LABELS
from alifelm.model.phase_scoring import phase_boundary_token_ids, score_phase_switched_labels
from alifelm.model.profile import ModelProfile
from alifelm.model.transformers_backend import GenerationError, TransformersModelRuntime


class FakeTokenizer:
    def __init__(self):
        alphabet = sorted(
            set(ACTION_SCORE_PREFIX.decode("utf-8") + "".join(ACTION_LABELS) + "CTX\n")
        )
        self.ids = {char: index + 1 for index, char in enumerate(alphabet)}

    def encode(self, text, add_special_tokens=False):
        values = [self.ids[char] for char in text]
        if add_special_tokens:
            return [99] + values
        return values


class BoundaryMergingTokenizer(FakeTokenizer):
    def encode(self, text, add_special_tokens=False):
        values = super().encode(text, add_special_tokens=add_special_tokens)
        prefix = ACTION_SCORE_PREFIX.decode("utf-8")
        # Simulate a tokenizer merge that occurs only when the WORLD context
        # and selector prefix are concatenated. The standalone context and
        # standalone prefix tokenizations remain unchanged.
        if text.startswith("CTX\n") and text.endswith(prefix):
            context_length = len(super().encode("CTX\n", add_special_tokens=add_special_tokens))
            return values[: context_length - 1] + [98] + values[context_length + 1 :]
        return values


class FakePeftModel:
    def __init__(self, *, signal_token_id, vocab_size=128):
        self.vocab_size = vocab_size
        self.signal_token_id = signal_token_id
        self.adapter_enabled = True
        self.prefill_calls = 0
        self.selector_prefix_calls = 0

    @contextmanager
    def disable_adapter(self):
        previous = self.adapter_enabled
        self.adapter_enabled = False
        try:
            yield
        finally:
            self.adapter_enabled = previous

    def __call__(self, *, input_ids, attention_mask, use_cache, past_key_values=None):
        del attention_mask, use_cache
        batch, length = input_ids.shape
        logits = torch.zeros((batch, length, self.vocab_size), dtype=torch.float32)
        # Shift one token that is guaranteed to occur in the frozen action
        # labels. This proves adapter phase switching changes model scores
        # without encoding a preferred WORLD action in the fake.
        logits[..., self.signal_token_id] = 1.0 if self.adapter_enabled else -1.0
        prior_len = 0 if past_key_values is None else int(past_key_values[0].item())
        if past_key_values is None:
            self.prefill_calls += 1
        else:
            self.selector_prefix_calls += 1
        cache = (torch.tensor(prior_len + length),)
        return SimpleNamespace(logits=logits, past_key_values=cache)

    def generate(self, *args, **kwargs):  # pragma: no cover - runtime contract only
        raise NotImplementedError


def _profile():
    return ModelProfile(
        profile_id="P1C_TEST",
        profile_version="1.0.0",
        model_identifier="local/test",
        model_revision="rev",
        model_digest=None,
        tokenizer_identifier="local/test",
        tokenizer_revision="rev",
        tokenizer_digest=None,
        model_class="AUTO_CAUSAL_LM",
        generation_policy_id="P1C_TEST_POLICY",
        device="cpu",
        dtype="float32",
        adapter_ref=None,
        trust_remote_code=False,
        add_special_tokens=True,
    )


def _runtime(tokenizer=None):
    tokenizer = tokenizer or FakeTokenizer()
    return TransformersModelRuntime.from_components(
        _profile(),
        tokenizer=tokenizer,
        model=FakePeftModel(signal_token_id=tokenizer.ids["D"]),
        torch_module=torch,
    )


def test_phase_boundary_matches_combined_tokenization():
    runtime = _runtime()
    context, prefix, combined = phase_boundary_token_ids(runtime, b"CTX\n")
    assert combined == context + prefix
    assert prefix


def test_phase_boundary_fails_closed_on_cross_boundary_retokenization():
    runtime = _runtime(BoundaryMergingTokenizer())
    try:
        phase_boundary_token_ids(runtime, b"CTX\n")
    except GenerationError as error:
        assert "not token-aligned" in str(error)
    else:
        raise AssertionError("cross-boundary retokenization must fail closed")


def test_phase_switch_scorer_scores_frozen_labels_and_restores_adapter():
    runtime = _runtime()
    result = score_phase_switched_labels(
        runtime,
        rendered_input=b"CTX\n",
        prefill_adapter=True,
        selector_adapter=False,
    )
    assert tuple(score.model_label for score in result.scores) == ACTION_LABELS
    assert {score.rank for score in result.scores} == {1, 2, 3, 4, 5}
    assert all(score.token_ids for score in result.scores)
    assert result.prefill_forward_count == 1
    assert result.selector_prefix_forward_count == 1
    assert runtime.model.adapter_enabled is True


def test_phase_switch_scorer_prefills_world_context_once_per_measurement():
    runtime = _runtime()
    before = runtime.model.prefill_calls
    score_phase_switched_labels(
        runtime,
        rendered_input=b"CTX\n",
        prefill_adapter=False,
        selector_adapter=True,
    )
    assert runtime.model.prefill_calls - before == 1


def test_phase_conditions_can_change_scores_without_changing_tokenization():
    runtime = _runtime()
    c00 = score_phase_switched_labels(
        runtime,
        rendered_input=b"CTX\n",
        prefill_adapter=False,
        selector_adapter=False,
    )
    c11 = score_phase_switched_labels(
        runtime,
        rendered_input=b"CTX\n",
        prefill_adapter=True,
        selector_adapter=True,
    )
    assert c00.combined_token_ids == c11.combined_token_ids
    assert c00.totals() != c11.totals()
