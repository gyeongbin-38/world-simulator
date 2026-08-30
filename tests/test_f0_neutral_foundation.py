from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from alifelm.model.foundation_data import (
    Direction,
    ExampleValidationError,
    MessageRecord,
    ProposalRecord,
    SPLIT_SIZES,
    SemanticFamily,
    SyntheticVisibleState,
    canonical_json,
    derive_split_seed,
    evaluation_probe_fingerprint,
    generate_example,
    generate_visible_state,
    load_reserved_evaluation_fingerprints,
    solve,
    structural_fingerprint,
    validate_example,
)


def _load_spec(repository_root: Path, relative_path: str) -> dict[str, object]:
    return json.loads((repository_root / relative_path).read_text(encoding="utf-8"))


def test_c0v2_provenance_and_ambiguity_retirement(repository_root: Path) -> None:
    """C0V2-PROVENANCE-001; C0V2-AMBIGUITY-001."""

    spec = _load_spec(repository_root, "specs/experiments/founder-c0-v2.yaml")
    retired = spec["historical_v1"]["retired_probe"]
    assert retired == {
        "id": "VC02",
        "category": "peer",
        "visible_facts": [
            "Own visible age: 4",
            "Visible peer handles: P0, P1",
        ],
        "question": "Select the option exactly supported by the visible peer directory.",
        "choices": ["1", "2", "3"],
        "expected": "2",
        "source_binding": "peer_directory",
        "status": "RETIRED_AMBIGUOUS",
        "retirement_reason": (
            "question lacks an explicit predicate identifying what quantity should be selected"
        ),
    }
    assert spec["firewalls"]["v1_probe_modified"] is False
    for result in spec["historical_v1"]["results"]:
        assert result["score_recomputed"] is False
        assert result["clean_critical_failures_supporting_rejection"]


def test_c0v2_replacement_freeze_and_digest(repository_root: Path) -> None:
    """C0V2-PROVENANCE-002; C0V2-AMBIGUITY-002."""

    spec = _load_spec(repository_root, "specs/experiments/founder-c0-v2.yaml")
    assert spec["corpus_id"] == "FOUNDER_C0_V2"
    assert spec["status"] == "FROZEN"
    assert spec["probe_order"] == [
        "VC00",
        "VC02R",
        "VC09",
        "VC12",
        "VC15",
        "VC01",
        "VC11",
        "VC05",
        "VC10",
        "VC16",
    ]
    probes = {probe["id"]: probe for probe in spec["probes"]}
    assert "VC02" not in probes
    assert probes["VC02R"]["semantic_family"] == "VISIBLE_PEER_HANDLE_CARDINALITY"
    assert probes["VC02R"]["question"] == "How many visible peer handles are listed?"
    assert probes["VC02R"]["expected"] == "2"
    assert probes["VC02R"]["critical_core"] is True
    assert all(probe["classification"] == "CLEAN" for probe in spec["probes"])
    assert spec["scoring"] == {
        "probe_count": 10,
        "factual_correct_minimum": 9,
        "reference_structure_valid_required": 10,
        "malformed_maximum": 0,
        "critical_core_accuracy_required": 1.0,
        "critical_core_error_policy": "FAIL_REGARDLESS_OF_AGGREGATE",
        "social_desirability_scored": False,
    }
    payload = {
        field: spec[field] for field in spec["corpus_digest_law"]["payload_fields"]
    }
    actual_digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    assert actual_digest == spec["corpus_sha256"]
    assert {
        "TRAIN",
        "DEV",
        "HYPERPARAMETER_SELECTION",
        "EARLY_STOPPING",
        "PROMPT_TUNING",
        "FOUNDATION_ADAPTER_SELECTION",
    } == set(spec["sealed_from"])


@pytest.mark.parametrize("family", list(SemanticFamily))
def test_generator_is_deterministic_and_symbolically_solved(
    family: SemanticFamily,
) -> None:
    """F0-GENERATOR-001; F0-UNIQUE-ANSWER-001; F0-VISIBILITY-001."""

    first = generate_example(417, family)
    second = generate_example(417, family)
    assert first == second
    assert first.answer == solve(first.state, first.query)
    assert first.choices.count(first.answer) == 1
    validate_example(first)


def test_generator_constructs_relational_hard_negatives() -> None:
    """F0-GENERATOR-002."""

    state = generate_visible_state(91)
    peer_suffixes = sorted(int(handle[1:]) for handle in state.peer_handles)
    assert all(right - left == 1 for left, right in zip(peer_suffixes, peer_suffixes[1:]))
    assert any(
        proposal.proposal_id[1:] == peer[1:]
        for proposal in state.proposals
        for peer in state.peer_handles
    )
    directions = [
        Direction.OUTGOING
        if proposal.owner == state.self_handle
        else Direction.INCOMING
        for proposal in state.proposals
    ]
    assert directions.count(Direction.INCOMING) == 2
    assert directions.count(Direction.OUTGOING) == 1
    assert any(
        message.sender == state.self_handle for message in state.messages
    ) and any(message.receiver == state.self_handle for message in state.messages)


def test_policy_firewall_allows_only_supplied_action_serialization() -> None:
    """F0-POLICY-FIREWALL-001; F0-POLICY-FIREWALL-002."""

    example = generate_example(7, SemanticFamily.ALREADY_SELECTED_ACTION_SERIALIZATION)
    assert "already supplied" in example.rendered_input
    assert "selection is not requested" in example.rendered_input
    parsed = json.loads(example.answer)
    assert set(parsed) == {"action_label", "payload"}
    validate_example(example)

    with pytest.raises(ExampleValidationError, match="policy-firewall"):
        validate_example(
            replace(example, rendered_input=example.rendered_input + "\nWhich action should be chosen?")
        )
    with pytest.raises(ExampleValidationError, match="policy-firewall"):
        validate_example(
            replace(example, rendered_input=example.rendered_input + "\nCooperate with a peer.")
        )


def test_reserved_fingerprint_is_rejected() -> None:
    """F0-CONTAMINATION-001."""

    example = generate_example(19, SemanticFamily.PROPOSAL_TARGET)
    with pytest.raises(ExampleValidationError, match="reserved evaluation fingerprint"):
        validate_example(
            example,
            reserved_eval_fingerprints=frozenset({example.structural_fingerprint}),
        )


def test_c0v2_and_c20_reserved_fingerprints_are_jointly_frozen(
    repository_root: Path,
) -> None:
    """F0-CONTAMINATION-001; F0-FINGERPRINT-001."""

    registry = _load_spec(
        repository_root,
        "specs/experiments/F0-reserved-evaluation-fingerprints.yaml",
    )
    assert registry["status"] == "FROZEN"
    assert registry["fingerprint_version"] == "F0_GRAPH_FINGERPRINT_V1"
    assert {key: len(value) for key, value in registry["reservations"].items()} == {
        "FOUNDER_C0_V2": 10,
        "FOUNDER_C20_V1": 20,
    }
    payload = {
        field: registry[field]
        for field in registry["aggregate_digest_law"]["payload_fields"]
    }
    assert hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest() == (
        registry["aggregate_sha256"]
    )
    frozen = load_reserved_evaluation_fingerprints(
        repository_root
        / "specs"
        / "experiments"
        / "F0-reserved-evaluation-fingerprints.yaml"
    )
    assert frozen == {
        item["fingerprint"]
        for entries in registry["reservations"].values()
        for item in entries
    }
    assert len(frozen) == registry["unique_fingerprint_count"]


def test_reserved_fingerprints_recompute_from_exact_sources(
    repository_root: Path,
) -> None:
    """F0-FINGERPRINT-002."""

    registry = _load_spec(
        repository_root,
        "specs/experiments/F0-reserved-evaluation-fingerprints.yaml",
    )
    c0 = _load_spec(repository_root, "specs/experiments/founder-c0-v2.yaml")
    source_fields = (
        "id",
        "category",
        "visible_facts",
        "question",
        "choices",
        "expected",
        "source_binding",
    )
    c0_by_id = {probe["id"]: probe for probe in c0["probes"]}
    for reservation in registry["reservations"]["FOUNDER_C0_V2"]:
        probe = {field: c0_by_id[reservation["probe_id"]][field] for field in source_fields}
        assert hashlib.sha256(canonical_json(probe).encode("utf-8")).hexdigest() == (
            reservation["source_probe_sha256"]
        )
        assert evaluation_probe_fingerprint(
            probe,
            semantic_query_family=reservation["semantic_query_family"],
        ) == reservation["fingerprint"]

    c20_path = Path("E:/WORLD/AI_CACHE/evidence/i05r6c/validated_context.json")
    if not c20_path.is_file():
        pytest.skip("external immutable C20 source artifact is not resident")
    assert hashlib.sha256(c20_path.read_bytes()).hexdigest() == (
        registry["sources"][1]["source_artifact_sha256"]
    )
    c20 = json.loads(c20_path.read_text(encoding="utf-8"))
    c20_by_id = {probe["id"]: probe for probe in c20["probes"]}
    for reservation in registry["reservations"]["FOUNDER_C20_V1"]:
        probe = c20_by_id[reservation["probe_id"]]
        assert hashlib.sha256(canonical_json(probe).encode("utf-8")).hexdigest() == (
            reservation["source_probe_sha256"]
        )
        assert evaluation_probe_fingerprint(
            probe,
            semantic_query_family=reservation["semantic_query_family"],
        ) == reservation["fingerprint"]


def _renamed_state_and_query(example):
    state = example.state
    mapping = {state.self_handle: "A9000"}
    mapping.update(
        {handle: f"P{9001 + index}" for index, handle in enumerate(state.peer_handles)}
    )
    renamed = SyntheticVisibleState(
        self_handle=mapping[state.self_handle],
        peer_handles=tuple(mapping[handle] for handle in reversed(state.peer_handles)),
        messages=tuple(
            MessageRecord(
                record.message_id,
                mapping[record.sender],
                mapping[record.receiver],
                record.body,
            )
            for record in reversed(state.messages)
        ),
        proposals=tuple(
            ProposalRecord(
                record.proposal_id,
                mapping[record.owner],
                mapping[record.target],
            )
            for record in reversed(state.proposals)
        ),
        neutral_state_value=state.neutral_state_value,
    )
    query = replace(
        example.query,
        candidate_handle=(
            mapping[example.query.candidate_handle]
            if example.query.candidate_handle in mapping
            else example.query.candidate_handle
        ),
    )
    return renamed, query, mapping


def test_fingerprint_is_identity_and_order_invariant() -> None:
    """F0-FINGERPRINT-001; F0-NEUTRALITY-001."""

    example = generate_example(29, SemanticFamily.PEER_HANDLE_LOOKUP)
    renamed, query, mapping = _renamed_state_and_query(example)
    assert solve(renamed, query) == mapping[example.answer]
    assert structural_fingerprint(
        renamed, query, example.distractor_pattern
    ) == example.structural_fingerprint


def test_role_reversal_reverses_grounded_direction() -> None:
    """F0-FINGERPRINT-002; F0-NEUTRALITY-002."""

    example = generate_example(31, SemanticFamily.MESSAGE_DIRECTION)
    target = next(
        record for record in example.state.messages if record.message_id == example.query.record_id
    )
    reversed_messages = tuple(
        MessageRecord(record.message_id, record.receiver, record.sender, record.body)
        if record.message_id == target.message_id
        else record
        for record in example.state.messages
    )
    reversed_state = replace(example.state, messages=reversed_messages)
    before = solve(example.state, example.query)
    after = solve(reversed_state, example.query)
    assert {before, after} == {Direction.INCOMING.value, Direction.OUTGOING.value}


def test_split_seeds_are_namespace_disjoint() -> None:
    """F0-SPLIT-001."""

    samples = {
        split: {derive_split_seed(8675309, split, index) for index in range(64)}
        for split in SPLIT_SIZES
    }
    assert SPLIT_SIZES == {
        "TRAIN": 4096,
        "DEV": 512,
        "STRUCTURAL_HOLDOUT": 1024,
        "TEMPLATE_HOLDOUT": 1024,
        "DOUBLE_HOLDOUT": 1024,
        "ADVERSARIAL_HOLDOUT": 512,
    }
    all_values = set().union(*samples.values())
    assert len(all_values) == sum(len(values) for values in samples.values())


def test_f0_spec_freezes_neutrality_retention_and_training_bounds(
    repository_root: Path,
) -> None:
    """F0-RETENTION-001; F0-TRAINING-CONFIG-001/002."""

    spec = _load_spec(
        repository_root, "specs/experiments/F0-neutral-foundation-adaptation.yaml"
    )
    assert spec["status"] == "PRE_TRAINING_FROZEN"
    assert spec["execution_authorized_by_this_spec"] is False
    assert spec["foundation_is_policy"] is False
    assert spec["preserved_baseline"]["EXP_000_genome"] == "NullGenome"
    assert spec["preserved_baseline"]["SELF_SEND"] == "FORBIDDEN"
    assert spec["preserved_baseline"]["foundation_in_canonical_runtime"] is False
    assert spec["training_targets"]["action_serialization"]["choice_learned"] is False
    assert spec["contamination_firewall"]["reserved_evaluations"] == [
        "FOUNDER_C0_V2",
        "C20",
    ]
    configs = spec["minimum_intervention"]["configurations"]
    assert [(item["id"], item["rank"], item["targets"]) for item in configs] == [
        ("FA-v0", 8, "ATTENTION_PROJECTIONS_ONLY"),
        ("FA-v1", 16, "ATTENTION_PROJECTIONS_ONLY"),
        ("FA-v2", 16, "BROADER_LINEAR_TARGETS"),
    ]
    assert spec["minimum_intervention"]["maximum_escalations_after_FA_v0"] == 2
    smoke = spec["qlora_feasibility_smoke"]
    assert smoke["status"] == "PASS_LOCAL"
    assert smoke["temporary_training_quantization"] == "4_BIT_NF4"
    assert smoke["bounded_steps"] == [
        "ONE_FORWARD",
        "ONE_BACKWARD",
        "TEN_OPTIMIZER_STEPS",
    ]
    assert spec["retention_sentinel"]["status"] == "FROZEN"
    assert spec["retention_sentinel"]["size_minimum"] == 50
    assert spec["retention_sentinel"]["size_maximum"] == 100
    assert spec["interaction_friction"]["interaction_rate"] == (
        "OUTCOME_VARIABLE_NOT_ADMISSION_METRIC"
    )
    assert spec["future_neural_substrate"]["foundation_heritable"] is False
    assert spec["future_neural_substrate"]["foundation_mutable"] is False
    assert spec["future_neural_substrate"]["genome_separate"] is True
    assert spec["future_neural_substrate"]["ARC_350_implementation_modified"] is False


def test_fa_v0_smoke_manifest_pins_backend_modules_and_pass_result(
    repository_root: Path,
) -> None:
    """F0-TRAINING-CONFIG-001/002."""

    smoke = _load_spec(
        repository_root, "specs/experiments/F0-FA-v0-qlora-smoke.yaml"
    )
    assert smoke["status"] == "EXECUTED_PASS_LOCAL"
    assert [phase["status"] for phase in smoke["ordered_preconditions"]] == [
        "PASS",
        "PASS",
        "PASS_LOCAL",
    ]
    assert smoke["model"]["revision"] == "48d788eca847d4d7548f375ad03d3c9312f6139e"
    assert smoke["model"]["checkpoint_sha256"] == (
        "36d044c73655bb904f822915e6294ba3dae8e6e1af5e703e9d452f2d6a3a294f"
    )
    assert smoke["FA_v0"]["target_modules"] == [
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
    ]
    assert smoke["FA_v0"]["MLP_included"] is False
    assert smoke["training"]["sequence_fallback_ladder"] == [256, 192, 128]
    assert smoke["training"]["gradient_accumulation"] == 8
    assert smoke["training"]["optimizer_steps"] == 10
    assert smoke["smoke_data"]["formal_F0_dataset"] is False
    assert smoke["result"]["status"] == "PASS_LOCAL"
    assert smoke["result"]["sequence_selected"] == 256
    assert smoke["result"]["optimizer_steps"] == 10
    assert smoke["result"]["loss_finite"] is True
    assert smoke["result"]["base_frozen"] is True
    assert smoke["result"]["LoRA_changed"] is True
    assert smoke["result"]["reserved_collision_count"] == 0
    assert smoke["result"]["policy_example_count"] == 0
    assert smoke["immutability"]["checkpoint_unchanged"] is True
    assert smoke["immutability"]["smoke_adapter_saved"] is False


def test_fa_v0_local_smoke_evidence_matches_manifest(repository_root: Path) -> None:
    """F0-TRAINING-CONFIG-002."""

    smoke = _load_spec(
        repository_root, "specs/experiments/F0-FA-v0-qlora-smoke.yaml"
    )
    evidence_path = Path(smoke["result"]["evidence_ref"])
    if not evidence_path.is_file():
        pytest.skip("external smoke evidence is not resident")
    assert hashlib.sha256(evidence_path.read_bytes()).hexdigest() == (
        smoke["result"]["evidence_sha256"]
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    result = evidence["result"]
    assert result["status"] == "PASS_LOCAL"
    assert result["forward"] is True
    assert result["backward"] is True
    assert result["optimizer_steps"] == 10
    assert result["loss_finite"] is True
    assert result["base_frozen"] is True
    assert result["lora_changed"] is True
    assert all(
        ".self_attn." in name and (".lora_A." in name or ".lora_B." in name)
        for name in result["trainable_parameter_names"]
    )
    assert evidence["smoke_data"]["reserved_collision"] == []
    assert evidence["smoke_data"]["policy_examples"] == 0
    assert evidence["provenance"]["checkpoint_unchanged"] is True


def test_retention_sentinel_is_frozen_neutral_and_digest_stable(
    repository_root: Path,
) -> None:
    """F0-RETENTION-001."""

    sentinel = _load_spec(
        repository_root, "specs/experiments/F0-retention-sentinel.yaml"
    )
    assert sentinel["status"] == "FROZEN"
    assert 50 <= len(sentinel["cases"]) <= 100
    assert sentinel["social_policy_content"] is False
    assert sentinel["selection_objective"] is False
    case_ids = [case["id"] for case in sentinel["cases"]]
    assert len(case_ids) == len(set(case_ids))
    assert {case["family"] for case in sentinel["cases"]} == {
        "BASIC_INSTRUCTION_FOLLOWING",
        "SIMPLE_FACTUAL_EXTRACTION",
        "SIMPLE_ARITHMETIC",
        "BASIC_TEXT_TRANSFORMATION",
        "GENERIC_JSON_FORMATTING",
    }
    payload = {
        field: sentinel[field] for field in sentinel["digest_law"]["payload_fields"]
    }
    actual_digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    assert actual_digest == sentinel["sentinel_sha256"]


def test_contract_manifest_routes_f0_specs(repository_root: Path) -> None:
    manifest = _load_spec(repository_root, "specs/contracts/manifest.json")
    assert "experiments/founder-c0-v2.yaml" in manifest["admission_specs"]
    assert "experiments/F0-neutral-foundation-adaptation.yaml" in manifest[
        "experiment_specs"
    ]
    assert "experiments/F0-retention-sentinel.yaml" in manifest["evaluation_specs"]
    for group in ("admission_specs", "experiment_specs", "evaluation_specs"):
        for relative_path in manifest[group]:
            assert (repository_root / "specs" / relative_path).is_file()
