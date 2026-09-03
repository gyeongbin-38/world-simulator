"""D1-compatible scoring from supplied WORLD-prefill caches for P2-D2."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
import math
from typing import Any

from alifelm.context import DEFAULT_ACTION_PRESENTATION

from . import p2_d1_boundary as d1
from .p2_d2_cache_patch import cache_signature, validate_cache_pair
from .p2_hardening import stable_allowed_argmax
from .phase_generation import phase_generation_boundary_token_ids
from .phase_scoring import adapter_state, clone_past_key_values
from .transformers_backend import GenerationError, TransformersModelRuntime
from .treatments import build_transformers_constraint, forced_action_codec_json_schema


D2_SCREEN_ACTIONS = ("WAIT", "SEND")


@dataclass(frozen=True, slots=True)
class D2PrefillCaches:
    context_token_ids: tuple[int, ...]
    prefix_token_ids: tuple[int, ...]
    combined_token_ids: tuple[int, ...]
    base_cache: Any
    fa_cache: Any
    cache_signature: tuple[tuple[Any, ...], ...]
    world_prefill_forward_count: int


@dataclass(frozen=True, slots=True)
class D2CacheScoreResult:
    actions_scored: tuple[str, ...]
    context_token_ids: tuple[int, ...]
    prefix_token_ids: tuple[int, ...]
    combined_token_ids: tuple[int, ...]
    common_prefix_token_ids: tuple[int, ...]
    divergence_step: int
    selector_prefix_forward_count: int
    common_prefix_forward_count: int
    branch_continuation_forward_count: int
    branch_scores: tuple[d1.D1BranchScore, ...]

    def total_scores(self) -> dict[str, float]:
        return {score.internal_action: score.total_log_probability for score in self.branch_scores}

    def mean_scores(self) -> dict[str, float]:
        return {score.internal_action: score.mean_log_probability for score in self.branch_scores}

    def wait_send_total_gap(self) -> float:
        scores = self.total_scores()
        return scores["WAIT"] - scores["SEND"]

    def wait_send_mean_gap(self) -> float:
        scores = self.mean_scores()
        return scores["WAIT"] - scores["SEND"]


def build_prefill_caches(runtime: TransformersModelRuntime, *, rendered_input: bytes) -> D2PrefillCaches:
    """Compute exactly one BASE and one FA WORLD-prefill cache."""

    if not isinstance(runtime, TransformersModelRuntime):
        raise TypeError("runtime must be a TransformersModelRuntime")
    torch_module = runtime.torch_module
    if torch_module is None:
        raise GenerationError("P2-D2 requires PyTorch")
    context_ids, prefix_ids, combined_ids = phase_generation_boundary_token_ids(runtime, rendered_input)
    device = runtime.profile.device
    context_tensor = d1._tensor_ids(torch_module, context_ids, device=device)
    attention = d1._ones(torch_module, len(context_ids), device=device)
    inference = torch_module.inference_mode() if hasattr(torch_module, "inference_mode") else nullcontext()
    with inference:
        with adapter_state(runtime.model, False):
            base_output = d1._forward(runtime.model, input_ids=context_tensor, attention_mask=attention)
        base_cache = getattr(base_output, "past_key_values", None)
        if base_cache is None:
            raise GenerationError("P2-D2 BASE prefill did not return past_key_values")
        base_cache = clone_past_key_values(base_cache)

        with adapter_state(runtime.model, True):
            fa_output = d1._forward(runtime.model, input_ids=context_tensor, attention_mask=attention)
        fa_cache = getattr(fa_output, "past_key_values", None)
        if fa_cache is None:
            raise GenerationError("P2-D2 FA prefill did not return past_key_values")
        fa_cache = clone_past_key_values(fa_cache)

    signature = validate_cache_pair(base_cache, fa_cache)
    return D2PrefillCaches(
        context_token_ids=context_ids,
        prefix_token_ids=prefix_ids,
        combined_token_ids=combined_ids,
        base_cache=base_cache,
        fa_cache=fa_cache,
        cache_signature=signature,
        world_prefill_forward_count=2,
    )


def score_i3_from_prefill_cache(
    runtime: TransformersModelRuntime,
    *,
    rendered_input: bytes,
    phase_a_cache: Any,
    actions_to_score: tuple[str, ...] = d1.D1_ACTION_ORDER,
) -> D2CacheScoreResult:
    """Apply the frozen BASE selector to a supplied WORLD-prefill cache.

    All five D1 schemas still determine the common-prefix divergence point even
    when screening persists only WAIT and SEND continuations.
    """

    if not isinstance(runtime, TransformersModelRuntime):
        raise TypeError("runtime must be a TransformersModelRuntime")
    expected_subset = tuple(action for action in d1.D1_ACTION_ORDER if action in actions_to_score)
    if not actions_to_score or expected_subset != actions_to_score:
        raise ValueError("D2 actions_to_score must be a frozen-order subset")
    if "WAIT" not in actions_to_score or "SEND" not in actions_to_score:
        raise ValueError("D2 scoring must include WAIT and SEND")

    torch_module = runtime.torch_module
    if torch_module is None:
        raise GenerationError("P2-D2 requires PyTorch")
    cache_signature(phase_a_cache)
    context_ids, prefix_ids, combined_ids = phase_generation_boundary_token_ids(runtime, rendered_input)
    device = runtime.profile.device
    prefix_tensor = d1._tensor_ids(torch_module, prefix_ids, device=device)
    constraints = {
        action: build_transformers_constraint(runtime.tokenizer, schema=forced_action_codec_json_schema(action))
        for action in d1.D1_ACTION_ORDER
    }
    inference = torch_module.inference_mode() if hasattr(torch_module, "inference_mode") else nullcontext()

    with inference:
        with adapter_state(runtime.model, False):
            prefix_output = d1._forward(
                runtime.model,
                input_ids=prefix_tensor,
                attention_mask=d1._ones(torch_module, len(combined_ids), device=device),
                past_key_values=clone_past_key_values(phase_a_cache),
            )
        common_cache = getattr(prefix_output, "past_key_values", None)
        if common_cache is None:
            raise GenerationError("P2-D2 selector prefix did not return past_key_values")
        common_logits = prefix_output.logits[0, -1]

        common_generated: list[int] = []
        common_forwards = 0
        divergence_step: int | None = None
        for step in range(d1.D1_MAX_COMMON_PREFIX_TOKENS + 1):
            sent = d1._tensor_ids(torch_module, combined_ids + tuple(common_generated), device=device)[0]
            legal = {action: d1._allowed(constraints[action], sent) for action in d1.D1_ACTION_ORDER}
            if not d1.legal_sets_identical(legal):
                divergence_step = step
                break
            if step >= d1.D1_MAX_COMMON_PREFIX_TOKENS:
                raise GenerationError("P2-D2 action branches did not diverge within guard")
            token_id = stable_allowed_argmax(torch_module, common_logits, list(legal[d1.D1_ACTION_ORDER[0]]))
            common_generated.append(token_id)
            with adapter_state(runtime.model, False):
                output = d1._forward(
                    runtime.model,
                    input_ids=d1._tensor_ids(torch_module, (token_id,), device=device),
                    attention_mask=d1._ones(torch_module, len(combined_ids) + len(common_generated), device=device),
                    past_key_values=common_cache,
                )
            common_forwards += 1
            common_cache = getattr(output, "past_key_values", None)
            if common_cache is None:
                raise GenerationError("P2-D2 common-prefix continuation lost cache")
            common_logits = output.logits[0, -1]

        if divergence_step is None:
            raise GenerationError("P2-D2 could not locate action divergence")

        raw: list[tuple[str, str, tuple[int, ...], float]] = []
        branch_forwards = 0
        common_tuple = tuple(common_generated)
        for target in actions_to_score:
            cache = clone_past_key_values(common_cache)
            logits = common_logits
            generated: list[int] = []
            survivors = d1.D1_ACTION_ORDER
            total = None
            for _ in range(d1.D1_MAX_BRANCH_TOKENS):
                sent = d1._tensor_ids(torch_module, combined_ids + common_tuple + tuple(generated), device=device)[0]
                legal = {action: d1._allowed(constraints[action], sent) for action in survivors}
                allowed = legal.get(target)
                if allowed is None:
                    raise GenerationError("P2-D2 target branch became impossible")
                token_id = stable_allowed_argmax(torch_module, logits, list(allowed))
                lp = torch_module.log_softmax(logits, dim=-1)[token_id]
                total = lp if total is None else total + lp
                generated.append(token_id)
                survivors = d1.survivors_after_token(survivors, legal, token_id)
                if target not in survivors:
                    raise GenerationError("P2-D2 chosen token excluded target branch")
                if len(survivors) == 1:
                    if survivors[0] != target:
                        raise GenerationError("P2-D2 unique survivor is not target")
                    break
                with adapter_state(runtime.model, False):
                    output = d1._forward(
                        runtime.model,
                        input_ids=d1._tensor_ids(torch_module, (token_id,), device=device),
                        attention_mask=d1._ones(
                            torch_module,
                            len(combined_ids) + len(common_tuple) + len(generated),
                            device=device,
                        ),
                        past_key_values=cache,
                    )
                branch_forwards += 1
                cache = getattr(output, "past_key_values", None)
                if cache is None:
                    raise GenerationError("P2-D2 branch continuation lost cache")
                logits = output.logits[0, -1]
            else:
                raise GenerationError("P2-D2 branch did not become unique within guard")

            if total is None or not generated:
                raise GenerationError("P2-D2 branch score is empty")
            total_value = float(total.detach().cpu())
            if not math.isfinite(total_value):
                raise GenerationError("P2-D2 produced non-finite branch score")
            raw.append((target, DEFAULT_ACTION_PRESENTATION.entry(target).model_label, tuple(generated), total_value))

    return D2CacheScoreResult(
        actions_scored=actions_to_score,
        context_token_ids=context_ids,
        prefix_token_ids=prefix_ids,
        combined_token_ids=combined_ids,
        common_prefix_token_ids=tuple(common_generated),
        divergence_step=divergence_step,
        selector_prefix_forward_count=1,
        common_prefix_forward_count=common_forwards,
        branch_continuation_forward_count=branch_forwards,
        branch_scores=d1._rank(raw),
    )


__all__ = [
    "D2_SCREEN_ACTIONS",
    "D2PrefillCaches",
    "D2CacheScoreResult",
    "build_prefill_caches",
    "score_i3_from_prefill_cache",
]
