"""Research-only cached phase-switch scoring for WORLD P1C.

This module performs no simulation commit and no weight update. It isolates
adapter activity between canonical WORLD-context prefill (Phase A) and the
researcher-only action-label scoring continuation (Phase B).
"""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
import copy
from dataclasses import dataclass
import math
from typing import Any, Iterable, Sequence

from .action_diagnostics import ACTION_SCORE_PREFIX
from .p1b_metrics import ACTION_LABELS
from .transformers_backend import GenerationError, TransformersModelRuntime


@dataclass(frozen=True, slots=True)
class PhaseScore:
    model_label: str
    token_ids: tuple[int, ...]
    total_log_probability: float
    mean_log_probability: float
    rank: int


@dataclass(frozen=True, slots=True)
class PhaseScoreResult:
    prefill_adapter: bool
    selector_adapter: bool
    context_token_ids: tuple[int, ...]
    prefix_token_ids: tuple[int, ...]
    combined_token_ids: tuple[int, ...]
    phase_boundary_token_aligned: bool
    prefill_forward_count: int
    selector_prefix_forward_count: int
    scores: tuple[PhaseScore, ...]

    def totals(self) -> dict[str, float]:
        return {score.model_label: score.total_log_probability for score in self.scores}

    def means(self) -> dict[str, float]:
        return {score.model_label: score.mean_log_probability for score in self.scores}

    def rank1_label(self) -> str:
        return next(score.model_label for score in self.scores if score.rank == 1)


@contextmanager
def adapter_state(model: Any, enabled: bool):
    """Enter one explicit PEFT adapter state without changing parameters."""

    if enabled:
        yield
        return
    disable = getattr(model, "disable_adapter", None)
    if not callable(disable):
        raise GenerationError("phase switching requires a PEFT model with disable_adapter()")
    with disable():
        yield


def clone_past_key_values(value: Any) -> Any:
    """Clone a cache so candidate branches cannot mutate the frozen prefix cache."""

    try:
        return copy.deepcopy(value)
    except Exception as error:  # pragma: no cover - defensive production boundary
        raise GenerationError("unable to clone phase cache without recomputation") from error


def _as_tuple_ids(value: Any) -> tuple[int, ...]:
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, list) and value and isinstance(value[0], list):
        value = value[0]
    if not isinstance(value, (list, tuple)) or any(type(item) is not int for item in value):
        raise GenerationError("tokenizer did not return a usable integer token sequence")
    return tuple(value)


def phase_boundary_token_ids(
    runtime: TransformersModelRuntime, rendered_input: bytes
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    """Return context, selector-prefix and combined IDs, failing on retokenization.

    P1C requires C00 to be comparable with the ordinary P1/P1B scorer. The
    exact tokenization of ``context + ACTION_SCORE_PREFIX`` therefore must be
    identical to standalone context tokenization followed by standalone
    selector-prefix tokenization. Any token merge, split, or replacement
    induced by concatenation fails closed before model inference.
    """

    if not isinstance(rendered_input, bytes):
        raise TypeError("rendered_input must be bytes")
    tokenizer = runtime.tokenizer
    add_special = runtime.profile.add_special_tokens
    context_text = rendered_input.decode("utf-8")
    prefix_text = ACTION_SCORE_PREFIX.decode("utf-8")
    combined_text = (rendered_input + ACTION_SCORE_PREFIX).decode("utf-8")
    context_ids = tuple(tokenizer.encode(context_text, add_special_tokens=add_special))
    prefix_ids = tuple(tokenizer.encode(prefix_text, add_special_tokens=False))
    combined_ids = tuple(tokenizer.encode(combined_text, add_special_tokens=add_special))
    if not context_ids or not prefix_ids:
        raise GenerationError("P1C phase boundary produced an empty token segment")
    if combined_ids != context_ids + prefix_ids:
        raise GenerationError("P1C byte boundary is not token-aligned under frozen tokenizer")
    return context_ids, prefix_ids, combined_ids


def _tensor_ids(torch_module: Any, ids: Sequence[int], *, device: str) -> Any:
    tensor = torch_module.tensor([list(ids)], dtype=torch_module.long)
    if device != "auto" and hasattr(tensor, "to"):
        tensor = tensor.to(device)
    return tensor


def _ones(torch_module: Any, length: int, *, device: str) -> Any:
    value = torch_module.ones((1, length), dtype=torch_module.long)
    if device != "auto" and hasattr(value, "to"):
        value = value.to(device)
    return value


def _forward(
    model: Any,
    *,
    input_ids: Any,
    attention_mask: Any,
    past_key_values: Any | None = None,
) -> Any:
    kwargs = {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "use_cache": True,
    }
    if past_key_values is not None:
        kwargs["past_key_values"] = past_key_values
    return model(**kwargs)


def _label_ids(runtime: TransformersModelRuntime, label: str) -> tuple[int, ...]:
    ids = tuple(runtime.tokenizer.encode(label, add_special_tokens=False))
    if not ids:
        raise GenerationError(f"action label {label!r} has no tokenizer IDs")
    return ids


def score_phase_switched_labels(
    runtime: TransformersModelRuntime,
    *,
    rendered_input: bytes,
    prefill_adapter: bool,
    selector_adapter: bool,
    labels: Iterable[str] = ACTION_LABELS,
) -> PhaseScoreResult:
    """Score frozen action labels with one cached prefill and one selector prefix.

    Phase A is executed exactly once. Its cache is cloned once for the Phase B
    selector prefix. The resulting Phase B cache is cloned per candidate label,
    so the WORLD context is never recomputed after the adapter-state switch.
    """

    if not isinstance(runtime, TransformersModelRuntime):
        raise TypeError("runtime must be a TransformersModelRuntime")
    torch_module = runtime.torch_module
    if torch_module is None:
        raise GenerationError("P1C phase scoring requires PyTorch")
    requested_labels = tuple(labels)
    if requested_labels != ACTION_LABELS:
        raise ValueError("P1C must score exactly the frozen five action labels in frozen order")

    context_ids, prefix_ids, combined_ids = phase_boundary_token_ids(runtime, rendered_input)
    device = runtime.profile.device
    context_tensor = _tensor_ids(torch_module, context_ids, device=device)
    prefix_tensor = _tensor_ids(torch_module, prefix_ids, device=device)

    inference_context = (
        torch_module.inference_mode()
        if hasattr(torch_module, "inference_mode")
        else nullcontext()
    )
    with inference_context:
        with adapter_state(runtime.model, prefill_adapter):
            prefill_output = _forward(
                runtime.model,
                input_ids=context_tensor,
                attention_mask=_ones(torch_module, len(context_ids), device=device),
            )
        phase_a_cache = getattr(prefill_output, "past_key_values", None)
        if phase_a_cache is None:
            raise GenerationError("P1C prefill did not return past_key_values")

        with adapter_state(runtime.model, selector_adapter):
            prefix_output = _forward(
                runtime.model,
                input_ids=prefix_tensor,
                attention_mask=_ones(torch_module, len(combined_ids), device=device),
                past_key_values=clone_past_key_values(phase_a_cache),
            )
        phase_b_cache = getattr(prefix_output, "past_key_values", None)
        if phase_b_cache is None:
            raise GenerationError("P1C selector prefix did not return past_key_values")
        first_logits = prefix_output.logits[0, -1]

        raw: list[tuple[str, tuple[int, ...], float]] = []
        for label in requested_labels:
            ids = _label_ids(runtime, label)
            first_lp = torch_module.log_softmax(first_logits, dim=-1)[ids[0]]
            total = first_lp
            if len(ids) > 1:
                continuation = _tensor_ids(torch_module, ids[:-1], device=device)
                with adapter_state(runtime.model, selector_adapter):
                    continuation_output = _forward(
                        runtime.model,
                        input_ids=continuation,
                        attention_mask=_ones(
                            torch_module,
                            len(combined_ids) + len(ids) - 1,
                            device=device,
                        ),
                        past_key_values=clone_past_key_values(phase_b_cache),
                    )
                logits = continuation_output.logits[0]
                log_probs = torch_module.log_softmax(logits, dim=-1)
                targets = _tensor_ids(torch_module, ids[1:], device=device)[0]
                total = total + log_probs.gather(1, targets.unsqueeze(1)).sum()
            total_value = float(total.detach().cpu())
            if not math.isfinite(total_value):
                raise GenerationError("P1C produced a non-finite action-label score")
            raw.append((label, ids, total_value))

    ordered = sorted(raw, key=lambda item: (-item[2], item[0]))
    rank_by_label = {
        label: rank for rank, (label, _, _) in enumerate(ordered, 1)
    }
    scores = tuple(
        PhaseScore(
            model_label=label,
            token_ids=ids,
            total_log_probability=total,
            mean_log_probability=total / len(ids),
            rank=rank_by_label[label],
        )
        for label, ids, total in raw
    )
    return PhaseScoreResult(
        prefill_adapter=prefill_adapter,
        selector_adapter=selector_adapter,
        context_token_ids=context_ids,
        prefix_token_ids=prefix_ids,
        combined_token_ids=combined_ids,
        phase_boundary_token_aligned=True,
        prefill_forward_count=1,
        selector_prefix_forward_count=1,
        scores=scores,
    )


__all__ = [
    "PhaseScore",
    "PhaseScoreResult",
    "adapter_state",
    "clone_past_key_values",
    "phase_boundary_token_ids",
    "score_phase_switched_labels",
]
