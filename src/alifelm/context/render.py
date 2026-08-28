"""Deterministic model-facing renderer for the EXP-000 mechanics baseline."""

from __future__ import annotations

from .types import (
    ActionPresentation,
    DEFAULT_ACTION_PRESENTATION,
    ModelInput,
    VisibleRecord,
    VisibleRecordCategory,
)


def _render_record(record: VisibleRecord) -> str:
    payload = record.payload
    if record.category is VisibleRecordCategory.DELIVERED_MESSAGE:
        return f"- from {payload.sender_id}: {payload.body}"
    if record.category is VisibleRecordCategory.SENT_MESSAGE:
        return f"- to {payload.recipient_id}: {payload.body}"
    if record.category is VisibleRecordCategory.INCOMING_PROPOSAL:
        return f"- request {payload.proposal_id} from {payload.proposer_id}"
    if record.category is VisibleRecordCategory.OUTGOING_PROPOSAL:
        return f"- request {payload.proposal_id} to {payload.target_id}"
    return (
        f"- request {payload.proposal_id} with {payload.counterparty_id}: "
        f"{payload.result.value}"
    )


def _render_section(title: str, records: tuple[VisibleRecord, ...]) -> list[str]:
    lines = [title]
    if not records:
        lines.append("- none")
    else:
        lines.extend(_render_record(record) for record in records)
    return lines


def render_model_input(
    model_input: ModelInput,
    action_presentation: ActionPresentation = DEFAULT_ACTION_PRESENTATION,
) -> str:
    """Render only ``ModelInput`` and the versioned neutral action reference."""

    if not isinstance(model_input, ModelInput):
        raise TypeError("model_input must be a ModelInput")
    if not isinstance(action_presentation, ActionPresentation):
        raise TypeError("action_presentation must be an ActionPresentation")
    if (
        model_input.stable_prefix.action_presentation_policy_id
        != action_presentation.policy_id
        or model_input.stable_prefix.action_presentation_version
        != action_presentation.version
    ):
        raise ValueError("model input action presentation reference does not match")

    lines = [
        "Self:",
        f"- opaque id: {model_input.current_self.agent_id}",
        f"- age: {model_input.current_self.age}",
        "Listed opaque agents:",
    ]
    if model_input.peer_directory:
        lines.extend(f"- {entry.agent_id}" for entry in model_input.peer_directory)
    else:
        lines.append("- none")

    lines.extend(_render_section("New directed information:", model_input.newly_delivered))
    lines.extend(_render_section("Visible bilateral requests:", model_input.visible_protocol_state))
    lines.extend(_render_section("Prior visible records:", model_input.prior_history))
    lines.append("Actions:")
    for internal_action in action_presentation.presentation_order:
        entry = action_presentation.entry(internal_action)
        fields = ",".join(entry.payload_fields) if entry.payload_fields else "none"
        lines.append(
            f"- {entry.model_label}: {entry.description} payload_fields={fields}"
        )
    return "\n".join(lines)


def render_model_input_bytes(
    model_input: ModelInput,
    action_presentation: ActionPresentation = DEFAULT_ACTION_PRESENTATION,
) -> bytes:
    return render_model_input(model_input, action_presentation).encode("utf-8")


class ModelFacingRenderer:
    """Small object form for dependency injection in later runtime work."""

    def __init__(self, action_presentation: ActionPresentation = DEFAULT_ACTION_PRESENTATION):
        if not isinstance(action_presentation, ActionPresentation):
            raise TypeError("action_presentation must be an ActionPresentation")
        self._action_presentation = action_presentation

    def render(self, model_input: ModelInput) -> str:
        return render_model_input(model_input, self._action_presentation)
