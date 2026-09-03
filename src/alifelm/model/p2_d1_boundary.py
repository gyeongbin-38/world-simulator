"""Research-only P2-D1 action decision-boundary probe.

This module does not generate an ActionIntent, commit WORLD state, update
weights, calibrate scores, or change the frozen P2 result. It measures raw
counterfactual branch log-probabilities from the exact P2 cached phase topology.
"""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
import math
from typing import Any

from alifelm.context import DEFAULT_ACTION_PRESENTATION

from .p2_hardening import canonical_allowed_tokens, stable_allowed_argmax
from .phase_generation import phase_generation_boundary_token_ids
from .phase_scoring import adapter_state, clone_past_key_values
from .transformers_backend import GenerationError, TransformersModelRuntime
from .treatments import build_transformers_constraint, forced_action_codec_json_schema


D1_ACTION_ORDER = ("WAIT", "SEND", "PROPOSE", "ACCEPT", "REJECT")
D1_MAX_COMMON_PREFIX_TOKENS = 64
D1_MAX_BRANCH_TOKENS = 32


@dataclass(frozen=True, slots=True)
class D1BranchScore:
    internal_action: str
    model_label: str
    token_ids: tuple[int, ...]
    total_log_probability: float
    mean_log_probability: float
    total_rank: int
    mean_rank: int


@dataclass(frozen=True, slots=True)
class D1BoundaryProbeResult:
    prefill_adapter: bool
    selector_adapter: bool
    context_token_ids: tuple[int, ...]
    prefix_token_ids: tuple[int, ...]
    combined_token_ids: tuple[int, ...]
    common_prefix_token_ids: tuple[int, ...]
    divergence_step: int
    phase_boundary_token_aligned: bool
    world_prefill_forward_count: int
    selector_prefix_forward_count: int
    common_prefix_forward_count: int
    branch_continuation_forward_count: int
    world_context_recomputed_after_switch: bool
    branch_scores: tuple[D1BranchScore, ...]

    def total_scores(self) -> dict[str, float]:
        return {score.internal_action: score.total_log_probability for score in self.branch_scores}

    def mean_scores(self) -> dict[str, float]:
        return {score.internal_action: score.mean_log_probability for score in self.branch_scores}

    def total_rank1(self) -> str:
        return next(score.internal_action for score in self.branch_scores if score.total_rank == 1)

    def mean_rank1(self) -> str:
        return next(score.internal_action for score in self.branch_scores if score.mean_rank == 1)

    def nda_total_margin(self) -> float:
        totals = self.total_scores()
        return totals["WAIT"] - max(totals[action] for action in D1_ACTION_ORDER if action != "WAIT")


def _tensor_ids(torch_module: Any, ids: tuple[int, ...], *, device: str) -> Any:
    value = torch_module.tensor([list(ids)], dtype=torch_module.long)
    if device != "auto" and hasattr(value, "to"):
        value = value.to(device)
    return value


def _ones(torch_module: Any, length: int, *, device: str) -> Any:
    value = torch_module.ones((1, length), dtype=torch_module.long)
    if device != "auto" and hasattr(value, "to"):
        value = value.to(device)
    return value


def _forward(model: Any, *, input_ids: Any, attention_mask: Any, past_key_values: Any | None = None) -> Any:
    kwargs = {"input_ids": input_ids, "attention_mask": attention_mask, "use_cache": True}
    if past_key_values is not None:
        kwargs["past_key_values"] = past_key_values
    return model(**kwargs)


def _allowed(constraint: Any, sent: Any) -> tuple[int, ...]:
    try:
        return canonical_allowed_tokens(list(constraint(0, sent)))
    except Exception as error:
        if isinstance(error, GenerationError):
            raise
        raise GenerationError("D1 forced I3 constraint failed") from error


def legal_sets_identical(values: dict[str, tuple[int, ...]]) -> bool:
    """True only when every frozen branch exposes exactly the same legal set."""

    if tuple(values) != D1_ACTION_ORDER:
        raise ValueError("D1 legal-set mapping must use frozen action order")
    first = values[D1_ACTION_ORDER[0]]
    return all(values[action] == first for action in D1_ACTION_ORDER[1:])


def survivors_after_token(
    survivors: tuple[str, ...],
    legal_sets: dict[str, tuple[int, ...]],
    token_id: int,
) -> tuple[str, ...]:
    """Return forced branches still compatible after one observed token."""

    if not survivors or any(action not in D1_ACTION_ORDER for action in survivors):
        raise ValueError("invalid D1 survivor set")
    return tuple(action for action in survivors if token_id in legal_sets[action])


def _rank(raw: list[tuple[str, str, tuple[int, ...], float]]) -> tuple[D1BranchScore, ...]:
    order_index = {action: index for index, action in enumerate(D1_ACTION_ORDER)}
    total_order = sorted(raw, key=lambda item: (-item[3], order_index[item[0]]))
    mean_order = sorted(raw, key=lambda item: (-(item[3] / len(item[2])), order_index[item[0]]))
    total_rank = {item[0]: rank for rank, item in enumerate(total_order, 1)}
    mean_rank = {item[0]: rank for rank, item in enumerate(mean_order, 1)}
    return tuple(
        D1BranchScore(
            internal_action=action,
            model_label=label,
            token_ids=ids,
            total_log_probability=total,
            mean_log_probability=total / len(ids),
            total_rank=total_rank[action],
            mean_rank=mean_rank[action],
        )
        for action, label, ids, total in raw
    )


def score_i3_decision_boundary(
    runtime: TransformersModelRuntime,
    *,
    rendered_input: bytes,
    prefill_adapter: bool,
    selector_adapter: bool,
) -> D1BoundaryProbeResult:
    """Measure five forced I3 action branches from their first legal-set split.

    WORLD context is forwarded exactly once. The I3 selector suffix is then
    forwarded under the selector adapter state. Shared constrained continuation
    tokens are greedily advanced only while all five forced-action schemas have
    identical legal token sets. At the first divergence, each branch is scored
    counterfactually from an identical cloned cache until that branch becomes
    the sole surviving forced schema. Shared-prefix tokens are excluded.
    """

    if not isinstance(runtime, TransformersModelRuntime):
        raise TypeError("runtime must be a TransformersModelRuntime")
    if type(prefill_adapter) is not bool or type(selector_adapter) is not bool:
        raise TypeError("phase adapter flags must be booleans")
    torch_module = runtime.torch_module
    if torch_module is None:
        raise GenerationError("P2-D1 requires PyTorch")

    context_ids, prefix_ids, combined_ids = phase_generation_boundary_token_ids(runtime, rendered_input)
    device = runtime.profile.device
    context_tensor = _tensor_ids(torch_module, context_ids, device=device)
    prefix_tensor = _tensor_ids(torch_module, prefix_ids, device=device)
    constraints = {
        action: build_transformers_constraint(
            runtime.tokenizer,
            schema=forced_action_codec_json_schema(action),
        )
        for action in D1_ACTION_ORDER
    }

    inference_context = torch_module.inference_mode() if hasattr(torch_module, "inference_mode") else nullcontext()
    with inference_context:
        with adapter_state(runtime.model, prefill_adapter):
            prefill_output = _forward(
                runtime.model,
                input_ids=context_tensor,
                attention_mask=_ones(torch_module, len(context_ids), device=device),
            )
        phase_a_cache = getattr(prefill_output, "past_key_values", None)
        if phase_a_cache is None:
            raise GenerationError("P2-D1 WORLD prefill did not return past_key_values")

        with adapter_state(runtime.model, selector_adapter):
            prefix_output = _forward(
                runtime.model,
                input_ids=prefix_tensor,
                attention_mask=_ones(torch_module, len(combined_ids), device=device),
                past_key_values=clone_past_key_values(phase_a_cache),
            )
        common_cache = getattr(prefix_output, "past_key_values", None)
        if common_cache is None:
            raise GenerationError("P2-D1 selector prefix did not return past_key_values")
        common_logits = prefix_output.logits[0, -1]

        common_generated: list[int] = []
        common_forwards = 0
        divergence_step: int | None = None
        for step in range(D1_MAX_COMMON_PREFIX_TOKENS + 1):
            sent = _tensor_ids(torch_module, combined_ids + tuple(common_generated), device=device)[0]
            legal = {action: _allowed(constraints[action], sent) for action in D1_ACTION_ORDER}
            if not legal_sets_identical(legal):
                divergence_step = step
                break
            if step >= D1_MAX_COMMON_PREFIX_TOKENS:
                raise GenerationError("P2-D1 action branches did not diverge within fail-closed guard")
            token_id = stable_allowed_argmax(torch_module, common_logits, list(legal[D1_ACTION_ORDER[0]]))
            common_generated.append(token_id)
            token_tensor = _tensor_ids(torch_module, (token_id,), device=device)
            with adapter_state(runtime.model, selector_adapter):
                output = _forward(
                    runtime.model,
                    input_ids=token_tensor,
                    attention_mask=_ones(
                        torch_module,
                        len(combined_ids) + len(common_generated),
                        device=device,
                    ),
                    past_key_values=common_cache,
                )
            common_forwards += 1
            common_cache = getattr(output, "past_key_values", None)
            if common_cache is None:
                raise GenerationError("P2-D1 common-prefix continuation lost past_key_values")
            common_logits = output.logits[0, -1]

        if divergence_step is None:
            raise GenerationError("P2-D1 could not locate action-branch divergence")

        raw: list[tuple[str, str, tuple[int, ...], float]] = []
        branch_forwards = 0
        common_tuple = tuple(common_generated)
        for target in D1_ACTION_ORDER:
            cache = clone_past_key_values(common_cache)
            logits = common_logits
            generated: list[int] = []
            survivors = D1_ACTION_ORDER
            total = None
            for step in range(D1_MAX_BRANCH_TOKENS):
                sent = _tensor_ids(
                    torch_module,
                    combined_ids + common_tuple + tuple(generated),
                    device=device,
                )[0]
                legal = {action: _allowed(constraints[action], sent) for action in survivors}
                target_allowed = legal.get(target)
                if target_allowed is None:
                    raise GenerationError("P2-D1 target branch became impossible")
                token_id = stable_allowed_argmax(torch_module, logits, list(target_allowed))
                lp = torch_module.log_softmax(logits, dim=-1)[token_id]
                total = lp if total is None else total + lp
                generated.append(token_id)
                survivors = survivors_after_token(survivors, legal, token_id)
                if target not in survivors:
                    raise GenerationError("P2-D1 chosen forced token excluded target branch")
                if len(survivors) == 1:
                    if survivors[0] != target:
                        raise GenerationError("P2-D1 unique survivor is not target branch")
                    break
                token_tensor = _tensor_ids(torch_module, (token_id,), device=device)
                with adapter_state(runtime.model, selector_adapter):
                    output = _forward(
                        runtime.model,
                        input_ids=token_tensor,
                        attention_mask=_ones(
                            torch_module,
                            len(combined_ids) + len(common_tuple) + len(generated),
                            device=device,
                        ),
                        past_key_values=cache,
                    )
                branch_forwards += 1
                cache = getattr(output, "past_key_values", None)
                if cache is None:
                    raise GenerationError("P2-D1 branch continuation lost past_key_values")
                logits = output.logits[0, -1]
            else:
                raise GenerationError("P2-D1 branch did not become unique within fail-closed guard")

            if total is None or not generated:
                raise GenerationError("P2-D1 branch score is empty")
            total_value = float(total.detach().cpu())
            if not math.isfinite(total_value):
                raise GenerationError("P2-D1 produced non-finite branch score")
            raw.append(
                (
                    target,
                    DEFAULT_ACTION_PRESENTATION.entry(target).model_label,
                    tuple(generated),
                    total_value,
                )
            )

    return D1BoundaryProbeResult(
        prefill_adapter=prefill_adapter,
        selector_adapter=selector_adapter,
        context_token_ids=context_ids,
        prefix_token_ids=prefix_ids,
        combined_token_ids=combined_ids,
        common_prefix_token_ids=tuple(common_generated),
        divergence_step=divergence_step,
        phase_boundary_token_aligned=True,
        world_prefill_forward_count=1,
        selector_prefix_forward_count=1,
        common_prefix_forward_count=common_forwards,
        branch_continuation_forward_count=branch_forwards,
        world_context_recomputed_after_switch=False,
        branch_scores=_rank(raw),
    )


__all__ = [
    "D1_ACTION_ORDER",
    "D1BranchScore",
    "D1BoundaryProbeResult",
    "legal_sets_identical",
    "survivors_after_token",
    "score_i3_decision_boundary",
]
