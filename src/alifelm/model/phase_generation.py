"""Research-only cached phase-switched generation for WORLD P2.

The runtime performs exactly one WORLD-context prefill, switches the PEFT
adapter state at the frozen phase boundary, and then greedily generates the I3
continuation without recomputing WORLD context.  It never commits simulation
state and never changes model parameters.
"""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any

from .generation import GenerationRequest, RawGenerationResult
from .phase_scoring import adapter_state, clone_past_key_values
from .transformers_backend import GenerationError, TransformersModelRuntime
from .treatments import I3_CONDITIONAL_TYPED_CODEC


@dataclass(frozen=True, slots=True)
class PhaseGenerationTrace:
    prefill_adapter: bool
    selector_adapter: bool
    context_token_ids: tuple[int, ...]
    prefix_token_ids: tuple[int, ...]
    combined_token_ids: tuple[int, ...]
    phase_boundary_token_aligned: bool
    world_prefill_forward_count: int
    selector_prefix_forward_count: int
    selector_continuation_forward_count: int
    world_context_recomputed_after_switch: bool
    generated_token_ids: tuple[int, ...]
    finish_reason: str


def _as_ids(value: Any) -> tuple[int, ...]:
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, list) and value and isinstance(value[0], list):
        value = value[0]
    if not isinstance(value, (list, tuple)) or any(type(item) is not int for item in value):
        raise GenerationError("phase generation received unusable token IDs")
    return tuple(value)


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


def phase_generation_boundary_token_ids(
    runtime: TransformersModelRuntime, rendered_input: bytes
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    """Split exact I3 suffix from WORLD context and require token alignment."""

    if not isinstance(rendered_input, bytes):
        raise TypeError("rendered_input must be bytes")
    suffix = I3_CONDITIONAL_TYPED_CODEC.completion_suffix.encode("utf-8")
    if not suffix or not rendered_input.endswith(suffix):
        raise GenerationError("P2 request does not end at the frozen I3 phase boundary")
    context_bytes = rendered_input[: -len(suffix)]
    context_text = context_bytes.decode("utf-8")
    prefix_text = suffix.decode("utf-8")
    combined_text = rendered_input.decode("utf-8")
    tokenizer = runtime.tokenizer
    add_special = runtime.profile.add_special_tokens
    context_ids = tuple(tokenizer.encode(context_text, add_special_tokens=add_special))
    prefix_ids = tuple(tokenizer.encode(prefix_text, add_special_tokens=False))
    combined_ids = tuple(tokenizer.encode(combined_text, add_special_tokens=add_special))
    if not context_ids or not prefix_ids:
        raise GenerationError("P2 phase boundary produced an empty token segment")
    if combined_ids != context_ids + prefix_ids:
        raise GenerationError("P2 I3 byte boundary is not token-aligned under frozen tokenizer")
    return context_ids, prefix_ids, combined_ids


def _allowed_argmax(torch_module: Any, logits: Any, allowed_tokens: list[int]) -> int:
    if not allowed_tokens:
        raise GenerationError("I3 constraint returned no allowed tokens")
    if any(type(token_id) is not int or token_id < 0 for token_id in allowed_tokens):
        raise GenerationError("I3 constraint returned invalid token IDs")
    indices = torch_module.tensor(allowed_tokens, dtype=torch_module.long, device=logits.device)
    selected = int(torch_module.argmax(logits.index_select(0, indices)).item())
    return int(allowed_tokens[selected])


class PhaseSwitchedGenerationRuntime:
    """Expose cached phase-switched greedy generation through ModelRuntime."""

    def __init__(
        self,
        runtime: TransformersModelRuntime,
        *,
        prefill_adapter: bool,
        selector_adapter: bool,
    ) -> None:
        if not isinstance(runtime, TransformersModelRuntime):
            raise TypeError("runtime must be a TransformersModelRuntime")
        if type(prefill_adapter) is not bool or type(selector_adapter) is not bool:
            raise TypeError("phase adapter flags must be booleans")
        self.runtime = runtime
        self.profile = runtime.profile
        self.prefill_adapter = prefill_adapter
        self.selector_adapter = selector_adapter
        self.last_trace: PhaseGenerationTrace | None = None

    def generate(self, request: GenerationRequest) -> RawGenerationResult:
        if not isinstance(request, GenerationRequest):
            raise TypeError("request must be a GenerationRequest")
        if request.model_profile != self.profile:
            raise ValueError("request profile does not match phase runtime")
        policy = request.generation_policy
        if (
            policy.do_sample
            or policy.temperature is not None
            or policy.top_p is not None
            or policy.top_k is not None
            or float(policy.repetition_penalty) != 1.0
        ):
            raise GenerationError("P2 phase runtime accepts only the frozen greedy policy")
        if request.generator is not None or request.stop_hooks:
            raise GenerationError("P2 forbids external generators and stop hooks")
        if request.prefix_allowed_tokens_fn is None:
            raise GenerationError("P2 requires the frozen I3 constrained codec")

        torch_module = self.runtime.torch_module
        if torch_module is None:
            raise GenerationError("P2 phase generation requires PyTorch")
        context_ids, prefix_ids, combined_ids = phase_generation_boundary_token_ids(
            self.runtime, request.rendered_input
        )
        device = self.profile.device
        context_tensor = _tensor_ids(torch_module, context_ids, device=device)
        prefix_tensor = _tensor_ids(torch_module, prefix_ids, device=device)
        inference_context = (
            torch_module.inference_mode()
            if hasattr(torch_module, "inference_mode")
            else nullcontext()
        )
        rng_context = self.runtime._rng_context(request)

        generated: list[int] = []
        selector_continuation_forwards = 0
        with rng_context:
            with inference_context:
                with adapter_state(self.runtime.model, self.prefill_adapter):
                    prefill_output = _forward(
                        self.runtime.model,
                        input_ids=context_tensor,
                        attention_mask=_ones(torch_module, len(context_ids), device=device),
                    )
                phase_a_cache = getattr(prefill_output, "past_key_values", None)
                if phase_a_cache is None:
                    raise GenerationError("P2 WORLD prefill did not return past_key_values")

                with adapter_state(self.runtime.model, self.selector_adapter):
                    prefix_output = _forward(
                        self.runtime.model,
                        input_ids=prefix_tensor,
                        attention_mask=_ones(torch_module, len(combined_ids), device=device),
                        past_key_values=clone_past_key_values(phase_a_cache),
                    )
                    cache = getattr(prefix_output, "past_key_values", None)
                    if cache is None:
                        raise GenerationError("P2 selector prefix did not return past_key_values")
                    logits = prefix_output.logits[0, -1]

                    generation_config = getattr(self.runtime.model, "generation_config", None)
                    eos_ids = getattr(generation_config, "eos_token_id", None)
                    if isinstance(eos_ids, int):
                        eos_set = {eos_ids}
                    elif eos_ids is None:
                        eos_set = set()
                    else:
                        eos_set = set(eos_ids)

                    finish_reason = "length"
                    for step in range(policy.max_new_tokens):
                        full_sequence = combined_ids + tuple(generated)
                        sent = _tensor_ids(torch_module, full_sequence, device=device)[0]
                        allowed = list(request.prefix_allowed_tokens_fn(0, sent))
                        token_id = _allowed_argmax(torch_module, logits, allowed)
                        generated.append(token_id)
                        if token_id in eos_set:
                            finish_reason = "eos_token"
                            break
                        if step + 1 >= policy.max_new_tokens:
                            finish_reason = "length"
                            break
                        token_tensor = _tensor_ids(torch_module, (token_id,), device=device)
                        continuation_output = _forward(
                            self.runtime.model,
                            input_ids=token_tensor,
                            attention_mask=_ones(
                                torch_module,
                                len(combined_ids) + len(generated),
                                device=device,
                            ),
                            past_key_values=cache,
                        )
                        selector_continuation_forwards += 1
                        cache = getattr(continuation_output, "past_key_values", None)
                        if cache is None:
                            raise GenerationError("P2 continuation did not return past_key_values")
                        logits = continuation_output.logits[0, -1]

        generated_ids = tuple(generated)
        raw_text = self.runtime.tokenizer.decode(list(generated_ids), skip_special_tokens=True)
        self.last_trace = PhaseGenerationTrace(
            prefill_adapter=self.prefill_adapter,
            selector_adapter=self.selector_adapter,
            context_token_ids=context_ids,
            prefix_token_ids=prefix_ids,
            combined_token_ids=combined_ids,
            phase_boundary_token_aligned=True,
            world_prefill_forward_count=1,
            selector_prefix_forward_count=1,
            selector_continuation_forward_count=selector_continuation_forwards,
            world_context_recomputed_after_switch=False,
            generated_token_ids=generated_ids,
            finish_reason=finish_reason,
        )
        return RawGenerationResult(
            opportunity_id=request.opportunity_id,
            generation_id=request.generation_id,
            context_pack_id=request.context_pack_id,
            context_hash=request.context_hash,
            rendered_input_hash=request.rendered_input_hash,
            interface_treatment_id=request.interface_treatment_id,
            interface_treatment_version=request.interface_treatment_version,
            interface_treatment_digest=request.interface_treatment_digest,
            constraint_policy_id=request.constraint_policy_id,
            raw_text=raw_text,
            token_ids=generated_ids,
            model_profile_id=self.profile.profile_id,
            generation_policy_id=policy.policy_id,
            generation_policy_version=policy.version,
            generation_seed_id=request.generation_seed_id,
            generation_seed=request.generation_seed,
            finish_reason=finish_reason,
        )


__all__ = [
    "PhaseGenerationTrace",
    "PhaseSwitchedGenerationRuntime",
    "phase_generation_boundary_token_ids",
]
