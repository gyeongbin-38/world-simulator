from __future__ import annotations

import json

from alifelm.context import DEFAULT_ACTION_PRESENTATION
from alifelm.domain import AgentId, Duration, RunId
from alifelm.kernel import EqualOpportunityScheduler, SimulationRun
from alifelm.model import (
    CodecValidityStatus,
    CommitValidityStatus,
    DomainValidityStatus,
    I0_STRICT_FREE_GENERATION,
    I1_NEUTRAL_CODEC_SCAFFOLD,
    I2_SYNTAX_CONSTRAINED_CODEC,
    I3_CONDITIONAL_TYPED_CODEC,
    ResearchDiagnosticLabel,
    action_codec_json_schema,
    diagnose_generation,
    evaluate_typed_codec,
    typed_codec_evaluation_bytes,
    typed_action_codec_json_schema,
)
from alifelm.model.evidence import ModelOutputStatus, classify_parse_failure


def test_i0_exactly_preserves_baseline_rendering() -> None:
    baseline = b"neutral baseline"
    assert I0_STRICT_FREE_GENERATION.render(baseline) == baseline


def test_i1_is_versioned_syntax_only_suffix() -> None:
    baseline = b"neutral baseline"
    rendered = I1_NEUTRAL_CODEC_SCAFFOLD.render(baseline).decode()
    assert rendered == "neutral baseline\nAction selection JSON:\n"
    forbidden = ("survive", "cooperate", "best action", "think carefully", "family")
    assert not any(value in rendered.lower() for value in forbidden)
    assert len(I1_NEUTRAL_CODEC_SCAFFOLD.digest) == 64


def test_i2_is_explicitly_distinct_from_i1() -> None:
    assert I2_SYNTAX_CONSTRAINED_CODEC.completion_suffix == I1_NEUTRAL_CODEC_SCAFFOLD.completion_suffix
    assert I2_SYNTAX_CONSTRAINED_CODEC.constraint_policy_id is not None
    assert I2_SYNTAX_CONSTRAINED_CODEC.digest != I1_NEUTRAL_CODEC_SCAFFOLD.digest


def test_i3_is_distinct_versioned_typed_treatment() -> None:
    assert I3_CONDITIONAL_TYPED_CODEC.constraint_policy_id is not None
    assert I3_CONDITIONAL_TYPED_CODEC.digest != I2_SYNTAX_CONSTRAINED_CODEC.digest


def test_i2_schema_constrains_codec_not_action_preference() -> None:
    schema = action_codec_json_schema()
    labels = schema["properties"]["action_label"]["enum"]
    assert labels == [
        DEFAULT_ACTION_PRESENTATION.entry(action).model_label
        for action in DEFAULT_ACTION_PRESENTATION.presentation_order
    ]
    assert "default" not in json.dumps(schema)
    assert set(schema["properties"]["payload"]["properties"]) == {
        "body",
        "proposal_id",
        "target_agent_id",
    }


def test_i3_schema_has_exact_action_conditional_payload_shapes() -> None:
    schema = typed_action_codec_json_schema()
    branches = schema["oneOf"]
    observed = {
        branch["properties"]["action_label"]["const"]: tuple(
            branch["properties"]["payload"]["required"]
        )
        for branch in branches
    }
    expected = {
        entry.model_label: entry.payload_fields
        for entry in DEFAULT_ACTION_PRESENTATION.actions
    }
    assert observed == expected
    serialized = json.dumps(schema)
    assert '"enum": ["A"' not in serialized
    assert "proposal-" not in serialized


def test_research_diagnostic_never_upgrades_malformed_known_action() -> None:
    raw = "I choose NO_DIRECTED_ACTION because that seems suitable."
    result = diagnose_generation(raw, "Actions:\n- NO_DIRECTED_ACTION: description", strict_valid=False)
    assert ResearchDiagnosticLabel.PROSE_WITH_KNOWN_ACTION in result.labels
    assert ResearchDiagnosticLabel.VALID_CODEC not in result.labels


def test_prompt_echo_detects_near_copy() -> None:
    prompt = "- NO_DIRECTED_ACTION: Submit no directed text or bilateral request in this opportunity."
    raw = "- NO_DIRECTED_ACTION: No directed text or bilateral request is submitted."
    result = diagnose_generation(raw, prompt, strict_valid=False)
    assert result.prompt_echo is True
    assert ResearchDiagnosticLabel.PROMPT_ECHO in result.labels


def test_format_near_miss_is_research_only_label() -> None:
    raw = '{"action_label":"NO_DIRECTED_ACTION","payload":'
    result = diagnose_generation(raw, "Actions:", strict_valid=False)
    assert result.primary_label is ResearchDiagnosticLabel.FORMAT_NEAR_MISS
    assert ResearchDiagnosticLabel.VALID_CODEC not in result.labels


def test_valid_codec_label_requires_strict_parser_success() -> None:
    raw = '{"action_label":"NO_DIRECTED_ACTION","payload":{}}'
    invalid = diagnose_generation(raw, "Actions:", strict_valid=False)
    valid = diagnose_generation(raw, "Actions:", strict_valid=True)
    assert ResearchDiagnosticLabel.VALID_CODEC not in invalid.labels
    assert valid.primary_label is ResearchDiagnosticLabel.VALID_CODEC


def test_unclosed_outer_json_at_token_boundary_is_truncated() -> None:
    raw = '{"action_label":"NO_DIRECTED_ACTION","payload":{}'
    try:
        json.loads(raw)
    except json.JSONDecodeError as error:
        assert classify_parse_failure(raw, error) is ModelOutputStatus.TRUNCATED
    else:  # pragma: no cover - fixture itself must remain malformed
        raise AssertionError("truncation fixture unexpectedly parsed")


def _diagnostic_run():
    run = SimulationRun.bootstrap(
        RunId("i05r2-test"),
        lifespan_ticks=Duration(20),
        founder_ids=(AgentId("A"), AgentId("B")),
    )
    opportunity = EqualOpportunityScheduler().enumerate(run.snapshot)[0]
    return run, opportunity


def test_i3_wait_is_codec_domain_and_commit_valid_without_mutation() -> None:
    run, opportunity = _diagnostic_run()
    before = run.state_hash()
    result = evaluate_typed_codec(
        '{"action_label":"NO_DIRECTED_ACTION","payload":{}}',
        opportunity,
        run,
    )
    assert result.codec_status is CodecValidityStatus.CODEC_VALID
    assert result.domain_status is DomainValidityStatus.DOMAIN_VALID
    assert result.commit_status is CommitValidityStatus.COMMIT_VALID
    assert run.state_hash() == before


def test_i3_unknown_target_is_codec_valid_but_domain_invalid() -> None:
    run, opportunity = _diagnostic_run()
    result = evaluate_typed_codec(
        '{"action_label":"DIRECT_TEXT","payload":{"target_agent_id":"Z","body":"x"}}',
        opportunity,
        run,
    )
    assert result.codec_status is CodecValidityStatus.CODEC_VALID
    assert result.domain_status is DomainValidityStatus.UNKNOWN_TARGET
    assert result.commit_status is CommitValidityStatus.DOMAIN_INVALID


def test_i3_unknown_proposal_is_codec_valid_but_domain_invalid() -> None:
    run, opportunity = _diagnostic_run()
    result = evaluate_typed_codec(
        '{"action_label":"CONFIRM_BILATERAL_REQUEST","payload":{"proposal_id":"P"}}',
        opportunity,
        run,
    )
    assert result.codec_status is CodecValidityStatus.CODEC_VALID
    assert result.domain_status is DomainValidityStatus.UNKNOWN_PROPOSAL


def test_i3_action_payload_mismatch_never_becomes_domain_valid() -> None:
    run, opportunity = _diagnostic_run()
    result = evaluate_typed_codec(
        '{"action_label":"NO_DIRECTED_ACTION","payload":{"body":"x"}}',
        opportunity,
        run,
    )
    assert result.codec_status is CodecValidityStatus.ACTION_PAYLOAD_TYPE_MISMATCH
    assert result.domain_status is DomainValidityStatus.NOT_CODEC_VALID


def test_typed_codec_evidence_is_deterministic_and_researcher_only() -> None:
    run, opportunity = _diagnostic_run()
    evaluation = evaluate_typed_codec(
        '{"action_label":"NO_DIRECTED_ACTION","payload":{}}', opportunity, run
    )
    arguments = {
        "generation_id": "generation-1",
        "context_hash": "a" * 64,
        "treatment_id": I3_CONDITIONAL_TYPED_CODEC.treatment_id,
        "treatment_version": I3_CONDITIONAL_TYPED_CODEC.version,
    }
    first = typed_codec_evaluation_bytes(evaluation, **arguments)
    second = typed_codec_evaluation_bytes(evaluation, **arguments)

    assert first == second
    decoded = json.loads(first)
    assert decoded["codec_status"] == "CODEC_VALID"
    assert decoded["domain_status"] == "DOMAIN_VALID"
    assert "simulation_state" not in decoded
