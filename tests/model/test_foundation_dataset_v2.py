from __future__ import annotations

from dataclasses import replace

import pytest

from alifelm.model.foundation_data import SemanticFamily
from alifelm.model.foundation_data_v2 import (
    CurriculumProfile,
    DatasetV2LeakageError,
    build_sensor_invariant_records,
    build_v2_split,
    derive_v2_seed,
    family_counts,
    generate_relational_pair,
    relational_curriculum_coverage,
    screening_subset,
    validate_v2_split_isolation,
)


def test_v2_neural_split_excludes_sensor_owned_peer_count_and_balances_families() -> None:
    records = build_v2_split("TRAIN", 256)
    assert records
    assert all(
        record.semantic_family != SemanticFamily.VISIBLE_PEER_COUNT.value
        for record in records
    )
    counts = family_counts(records)
    assert max(counts.values()) - min(counts.values()) <= 1


def test_message_minimal_pair_changes_only_target_message_relation() -> None:
    seed = derive_v2_seed("TRAIN", 91)
    siblings = generate_relational_pair(
        split="TRAIN",
        seed=seed,
        family=SemanticFamily.MESSAGE_DIRECTION,
        topology_profile="BASE_I2O1",
        template_id="F0_EXPLICIT_TRAIN_V1",
        profile=CurriculumProfile.MINIMAL_PAIR,
    )
    left, right = siblings
    assert left.pair_group_id == right.pair_group_id
    assert {left.pair_role, right.pair_role} == {"INCOMING", "OUTGOING"}
    assert left.example.query == right.example.query
    assert left.example.choices == right.example.choices
    assert {left.example.answer, right.example.answer} == {"INCOMING", "OUTGOING"}

    left_state = left.example.state
    right_state = right.example.state
    assert left_state.self_handle == right_state.self_handle
    assert left_state.peer_handles == right_state.peer_handles
    assert left_state.proposals == right_state.proposals
    assert left_state.neutral_state_value == right_state.neutral_state_value

    changed = [
        (first, second)
        for first, second in zip(
            left_state.messages, right_state.messages, strict=True
        )
        if first != second
    ]
    assert len(changed) == 1
    first, second = changed[0]
    assert first.message_id == second.message_id
    assert first.body == second.body
    assert first.sender == second.receiver
    assert first.receiver == second.sender


def test_proposal_counterfactual_has_factual_and_counterfactual_sibling() -> None:
    seed = derive_v2_seed("DEV", 92)
    siblings = generate_relational_pair(
        split="DEV",
        seed=seed,
        family=SemanticFamily.PROPOSAL_DIRECTION,
        topology_profile="BASE_I2O2",
        template_id="F0_EXPLICIT_TRAIN_V2",
        profile=CurriculumProfile.COUNTERFACTUAL,
    )
    assert {item.pair_role for item in siblings} == {"FACTUAL", "COUNTERFACTUAL"}
    assert {item.intervention for item in siblings} == {"SWAP_PROPOSAL_DIRECTION"}
    assert siblings[0].pair_group_id == siblings[1].pair_group_id
    assert siblings[0].example.query == siblings[1].example.query
    assert siblings[0].example.answer != siblings[1].example.answer


def test_direction_families_receive_all_six_curriculum_profiles() -> None:
    records = build_v2_split("TRAIN", 512)
    coverage = relational_curriculum_coverage(records)
    expected = {
        "ADVERSARIAL",
        "COUNTERFACTUAL",
        "EASY",
        "HARD",
        "MEDIUM",
        "MINIMAL_PAIR",
    }
    assert set(coverage[SemanticFamily.MESSAGE_DIRECTION.value]) == expected
    assert set(coverage[SemanticFamily.PROPOSAL_DIRECTION.value]) == expected


def test_split_isolation_rejects_pair_sibling_crossing_boundary() -> None:
    train = build_v2_split("TRAIN", 256)
    paired = next(record for record in train if record.pair_group_id is not None)
    leaked = replace(
        paired,
        example_id="F0V2-DEV-LEAK",
        split="DEV",
    )
    with pytest.raises(DatasetV2LeakageError):
        validate_v2_split_isolation({"TRAIN": train, "DEV": [leaked]})


def test_screening_subset_preserves_complete_pair_groups() -> None:
    records = build_v2_split("TRAIN", 512)
    selected = screening_subset(records, split="TRAIN", size=128)
    assert len(selected) == 128
    selected_groups = {
        record.pair_group_id
        for record in selected
        if record.pair_group_id is not None
    }
    assert selected_groups
    for group_id in selected_groups:
        assert sum(record.pair_group_id == group_id for record in selected) == 2


def test_sensor_invariants_remain_outside_neural_training() -> None:
    records = build_sensor_invariant_records(8)
    assert len(records) == 8
    assert all(
        record["semantic_family"] == SemanticFamily.VISIBLE_PEER_COUNT.value
        for record in records
    )
    assert all(
        record["role"] == "DETERMINISTIC_SENSOR_INVARIANT_ONLY"
        and record["gradient_target"] is False
        for record in records
    )
    for record in records:
        assert int(record["ground_truth"]) == len(
            record["visible_state"]["peer_handles"]
        )
