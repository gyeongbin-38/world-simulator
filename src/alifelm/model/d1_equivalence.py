"""Post-hoc numerical path diagnostics for WORLD P1C-D1.

This module does not generate actions, mutate simulation state, or update model
weights.  It provides a bare-model cached scorer that mirrors the frozen P1C
cache boundary and pure comparison summaries for D1.
"""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
import math
import statistics
from typing import Any, Iterable, Mapping, Sequence

from .p1b_metrics import ACTION_LABELS
from .phase_scoring import clone_past_key_values, phase_boundary_token_ids
from .transformers_backend import GenerationError, TransformersModelRuntime


@dataclass(frozen=True, slots=True)
class D1LabelScore:
    model_label: str
    token_ids: tuple[int, ...]
    total_log_probability: float
    mean_log_probability: float
    rank: int


@dataclass(frozen=True, slots=True)
class D1CachedScoreResult:
    context_token_ids: tuple[int, ...]
    prefix_token_ids: tuple[int, ...]
    combined_token_ids: tuple[int, ...]
    peft_disabled: bool
    prefill_forward_count: int
    selector_prefix_forward_count: int
    scores: tuple[D1LabelScore, ...]

    def as_record(self) -> dict[str, object]:
        return {
            "context_token_ids": list(self.context_token_ids),
            "prefix_token_ids": list(self.prefix_token_ids),
            "combined_token_ids": list(self.combined_token_ids),
            "peft_disabled": self.peft_disabled,
            "prefill_forward_count": self.prefill_forward_count,
            "selector_prefix_forward_count": self.selector_prefix_forward_count,
            "scores": [
                {
                    "model_label": score.model_label,
                    "token_ids": list(score.token_ids),
                    "total_log_probability": score.total_log_probability,
                    "mean_log_probability": score.mean_log_probability,
                    "rank": score.rank,
                }
                for score in self.scores
            ],
        }


@dataclass(frozen=True, slots=True)
class DifferenceSummary:
    count: int
    maximum: float
    median: float
    mean: float
    nonzero_fraction: float

    def as_dict(self) -> dict[str, float | int]:
        return {
            "count": self.count,
            "max": self.maximum,
            "median": self.median,
            "mean": self.mean,
            "nonzero_fraction": self.nonzero_fraction,
        }


@contextmanager
def peft_disabled_state(model: Any, disabled: bool):
    """Disable an adapter only when the D1 path explicitly requires it."""

    if not disabled:
        yield
        return
    disable = getattr(model, "disable_adapter", None)
    if not callable(disable):
        raise GenerationError("D1 PEFT-disabled path requires disable_adapter()")
    with disable():
        yield


def _tensor_ids(torch_module: Any, ids: Sequence[int], *, device: str) -> Any:
    tensor = torch_module.tensor([list(ids)], dtype=torch_module.long)
    if device != "auto" and hasattr(tensor, "to"):
        tensor = tensor.to(device)
    return tensor


def _ones(torch_module: Any, length: int, *, device: str) -> Any:
    tensor = torch_module.ones((1, length), dtype=torch_module.long)
    if device != "auto" and hasattr(tensor, "to"):
        tensor = tensor.to(device)
    return tensor


def _forward(
    model: Any,
    *,
    input_ids: Any,
    attention_mask: Any,
    past_key_values: Any | None = None,
) -> Any:
    kwargs: dict[str, Any] = {
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
        raise GenerationError(f"D1 action label {label!r} has no tokenizer IDs")
    return ids


def score_cached_labels(
    runtime: TransformersModelRuntime,
    *,
    rendered_input: bytes,
    peft_disabled: bool,
    labels: Iterable[str] = ACTION_LABELS,
) -> D1CachedScoreResult:
    """Score labels across the frozen P1C context/prefix cache boundary.

    Bare-model paths use ``peft_disabled=False`` and never require a PEFT
    wrapper.  PEFT-disabled diagnostic paths use ``peft_disabled=True``.  The
    WORLD context is forwarded exactly once per score set and never recomputed
    for candidate labels.
    """

    if not isinstance(runtime, TransformersModelRuntime):
        raise TypeError("runtime must be a TransformersModelRuntime")
    requested_labels = tuple(labels)
    if requested_labels != ACTION_LABELS:
        raise ValueError("D1 must score exactly the frozen five labels in frozen order")
    torch_module = runtime.torch_module
    if torch_module is None:
        raise GenerationError("D1 cached scoring requires PyTorch")

    context_ids, prefix_ids, combined_ids = phase_boundary_token_ids(runtime, rendered_input)
    device = runtime.profile.device
    context_tensor = _tensor_ids(torch_module, context_ids, device=device)
    prefix_tensor = _tensor_ids(torch_module, prefix_ids, device=device)

    inference_context = (
        torch_module.inference_mode() if hasattr(torch_module, "inference_mode") else nullcontext()
    )
    with inference_context:
        with peft_disabled_state(runtime.model, peft_disabled):
            prefill = _forward(
                runtime.model,
                input_ids=context_tensor,
                attention_mask=_ones(torch_module, len(context_ids), device=device),
            )
        phase_a_cache = getattr(prefill, "past_key_values", None)
        if phase_a_cache is None:
            raise GenerationError("D1 cached prefill returned no past_key_values")

        with peft_disabled_state(runtime.model, peft_disabled):
            prefix = _forward(
                runtime.model,
                input_ids=prefix_tensor,
                attention_mask=_ones(torch_module, len(combined_ids), device=device),
                past_key_values=clone_past_key_values(phase_a_cache),
            )
        phase_b_cache = getattr(prefix, "past_key_values", None)
        if phase_b_cache is None:
            raise GenerationError("D1 cached selector prefix returned no past_key_values")
        first_logits = prefix.logits[0, -1]
        first_log_probs = torch_module.log_softmax(first_logits, dim=-1)

        raw: list[tuple[str, tuple[int, ...], float]] = []
        for label in requested_labels:
            ids = _label_ids(runtime, label)
            total = first_log_probs[ids[0]]
            if len(ids) > 1:
                continuation = _tensor_ids(torch_module, ids[:-1], device=device)
                with peft_disabled_state(runtime.model, peft_disabled):
                    output = _forward(
                        runtime.model,
                        input_ids=continuation,
                        attention_mask=_ones(
                            torch_module,
                            len(combined_ids) + len(ids) - 1,
                            device=device,
                        ),
                        past_key_values=clone_past_key_values(phase_b_cache),
                    )
                logits = output.logits[0]
                log_probs = torch_module.log_softmax(logits, dim=-1)
                targets = _tensor_ids(torch_module, ids[1:], device=device)[0]
                total = total + log_probs.gather(1, targets.unsqueeze(1)).sum()
            value = float(total.detach().cpu())
            if not math.isfinite(value):
                raise GenerationError("D1 cached scorer produced non-finite log probability")
            raw.append((label, ids, value))

    ordered = sorted(raw, key=lambda item: (-item[2], item[0]))
    rank_by_label = {label: rank for rank, (label, _, _) in enumerate(ordered, 1)}
    scores = tuple(
        D1LabelScore(
            model_label=label,
            token_ids=ids,
            total_log_probability=total,
            mean_log_probability=total / len(ids),
            rank=rank_by_label[label],
        )
        for label, ids, total in raw
    )
    return D1CachedScoreResult(
        context_token_ids=context_ids,
        prefix_token_ids=prefix_ids,
        combined_token_ids=combined_ids,
        peft_disabled=peft_disabled,
        prefill_forward_count=1,
        selector_prefix_forward_count=1,
        scores=scores,
    )


def score_map(record: Mapping[str, object]) -> dict[str, tuple[tuple[int, ...], float, float, int]]:
    """Normalize a D1 score record for exact path-to-path comparisons."""

    rows = record.get("scores")
    if not isinstance(rows, list):
        raise ValueError("D1 score record requires a scores list")
    output: dict[str, tuple[tuple[int, ...], float, float, int]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("D1 score row must be an object")
        label = row.get("model_label")
        token_ids = row.get("token_ids")
        total = row.get("total_log_probability")
        mean = row.get("mean_log_probability")
        rank = row.get("rank")
        if not isinstance(label, str) or not isinstance(token_ids, list) or not isinstance(rank, int):
            raise ValueError("D1 score row identity drift")
        output[label] = (
            tuple(int(value) for value in token_ids),
            float(total),
            float(mean),
            rank,
        )
    if tuple(output) != ACTION_LABELS:
        raise ValueError("D1 score record label order drift")
    return output


def summarize_absolute(values: Sequence[float]) -> DifferenceSummary:
    normalized = tuple(abs(float(value)) for value in values)
    if not normalized:
        raise ValueError("D1 difference summary requires at least one value")
    return DifferenceSummary(
        count=len(normalized),
        maximum=max(normalized),
        median=float(statistics.median(normalized)),
        mean=float(statistics.fmean(normalized)),
        nonzero_fraction=sum(value != 0.0 for value in normalized) / len(normalized),
    )


def compare_score_records(
    left_records: Sequence[Mapping[str, object]],
    right_records: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Compare matched D1 score records label-by-label in frozen order."""

    if not left_records or len(left_records) != len(right_records):
        raise ValueError("D1 score-record sequences must be non-empty and matched")
    token_ids_exact = True
    total_differences: list[float] = []
    mean_differences: list[float] = []
    rank_equal = True
    for left_record, right_record in zip(left_records, right_records, strict=True):
        left = score_map(left_record)
        right = score_map(right_record)
        for label in ACTION_LABELS:
            left_ids, left_total, left_mean, left_rank = left[label]
            right_ids, right_total, right_mean, right_rank = right[label]
            token_ids_exact = token_ids_exact and left_ids == right_ids
            rank_equal = rank_equal and left_rank == right_rank
            total_differences.append(right_total - left_total)
            mean_differences.append(right_mean - left_mean)
    return {
        "comparisons": len(total_differences),
        "token_ids_exact": token_ids_exact,
        "rank_exact": rank_equal,
        "total": summarize_absolute(total_differences).as_dict(),
        "mean": summarize_absolute(mean_differences).as_dict(),
        "signed_total_differences": total_differences,
        "signed_mean_differences": mean_differences,
    }


__all__ = [
    "D1LabelScore",
    "D1CachedScoreResult",
    "DifferenceSummary",
    "peft_disabled_state",
    "score_cached_labels",
    "score_map",
    "summarize_absolute",
    "compare_score_records",
]
