"""Researcher-only evaluator for the F0 Foundation Tuning Study v1.

Evaluator v2 separates closed-set competence from free-form formatting:
scalar grounding tasks are scored by teacher-forced candidate likelihood, while
motor serialization remains generative and is checked for schema validity and
semantic correctness separately. Nothing in this module enters canonical
WORLD state or chooses an agent action.
"""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Mapping, Sequence

from alifelm.context import DEFAULT_ACTION_PRESENTATION

from .foundation_data import SemanticFamily, canonical_json
from .transformers_backend import GenerationError, TransformersModelRuntime


FOUNDATION_EVALUATOR_ID = "F0_FOUNDATION_EVALUATOR_V2"
FOUNDATION_EVALUATOR_VERSION = "2.0.0"
FOUNDATION_ANSWER_PREFIX = b"\nAnswer:\n"
FOUNDATION_RANKING_METRIC = "MEAN_TOKEN_LOG_PROBABILITY"

SERIALIZATION_FAMILY = SemanticFamily.ALREADY_SELECTED_ACTION_SERIALIZATION
SCALAR_FAMILIES = frozenset(
    family for family in SemanticFamily if family is not SERIALIZATION_FAMILY
)


@dataclass(frozen=True, slots=True)
class CandidateSequenceScore:
    candidate: str
    token_ids: tuple[int, ...]
    total_log_probability: float
    mean_log_probability: float
    rank: int

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, str) or not self.candidate:
            raise ValueError("candidate must be a non-empty string")
        if not self.token_ids or any(
            type(token_id) is not int for token_id in self.token_ids
        ):
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
class FoundationScalarEvaluation:
    example_id: str
    semantic_family: str
    expected: str
    predicted: str
    exact_match: bool
    ranking_metric: str
    prompt_hash: str
    scores: tuple[CandidateSequenceScore, ...]

    def __post_init__(self) -> None:
        if self.ranking_metric != FOUNDATION_RANKING_METRIC:
            raise ValueError("unsupported foundation ranking metric")
        if len(self.prompt_hash) != 64 or any(
            character not in "0123456789abcdef" for character in self.prompt_hash
        ):
            raise ValueError("prompt_hash must be a lowercase SHA-256 digest")
        if not self.scores or self.scores[0].candidate != self.predicted:
            raise ValueError("rank-1 candidate must equal predicted")
        if {score.rank for score in self.scores} != set(
            range(1, len(self.scores) + 1)
        ):
            raise ValueError("candidate ranks must be contiguous and unique")


@dataclass(frozen=True, slots=True)
class FoundationSerializationEvaluation:
    example_id: str
    semantic_family: str
    expected: str
    raw_model_output: str
    schema_valid: bool
    semantic_correct: bool
    canonical_output: str | None
    parse_error: str | None

    def __post_init__(self) -> None:
        if self.semantic_family != SERIALIZATION_FAMILY.value:
            raise ValueError("serialization evaluation requires the serialization family")
        if self.semantic_correct and not self.schema_valid:
            raise ValueError("semantic correctness requires schema validity")
        if self.schema_valid and self.canonical_output is None:
            raise ValueError("schema-valid serialization requires canonical_output")
        if not self.schema_valid and self.parse_error is None:
            raise ValueError("schema-invalid serialization requires parse_error")


def rank_candidate_sequence_scores(
    values: Sequence[tuple[str, tuple[int, ...], float]],
) -> tuple[CandidateSequenceScore, ...]:
    """Rank candidate continuations by mean token log probability.

    Mean token log probability is the primary metric because F0 candidate labels
    have unequal token lengths. Total sequence probability is retained as
    diagnostic evidence but is not used to prefer shorter surface forms.
    """

    if len(values) < 2:
        raise ValueError("at least two candidate scores are required")
    labels = [candidate for candidate, _, _ in values]
    if len(labels) != len(set(labels)):
        raise ValueError("candidate labels must be unique")

    enriched: list[tuple[str, tuple[int, ...], float, float]] = []
    for candidate, token_ids, total in values:
        if not token_ids:
            raise ValueError(f"candidate {candidate!r} has no token ids")
        if not math.isfinite(total):
            raise ValueError(
                f"candidate {candidate!r} has non-finite total log probability"
            )
        mean = total / len(token_ids)
        enriched.append((candidate, token_ids, total, mean))

    ordered = sorted(enriched, key=lambda item: (-item[3], item[0]))
    return tuple(
        CandidateSequenceScore(
            candidate=candidate,
            token_ids=token_ids,
            total_log_probability=total,
            mean_log_probability=mean,
            rank=rank,
        )
        for rank, (candidate, token_ids, total, mean) in enumerate(ordered, 1)
    )


def foundation_scoring_prompt(rendered_input: str | bytes) -> bytes:
    if isinstance(rendered_input, str):
        rendered = rendered_input.encode("utf-8")
    elif isinstance(rendered_input, bytes):
        rendered = rendered_input
    else:
        raise TypeError("rendered_input must be str or bytes")
    return rendered.rstrip() + FOUNDATION_ANSWER_PREFIX


def _encode_ids(
    tokenizer: Any, text: str, *, add_special_tokens: bool
) -> tuple[int, ...]:
    values = tokenizer.encode(text, add_special_tokens=add_special_tokens)
    if hasattr(values, "tolist"):
        values = values.tolist()
    if not isinstance(values, (list, tuple)) or any(
        type(value) is not int for value in values
    ):
        raise GenerationError("tokenizer.encode did not return integer token ids")
    if not values:
        raise GenerationError("tokenizer produced an empty token sequence")
    return tuple(values)


def score_foundation_candidates(
    runtime: TransformersModelRuntime,
    *,
    rendered_input: str | bytes,
    candidates: Sequence[str],
) -> tuple[CandidateSequenceScore, ...]:
    """Teacher-force candidate answer sequences without generating an answer.

    A tokenization-boundary audit verifies that separately encoded candidate
    tokens exactly match the suffix of the combined prompt+candidate encoding.
    This prevents silent score corruption from BPE boundary retokenization.
    """

    if not isinstance(runtime, TransformersModelRuntime):
        raise TypeError("runtime must be a TransformersModelRuntime")
    if len(candidates) < 2 or len(set(candidates)) != len(candidates):
        raise ValueError("candidates must contain at least two unique strings")
    if any(
        not isinstance(candidate, str) or not candidate for candidate in candidates
    ):
        raise ValueError("candidates must be non-empty strings")

    torch_module = runtime.torch_module
    if torch_module is None:
        raise GenerationError("foundation candidate scoring requires loaded PyTorch")

    prompt = foundation_scoring_prompt(rendered_input)
    prompt_text = prompt.decode("utf-8")
    prefix_ids = _encode_ids(
        runtime.tokenizer,
        prompt_text,
        add_special_tokens=runtime.profile.add_special_tokens,
    )
    device = runtime.profile.device if runtime.profile.device != "auto" else None
    input_ids = torch_module.tensor(
        [prefix_ids],
        dtype=torch_module.long,
        **({} if device is None else {"device": device}),
    )

    raw_values: list[tuple[str, tuple[int, ...], float]] = []
    for candidate in candidates:
        candidate_ids = _encode_ids(
            runtime.tokenizer,
            candidate,
            add_special_tokens=False,
        )
        combined_ids = _encode_ids(
            runtime.tokenizer,
            prompt_text + candidate,
            add_special_tokens=runtime.profile.add_special_tokens,
        )
        if combined_ids != prefix_ids + candidate_ids:
            raise GenerationError(
                "candidate tokenization is not prefix-stable at the evaluator boundary; "
                f"candidate={candidate!r}"
            )

        continuation = torch_module.tensor(
            [candidate_ids],
            dtype=input_ids.dtype,
            device=input_ids.device,
        )
        sequence = torch_module.cat((input_ids, continuation), dim=1)
        attention_mask = torch_module.ones_like(sequence)
        inference_context = (
            torch_module.inference_mode()
            if hasattr(torch_module, "inference_mode")
            else nullcontext()
        )
        with inference_context:
            output = runtime.model(
                input_ids=sequence,
                attention_mask=attention_mask,
            )
        logits = output.logits[0]
        prefix_length = len(prefix_ids)
        positions = logits[
            prefix_length - 1 : prefix_length + len(candidate_ids) - 1
        ]
        if hasattr(positions, "float"):
            positions = positions.float()
        log_probabilities = torch_module.log_softmax(positions, dim=-1)
        target = continuation[0]
        total = float(
            log_probabilities.gather(1, target.unsqueeze(1)).sum().detach().cpu()
        )
        if not math.isfinite(total):
            raise GenerationError(
                f"non-finite candidate score for {candidate!r}: {total}"
            )
        raw_values.append((candidate, candidate_ids, total))

    return rank_candidate_sequence_scores(raw_values)


def evaluate_foundation_scalar_record(
    runtime: TransformersModelRuntime,
    record: Mapping[str, Any],
) -> FoundationScalarEvaluation:
    family = SemanticFamily(str(record["semantic_family"]))
    if family not in SCALAR_FAMILIES:
        raise ValueError(
            "serialization must be evaluated with "
            "evaluate_foundation_serialization_text"
        )
    choices = tuple(str(value) for value in record["choices"])
    expected = str(record["ground_truth"])
    if expected not in choices:
        raise ValueError("ground truth must be present in candidate choices")

    scores = score_foundation_candidates(
        runtime,
        rendered_input=str(record["input"]),
        candidates=choices,
    )
    predicted = scores[0].candidate
    prompt_hash = hashlib.sha256(
        foundation_scoring_prompt(str(record["input"]))
    ).hexdigest()
    return FoundationScalarEvaluation(
        example_id=str(record["example_id"]),
        semantic_family=family.value,
        expected=expected,
        predicted=predicted,
        exact_match=predicted.strip() == expected.strip(),
        ranking_metric=FOUNDATION_RANKING_METRIC,
        prompt_hash=prompt_hash,
        scores=scores,
    )


def _serialization_schema_error(value: Any) -> str | None:
    if not isinstance(value, Mapping):
        return "serialization output must be an object"
    if set(value) != {"action_label", "payload"}:
        return "serialization object must contain exactly action_label and payload"

    action_label = value["action_label"]
    payload = value["payload"]
    if not isinstance(action_label, str):
        return "action_label must be a string"
    entries = {
        entry.model_label: entry for entry in DEFAULT_ACTION_PRESENTATION.actions
    }
    if action_label not in entries:
        return "action_label is not a canonical model-facing label"
    if not isinstance(payload, Mapping):
        return "payload must be an object"
    if any(not isinstance(key, str) for key in payload):
        return "payload keys must be strings"

    entry = entries[action_label]
    if set(payload) != set(entry.payload_fields):
        return "payload fields do not match the selected action label"
    if any(not isinstance(item, str) for item in payload.values()):
        return "payload values must be strings"
    return None


def evaluate_foundation_serialization_text(
    record: Mapping[str, Any],
    raw_model_output: str,
) -> FoundationSerializationEvaluation:
    family = SemanticFamily(str(record["semantic_family"]))
    if family is not SERIALIZATION_FAMILY:
        raise ValueError("record is not an action-serialization example")
    expected = str(record["ground_truth"])

    try:
        parsed = json.loads(raw_model_output)
    except (json.JSONDecodeError, TypeError) as error:
        return FoundationSerializationEvaluation(
            example_id=str(record["example_id"]),
            semantic_family=family.value,
            expected=expected,
            raw_model_output=raw_model_output,
            schema_valid=False,
            semantic_correct=False,
            canonical_output=None,
            parse_error=f"{type(error).__name__}: {error}",
        )

    schema_error = _serialization_schema_error(parsed)
    if schema_error is not None:
        return FoundationSerializationEvaluation(
            example_id=str(record["example_id"]),
            semantic_family=family.value,
            expected=expected,
            raw_model_output=raw_model_output,
            schema_valid=False,
            semantic_correct=False,
            canonical_output=None,
            parse_error=schema_error,
        )

    canonical_output = canonical_json(parsed)
    try:
        canonical_expected = canonical_json(json.loads(expected))
    except json.JSONDecodeError as error:
        raise ValueError("ground truth serialization is not valid JSON") from error
    return FoundationSerializationEvaluation(
        example_id=str(record["example_id"]),
        semantic_family=family.value,
        expected=expected,
        raw_model_output=raw_model_output,
        schema_valid=True,
        semantic_correct=canonical_output == canonical_expected,
        canonical_output=canonical_output,
        parse_error=None,
    )


def foundation_evaluation_bytes(
    result: FoundationScalarEvaluation | FoundationSerializationEvaluation,
) -> bytes:
    if isinstance(result, FoundationScalarEvaluation):
        document: dict[str, Any] = {
            "evaluator_id": FOUNDATION_EVALUATOR_ID,
            "evaluator_version": FOUNDATION_EVALUATOR_VERSION,
            "example_id": result.example_id,
            "semantic_family": result.semantic_family,
            "expected": result.expected,
            "predicted": result.predicted,
            "exact_match": result.exact_match,
            "ranking_metric": result.ranking_metric,
            "prompt_hash": result.prompt_hash,
            "scores": [
                {
                    "candidate": score.candidate,
                    "mean_log_probability": score.mean_log_probability,
                    "rank": score.rank,
                    "token_count": score.token_count,
                    "token_ids": list(score.token_ids),
                    "total_log_probability": score.total_log_probability,
                }
                for score in result.scores
            ],
        }
    elif isinstance(result, FoundationSerializationEvaluation):
        document = {
            "evaluator_id": FOUNDATION_EVALUATOR_ID,
            "evaluator_version": FOUNDATION_EVALUATOR_VERSION,
            "example_id": result.example_id,
            "semantic_family": result.semantic_family,
            "expected": result.expected,
            "raw_model_output": result.raw_model_output,
            "schema_valid": result.schema_valid,
            "semantic_correct": result.semantic_correct,
            "canonical_output": result.canonical_output,
            "parse_error": result.parse_error,
        }
    else:
        raise TypeError("unsupported foundation evaluation result")
    return (
        json.dumps(
            document,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
