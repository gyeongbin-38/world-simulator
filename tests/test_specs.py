from dataclasses import fields
import json
from pathlib import Path

import pytest

from alifelm.domain import (
    ActionKind,
    ActionIntent,
    AgentState,
    ArtifactRef,
    BirthCandidate,
    BirthResolution,
    ConflictReason,
    DomainEvent,
    IntentBatch,
    MessageRecord,
    ProposalState,
    RecordKind,
    ReproductionProposal,
    TICK_PHASES,
    TickPhase,
    ValidatedIntent,
)
from alifelm.kernel import (
    CognitionFixture,
    CognitionOpportunity,
    CommitRequest,
    CommitResult,
    CommitError,
    Snapshot,
    TransitionFragment,
    TransitionKind,
)
from alifelm.model import (
    CodecValidityStatus,
    CommitValidityStatus,
    DomainValidityStatus,
    InterfaceMode,
)


def test_contract_manifest_points_to_existing_canonical_sources(repository_root: Path) -> None:
    manifest_path = repository_root / "specs" / "contracts" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    for relative_path in manifest["canonical_sources"]:
        assert (repository_root / relative_path).is_file(), relative_path
    for relative_path in manifest["schemas"]:
        assert (repository_root / "specs" / relative_path).is_file(), relative_path


def test_schema_files_are_valid_json_documents(repository_root: Path) -> None:
    for schema_path in (repository_root / "specs").rglob("*.json"):
        document = json.loads(schema_path.read_text(encoding="utf-8"))
        assert document["$schema"] == "https://json-schema.org/draft/2020-12/schema"


@pytest.mark.parametrize(
    ("python_type", "schema_path"),
    [
        (AgentState, "specs/contracts/agent-state.schema.json"),
        (ActionIntent, "specs/contracts/action-intent.schema.json"),
        (IntentBatch, "specs/contracts/intent-batch.schema.json"),
        (ReproductionProposal, "specs/contracts/reproduction-proposal.schema.json"),
        (BirthCandidate, "specs/contracts/birth-candidate.schema.json"),
        (ArtifactRef, "specs/contracts/artifact-ref.schema.json"),
        (DomainEvent, "specs/contracts/domain-event.schema.json"),
        (MessageRecord, "specs/contracts/message-record.schema.json"),
        (ValidatedIntent, "specs/contracts/validated-intent.schema.json"),
        (Snapshot, "specs/contracts/snapshot.schema.json"),
        (CognitionFixture, "specs/contracts/cognition-fixture.schema.json"),
        (CognitionOpportunity, "specs/contracts/cognition-opportunity.schema.json"),
        (TransitionFragment, "specs/contracts/transition-fragment.schema.json"),
        (CommitRequest, "specs/contracts/commit-request.schema.json"),
        (CommitResult, "specs/contracts/commit-result.schema.json"),
        (BirthResolution, "specs/contracts/birth-resolution.schema.json"),
    ],
)
def test_python_and_schema_field_sets_match(
    repository_root: Path, python_type: type, schema_path: str
) -> None:
    schema = json.loads((repository_root / schema_path).read_text(encoding="utf-8"))
    assert set(schema["properties"]) == {field.name for field in fields(python_type)}
    assert set(schema["required"]) == set(schema["properties"])
    assert python_type.__dataclass_params__.frozen


def test_schema_enums_and_action_payload_discriminator_match_python(repository_root: Path) -> None:
    action_schema = json.loads(
        (repository_root / "specs/contracts/action-intent.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert action_schema["properties"]["kind"]["enum"] == [
        action.value for action in ActionKind
    ]
    assert [branch["properties"]["kind"]["const"] for branch in action_schema["oneOf"]] == [
        action.value for action in ActionKind
    ]

    state_schema = json.loads(
        (repository_root / "specs/contracts/agent-state.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert state_schema["properties"]["state"]["enum"] == ["ALIVE", "DEAD"]
    assert [state.value for state in ProposalState] == json.loads(
        (repository_root / "specs/contracts/reproduction-proposal.schema.json").read_text(
            encoding="utf-8"
        )
    )["properties"]["state"]["enum"]
    record_schema = json.loads(
        (repository_root / "specs/contracts/record.schema.json").read_text(encoding="utf-8")
    )
    assert [branch["const"] for branch in record_schema["oneOf"]] == [
        record.value for record in RecordKind
    ]
    phase_schema = json.loads(
        (repository_root / "specs/contracts/tick-phase.schema.json").read_text(encoding="utf-8")
    )
    assert phase_schema["enum"] == [phase.value for phase in TICK_PHASES]
    assert tuple(TickPhase) == TICK_PHASES

    assert "SEND target_agent_id != actor_id" in action_schema["x-alifelm-invariants"]

    transition_schema = json.loads(
        (repository_root / "specs/contracts/transition-fragment.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert transition_schema["properties"]["kind"]["enum"] == [
        kind.value for kind in TransitionKind
    ]
    assert [branch["properties"]["kind"]["const"] for branch in transition_schema["oneOf"]] == [
        kind.value for kind in TransitionKind
    ]
    commit_result_schema = json.loads(
        (repository_root / "specs/contracts/commit-result.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert commit_result_schema["properties"]["error"]["anyOf"][0]["enum"] == [
        error.value for error in CommitError
    ]
    assert [reason.value for reason in ConflictReason] == [
        transition_schema["oneOf"][3]["properties"]["payload"]["properties"]["reason"]["const"]
    ]


def test_context_fabric_machine_contracts_pin_exp000_baseline(
    repository_root: Path,
) -> None:
    contracts = repository_root / "specs" / "contracts"
    policy = json.loads((contracts / "context-policy.schema.json").read_text(encoding="utf-8"))
    context_pack = json.loads((contracts / "context-pack.schema.json").read_text(encoding="utf-8"))
    presentation = json.loads(
        (contracts / "action-presentation.schema.json").read_text(encoding="utf-8")
    )

    visibility = policy["properties"]["visibility"]["properties"]
    assert visibility["current_tick"]["const"] is False
    assert visibility["lineage_or_parent_ids"]["const"] is False
    assert visibility["peer_private_records"]["const"] is False
    assert visibility["same_tick_peer_outputs"]["const"] is False
    assert visibility["sprite_or_ui_identity"]["const"] is False
    assert policy["properties"]["recall"]["properties"]["mode"]["const"] == "DISABLED"
    assert (
        policy["properties"]["history"]["properties"]["lossy_summarization"]["const"]
        is False
    )

    model_input = context_pack["properties"]["model_input"]["properties"]
    assert set(model_input["current_self"]["properties"]) == {"agent_id", "age"}
    assert "bound_tick" not in model_input
    assert "lineage" not in model_input
    assert "infrastructure" not in model_input

    actions = presentation["properties"]["actions"]["properties"]
    assert set(actions) == {"SEND", "PROPOSE", "ACCEPT", "REJECT", "WAIT"}
    assert presentation["properties"]["model_supplied_fields"]["const"] == [
        "action_label",
        "payload",
    ]
    assert presentation["properties"]["gateway_supplied_fields"]["const"] == [
        "intent_id",
        "actor_id",
        "tick",
    ]
    labels = [action["properties"]["model_label"]["const"] for action in actions.values()]
    assert len(labels) == len(set(labels))
    rendered_mechanics = " ".join(
        action["properties"]["description"]["const"].lower()
        for action in actions.values()
    )
    assert not {"survive", "mate", "family", "friend", "cooperate", "civilization"} & set(
        rendered_mechanics.split()
    )


def test_typed_codec_diagnostic_contract_is_research_only(
    repository_root: Path,
) -> None:
    contracts = repository_root / "specs" / "contracts"
    treatment = json.loads(
        (contracts / "interface-treatment.schema.json").read_text(encoding="utf-8")
    )
    diagnostic = json.loads(
        (contracts / "typed-codec-diagnostic.schema.json").read_text(encoding="utf-8")
    )

    assert treatment["properties"]["mode"]["enum"] == [mode.value for mode in InterfaceMode]
    assert diagnostic["properties"]["codec_status"]["enum"] == [
        status.value for status in CodecValidityStatus
    ]
    assert diagnostic["properties"]["domain_status"]["enum"] == [
        status.value for status in DomainValidityStatus
    ]
    assert diagnostic["properties"]["commit_status"]["enum"] == [
        status.value for status in CommitValidityStatus
    ]
    assert "researcher-only" in diagnostic["x-alifelm-classification"]

    action_score = json.loads(
        (contracts / "action-label-score-diagnostic.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert action_score["properties"]["scores"]["minItems"] == 5
    assert action_score["properties"]["scores"]["maxItems"] == 5
    assert "researcher-only" in action_score["x-alifelm-classification"]
