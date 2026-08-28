"""Versioned, non-canonical model/interface diagnostic treatments."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import StrEnum
import hashlib
import json
import re
from typing import Any

from alifelm.context import ActionPresentation, DEFAULT_ACTION_PRESENTATION


class InterfaceMode(StrEnum):
    I0 = "I0"
    I1 = "I1"
    I2 = "I2"
    I3 = "I3"


@dataclass(frozen=True, slots=True)
class InterfaceTreatment:
    treatment_id: str
    version: str
    mode: InterfaceMode
    completion_suffix: str
    constraint_policy_id: str | None

    @property
    def digest(self) -> str:
        value = {
            "domain": "ALIFELM_INTERFACE_TREATMENT_V1",
            "treatment_id": self.treatment_id,
            "version": self.version,
            "mode": self.mode.value,
            "completion_suffix": self.completion_suffix,
            "constraint_policy_id": self.constraint_policy_id,
        }
        encoded = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def render(self, baseline: bytes) -> bytes:
        if not isinstance(baseline, bytes):
            raise TypeError("baseline model input must be bytes")
        return baseline + self.completion_suffix.encode("utf-8")


I0_STRICT_FREE_GENERATION = InterfaceTreatment(
    treatment_id="i05r-i0-strict-free-generation",
    version="1.0.0",
    mode=InterfaceMode.I0,
    completion_suffix="",
    constraint_policy_id=None,
)

# Syntax-only completion boundary. It contains no objective, preferred action,
# example, role, or request for reasoning.
I1_NEUTRAL_CODEC_SCAFFOLD = InterfaceTreatment(
    treatment_id="i05r-i1-neutral-codec-scaffold",
    version="1.0.0",
    mode=InterfaceMode.I1,
    completion_suffix="\nAction selection JSON:\n",
    constraint_policy_id=None,
)

I2_SYNTAX_CONSTRAINED_CODEC = InterfaceTreatment(
    treatment_id="i05r-i2-syntax-constrained-codec",
    version="1.0.0",
    mode=InterfaceMode.I2,
    completion_suffix="\nAction selection JSON:\n",
    constraint_policy_id="i05r-neutral-action-json-syntax-v1",
)

I3_CONDITIONAL_TYPED_CODEC = InterfaceTreatment(
    treatment_id="i05r2-i3-conditional-typed-codec",
    version="1.0.0",
    mode=InterfaceMode.I3,
    completion_suffix="\nAction selection JSON:\n",
    constraint_policy_id="i05r2-conditional-typed-action-json-v1",
)


def action_codec_json_schema(
    presentation: ActionPresentation = DEFAULT_ACTION_PRESENTATION,
) -> dict[str, Any]:
    """Return syntax-only I2 schema without choosing action or payload values."""

    labels = [presentation.entry(action).model_label for action in presentation.presentation_order]
    payload_keys = sorted(
        {field for entry in presentation.actions for field in entry.payload_fields}
    )
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["action_label", "payload"],
        "properties": {
            "action_label": {"type": "string", "enum": labels},
            "payload": {
                "type": "object",
                "additionalProperties": False,
                "properties": {key: {"type": "string"} for key in payload_keys},
            },
        },
    }


def typed_action_codec_json_schema(
    presentation: ActionPresentation = DEFAULT_ACTION_PRESENTATION,
) -> dict[str, Any]:
    """Action-conditional structure without constraining any semantic value."""

    opaque_string = {
        "type": "string",
        "pattern": "^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$",
    }
    field_schemas = {
        "target_agent_id": opaque_string,
        "proposal_id": opaque_string,
        "body": {"type": "string"},
    }
    branches = []
    for action in presentation.presentation_order:
        entry = presentation.entry(action)
        branches.append(
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["action_label", "payload"],
                "properties": {
                    "action_label": {"const": entry.model_label},
                    "payload": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": list(entry.payload_fields),
                        "properties": {
                            field: field_schemas[field]
                            for field in entry.payload_fields
                        },
                    },
                },
            }
        )
    return {"oneOf": branches}


def build_transformers_constraint(tokenizer: Any, *, schema: dict[str, Any] | None = None):
    """Build an optional constrained-codec mask without affecting core paths."""

    try:
        from lmformatenforcer import JsonSchemaParser
        from lmformatenforcer.tokenenforcer import TokenEnforcer, TokenEnforcerTokenizerData
    except ImportError as error:
        raise RuntimeError(
            "constrained codecs require the optional 'model-diagnostics' dependency extra"
        ) from error
    parser = JsonSchemaParser(schema or action_codec_json_schema())
    vocab_size = len(tokenizer)
    token_zero = tokenizer.encode("0", add_special_tokens=False)[-1]
    special_ids = set(tokenizer.all_special_ids)
    regular_tokens = []
    for token_id in range(vocab_size):
        if token_id in special_ids:
            continue
        after_zero = tokenizer.decode([token_zero, token_id])
        decoded = tokenizer.decode([token_id])
        decoded_after_zero = after_zero[1:] if after_zero.startswith("0") else after_zero
        is_word_start = len(decoded_after_zero) > len(decoded)
        regular_tokens.append((token_id, decoded_after_zero, is_word_start))
    tokenizer_data = TokenEnforcerTokenizerData(
        regular_tokens,
        lambda tokens: tokenizer.decode(tokens),
        tokenizer.eos_token_id,
        False,
        vocab_size,
    )
    enforcer = TokenEnforcer(tokenizer_data, parser)

    def allowed_tokens(batch_id: int, sent: Any) -> list[int]:
        del batch_id
        sequence = sent.tolist() if hasattr(sent, "tolist") else list(sent)
        return list(enforcer.get_allowed_tokens(sequence).allowed_tokens)

    return allowed_tokens


class ResearchDiagnosticLabel(StrEnum):
    PROMPT_ECHO = "PROMPT_ECHO"
    PROSE_WITH_KNOWN_ACTION = "PROSE_WITH_KNOWN_ACTION"
    INVENTED_ACTION = "INVENTED_ACTION"
    FORMAT_NEAR_MISS = "FORMAT_NEAR_MISS"
    NARRATIVE_CONTINUATION = "NARRATIVE_CONTINUATION"
    VALID_CODEC = "VALID_CODEC"


@dataclass(frozen=True, slots=True)
class ResearchGenerationDiagnostic:
    primary_label: ResearchDiagnosticLabel
    labels: tuple[ResearchDiagnosticLabel, ...]
    prompt_echo: bool


_ACTIONISH = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")


def diagnose_generation(
    raw_text: str,
    rendered_input: str,
    *,
    strict_valid: bool,
    presentation: ActionPresentation = DEFAULT_ACTION_PRESENTATION,
) -> ResearchGenerationDiagnostic:
    """Deterministic post-hoc labels that never feed parser or simulation state."""

    if not isinstance(raw_text, str) or not isinstance(rendered_input, str):
        raise TypeError("diagnostic inputs must be strings")
    known = {entry.model_label for entry in presentation.actions}
    raw_upper = raw_text.upper()
    prompt_lines = {
        line.strip() for line in rendered_input.splitlines() if len(line.strip()) >= 20
    }
    raw_lines = [line.strip() for line in raw_text.splitlines() if len(line.strip()) >= 20]
    echo = any(
        source in raw_text
        or SequenceMatcher(None, source, generated, autojunk=False).ratio() >= 0.72
        for source in prompt_lines
        for generated in raw_lines
    )
    labels: list[ResearchDiagnosticLabel] = []
    if strict_valid:
        labels.append(ResearchDiagnosticLabel.VALID_CODEC)
    if echo:
        labels.append(ResearchDiagnosticLabel.PROMPT_ECHO)
    if not strict_valid and (
        raw_text.lstrip().startswith("{")
        or '"action_label"' in raw_text
        or '"payload"' in raw_text
    ):
        labels.append(ResearchDiagnosticLabel.FORMAT_NEAR_MISS)
    if not strict_valid and any(label in raw_upper for label in known):
        labels.append(ResearchDiagnosticLabel.PROSE_WITH_KNOWN_ACTION)
    structural_names = {
        "ACTION_LABEL",
        "PAYLOAD_FIELDS",
        "TARGET_AGENT_ID",
        "PROPOSAL_ID",
    }
    invented = {
        value
        for value in _ACTIONISH.findall(raw_upper)
        if value not in known and value not in structural_names
    }
    if not strict_valid and invented:
        labels.append(ResearchDiagnosticLabel.INVENTED_ACTION)
    if not labels:
        labels.append(ResearchDiagnosticLabel.NARRATIVE_CONTINUATION)
    priority = (
        ResearchDiagnosticLabel.VALID_CODEC,
        ResearchDiagnosticLabel.PROMPT_ECHO,
        ResearchDiagnosticLabel.FORMAT_NEAR_MISS,
        ResearchDiagnosticLabel.PROSE_WITH_KNOWN_ACTION,
        ResearchDiagnosticLabel.INVENTED_ACTION,
        ResearchDiagnosticLabel.NARRATIVE_CONTINUATION,
    )
    primary = next(item for item in priority if item in labels)
    return ResearchGenerationDiagnostic(primary, tuple(labels), echo)
