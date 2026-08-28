"""Researcher-only runtime and tokenizer contamination inspection."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import platform
from typing import Any

from .profile import ModelProfile


@dataclass(frozen=True, slots=True)
class RuntimeEnvironment:
    python_version: str
    os_runtime: str
    torch_version: str
    transformers_version: str
    cuda_available: bool
    cuda_runtime: str | None
    gpu_name: str | None
    device_selected: str
    dtype: str
    model_revision: str | None
    tokenizer_revision: str | None


@dataclass(frozen=True, slots=True)
class ChatTemplateAudit:
    encoding_mode: str
    add_special_tokens: bool
    bos_token: str | None
    eos_token: str | None
    pad_token: str | None
    special_tokens_map: tuple[tuple[str, str], ...]
    chat_template_present: bool
    chat_template_digest: str | None
    chat_template_rendered_digest: str | None
    role_or_control_tokens_present: bool
    default_system_prompt_detected: bool
    baseline_uses_chat_template: bool


@dataclass(frozen=True, slots=True)
class GenerationSemanticsAudit:
    do_sample: bool
    temperature: float | None
    top_p: float | None
    top_k: int | None
    max_new_tokens: int
    eos_token_id: tuple[int, ...]
    bos_token_id: int | None
    pad_token_id: int | None
    repetition_penalty: float
    seed_id: str | None
    generation_seed: int | None
    retry_count_in_identity: bool
    wall_clock_in_identity: bool


def collect_runtime_environment(
    profile: ModelProfile,
    *,
    torch_module: Any,
    transformers_module: Any,
) -> RuntimeEnvironment:
    cuda_available = bool(torch_module.cuda.is_available())
    return RuntimeEnvironment(
        python_version=platform.python_version(),
        os_runtime=platform.platform(),
        torch_version=str(torch_module.__version__),
        transformers_version=str(transformers_module.__version__),
        cuda_available=cuda_available,
        cuda_runtime=str(torch_module.version.cuda) if torch_module.version.cuda else None,
        gpu_name=(torch_module.cuda.get_device_name(0) if cuda_available else None),
        device_selected=profile.device,
        dtype=profile.dtype,
        model_revision=profile.model_revision,
        tokenizer_revision=profile.tokenizer_revision,
    )


def inspect_chat_template(
    tokenizer: Any,
    canonical_input: str,
    *,
    add_special_tokens: bool,
) -> ChatTemplateAudit:
    """Inspect but never select a model-provided chat template."""

    template = getattr(tokenizer, "chat_template", None)
    template_text = (
        json.dumps(template, ensure_ascii=False, sort_keys=True)
        if isinstance(template, dict)
        else str(template) if template else None
    )
    rendered: str | None = None
    if template and hasattr(tokenizer, "apply_chat_template"):
        try:
            rendered = tokenizer.apply_chat_template(
                [{"role": "user", "content": canonical_input}],
                tokenize=False,
                add_generation_prompt=True,
            )
        except Exception:
            rendered = None
    remainder = rendered.replace(canonical_input, "") if rendered else ""
    lowered = remainder.lower()
    role_control = any(
        marker in lowered
        for marker in ("system", "assistant", "user", "<|im_", "[inst]", "<s>")
    )
    default_system = "system" in lowered and any(
        marker in lowered for marker in ("helpful", "assistant", "you are")
    )
    special_map = tuple(
        sorted(
            (str(key), str(value))
            for key, value in getattr(tokenizer, "special_tokens_map", {}).items()
        )
    )
    digest = lambda text: hashlib.sha256(text.encode("utf-8")).hexdigest()
    return ChatTemplateAudit(
        encoding_mode="MINIMAL_EXPLICIT_TOKENIZER_ENCODING",
        add_special_tokens=add_special_tokens,
        bos_token=getattr(tokenizer, "bos_token", None),
        eos_token=getattr(tokenizer, "eos_token", None),
        pad_token=getattr(tokenizer, "pad_token", None),
        special_tokens_map=special_map,
        chat_template_present=bool(template),
        chat_template_digest=digest(template_text) if template_text else None,
        chat_template_rendered_digest=digest(rendered) if rendered else None,
        role_or_control_tokens_present=role_control,
        default_system_prompt_detected=default_system,
        baseline_uses_chat_template=False,
    )


def inspect_generation_semantics(runtime: Any, request: Any) -> GenerationSemanticsAudit:
    """Resolve explicit policy controls against pinned model generation config."""

    config = runtime.model.generation_config
    eos = getattr(config, "eos_token_id", None)
    if eos is None:
        eos_ids: tuple[int, ...] = ()
    elif isinstance(eos, int):
        eos_ids = (eos,)
    else:
        eos_ids = tuple(int(value) for value in eos)
    policy = request.generation_policy
    return GenerationSemanticsAudit(
        do_sample=policy.do_sample,
        temperature=policy.temperature,
        top_p=policy.top_p,
        top_k=policy.top_k,
        max_new_tokens=policy.max_new_tokens,
        eos_token_id=eos_ids,
        bos_token_id=getattr(config, "bos_token_id", None),
        pad_token_id=getattr(config, "pad_token_id", None),
        repetition_penalty=float(policy.repetition_penalty),
        seed_id=policy.seed_id,
        generation_seed=request.generation_seed,
        retry_count_in_identity=False,
        wall_clock_in_identity=False,
    )
