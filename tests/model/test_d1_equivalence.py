from contextlib import contextmanager
from types import SimpleNamespace

import torch

from alifelm.model.action_diagnostics import ACTION_SCORE_PREFIX
from alifelm.model.d1_equivalence import (
    compare_score_records,
    peft_disabled_state,
    score_cached_labels,
    summarize_absolute,
)
from alifelm.model.p1b_metrics import ACTION_LABELS
from alifelm.model.profile import ModelProfile
from alifelm.model.transformers_backend import TransformersModelRuntime


class FakeTokenizer:
    def __init__(self):
        alphabet = sorted(set(ACTION_SCORE_PREFIX.decode("utf-8") + "".join(ACTION_LABELS) + "CTX\n"))
        self.ids = {char: index + 1 for index, char in enumerate(alphabet)}

    def encode(self, text, add_special_tokens=False):
        values = [self.ids[char] for char in text]
        return ([99] + values) if add_special_tokens else values


class FakeBareModel:
    def __init__(self, vocab_size=128):
        self.vocab_size = vocab_size
        self.prefill_calls = 0

    def __call__(self, *, input_ids, attention_mask, use_cache, past_key_values=None):
        del attention_mask, use_cache
        batch, length = input_ids.shape
        logits = torch.zeros((batch, length, self.vocab_size), dtype=torch.float32)
        logits[..., 4] = 0.5
        prior = 0 if past_key_values is None else int(past_key_values[0].item())
        if past_key_values is None:
            self.prefill_calls += 1
        return SimpleNamespace(
            logits=logits,
            past_key_values=(torch.tensor(prior + length),),
        )


class FakePeftModel(FakeBareModel):
    def __init__(self, vocab_size=128):
        super().__init__(vocab_size=vocab_size)
        self.adapter_enabled = True

    @contextmanager
    def disable_adapter(self):
        previous = self.adapter_enabled
        self.adapter_enabled = False
        try:
            yield
        finally:
            self.adapter_enabled = previous

    def __call__(self, **kwargs):
        output = super().__call__(**kwargs)
        if self.adapter_enabled:
            output.logits[..., 4] += 2.0
        return output


def _profile():
    return ModelProfile(
        profile_id="D1_TEST",
        profile_version="1.0.0",
        model_identifier="local/test",
        model_revision="rev",
        model_digest=None,
        tokenizer_identifier="local/test",
        tokenizer_revision="rev",
        tokenizer_digest=None,
        model_class="AUTO_CAUSAL_LM",
        generation_policy_id="D1_TEST_POLICY",
        device="cpu",
        dtype="float32",
        adapter_ref=None,
        trust_remote_code=False,
        add_special_tokens=True,
    )


def _runtime(model):
    return TransformersModelRuntime.from_components(
        _profile(), tokenizer=FakeTokenizer(), model=model, torch_module=torch
    )


def test_bare_cached_scorer_requires_no_peft_wrapper_and_prefills_once():
    model = FakeBareModel()
    result = score_cached_labels(
        _runtime(model), rendered_input=b"CTX\n", peft_disabled=False
    )
    assert tuple(score.model_label for score in result.scores) == ACTION_LABELS
    assert {score.rank for score in result.scores} == {1, 2, 3, 4, 5}
    assert result.prefill_forward_count == 1
    assert result.selector_prefix_forward_count == 1
    assert model.prefill_calls == 1


def test_peft_disabled_cached_scorer_restores_adapter_state():
    model = FakePeftModel()
    disabled = score_cached_labels(
        _runtime(model), rendered_input=b"CTX\n", peft_disabled=True
    )
    enabled = score_cached_labels(
        _runtime(model), rendered_input=b"CTX\n", peft_disabled=False
    )
    assert model.adapter_enabled is True
    assert disabled.as_record() != enabled.as_record()


def test_peft_disabled_state_fails_only_when_requested():
    bare = FakeBareModel()
    with peft_disabled_state(bare, False):
        pass
    try:
        with peft_disabled_state(bare, True):
            pass
    except Exception as error:
        assert "disable_adapter" in str(error)
    else:
        raise AssertionError("PEFT-disabled path must fail closed on bare model")


def _record(offset=0.0, rank_shift=False):
    rows = []
    for index, label in enumerate(ACTION_LABELS, 1):
        rows.append(
            {
                "model_label": label,
                "token_ids": [index, index + 10],
                "total_log_probability": -float(index) + offset,
                "mean_log_probability": (-float(index) + offset) / 2.0,
                "rank": (6 - index) if rank_shift else index,
            }
        )
    return {"scores": rows}


def test_compare_score_records_reports_matched_absolute_magnitudes():
    result = compare_score_records([_record()], [_record(offset=0.25)])
    assert result["comparisons"] == 5
    assert result["token_ids_exact"] is True
    assert result["rank_exact"] is True
    assert result["total"]["max"] == 0.25
    assert result["mean"]["max"] == 0.125
    assert result["total"]["nonzero_fraction"] == 1.0


def test_summarize_absolute_keeps_zero_fraction_and_sign_invariant():
    summary = summarize_absolute([0.0, -2.0, 1.0, 0.0])
    assert summary.maximum == 2.0
    assert summary.median == 0.5
    assert summary.mean == 0.75
    assert summary.nonzero_fraction == 0.5
