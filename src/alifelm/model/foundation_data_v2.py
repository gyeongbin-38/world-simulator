"""Balanced curriculum and leakage controls for F0_DATASET_V2.

F0_DATASET_V1 is frozen and is never modified by this module. V2 composes the
existing symbolic generator with:

- near-equal quotas across neural semantic families;
- explicit EASY/MEDIUM/HARD/ADVERSARIAL curriculum metadata;
- within-family MESSAGE_DIRECTION / PROPOSAL_DIRECTION minimal pairs and
  counterfactual siblings;
- deterministic screening subsets that never split a sibling pair;
- cross-split exact/template/identifier/pair leakage checks; and
- a separate deterministic VISIBLE_PEER_COUNT sensor-invariant suite.

The module is research/evaluation infrastructure only. It does not modify
ContextPack, canonical WORLD state, or agent action policy.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
import hashlib
from typing import Any, Iterable, Mapping, Sequence

from .foundation_data import (
    FORMAL_HOLDOUT_TEMPLATE_IDS,
    FORMAL_TRAIN_TEMPLATE_IDS,
    GENERATOR_VERSION as V1_GENERATOR_VERSION,
    ExampleInvariants,
    FoundationQuery,
    MessageRecord,
    ProposalRecord,
    SemanticFamily,
    SyntheticVisibleState,
    TrainingExample,
    _formal_hard_negative_tags,
    _render_formal_input,
    canonical_digest,
    generate_formal_example,
    generate_formal_visible_state,
    load_reserved_evaluation_fingerprints,
    solve,
    structural_fingerprint,
    validate_example,
)


DATASET_V2_ID = "F0_DATASET_V2"
DATASET_V2_GENERATOR_VERSION = "F0_PROCEDURAL_GENERATOR_V2"
DATASET_V2_ROOT_SEED = 351_202_608_30
PAIR_SCHEMA_VERSION = "F0_RELATIONAL_PAIR_V1"
LEAKAGE_SCHEMA_VERSION = "F0_DATASET_V2_LEAKAGE_V1"
SCREENING_SCHEMA_VERSION = "F0_DATASET_V2_SCREENING_V1"

V2_SPLIT_SIZES: Mapping[str, int] = {
    "TRAIN": 4096,
    "DEV": 512,
    "STRUCTURAL_HOLDOUT": 1024,
    "TEMPLATE_HOLDOUT": 1024,
    "DOUBLE_HOLDOUT": 1024,
    "ADVERSARIAL_HOLDOUT": 512,
}

SCREENING_SIZES: Mapping[str, int] = {"TRAIN": 1024, "DEV": 256}

BASE_PROFILES = ("BASE_I2O1", "BASE_I1O2", "BASE_I2O2")
HOLDOUT_PROFILES = ("HOLDOUT_I3O1", "HOLDOUT_I1O3", "HOLDOUT_I3O2")

# VISIBLE_PEER_COUNT is owned by F0_SENSOR_NORMALIZER_V1, not neural gradients.
NEURAL_FAMILIES = tuple(
    family
    for family in SemanticFamily
    if family is not SemanticFamily.VISIBLE_PEER_COUNT
)
PAIRABLE_RELATIONAL_FAMILIES = (
    SemanticFamily.MESSAGE_DIRECTION,
    SemanticFamily.PROPOSAL_DIRECTION,
)


class CurriculumProfile(StrEnum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"
    MINIMAL_PAIR = "MINIMAL_PAIR"
    COUNTERFACTUAL = "COUNTERFACTUAL"
    ADVERSARIAL = "ADVERSARIAL"


STANDARD_PROFILES = (
    CurriculumProfile.EASY,
    CurriculumProfile.MEDIUM,
    CurriculumProfile.HARD,
    CurriculumProfile.ADVERSARIAL,
)


@dataclass(frozen=True, slots=True)
class V2Example:
    example: TrainingExample
    curriculum_profile: CurriculumProfile
    topology_profile: str
    pair_group_id: str | None = None
    pair_role: str | None = None
    intervention: str | None = None

    def __post_init__(self) -> None:
        paired = self.curriculum_profile in {
            CurriculumProfile.MINIMAL_PAIR,
            CurriculumProfile.COUNTERFACTUAL,
        }
        if paired and (self.pair_group_id is None or self.pair_role is None):
            raise ValueError("paired examples require pair_group_id and pair_role")
        if not paired and (self.pair_group_id is not None or self.pair_role is not None):
            raise ValueError("non-paired examples must not carry pair metadata")
        if self.curriculum_profile is CurriculumProfile.COUNTERFACTUAL:
            if self.intervention is None:
                raise ValueError("counterfactual examples require an intervention")
        elif self.intervention is not None:
            raise ValueError("only counterfactual examples carry interventions")


@dataclass(frozen=True, slots=True)
class V2Record:
    example_id: str
    split: str
    generator_seed: int
    curriculum_profile: str
    topology_profile: str
    semantic_family: str
    visible_state: Mapping[str, Any]
    input: str
    query: Mapping[str, Any]
    choices: tuple[str, ...]
    ground_truth: str
    answer_format: str
    structural_fingerprint: str
    template_id: str
    hard_negative_tags: tuple[str, ...]
    pair_group_id: str | None
    pair_role: str | None
    intervention: str | None
    identifier_tuple_digest: str
    template_instance_digest: str
    exact_instance_digest: str


class DatasetV2LeakageError(ValueError):
    """A F0_DATASET_V2 isolation rule was violated."""


def derive_v2_seed(split: str, unit_index: int, attempt: int = 0) -> int:
    if split not in V2_SPLIT_SIZES:
        raise ValueError(f"unknown V2 split: {split}")
    if unit_index < 0 or attempt < 0:
        raise ValueError("unit_index and attempt must be non-negative")
    material = (
        f"F0_DATASET_V2_SEED|{DATASET_V2_ROOT_SEED}|{split}|{unit_index}|{attempt}"
    ).encode("ascii")
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")


def family_quotas(size: int) -> dict[SemanticFamily, int]:
    """Allocate a split nearly equally across all neural families."""

    if size <= 0:
        raise ValueError("size must be positive")
    base, remainder = divmod(size, len(NEURAL_FAMILIES))
    return {
        family: base + int(index < remainder)
        for index, family in enumerate(NEURAL_FAMILIES)
    }


def _split_controls(
    split: str,
    ordinal: int,
    profile: CurriculumProfile,
) -> tuple[str, str]:
    if split == "ADVERSARIAL_HOLDOUT":
        topology = "ADVERSARIAL_I3O3"
    elif split in {"STRUCTURAL_HOLDOUT", "DOUBLE_HOLDOUT"}:
        topology = HOLDOUT_PROFILES[ordinal % len(HOLDOUT_PROFILES)]
    else:
        offset = {
            CurriculumProfile.EASY: 0,
            CurriculumProfile.MEDIUM: 1,
            CurriculumProfile.HARD: 2,
            CurriculumProfile.MINIMAL_PAIR: 1,
            CurriculumProfile.COUNTERFACTUAL: 2,
            CurriculumProfile.ADVERSARIAL: 2,
        }[profile]
        topology = BASE_PROFILES[(ordinal + offset) % len(BASE_PROFILES)]

    templates = (
        FORMAL_HOLDOUT_TEMPLATE_IDS
        if split in {"TEMPLATE_HOLDOUT", "DOUBLE_HOLDOUT", "ADVERSARIAL_HOLDOUT"}
        else FORMAL_TRAIN_TEMPLATE_IDS
    )
    return topology, templates[ordinal % len(templates)]


def _direction_for_message(state: SyntheticVisibleState, record: MessageRecord) -> str:
    return "OUTGOING" if record.sender == state.self_handle else "INCOMING"


def _direction_for_proposal(state: SyntheticVisibleState, record: ProposalRecord) -> str:
    return "OUTGOING" if record.owner == state.self_handle else "INCOMING"


def _replace_message_direction(
    state: SyntheticVisibleState,
    record_id: str,
    *,
    direction: str,
) -> SyntheticVisibleState:
    changed = False
    messages: list[MessageRecord] = []
    for record in state.messages:
        if record.message_id != record_id:
            messages.append(record)
            continue
        peer = record.receiver if record.sender == state.self_handle else record.sender
        if peer == state.self_handle:
            raise ValueError("message pair requires one peer endpoint")
        changed = True
        messages.append(
            MessageRecord(
                record.message_id,
                peer if direction == "INCOMING" else state.self_handle,
                state.self_handle if direction == "INCOMING" else peer,
                record.body,
            )
        )
    if not changed or direction not in {"INCOMING", "OUTGOING"}:
        raise ValueError("invalid message direction replacement")
    return replace(state, messages=tuple(messages))


def _replace_proposal_direction(
    state: SyntheticVisibleState,
    record_id: str,
    *,
    direction: str,
) -> SyntheticVisibleState:
    changed = False
    proposals: list[ProposalRecord] = []
    for record in state.proposals:
        if record.proposal_id != record_id:
            proposals.append(record)
            continue
        peer = record.target if record.owner == state.self_handle else record.owner
        if peer == state.self_handle:
            raise ValueError("proposal pair requires one peer endpoint")
        changed = True
        proposals.append(
            ProposalRecord(
                record.proposal_id,
                peer if direction == "INCOMING" else state.self_handle,
                state.self_handle if direction == "INCOMING" else peer,
            )
        )
    if not changed or direction not in {"INCOMING", "OUTGOING"}:
        raise ValueError("invalid proposal direction replacement")
    return replace(state, proposals=tuple(proposals))


def _pair_group_id(
    *,
    split: str,
    seed: int,
    family: SemanticFamily,
    topology_profile: str,
    template_id: str,
    profile: CurriculumProfile,
) -> str:
    return canonical_digest(
        {
            "schema": PAIR_SCHEMA_VERSION,
            "split": split,
            "seed": seed,
            "family": family.value,
            "topology_profile": topology_profile,
            "template_id": template_id,
            "curriculum_profile": profile.value,
        }
    )


def _paired_example(
    *,
    seed: int,
    state: SyntheticVisibleState,
    family: SemanticFamily,
    record_id: str,
    direction: str,
    template_id: str,
    topology_profile: str,
    profile: CurriculumProfile,
    group_id: str,
    factual_direction: str,
    reservations: frozenset[str],
) -> V2Example:
    if family is SemanticFamily.MESSAGE_DIRECTION:
        variant_state = _replace_message_direction(state, record_id, direction=direction)
        intervention_name = "SWAP_MESSAGE_DIRECTION"
    elif family is SemanticFamily.PROPOSAL_DIRECTION:
        variant_state = _replace_proposal_direction(state, record_id, direction=direction)
        intervention_name = "SWAP_PROPOSAL_DIRECTION"
    else:
        raise ValueError(f"unsupported paired family: {family.value}")

    query = FoundationQuery(
        semantic_family=family,
        record_id=record_id,
        template_id=template_id,
    )
    answer = solve(variant_state, query)
    if answer != direction:
        raise RuntimeError("pair transformation disagrees with symbolic solver")

    # Identical candidate order for siblings prevents answer-order leakage.
    choices = ("INCOMING", "OUTGOING", "NONE")
    distractor_pattern = ("ROLE_REVERSAL", "ABSENT_DIRECTION")
    rendered_input = _render_formal_input(variant_state, query, template_id)
    tags = set(_formal_hard_negative_tags(variant_state, choices, answer))
    tags.update({"RELATIONAL_PAIR", f"CURRICULUM_{profile.value}", "ROLE_REVERSAL"})

    if profile is CurriculumProfile.COUNTERFACTUAL:
        tags.add("COUNTERFACTUAL_RELATION_INTERVENTION")
        pair_role = "FACTUAL" if direction == factual_direction else "COUNTERFACTUAL"
        intervention = intervention_name
    else:
        pair_role = direction
        intervention = None

    example = TrainingExample(
        generator_version=DATASET_V2_GENERATOR_VERSION,
        seed=seed,
        state=variant_state,
        query=query,
        rendered_input=rendered_input,
        choices=choices,
        answer=answer,
        distractor_pattern=distractor_pattern,
        hard_negative_tags=tuple(sorted(tags)),
        structural_fingerprint=structural_fingerprint(
            variant_state, query, distractor_pattern
        ),
        invariants=ExampleInvariants(),
    )
    validate_example(example, reserved_eval_fingerprints=reservations)
    return V2Example(
        example=example,
        curriculum_profile=profile,
        topology_profile=topology_profile,
        pair_group_id=group_id,
        pair_role=pair_role,
        intervention=intervention,
    )


def generate_relational_pair(
    *,
    split: str,
    seed: int,
    family: SemanticFamily,
    topology_profile: str,
    template_id: str,
    profile: CurriculumProfile,
) -> tuple[V2Example, V2Example]:
    """Generate two same-split siblings differing in one target relation only."""

    if family not in PAIRABLE_RELATIONAL_FAMILIES:
        raise ValueError("only message/proposal direction families support V2 pairs")
    if profile not in {
        CurriculumProfile.MINIMAL_PAIR,
        CurriculumProfile.COUNTERFACTUAL,
    }:
        raise ValueError("pair generator requires MINIMAL_PAIR or COUNTERFACTUAL")

    reservations = load_reserved_evaluation_fingerprints()
    state = generate_formal_visible_state(seed, topology_profile)
    if family is SemanticFamily.MESSAGE_DIRECTION:
        target = min(state.messages, key=lambda item: item.message_id)
        record_id = target.message_id
        factual_direction = _direction_for_message(state, target)
    else:
        target = min(state.proposals, key=lambda item: item.proposal_id)
        record_id = target.proposal_id
        factual_direction = _direction_for_proposal(state, target)

    group_id = _pair_group_id(
        split=split,
        seed=seed,
        family=family,
        topology_profile=topology_profile,
        template_id=template_id,
        profile=profile,
    )
    directions = (
        ("INCOMING", "OUTGOING")
        if profile is CurriculumProfile.MINIMAL_PAIR
        else (
            factual_direction,
            "OUTGOING" if factual_direction == "INCOMING" else "INCOMING",
        )
    )
    first = _paired_example(
        seed=seed,
        state=state,
        family=family,
        record_id=record_id,
        direction=directions[0],
        template_id=template_id,
        topology_profile=topology_profile,
        profile=profile,
        group_id=group_id,
        factual_direction=factual_direction,
        reservations=reservations,
    )
    second = _paired_example(
        seed=seed,
        state=state,
        family=family,
        record_id=record_id,
        direction=directions[1],
        template_id=template_id,
        topology_profile=topology_profile,
        profile=profile,
        group_id=group_id,
        factual_direction=factual_direction,
        reservations=reservations,
    )
    return first, second


def generate_standard_v2_example(
    *,
    seed: int,
    family: SemanticFamily,
    topology_profile: str,
    template_id: str,
    profile: CurriculumProfile,
) -> V2Example:
    if family is SemanticFamily.VISIBLE_PEER_COUNT:
        raise ValueError("VISIBLE_PEER_COUNT is sensor-owned in F0_DATASET_V2")
    if profile in {CurriculumProfile.MINIMAL_PAIR, CurriculumProfile.COUNTERFACTUAL}:
        raise ValueError("paired profiles require generate_relational_pair")
    example = generate_formal_example(
        seed,
        family,
        topology_profile=topology_profile,
        template_id=template_id,
        reserved_eval_fingerprints=load_reserved_evaluation_fingerprints(),
    )
    tags = set(example.hard_negative_tags)
    tags.add(f"CURRICULUM_{profile.value}")
    return V2Example(
        example=replace(
            example,
            generator_version=DATASET_V2_GENERATOR_VERSION,
            hard_negative_tags=tuple(sorted(tags)),
        ),
        curriculum_profile=profile,
        topology_profile=topology_profile,
    )


def _state_mapping(state: SyntheticVisibleState) -> dict[str, Any]:
    return {
        "self_handle": state.self_handle,
        "peer_handles": list(state.peer_handles),
        "messages": [
            {
                "message_id": item.message_id,
                "sender": item.sender,
                "receiver": item.receiver,
                "body": item.body,
            }
            for item in state.messages
        ],
        "proposals": [
            {
                "proposal_id": item.proposal_id,
                "owner": item.owner,
                "target": item.target,
            }
            for item in state.proposals
        ],
        "neutral_state_value": state.neutral_state_value,
    }


def _query_mapping(query: FoundationQuery) -> dict[str, Any]:
    return {
        "semantic_family": query.semantic_family.value,
        "record_id": query.record_id,
        "candidate_handle": query.candidate_handle,
        "selected_action": query.selected_action,
        "selected_payload": (
            None if query.selected_payload is None else dict(query.selected_payload)
        ),
        "template_id": query.template_id,
    }


def _identifier_tuple_digest(state: SyntheticVisibleState) -> str:
    return canonical_digest(
        {
            "self": state.self_handle,
            "peers": sorted(state.peer_handles),
            "messages": sorted(item.message_id for item in state.messages),
            "proposals": sorted(item.proposal_id for item in state.proposals),
        }
    )


def v2_record(
    *,
    split: str,
    index: int,
    generator_seed: int,
    value: V2Example,
) -> V2Record:
    example = value.example
    answer_format = (
        "CANONICAL_JSON"
        if example.query.semantic_family
        is SemanticFamily.ALREADY_SELECTED_ACTION_SERIALIZATION
        else "EXACT_SCALAR"
    )
    template_digest = canonical_digest(
        {
            "template_id": example.query.template_id,
            "semantic_family": example.query.semantic_family.value,
            "input": example.rendered_input,
        }
    )
    exact_digest = canonical_digest(
        {
            "input": example.rendered_input,
            "choices": list(example.choices),
            "ground_truth": example.answer,
        }
    )
    return V2Record(
        example_id=f"F0V2-{split}-{index:06d}",
        split=split,
        generator_seed=generator_seed,
        curriculum_profile=value.curriculum_profile.value,
        topology_profile=value.topology_profile,
        semantic_family=example.query.semantic_family.value,
        visible_state=_state_mapping(example.state),
        input=example.rendered_input,
        query=_query_mapping(example.query),
        choices=tuple(example.choices),
        ground_truth=example.answer,
        answer_format=answer_format,
        structural_fingerprint=example.structural_fingerprint,
        template_id=example.query.template_id,
        hard_negative_tags=tuple(example.hard_negative_tags),
        pair_group_id=value.pair_group_id,
        pair_role=value.pair_role,
        intervention=value.intervention,
        identifier_tuple_digest=_identifier_tuple_digest(example.state),
        template_instance_digest=template_digest,
        exact_instance_digest=exact_digest,
    )


def _paired_record_count_per_profile(quota: int) -> int:
    """Approximately one quarter of a pairable family per paired profile."""

    # Must be even because each intervention unit contributes two siblings.
    return 2 * (quota // 8)


def _unit_seed_index(family_index: int, local_unit: int) -> int:
    return family_index * 100_000 + local_unit


def _build_family_records(
    split: str,
    family: SemanticFamily,
    family_index: int,
    quota: int,
) -> list[V2Record]:
    values: list[tuple[int, V2Example]] = []
    unit = 0

    minimal_records = 0
    counterfactual_records = 0
    if family in PAIRABLE_RELATIONAL_FAMILIES:
        minimal_records = _paired_record_count_per_profile(quota)
        counterfactual_records = _paired_record_count_per_profile(quota)
    standard_records = quota - minimal_records - counterfactual_records
    if standard_records < 0:
        raise RuntimeError("paired curriculum allocation exceeds family quota")

    for local_index in range(standard_records):
        profile = STANDARD_PROFILES[local_index % len(STANDARD_PROFILES)]
        topology, template = _split_controls(split, local_index, profile)
        seed_index = _unit_seed_index(family_index, unit)
        seed = derive_v2_seed(split, seed_index)
        value = generate_standard_v2_example(
            seed=seed,
            family=family,
            topology_profile=topology,
            template_id=template,
            profile=profile,
        )
        values.append((seed, value))
        unit += 1

    for profile, record_count in (
        (CurriculumProfile.MINIMAL_PAIR, minimal_records),
        (CurriculumProfile.COUNTERFACTUAL, counterfactual_records),
    ):
        for pair_index in range(record_count // 2):
            ordinal = standard_records + pair_index
            topology, template = _split_controls(split, ordinal, profile)
            seed_index = _unit_seed_index(family_index, unit)
            seed = derive_v2_seed(split, seed_index)
            pair = generate_relational_pair(
                split=split,
                seed=seed,
                family=family,
                topology_profile=topology,
                template_id=template,
                profile=profile,
            )
            values.extend((seed, sibling) for sibling in pair)
            unit += 1

    if len(values) != quota:
        raise RuntimeError(
            f"family quota mismatch for {family.value}: {len(values)} != {quota}"
        )
    return [
        v2_record(
            split=split,
            index=index,
            generator_seed=seed,
            value=value,
        )
        for index, (seed, value) in enumerate(values)
    ]


def build_v2_split(split: str, size: int | None = None) -> list[V2Record]:
    """Build a family-balanced split and keep every pair inside that split."""

    if split not in V2_SPLIT_SIZES:
        raise ValueError(split)
    target_size = V2_SPLIT_SIZES[split] if size is None else size
    if target_size <= 0 or target_size > V2_SPLIT_SIZES[split]:
        raise ValueError("invalid requested split size")

    quotas = family_quotas(target_size)
    records: list[V2Record] = []
    for family_index, family in enumerate(NEURAL_FAMILIES):
        records.extend(
            _build_family_records(
                split,
                family,
                family_index,
                quotas[family],
            )
        )

    if len(records) != target_size:
        raise RuntimeError("split size does not match family quota sum")

    # Remove family-block ordering while retaining deterministic reproducibility.
    records.sort(
        key=lambda record: hashlib.sha256(
            (
                "F0_DATASET_V2_ORDER_V1|"
                + split
                + "|"
                + record.exact_instance_digest
            ).encode("utf-8")
        ).digest()
    )
    records = [
        replace(record, example_id=f"F0V2-{split}-{index:06d}")
        for index, record in enumerate(records)
    ]

    counts = family_counts(records)
    if max(counts.values()) - min(counts.values()) > 1:
        raise RuntimeError("F0_DATASET_V2 family balance invariant failed")
    if any(record.semantic_family == SemanticFamily.VISIBLE_PEER_COUNT.value for record in records):
        raise RuntimeError("sensor-owned peer count leaked into neural split")
    return records


def _cross_split_duplicates(
    records_by_split: Mapping[str, Sequence[V2Record]],
    field: str,
    *,
    ignore_none: bool = False,
) -> dict[str, tuple[str, ...]]:
    owners: dict[str, set[str]] = {}
    for split, records in records_by_split.items():
        for record in records:
            value = getattr(record, field)
            if value is None and ignore_none:
                continue
            owners.setdefault(str(value), set()).add(split)
    return {
        value: tuple(sorted(splits))
        for value, splits in owners.items()
        if len(splits) > 1
    }


def validate_v2_split_isolation(
    records_by_split: Mapping[str, Sequence[V2Record]],
) -> dict[str, int]:
    """Fail closed on exact/template/identifier/sibling leakage across splits."""

    if not set(records_by_split).issubset(V2_SPLIT_SIZES):
        raise DatasetV2LeakageError("unknown split supplied to leakage validator")
    checks = {
        "exact_instance": _cross_split_duplicates(records_by_split, "exact_instance_digest"),
        "template_instance": _cross_split_duplicates(records_by_split, "template_instance_digest"),
        "identifier_tuple": _cross_split_duplicates(records_by_split, "identifier_tuple_digest"),
        "pair_sibling": _cross_split_duplicates(
            records_by_split, "pair_group_id", ignore_none=True
        ),
    }
    violations = {name: values for name, values in checks.items() if values}
    if violations:
        raise DatasetV2LeakageError(
            "F0_DATASET_V2 split leakage: "
            + str({name: len(values) for name, values in violations.items()})
        )
    return {f"{name}_cross_split_violations": 0 for name in checks}


def _screening_units(records: Sequence[V2Record]) -> list[tuple[str, tuple[V2Record, ...]]]:
    groups: dict[str, list[V2Record]] = {}
    for record in records:
        key = (
            "PAIR:" + record.pair_group_id
            if record.pair_group_id is not None
            else "SINGLE:" + record.example_id
        )
        groups.setdefault(key, []).append(record)
    units: list[tuple[str, tuple[V2Record, ...]]] = []
    for key, values in groups.items():
        if key.startswith("PAIR:") and len(values) != 2:
            raise RuntimeError("screening pair group must contain exactly two siblings")
        if key.startswith("SINGLE:") and len(values) != 1:
            raise RuntimeError("screening singleton unit must contain one record")
        units.append((key, tuple(values)))
    units.sort(
        key=lambda item: hashlib.sha256(
            (SCREENING_SCHEMA_VERSION + "|" + item[0]).encode("utf-8")
        ).digest()
    )
    return units


def screening_subset(
    records: Sequence[V2Record],
    *,
    split: str,
    size: int | None = None,
) -> list[V2Record]:
    """Stable-hash screen selection with pair groups as indivisible units."""

    if split not in SCREENING_SIZES:
        raise ValueError("screening is defined only for TRAIN and DEV")
    target = SCREENING_SIZES[split] if size is None else size
    if target <= 0 or target > len(records):
        raise ValueError("invalid screening subset size")
    if any(record.split != split for record in records):
        raise ValueError("screening records must belong to the requested split")

    chosen: list[V2Record] = []
    selected_keys: set[str] = set()
    units = _screening_units(records)
    for key, values in units:
        if len(chosen) + len(values) <= target:
            chosen.extend(values)
            selected_keys.add(key)
        if len(chosen) == target:
            break

    # If greedy unit sizes leave one slot, fill it with the next singleton.
    if len(chosen) < target:
        for key, values in units:
            if key in selected_keys or len(values) != 1:
                continue
            chosen.extend(values)
            selected_keys.add(key)
            if len(chosen) == target:
                break
    if len(chosen) != target:
        raise RuntimeError("unable to satisfy screening size without splitting a pair")

    selected_ids = {record.example_id for record in chosen}
    return [record for record in records if record.example_id in selected_ids]


def build_sensor_invariant_records(size: int = 512) -> list[dict[str, Any]]:
    """Build deterministic count probes that never enter neural training."""

    if size <= 0:
        raise ValueError("sensor invariant size must be positive")
    reservations = load_reserved_evaluation_fingerprints()
    records: list[dict[str, Any]] = []
    for index in range(size):
        seed = derive_v2_seed("DEV", 900_000 + index)
        topology = BASE_PROFILES[index % len(BASE_PROFILES)]
        template = FORMAL_TRAIN_TEMPLATE_IDS[index % len(FORMAL_TRAIN_TEMPLATE_IDS)]
        example = generate_formal_example(
            seed,
            SemanticFamily.VISIBLE_PEER_COUNT,
            topology_profile=topology,
            template_id=template,
            reserved_eval_fingerprints=reservations,
        )
        records.append(
            {
                "example_id": f"F0V2-SENSOR-{index:06d}",
                "semantic_family": SemanticFamily.VISIBLE_PEER_COUNT.value,
                "visible_state": _state_mapping(example.state),
                "input": example.rendered_input,
                "ground_truth": example.answer,
                "role": "DETERMINISTIC_SENSOR_INVARIANT_ONLY",
                "gradient_target": False,
            }
        )
    return records


def curriculum_counts(records: Iterable[V2Record]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        counts[record.curriculum_profile] = counts.get(record.curriculum_profile, 0) + 1
    return dict(sorted(counts.items()))


def family_counts(records: Iterable[V2Record]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        counts[record.semantic_family] = counts.get(record.semantic_family, 0) + 1
    return dict(sorted(counts.items()))


def relational_curriculum_coverage(records: Iterable[V2Record]) -> dict[str, tuple[str, ...]]:
    coverage: dict[str, set[str]] = {
        family.value: set() for family in PAIRABLE_RELATIONAL_FAMILIES
    }
    for record in records:
        if record.semantic_family in coverage:
            coverage[record.semantic_family].add(record.curriculum_profile)
    return {
        family: tuple(sorted(profiles))
        for family, profiles in sorted(coverage.items())
    }
