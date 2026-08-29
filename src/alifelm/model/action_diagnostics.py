"""Researcher-only action-label scoring for I-05R3."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Any

from alifelm.context import ActionPresentation, DEFAULT_ACTION_PRESENTATION

from .transformers_backend import GenerationError, TransformersModelRuntime


ACTION_SCORE_TREATMENT_ID = "i05r3-action-label-sequence-score"
ACTION_SCORE_TREATMENT_VERSION = "1.0.0"
ACTION_SCORE_PREFIX = b'\nAction selection JSON:\n{"action_label":"'
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ActionLabelScore:
    model_label: str
    token_ids: tuple[int, ...]
    total_log_probability: float
    mean_log_probability: float
    rank: int

    def __post_init__(self) -> None:
        if not self.model_label or not isinstance(self.model_label, str):
            raise ValueError("model_label must be a non-empty string")
        if not self.token_ids or any(type(value) is not int for value in self.token_ids):
            raise ValueError("token_ids must be a non-empty integer tuple")
        if not math.isfinite(self.total_log_probability):
            raise ValueError("total_log_probability must be finite")
        if not math.isfinite(self.mean_log_probability):
            raise ValueError("mean_log_probability must be finite")
        if type(self.rank) is not int or self.rank < 1:
            raise ValueError("rank must be a positive integer")

    @property
    def token_count(self) -> int:
        return len(self.token_ids)


@dataclass(frozen=True, slots=True)
class ActionLabelScoreResult:
    context_hash: str
    context_pack_ref: str
    rendered_input_hash: str
    rendered_input_ref: str
    model_profile_id: str
    model_revision: str
    treatment_id: str
    treatment_version: str
    score_prefix_hash: str
    scores: tuple[ActionLabelScore, ...]
    shared_token_prefixes: tuple[tuple[str, str, int], ...]

    def __post_init__(self) -> None:
        for name in (
            "context_hash",
            "context_pack_ref",
            "rendered_input_hash",
            "rendered_input_ref",
            "score_prefix_hash",
        ):
            if not _DIGEST.fullmatch(getattr(self, name)):
                raise ValueError(f"{name} must be a lowercase SHA-256 digest")
        if not self.model_profile_id or not isinstance(self.model_profile_id, str):
            raise ValueError("model_profile_id must be a non-empty string")
        if not self.model_revision or not isinstance(self.model_revision, str):
            raise ValueError("model_revision must be a non-empty string")
        if self.treatment_id != ACTION_SCORE_TREATMENT_ID:
            raise ValueError("unsupported action score treatment")
        if self.treatment_version != ACTION_SCORE_TREATMENT_VERSION:
            raise ValueError("unsupported action score treatment version")
        if len(self.scores) != 5 or {score.rank for score in self.scores} != set(
            range(1, 6)
        ):
            raise ValueError("exactly five uniquely ranked action scores are required")
        expected_labels = {
            entry.model_label for entry in DEFAULT_ACTION_PRESENTATION.actions
        }
        if {score.model_label for score in self.scores} != expected_labels:
            raise ValueError("scores must contain the canonical five model-facing labels")


def rank_action_label_scores(
    values: tuple[tuple[str, tuple[int, ...], float], ...],
) -> tuple[ActionLabelScore, ...]:
    """Rank by total sequence log probability with a stable label tie-break."""

    if len(values) != 5 or len({label for label, _, _ in values}) != 5:
        raise ValueError("five unique action label scores are required")
    ordered = sorted(values, key=lambda item: (-item[2], item[0]))
    return tuple(
        ActionLabelScore(label, token_ids, total, total / len(token_ids), rank)
        for rank, (label, token_ids, total) in enumerate(ordered, 1)
    )


def _shared_prefixes(
    values: tuple[tuple[str, tuple[int, ...], float], ...],
) -> tuple[tuple[str, str, int], ...]:
    overlaps = []
    for index, (left, left_ids, _) in enumerate(values):
        for right, right_ids, _ in values[index + 1 :]:
            count = 0
            for left_id, right_id in zip(left_ids, right_ids, strict=False):
                if left_id != right_id:
                    break
                count += 1
            overlaps.append((left, right, count))
    return tuple(overlaps)


def score_action_labels(
    runtime: TransformersModelRuntime,
    *,
    rendered_input: bytes,
    context_hash: str,
    context_pack_ref: str,
    rendered_input_ref: str,
    presentation: ActionPresentation = DEFAULT_ACTION_PRESENTATION,
) -> ActionLabelScoreResult:
    """Teacher-force full label token sequences without generating or acting."""

    if not isinstance(runtime, TransformersModelRuntime):
        raise TypeError("runtime must be a TransformersModelRuntime")
    if not isinstance(rendered_input, bytes):
        raise TypeError("rendered_input must be bytes")
    torch_module = runtime.torch_module
    if torch_module is None:
        raise GenerationError("action scoring requires the loaded PyTorch module")
    prefix = rendered_input + ACTION_SCORE_PREFIX
    prefix_text = prefix.decode("utf-8")
    encoded = runtime.tokenizer(
        prefix_text,
        return_tensors="pt",
        add_special_tokens=runtime.profile.add_special_tokens,
    )
    input_ids = encoded["input_ids"]
    if runtime.profile.device != "auto" and hasattr(input_ids, "to"):
        input_ids = input_ids.to(runtime.profile.device)
    raw_values: list[tuple[str, tuple[int, ...], float]] = []
    for internal_action in presentation.presentation_order:
        label = presentation.entry(internal_action).model_label
        label_ids = tuple(
            runtime.tokenizer.encode(label, add_special_tokens=False)
        )
        if not label_ids:
            raise GenerationError(f"action label {label!r} has no tokenizer IDs")
        continuation = torch_module.tensor(
            [label_ids], dtype=input_ids.dtype, device=input_ids.device
        )
        sequence = torch_module.cat((input_ids, continuation), dim=1)
        attention_mask = torch_module.ones_like(sequence)
        inference_context = (
            torch_module.inference_mode()
            if hasattr(torch_module, "inference_mode")
            else nullcontext()
        )
        with inference_context:
            output = runtime.model(input_ids=sequence, attention_mask=attention_mask)
        logits = output.logits[0]
        prefix_length = int(input_ids.shape[-1])
        positions = logits[prefix_length - 1 : prefix_length + len(label_ids) - 1]
        log_probabilities = torch_module.log_softmax(positions, dim=-1)
        target = continuation[0]
        total = float(
            log_probabilities.gather(1, target.unsqueeze(1)).sum().detach().cpu()
        )
        raw_values.append((label, label_ids, total))
    values = tuple(raw_values)
    revision = runtime.profile.model_revision or "UNPINNED"
    return ActionLabelScoreResult(
        context_hash=context_hash,
        context_pack_ref=context_pack_ref,
        rendered_input_hash=hashlib.sha256(prefix).hexdigest(),
        rendered_input_ref=rendered_input_ref,
        model_profile_id=runtime.profile.profile_id,
        model_revision=revision,
        treatment_id=ACTION_SCORE_TREATMENT_ID,
        treatment_version=ACTION_SCORE_TREATMENT_VERSION,
        score_prefix_hash=hashlib.sha256(ACTION_SCORE_PREFIX).hexdigest(),
        scores=rank_action_label_scores(values),
        shared_token_prefixes=_shared_prefixes(values),
    )


def action_label_score_bytes(result: ActionLabelScoreResult) -> bytes:
    document = {
        "context_hash": result.context_hash,
        "context_pack_ref": result.context_pack_ref,
        "model_profile_id": result.model_profile_id,
        "model_revision": result.model_revision,
        "rendered_input_hash": result.rendered_input_hash,
        "rendered_input_ref": result.rendered_input_ref,
        "score_prefix_hash": result.score_prefix_hash,
        "scores": [
            {
                "mean_log_probability": score.mean_log_probability,
                "model_label": score.model_label,
                "rank": score.rank,
                "token_count": score.token_count,
                "token_ids": list(score.token_ids),
                "total_log_probability": score.total_log_probability,
            }
            for score in result.scores
        ],
        "shared_token_prefixes": [list(value) for value in result.shared_token_prefixes],
        "treatment_id": result.treatment_id,
        "treatment_version": result.treatment_version,
    }
    return json.dumps(
        document, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
