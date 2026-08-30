"""Deterministic synthetic data contracts for the F0 foundation experiment.

This module is deliberately outside the runtime path.  It generates perception,
reference-grounding, and already-selected-action serialization examples only.
It never chooses an action and never calls a teacher model.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping


FINGERPRINT_SCHEMA_VERSION = "F0_GRAPH_FINGERPRINT_V1"
GENERATOR_VERSION = "F0_PROCEDURAL_GENERATOR_V1"
RESERVATION_SET_ID = "F0_RESERVED_EVALUATION_FINGERPRINTS_V1"


class SemanticFamily(StrEnum):
    SELF_IDENTITY = "SELF_IDENTITY"
    PEER_IDENTITY = "PEER_IDENTITY"
    PEER_HANDLE_LOOKUP = "PEER_HANDLE_LOOKUP"
    VISIBLE_PEER_COUNT = "VISIBLE_PEER_COUNT"
    MESSAGE_SENDER = "MESSAGE_SENDER"
    MESSAGE_RECEIVER = "MESSAGE_RECEIVER"
    MESSAGE_DIRECTION = "MESSAGE_DIRECTION"
    PROPOSAL_ID = "PROPOSAL_ID"
    PROPOSAL_OWNER = "PROPOSAL_OWNER"
    PROPOSAL_DIRECTION = "PROPOSAL_DIRECTION"
    PROPOSAL_TARGET = "PROPOSAL_TARGET"
    INCOMING_PROPOSAL_IDENTIFICATION = "INCOMING_PROPOSAL_IDENTIFICATION"
    OUTGOING_PROPOSAL_IDENTIFICATION = "OUTGOING_PROPOSAL_IDENTIFICATION"
    VISIBLE_VS_NOT_VISIBLE_FACT = "VISIBLE_VS_NOT_VISIBLE_FACT"
    OPAQUE_HANDLE_COPY = "OPAQUE_HANDLE_COPY"
    ALREADY_SELECTED_ACTION_SERIALIZATION = "ALREADY_SELECTED_ACTION_SERIALIZATION"


class Direction(StrEnum):
    INCOMING = "INCOMING"
    OUTGOING = "OUTGOING"


class ExampleValidationError(ValueError):
    """Raised when a generated example violates an F0 invariant."""


@dataclass(frozen=True)
class MessageRecord:
    message_id: str
    sender: str
    receiver: str
    body: str


@dataclass(frozen=True)
class ProposalRecord:
    proposal_id: str
    owner: str
    target: str


@dataclass(frozen=True)
class SyntheticVisibleState:
    self_handle: str
    peer_handles: tuple[str, ...]
    messages: tuple[MessageRecord, ...]
    proposals: tuple[ProposalRecord, ...]
    neutral_state_value: int


@dataclass(frozen=True)
class FoundationQuery:
    semantic_family: SemanticFamily
    record_id: str | None = None
    candidate_handle: str | None = None
    selected_action: str | None = None
    selected_payload: Mapping[str, Any] | None = None
    template_id: str = "F0_EXPLICIT_TRAIN_V1"


@dataclass(frozen=True)
class ExampleInvariants:
    exactly_one_correct_answer: bool = True
    question_predicate_explicit: bool = True
    visible_evidence_sufficient: bool = True
    hidden_state_required: bool = False
    social_policy_required: bool = False
    world_knowledge_required: bool = False
    renderer_specific_semantics: bool = False
    answer_computable_by_symbolic_solver: bool = True


@dataclass(frozen=True)
class TrainingExample:
    generator_version: str
    seed: int
    state: SyntheticVisibleState
    query: FoundationQuery
    rendered_input: str
    choices: tuple[str, ...]
    answer: str
    distractor_pattern: tuple[str, ...]
    hard_negative_tags: tuple[str, ...]
    structural_fingerprint: str
    invariants: ExampleInvariants


SPLIT_SIZES: Mapping[str, int] = {
    "TRAIN": 4096,
    "DEV": 512,
    "STRUCTURAL_HOLDOUT": 1024,
    "TEMPLATE_HOLDOUT": 1024,
    "DOUBLE_HOLDOUT": 1024,
    "ADVERSARIAL_HOLDOUT": 512,
}

FORMAL_TOPOLOGY_PROFILES: Mapping[str, tuple[int, int, int, int]] = {
    # peer_count, message_count, incoming_proposals, outgoing_proposals
    "BASE_I2O1": (2, 2, 2, 1),
    "BASE_I1O2": (3, 3, 1, 2),
    "BASE_I2O2": (3, 4, 2, 2),
    "HOLDOUT_I3O1": (4, 3, 3, 1),
    "HOLDOUT_I1O3": (5, 4, 1, 3),
    "HOLDOUT_I3O2": (5, 5, 3, 2),
    "ADVERSARIAL_I3O3": (5, 5, 3, 3),
}

FORMAL_TRAIN_TEMPLATE_IDS = (
    "F0_EXPLICIT_TRAIN_V1",
    "F0_EXPLICIT_TRAIN_V2",
    "F0_EXPLICIT_TRAIN_V3",
)
FORMAL_HOLDOUT_TEMPLATE_IDS = (
    "F0_EXPLICIT_HOLDOUT_V1",
    "F0_EXPLICIT_HOLDOUT_V2",
)


_FORBIDDEN_POLICY_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\brepl(?:y|ies|ied)\b",
        r"\binitiat(?:e|es|ed|ing) (?:a )?conversation\b",
        r"\bcooperat(?:e|es|ed|ing|ion)\b",
        r"\bcompet(?:e|es|ed|ing|ition)\b",
        r"\bfriendly\b|\bhostile\b",
        r"\btrust\b|\bdistrust\b",
        r"\bhelp\b|\bdeceiv(?:e|es|ed|ing)\b",
        r"\bsurviv(?:e|es|ed|ing|al)\b|\bdeath\b",
        r"\bseek resources?\b|\bseek social contact\b",
        r"\breproduc(?:e|es|ed|ing|tion|tive)\b",
        r"\bprefer(?:s|red|ring)? (?:a |the )?partner\b",
        r"\bleader\b|\bteam\b",
        r"\bmaximize\b|\boffspring\b|\bpreserve lineage\b",
        r"\bsocial standing\b",
        r"\bwhich action\b|\bchoose (?:an|one|the) action\b",
        r"\bdecide whether\b|\bwhen should\b",
    )
)


def canonical_json(value: Any) -> str:
    """Return the repository-independent JSON form used for F0 hashes/targets."""

    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def derive_split_seed(root_seed: int, split: str, index: int) -> int:
    """Derive a stable split-local seed without global RNG state."""

    if split not in SPLIT_SIZES:
        raise ValueError(f"unknown F0 split: {split}")
    if index < 0 or index >= SPLIT_SIZES[split]:
        raise ValueError(f"index {index} outside split {split}")
    material = f"F0_SPLIT_SEED_V1|{root_seed}|{split}|{index}".encode("ascii")
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")


class _HashStream:
    """Small SHA-256 counter stream with cross-platform deterministic behavior."""

    def __init__(self, seed: int, namespace: str) -> None:
        if seed < 0:
            raise ValueError("seed must be non-negative")
        self._key = f"{GENERATOR_VERSION}|{namespace}|{seed}".encode("ascii")
        self._counter = 0

    def draw(self, upper_exclusive: int) -> int:
        if upper_exclusive <= 0:
            raise ValueError("upper_exclusive must be positive")
        block = hashlib.sha256(
            self._key + b"|" + self._counter.to_bytes(8, "big")
        ).digest()
        self._counter += 1
        return int.from_bytes(block[:8], "big") % upper_exclusive

    def choice(self, values: tuple[Any, ...]) -> Any:
        return values[self.draw(len(values))]

    def shuffled(self, values: Iterable[Any]) -> tuple[Any, ...]:
        decorated = []
        for position, value in enumerate(values):
            token = hashlib.sha256(
                self._key
                + b"|shuffle|"
                + self._counter.to_bytes(8, "big")
                + position.to_bytes(8, "big")
            ).digest()
            decorated.append((token, value))
        self._counter += 1
        return tuple(value for _, value in sorted(decorated, key=lambda item: item[0]))


def _unique_opaque_handles(stream: _HashStream, prefix: str, count: int) -> tuple[str, ...]:
    values: list[str] = []
    while len(values) < count:
        candidate = f"{prefix}{stream.draw(9000) + 1000}"
        if candidate not in values:
            values.append(candidate)
    return tuple(values)


def generate_visible_state(seed: int) -> SyntheticVisibleState:
    """Generate visible facts with relational hard negatives and opaque identities."""

    stream = _HashStream(seed, "VISIBLE_STATE")
    self_handle = _unique_opaque_handles(stream, "A", 1)[0]
    peer_count = 2 + stream.draw(4)
    peer_suffix_start = 1000 + stream.draw(9000 - peer_count)
    peers = tuple(f"P{peer_suffix_start + offset}" for offset in range(peer_count))

    messages: list[MessageRecord] = [
        MessageRecord("M0", peers[0], self_handle, f"X{stream.draw(9000) + 1000}"),
        MessageRecord("M1", self_handle, peers[0], f"X{stream.draw(9000) + 1000}"),
    ]
    if peer_count > 2 or stream.draw(2) == 1:
        messages.append(
            MessageRecord("M2", peers[1], self_handle, f"X{stream.draw(9000) + 1000}")
        )

    shared_suffix = peers[0][1:]
    proposals = [
        ProposalRecord(f"R{shared_suffix}", peers[0], self_handle),
        ProposalRecord(f"R{stream.draw(9000) + 1000}", peers[1], self_handle),
        ProposalRecord(f"R{stream.draw(9000) + 1000}", self_handle, peers[0]),
    ]
    proposal_ids: set[str] = set()
    normalized_proposals: list[ProposalRecord] = []
    for position, proposal in enumerate(proposals):
        proposal_id = proposal.proposal_id
        while proposal_id in proposal_ids:
            proposal_id = f"R{stream.draw(9000) + 1000}"
        proposal_ids.add(proposal_id)
        normalized_proposals.append(
            ProposalRecord(proposal_id, proposal.owner, proposal.target)
        )

    return SyntheticVisibleState(
        self_handle=self_handle,
        peer_handles=stream.shuffled(peers),
        messages=stream.shuffled(messages),
        proposals=stream.shuffled(normalized_proposals),
        neutral_state_value=stream.draw(100),
    )


def generate_formal_visible_state(
    seed: int, topology_profile: str
) -> SyntheticVisibleState:
    """Generate one frozen-profile state for the formal F0 dataset.

    Profile membership, rather than a random split seed alone, establishes the
    structural holdout boundary. Identity and record order remain seed-derived.
    """

    if topology_profile not in FORMAL_TOPOLOGY_PROFILES:
        raise ValueError(f"unknown formal topology profile: {topology_profile}")
    peer_count, message_count, incoming_count, outgoing_count = (
        FORMAL_TOPOLOGY_PROFILES[topology_profile]
    )
    stream = _HashStream(seed, f"FORMAL_VISIBLE_STATE|{topology_profile}")
    self_handle = _unique_opaque_handles(stream, "A", 1)[0]
    peer_suffix_start = 1000 + stream.draw(9000 - peer_count)
    peers = tuple(f"P{peer_suffix_start + offset}" for offset in range(peer_count))

    messages: list[MessageRecord] = []
    for position in range(message_count):
        peer = peers[position % peer_count]
        if position % 2 == 0:
            sender, receiver = peer, self_handle
        else:
            sender, receiver = self_handle, peer
        messages.append(
            MessageRecord(
                f"M{position}", sender, receiver, f"X{stream.draw(9000) + 1000}"
            )
        )

    proposals: list[ProposalRecord] = []
    used_ids: set[str] = set()

    def next_proposal_id(position: int) -> str:
        candidate = (
            f"R{peers[0][1:]}" if position == 0 else f"R{stream.draw(9000) + 1000}"
        )
        while candidate in used_ids:
            candidate = f"R{stream.draw(9000) + 1000}"
        used_ids.add(candidate)
        return candidate

    for position in range(incoming_count):
        peer = peers[position % peer_count]
        proposals.append(
            ProposalRecord(next_proposal_id(len(proposals)), peer, self_handle)
        )
    for position in range(outgoing_count):
        # Starting at peer zero intentionally creates a same-peer direction
        # reversal without assigning any semantic meaning to that peer.
        peer = peers[position % peer_count]
        proposals.append(
            ProposalRecord(next_proposal_id(len(proposals)), self_handle, peer)
        )

    return SyntheticVisibleState(
        self_handle=self_handle,
        peer_handles=stream.shuffled(peers),
        messages=stream.shuffled(messages),
        proposals=stream.shuffled(proposals),
        neutral_state_value=stream.draw(100),
    )


def _direction(self_handle: str, owner: str, target: str) -> Direction:
    if owner == self_handle and target != self_handle:
        return Direction.OUTGOING
    if target == self_handle and owner != self_handle:
        return Direction.INCOMING
    raise ExampleValidationError("record is not a visible incoming/outgoing relation")


def _message(state: SyntheticVisibleState, record_id: str | None) -> MessageRecord:
    matches = [record for record in state.messages if record.message_id == record_id]
    if len(matches) != 1:
        raise ExampleValidationError("message reference is not unique")
    return matches[0]


def _proposal(state: SyntheticVisibleState, record_id: str | None) -> ProposalRecord:
    matches = [record for record in state.proposals if record.proposal_id == record_id]
    if len(matches) != 1:
        raise ExampleValidationError("proposal reference is not unique")
    return matches[0]


def serialize_selected_action(action: str, payload: Mapping[str, Any]) -> str:
    """Serialize a supplied action to the canonical model-side transport shape.

    Identity/tick/intent-id fields remain gateway-owned and are intentionally absent.
    """

    model_labels = {
        "WAIT": "NO_DIRECTED_ACTION",
        "SEND": "DIRECT_TEXT",
        "PROPOSE": "OPEN_BILATERAL_REQUEST",
        "ACCEPT": "CONFIRM_BILATERAL_REQUEST",
        "REJECT": "DECLINE_BILATERAL_REQUEST",
    }
    if action not in model_labels:
        raise ExampleValidationError(f"unsupported supplied action: {action}")
    return canonical_json(
        {"action_label": model_labels[action], "payload": dict(payload)}
    )


def solve(state: SyntheticVisibleState, query: FoundationQuery) -> str:
    """Compute ground truth directly from visible formal state."""

    family = query.semantic_family
    if family is SemanticFamily.SELF_IDENTITY:
        return state.self_handle
    if family in {
        SemanticFamily.PEER_IDENTITY,
        SemanticFamily.PEER_HANDLE_LOOKUP,
        SemanticFamily.OPAQUE_HANDLE_COPY,
    }:
        if query.candidate_handle not in state.peer_handles:
            raise ExampleValidationError("peer query lacks a visible candidate")
        return str(query.candidate_handle)
    if family is SemanticFamily.VISIBLE_PEER_COUNT:
        return str(len(state.peer_handles))
    if family in {
        SemanticFamily.MESSAGE_SENDER,
        SemanticFamily.MESSAGE_RECEIVER,
        SemanticFamily.MESSAGE_DIRECTION,
    }:
        message = _message(state, query.record_id)
        if family is SemanticFamily.MESSAGE_SENDER:
            return message.sender
        if family is SemanticFamily.MESSAGE_RECEIVER:
            return message.receiver
        return _direction(state.self_handle, message.sender, message.receiver).value
    if family in {
        SemanticFamily.PROPOSAL_ID,
        SemanticFamily.PROPOSAL_OWNER,
        SemanticFamily.PROPOSAL_DIRECTION,
        SemanticFamily.PROPOSAL_TARGET,
        SemanticFamily.INCOMING_PROPOSAL_IDENTIFICATION,
        SemanticFamily.OUTGOING_PROPOSAL_IDENTIFICATION,
    }:
        proposal = _proposal(state, query.record_id)
        direction = _direction(state.self_handle, proposal.owner, proposal.target)
        if (
            family is SemanticFamily.INCOMING_PROPOSAL_IDENTIFICATION
            and direction is not Direction.INCOMING
        ):
            raise ExampleValidationError("incoming query references an outgoing proposal")
        if (
            family is SemanticFamily.OUTGOING_PROPOSAL_IDENTIFICATION
            and direction is not Direction.OUTGOING
        ):
            raise ExampleValidationError("outgoing query references an incoming proposal")
        if family in {
            SemanticFamily.PROPOSAL_ID,
            SemanticFamily.INCOMING_PROPOSAL_IDENTIFICATION,
            SemanticFamily.OUTGOING_PROPOSAL_IDENTIFICATION,
        }:
            return proposal.proposal_id
        if family is SemanticFamily.PROPOSAL_OWNER:
            return proposal.owner
        if family is SemanticFamily.PROPOSAL_TARGET:
            return proposal.target
        return direction.value
    if family is SemanticFamily.VISIBLE_VS_NOT_VISIBLE_FACT:
        visible = {state.self_handle, *state.peer_handles}
        return "TRUE" if query.candidate_handle in visible else "FALSE"
    if family is SemanticFamily.ALREADY_SELECTED_ACTION_SERIALIZATION:
        if query.selected_action is None or query.selected_payload is None:
            raise ExampleValidationError("serialization query lacks a supplied action")
        return serialize_selected_action(query.selected_action, query.selected_payload)
    raise ExampleValidationError(f"unsupported semantic family: {family}")


def _visible_state_text(state: SyntheticVisibleState) -> str:
    lines = [
        f"Self handle: {state.self_handle}",
        "Visible peer handles: " + ", ".join(state.peer_handles),
        f"Neutral state value: {state.neutral_state_value}",
        "Visible messages:",
    ]
    lines.extend(
        f"- {record.message_id}: from {record.sender} to {record.receiver}; body={record.body}"
        for record in state.messages
    )
    lines.append("Visible proposals:")
    lines.extend(
        f"- {record.proposal_id}: owner {record.owner}; target {record.target}"
        for record in state.proposals
    )
    return "\n".join(lines)


def _render_question(state: SyntheticVisibleState, query: FoundationQuery) -> str:
    family = query.semantic_family
    if family is SemanticFamily.SELF_IDENTITY:
        return "What is the explicitly listed self handle?"
    if family is SemanticFamily.PEER_IDENTITY:
        return f"Which visible peer handle exactly equals {query.candidate_handle}?"
    if family is SemanticFamily.PEER_HANDLE_LOOKUP:
        return f"Copy the visible peer handle {query.candidate_handle} exactly."
    if family is SemanticFamily.VISIBLE_PEER_COUNT:
        return "How many visible peer handles are listed?"
    if family is SemanticFamily.MESSAGE_SENDER:
        return f"For visible message {query.record_id}, what is the sender handle?"
    if family is SemanticFamily.MESSAGE_RECEIVER:
        return f"For visible message {query.record_id}, what is the receiver handle?"
    if family is SemanticFamily.MESSAGE_DIRECTION:
        return (
            f"Relative to self, is visible message {query.record_id} INCOMING or OUTGOING?"
        )
    if family is SemanticFamily.PROPOSAL_ID:
        proposal = _proposal(state, query.record_id)
        return (
            "Which visible proposal ID has owner "
            f"{proposal.owner} and target {proposal.target}?"
        )
    if family is SemanticFamily.PROPOSAL_OWNER:
        return f"Who is the explicitly listed owner of proposal {query.record_id}?"
    if family is SemanticFamily.PROPOSAL_DIRECTION:
        return (
            f"Relative to self, is proposal {query.record_id} INCOMING or OUTGOING?"
        )
    if family is SemanticFamily.PROPOSAL_TARGET:
        return f"What is the explicitly listed target of proposal {query.record_id}?"
    if family is SemanticFamily.INCOMING_PROPOSAL_IDENTIFICATION:
        proposal = _proposal(state, query.record_id)
        return f"Which proposal ID is incoming from {proposal.owner}?"
    if family is SemanticFamily.OUTGOING_PROPOSAL_IDENTIFICATION:
        proposal = _proposal(state, query.record_id)
        return f"Which proposal ID is outgoing to {proposal.target}?"
    if family is SemanticFamily.VISIBLE_VS_NOT_VISIBLE_FACT:
        return (
            f"Is handle {query.candidate_handle} explicitly present in the visible facts? "
            "Answer TRUE or FALSE."
        )
    if family is SemanticFamily.OPAQUE_HANDLE_COPY:
        return f"Copy opaque handle {query.candidate_handle} exactly."
    if family is SemanticFamily.ALREADY_SELECTED_ACTION_SERIALIZATION:
        return (
            "Selected action (already supplied; selection is not requested): "
            f"{query.selected_action}\n"
            f"Selected payload: {canonical_json(query.selected_payload)}\n"
            "Serialize the supplied action as the canonical model action transport."
        )
    raise ExampleValidationError(f"unsupported semantic family: {family}")


def _render_formal_input(
    state: SyntheticVisibleState, query: FoundationQuery, template_id: str
) -> str:
    """Render mechanically distinct, semantically equivalent explicit templates."""

    question = _render_question(state, query)
    if template_id == "F0_EXPLICIT_TRAIN_V1":
        return _visible_state_text(state) + "\nQuestion:\n" + question
    if template_id == "F0_EXPLICIT_TRAIN_V2":
        return "VISIBLE FACTS\n" + _visible_state_text(state) + "\nEXPLICIT QUERY\n" + question
    if template_id == "F0_EXPLICIT_TRAIN_V3":
        return "[VISIBLE_STATE]\n" + _visible_state_text(state) + "\n[QUERY]\n" + question
    if template_id == "F0_EXPLICIT_HOLDOUT_V1":
        return "Canonical visible state follows.\n" + _visible_state_text(state) + "\nQuery: " + question
    if template_id == "F0_EXPLICIT_HOLDOUT_V2":
        return "STATE (visible only)\n" + _visible_state_text(state) + "\nTASK (explicit predicate)\n" + question
    raise ValueError(f"unknown formal template: {template_id}")


def _query_for_family(
    state: SyntheticVisibleState, family: SemanticFamily, stream: _HashStream
) -> FoundationQuery:
    peer = stream.choice(state.peer_handles)
    message = stream.choice(state.messages)
    proposal = stream.choice(state.proposals)
    if family is SemanticFamily.INCOMING_PROPOSAL_IDENTIFICATION:
        proposal = next(
            record
            for record in state.proposals
            if _direction(state.self_handle, record.owner, record.target)
            is Direction.INCOMING
        )
    if family is SemanticFamily.OUTGOING_PROPOSAL_IDENTIFICATION:
        proposal = next(
            record
            for record in state.proposals
            if _direction(state.self_handle, record.owner, record.target)
            is Direction.OUTGOING
        )
    if family is SemanticFamily.VISIBLE_VS_NOT_VISIBLE_FACT:
        if stream.draw(2):
            candidate = peer
        else:
            candidate = f"P{stream.draw(9000) + 1000}"
            while candidate in state.peer_handles:
                candidate = f"P{stream.draw(9000) + 1000}"
        return FoundationQuery(family, candidate_handle=candidate)
    if family is SemanticFamily.ALREADY_SELECTED_ACTION_SERIALIZATION:
        action = stream.choice(("WAIT", "SEND", "PROPOSE", "ACCEPT", "REJECT"))
        if action == "WAIT":
            payload: Mapping[str, Any] = {}
        elif action == "SEND":
            payload = {"target_agent_id": peer, "body": f"X{stream.draw(9000) + 1000}"}
        elif action == "PROPOSE":
            payload = {"target_agent_id": peer}
        else:
            incoming = next(
                record
                for record in state.proposals
                if _direction(state.self_handle, record.owner, record.target)
                is Direction.INCOMING
            )
            payload = {"proposal_id": incoming.proposal_id}
        return FoundationQuery(
            family, selected_action=action, selected_payload=payload
        )
    return FoundationQuery(
        family,
        record_id=(
            message.message_id
            if family
            in {
                SemanticFamily.MESSAGE_SENDER,
                SemanticFamily.MESSAGE_RECEIVER,
                SemanticFamily.MESSAGE_DIRECTION,
            }
            else proposal.proposal_id
            if family
            in {
                SemanticFamily.PROPOSAL_ID,
                SemanticFamily.PROPOSAL_OWNER,
                SemanticFamily.PROPOSAL_DIRECTION,
                SemanticFamily.PROPOSAL_TARGET,
                SemanticFamily.INCOMING_PROPOSAL_IDENTIFICATION,
                SemanticFamily.OUTGOING_PROPOSAL_IDENTIFICATION,
            }
            else None
        ),
        candidate_handle=(
            peer
            if family
            in {
                SemanticFamily.PEER_IDENTITY,
                SemanticFamily.PEER_HANDLE_LOOKUP,
                SemanticFamily.OPAQUE_HANDLE_COPY,
            }
            else None
        ),
    )


def _choices(
    state: SyntheticVisibleState,
    query: FoundationQuery,
    answer: str,
    stream: _HashStream,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    family = query.semantic_family
    if family is SemanticFamily.VISIBLE_PEER_COUNT:
        count = len(state.peer_handles)
        distractors = (str(max(0, count - 1)), str(count + 1))
        tags = ("CARDINALITY_DELTA:-1", "CARDINALITY_DELTA:+1")
    elif family in {
        SemanticFamily.MESSAGE_DIRECTION,
        SemanticFamily.PROPOSAL_DIRECTION,
    }:
        distractors = (
            Direction.OUTGOING.value
            if answer == Direction.INCOMING.value
            else Direction.INCOMING.value,
            "NONE",
        )
        tags = ("ROLE_REVERSAL", "ABSENT_DIRECTION")
    elif family is SemanticFamily.VISIBLE_VS_NOT_VISIBLE_FACT:
        distractors = ("FALSE" if answer == "TRUE" else "TRUE", "UNKNOWN")
        tags = ("BOOLEAN_REVERSAL", "UNSTATED_ESCAPE")
    elif family is SemanticFamily.ALREADY_SELECTED_ACTION_SERIALIZATION:
        parsed = json.loads(answer)
        alternate = dict(parsed)
        alternate["action_label"] = (
            "NO_DIRECTED_ACTION"
            if parsed["action_label"] != "NO_DIRECTED_ACTION"
            else "DIRECT_TEXT"
        )
        distractors = (canonical_json(alternate), canonical_json({"payload": parsed["payload"]}))
        tags = ("WRONG_SUPPLIED_ACTION", "MISSING_ACTION_LABEL")
    elif family in {
        SemanticFamily.PROPOSAL_ID,
        SemanticFamily.INCOMING_PROPOSAL_IDENTIFICATION,
        SemanticFamily.OUTGOING_PROPOSAL_IDENTIFICATION,
    }:
        other = [record.proposal_id for record in state.proposals if record.proposal_id != answer]
        distractors = tuple(other[:2])
        tags = ("COMPETING_VISIBLE_PROPOSAL", "FIRST_RECORD_DISTRACTOR")
    else:
        visible_handles = [state.self_handle, *state.peer_handles]
        other = [handle for handle in visible_handles if handle != answer]
        while len(other) < 2:
            other.append(f"P{stream.draw(9000) + 1000}")
        distractors = tuple(other[:2])
        tags = ("COMPETING_VISIBLE_HANDLE", "ROLE_DISTRACTOR")
    unique_distractors: list[str] = []
    for value in distractors:
        if value != answer and value not in unique_distractors:
            unique_distractors.append(value)
    while len(unique_distractors) < 2:
        unique_distractors.append(f"ABSENT_{len(unique_distractors)}")
    return stream.shuffled((answer, *unique_distractors[:2])), tags


def _peer_incidence_signature(
    state: SyntheticVisibleState, peer: str
) -> Mapping[str, int]:
    return {
        "messages_peer_to_self": sum(
            1
            for record in state.messages
            if record.sender == peer and record.receiver == state.self_handle
        ),
        "messages_self_to_peer": sum(
            1
            for record in state.messages
            if record.sender == state.self_handle and record.receiver == peer
        ),
        "proposals_peer_to_self": sum(
            1
            for record in state.proposals
            if record.owner == peer and record.target == state.self_handle
        ),
        "proposals_self_to_peer": sum(
            1
            for record in state.proposals
            if record.owner == state.self_handle and record.target == peer
        ),
    }


def _peer_incidence_signatures(state: SyntheticVisibleState) -> list[Mapping[str, int]]:
    return sorted(
        (_peer_incidence_signature(state, peer) for peer in state.peer_handles),
        key=canonical_json,
    )


def normalized_structural_fingerprint(
    *,
    semantic_query_family: str,
    entity_role_topology: Mapping[str, Any],
    edge_direction_topology: Iterable[str],
    ownership_topology: Iterable[str],
    target_relation_topology: Iterable[str],
    distractor_topology: Iterable[str],
    answer_role_topology: str,
) -> str:
    """Apply the common F0 evaluation/training structural fingerprint law."""

    payload = {
        "schema": FINGERPRINT_SCHEMA_VERSION,
        "semantic_query_family": semantic_query_family,
        "entity_role_topology": dict(entity_role_topology),
        "edge_direction_topology": sorted(edge_direction_topology),
        "ownership_topology": sorted(ownership_topology),
        "target_relation_topology": sorted(target_relation_topology),
        "distractor_topology": sorted(distractor_topology),
        "answer_role_topology": answer_role_topology,
    }
    return canonical_digest(payload)


def _evaluation_peer_signature(
    peer: str,
    *,
    messages: tuple[tuple[str, str], ...],
    proposals: tuple[tuple[str, str, str], ...],
) -> Mapping[str, int]:
    return {
        "messages_peer_to_self": sum(
            1 for sender, receiver in messages if sender == peer and receiver == "SELF"
        ),
        "messages_self_to_peer": sum(
            1 for sender, receiver in messages if sender == "SELF" and receiver == peer
        ),
        "proposals_peer_to_self": sum(
            1
            for _, owner, target in proposals
            if owner == peer and target == "SELF"
        ),
        "proposals_self_to_peer": sum(
            1
            for _, owner, target in proposals
            if owner == "SELF" and target == peer
        ),
    }


def evaluation_probe_topology(
    probe: Mapping[str, Any], *, semantic_query_family: str
) -> Mapping[str, Any]:
    """Derive the common normalized topology from one frozen C0/C20 probe."""

    facts = tuple(str(value) for value in probe["visible_facts"])
    peer_handles: tuple[str, ...] = ()
    messages: list[tuple[str, str]] = []
    proposals: list[tuple[str, str, str]] = []
    history_edges: list[str] = []
    for fact in facts:
        if fact.startswith("Visible peer handles: "):
            peer_handles = tuple(
                value.strip()
                for value in fact.removeprefix("Visible peer handles: ").split(",")
            )
        message_match = re.fullmatch(
            r"Newly delivered directed message from (P\d+): .+", fact
        )
        if message_match:
            messages.append((message_match.group(1), "SELF"))
        incoming_match = re.fullmatch(r"(R\d+) from (P\d+)", fact)
        if incoming_match:
            proposals.append((incoming_match.group(1), incoming_match.group(2), "SELF"))
        outgoing_match = re.fullmatch(
            r"Visible outgoing pending request (R\d+) to (P\d+)", fact
        )
        if outgoing_match:
            proposals.append((outgoing_match.group(1), "SELF", outgoing_match.group(2)))
        history_match = re.fullmatch(
            r"Prior visible committed interaction: text sent to (P\d+): .+", fact
        )
        if history_match:
            history_edges.append("HISTORY_TEXT:SELF_TO_PEER")

    peer_signatures = {
        peer: _evaluation_peer_signature(
            peer,
            messages=tuple(messages),
            proposals=tuple(proposals),
        )
        for peer in peer_handles
    }
    entity_roles: Mapping[str, Any] = {
        "SELF": 1,
        "PEER": len(peer_handles),
        "MESSAGE": len(messages),
        "PROPOSAL": len(proposals),
        "HISTORY": len(history_edges),
        "PEER_INCIDENCE_MULTISET": sorted(
            peer_signatures.values(), key=canonical_json
        ),
    }
    edge_directions = [
        "MESSAGE:PEER_TO_SELF" if receiver == "SELF" else "MESSAGE:SELF_TO_PEER"
        for sender, receiver in messages
    ]
    edge_directions.extend(
        "PROPOSAL:PEER_TO_SELF" if target == "SELF" else "PROPOSAL:SELF_TO_PEER"
        for _, owner, target in proposals
    )
    edge_directions.extend(history_edges)
    ownership = [
        "PROPOSAL_OWNER:SELF" if owner == "SELF" else "PROPOSAL_OWNER:PEER"
        for _, owner, _ in proposals
    ]
    targets = [
        "PROPOSAL_TARGET:SELF" if target == "SELF" else "PROPOSAL_TARGET:PEER"
        for _, _, target in proposals
    ]

    expected = str(probe["expected"])
    proposal_by_id = {proposal_id: (owner, target) for proposal_id, owner, target in proposals}

    def answer_topology(value: str) -> str:
        if value == "SELF":
            return "SELF"
        if value in peer_signatures:
            return "VISIBLE_PEER_INCIDENCE:" + canonical_json(peer_signatures[value])
        if value in proposal_by_id:
            owner, target = proposal_by_id[value]
            direction = "INCOMING" if target == "SELF" else "OUTGOING"
            return f"VISIBLE_PROPOSAL:{direction}"
        if value in {"INCOMING", "OUTGOING"}:
            return f"DIRECTION:{value}"
        if value.isdigit():
            if "incoming count" in str(probe["source_binding"]):
                return "INCOMING_PROPOSAL_CARDINALITY"
            return "VISIBLE_PEER_CARDINALITY"
        source_binding = str(probe["source_binding"])
        if "prior_history.body" in source_binding:
            return "VISIBLE_HISTORY_BODY"
        if "newly_delivered.body literal" in source_binding:
            return "VISIBLE_MESSAGE_BODY_LITERAL"
        if "newly_delivered.body" in source_binding:
            return "VISIBLE_MESSAGE_BODY"
        return semantic_query_family

    def distractor_topology(value: str) -> str:
        if value == "SELF":
            return "SELF_ROLE"
        if value in peer_signatures:
            return "OTHER_VISIBLE_PEER_INCIDENCE:" + canonical_json(
                peer_signatures[value]
            )
        if re.fullmatch(r"P\d+", value):
            return "ABSENT_PEER"
        if value in proposal_by_id:
            owner, target = proposal_by_id[value]
            direction = "INCOMING" if target == "SELF" else "OUTGOING"
            return f"OTHER_VISIBLE_PROPOSAL:{direction}"
        if re.fullmatch(r"R\d+", value):
            return "ABSENT_PROPOSAL"
        if value in {"INCOMING", "OUTGOING"}:
            return f"DIRECTION:{value}"
        if value == "RESOLVED":
            return "NON_PENDING_STATE"
        if value.isdigit() and expected.isdigit():
            delta = int(value) - int(expected)
            return f"CARDINALITY_DELTA:{delta:+d}"
        return "ABSENT_LITERAL"

    distractors = [
        distractor_topology(str(choice))
        for choice in probe["choices"]
        if str(choice) != expected
    ]
    return {
        "semantic_query_family": semantic_query_family,
        "entity_role_topology": entity_roles,
        "edge_direction_topology": edge_directions,
        "ownership_topology": ownership,
        "target_relation_topology": targets,
        "distractor_topology": distractors,
        "answer_role_topology": answer_topology(expected),
    }


def evaluation_probe_fingerprint(
    probe: Mapping[str, Any], *, semantic_query_family: str
) -> str:
    return normalized_structural_fingerprint(
        **evaluation_probe_topology(
            probe, semantic_query_family=semantic_query_family
        )
    )


def _answer_topology(state: SyntheticVisibleState, query: FoundationQuery) -> str:
    answer = solve(state, query)
    if answer == state.self_handle:
        return "SELF"
    if answer in state.peer_handles:
        return "VISIBLE_PEER_INCIDENCE:" + canonical_json(
            _peer_incidence_signature(state, answer)
        )
    for record in state.messages:
        if answer == record.message_id:
            direction = _direction(state.self_handle, record.sender, record.receiver).value
            return f"VISIBLE_MESSAGE:{direction}"
    for record in state.proposals:
        if answer == record.proposal_id:
            direction = _direction(state.self_handle, record.owner, record.target).value
            return f"VISIBLE_PROPOSAL:{direction}"
    family = query.semantic_family
    if family is SemanticFamily.VISIBLE_PEER_COUNT:
        return "VISIBLE_PEER_CARDINALITY"
    if family in {
        SemanticFamily.MESSAGE_DIRECTION,
        SemanticFamily.PROPOSAL_DIRECTION,
    }:
        return f"DIRECTION:{answer}"
    if family is SemanticFamily.VISIBLE_VS_NOT_VISIBLE_FACT:
        return f"VISIBILITY_BOOLEAN:{answer}"
    if family is SemanticFamily.ALREADY_SELECTED_ACTION_SERIALIZATION:
        return f"SUPPLIED_ACTION:{query.selected_action}"
    return family.value


def structural_fingerprint(
    state: SyntheticVisibleState,
    query: FoundationQuery,
    distractor_pattern: tuple[str, ...],
) -> str:
    """Hash identity/order-invariant relational topology, not surface strings."""

    edge_directions = [
        "MESSAGE:PEER_TO_SELF"
        if _direction(state.self_handle, record.sender, record.receiver)
        is Direction.INCOMING
        else "MESSAGE:SELF_TO_PEER"
        for record in state.messages
    ]
    edge_directions.extend(
        "PROPOSAL:PEER_TO_SELF"
        if _direction(state.self_handle, record.owner, record.target)
        is Direction.INCOMING
        else "PROPOSAL:SELF_TO_PEER"
        for record in state.proposals
    )
    ownership = [
        "PROPOSAL_OWNER:SELF"
        if record.owner == state.self_handle
        else "PROPOSAL_OWNER:PEER"
        for record in state.proposals
    ]
    targets = [
        "PROPOSAL_TARGET:SELF"
        if record.target == state.self_handle
        else "PROPOSAL_TARGET:PEER"
        for record in state.proposals
    ]
    entity_roles: Mapping[str, Any] = {
        "SELF": 1,
        "PEER": len(state.peer_handles),
        "MESSAGE": len(state.messages),
        "PROPOSAL": len(state.proposals),
        "HISTORY": 0,
        "PEER_INCIDENCE_MULTISET": _peer_incidence_signatures(state),
    }
    return normalized_structural_fingerprint(
        semantic_query_family=(
            "VISIBLE_PEER_HANDLE_CARDINALITY"
            if query.semantic_family is SemanticFamily.VISIBLE_PEER_COUNT
            else query.semantic_family.value
        ),
        entity_role_topology=entity_roles,
        edge_direction_topology=edge_directions,
        ownership_topology=ownership,
        target_relation_topology=targets,
        distractor_topology=distractor_pattern,
        answer_role_topology=_answer_topology(state, query),
    )


def _default_reservation_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "specs"
        / "experiments"
        / "F0-reserved-evaluation-fingerprints.yaml"
    )


@lru_cache(maxsize=4)
def load_reserved_evaluation_fingerprints(
    path: str | Path | None = None,
) -> frozenset[str]:
    """Load and verify the frozen C0-v2 plus C20 reservation set."""

    registry_path = Path(path) if path is not None else _default_reservation_path()
    try:
        document = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExampleValidationError("reserved evaluation registry unavailable") from exc
    if document.get("reservation_set_id") != RESERVATION_SET_ID:
        raise ExampleValidationError("unexpected reserved evaluation registry identity")
    if document.get("status") != "FROZEN":
        raise ExampleValidationError("reserved evaluation registry is not frozen")
    reservations = document.get("reservations")
    if not isinstance(reservations, Mapping):
        raise ExampleValidationError("reserved evaluation registry lacks reservations")
    if set(reservations) != {"FOUNDER_C0_V2", "FOUNDER_C20_V1"}:
        raise ExampleValidationError("C0-v2 and C20 must be jointly reserved")
    digest_fields = document.get("aggregate_digest_law", {}).get("payload_fields")
    if not isinstance(digest_fields, list):
        raise ExampleValidationError("reserved evaluation aggregate law is missing")
    aggregate_payload = {field: document[field] for field in digest_fields}
    if canonical_digest(aggregate_payload) != document.get("aggregate_sha256"):
        raise ExampleValidationError("reserved evaluation aggregate digest mismatch")
    expected_counts = {"FOUNDER_C0_V2": 10, "FOUNDER_C20_V1": 20}
    if any(len(reservations[key]) != count for key, count in expected_counts.items()):
        raise ExampleValidationError("reserved evaluation probe count mismatch")
    fingerprints = frozenset(
        item["fingerprint"]
        for entries in reservations.values()
        for item in entries
    )
    if not fingerprints:
        raise ExampleValidationError("reserved evaluation registry is empty")
    return fingerprints


def _assert_policy_firewall(rendered_input: str) -> None:
    for pattern in _FORBIDDEN_POLICY_PATTERNS:
        if pattern.search(rendered_input):
            raise ExampleValidationError(
                f"foundation policy-firewall match: {pattern.pattern}"
            )


def validate_example(
    example: TrainingExample,
    *,
    reserved_eval_fingerprints: frozenset[str] | None = None,
) -> None:
    """Fail closed on ambiguity, hidden facts, policy targets, and contamination."""

    invariants = example.invariants
    if example.choices.count(example.answer) != 1 or not invariants.exactly_one_correct_answer:
        raise ExampleValidationError("example does not contain exactly one correct answer")
    if not invariants.question_predicate_explicit:
        raise ExampleValidationError("question predicate is not explicit")
    if not invariants.visible_evidence_sufficient or invariants.hidden_state_required:
        raise ExampleValidationError("answer is not fully derivable from visible evidence")
    if invariants.social_policy_required:
        raise ExampleValidationError("example requires social policy")
    if invariants.world_knowledge_required:
        raise ExampleValidationError("example requires world knowledge")
    if invariants.renderer_specific_semantics:
        raise ExampleValidationError("example embeds renderer-specific semantics")
    if not invariants.answer_computable_by_symbolic_solver:
        raise ExampleValidationError("example lacks symbolic ground truth")
    if solve(example.state, example.query) != example.answer:
        raise ExampleValidationError("stored answer differs from symbolic solution")
    reservations = (
        load_reserved_evaluation_fingerprints()
        if reserved_eval_fingerprints is None
        else reserved_eval_fingerprints
    )
    if example.structural_fingerprint in reservations:
        raise ExampleValidationError("reserved evaluation fingerprint")
    _assert_policy_firewall(example.rendered_input)


def generate_example(
    seed: int,
    semantic_family: SemanticFamily,
    *,
    reserved_eval_fingerprints: frozenset[str] | None = None,
) -> TrainingExample:
    """Generate and validate one deterministic F0 training example."""

    state = generate_visible_state(seed)
    stream = _HashStream(seed, f"QUERY|{semantic_family.value}")
    query = _query_for_family(state, semantic_family, stream)
    answer = solve(state, query)
    choices, distractor_pattern = _choices(state, query, answer, stream)
    rendered_input = _visible_state_text(state) + "\nQuestion:\n" + _render_question(state, query)
    hard_negative_tags = (
        "SAME_PEER_MULTIPLE_RECORDS",
        "SAME_TARGET_DIFFERENT_DIRECTION",
        "MULTIPLE_INCOMING_ONE_OUTGOING",
        "FIRST_RECORD_DISTRACTOR",
        "CROSS_ENTITY_NUMERIC_SUFFIX",
        "NEARBY_OPAQUE_HANDLES",
        "IRRELEVANT_MESSAGE_BETWEEN_PROPOSALS",
        "SELF_PEER_ROLE_REVERSAL",
    )
    fingerprint = structural_fingerprint(state, query, distractor_pattern)
    example = TrainingExample(
        generator_version=GENERATOR_VERSION,
        seed=seed,
        state=state,
        query=query,
        rendered_input=rendered_input,
        choices=choices,
        answer=answer,
        distractor_pattern=distractor_pattern,
        hard_negative_tags=hard_negative_tags,
        structural_fingerprint=fingerprint,
        invariants=ExampleInvariants(),
    )
    validate_example(example, reserved_eval_fingerprints=reserved_eval_fingerprints)
    return example


def _formal_hard_negative_tags(
    state: SyntheticVisibleState, choices: tuple[str, ...], answer: str
) -> tuple[str, ...]:
    incoming = [
        record
        for record in state.proposals
        if _direction(state.self_handle, record.owner, record.target)
        is Direction.INCOMING
    ]
    outgoing = [
        record
        for record in state.proposals
        if _direction(state.self_handle, record.owner, record.target)
        is Direction.OUTGOING
    ]
    tags: set[str] = {
        "NEARBY_OPAQUE_HANDLES",
        "IRRELEVANT_MESSAGES_AMONG_PROPOSALS",
        "VARIABLE_PEER_COUNT",
        "VARIABLE_PROPOSAL_COUNT",
    }
    incidence = {
        peer: _peer_incidence_signature(state, peer) for peer in state.peer_handles
    }
    if any(sum(signature.values()) > 1 for signature in incidence.values()):
        tags.add("SAME_PEER_MULTIPLE_RECORDS")
    if any(
        incoming_record.owner == outgoing_record.target
        for incoming_record in incoming
        for outgoing_record in outgoing
    ):
        tags.update({"SAME_TARGET_DIFFERENT_DIRECTION", "SELF_PEER_ROLE_REVERSAL"})
    if len(incoming) >= 2 and len(outgoing) == 1:
        tags.add("MULTIPLE_INCOMING_ONE_OUTGOING")
    if len(outgoing) >= 2 and incoming:
        tags.add("MULTIPLE_OUTGOING_WITH_INCOMING_DISTRACTOR")
    if choices[0] != answer:
        tags.add("FIRST_ITEM_DISTRACTOR")
    if choices[-1] != answer:
        tags.add("LAST_ITEM_DISTRACTOR")
    if any(
        proposal.proposal_id[1:] == peer[1:]
        for proposal in state.proposals
        for peer in state.peer_handles
    ):
        tags.add("SAME_NUMERIC_SUFFIX_ACROSS_ENTITY_TYPES")
    if tuple(record.message_id for record in state.messages) != tuple(
        sorted(record.message_id for record in state.messages)
    ) or tuple(record.proposal_id for record in state.proposals) != tuple(
        sorted(record.proposal_id for record in state.proposals)
    ):
        tags.add("REORDERED_RECORDS")
    target_counts: dict[str, int] = {}
    for record in state.proposals:
        peer = record.owner if record.target == state.self_handle else record.target
        target_counts[peer] = target_counts.get(peer, 0) + 1
    if any(count > 1 for count in target_counts.values()):
        tags.add("PROPOSAL_TARGET_REUSED_BY_DISTRACTOR")
    return tuple(sorted(tags))


def generate_formal_example(
    seed: int,
    semantic_family: SemanticFamily,
    *,
    topology_profile: str,
    template_id: str,
    reserved_eval_fingerprints: frozenset[str] | None = None,
) -> TrainingExample:
    """Generate and validate one formal-dataset example with frozen split controls."""

    state = generate_formal_visible_state(seed, topology_profile)
    stream = _HashStream(
        seed, f"FORMAL_QUERY|{topology_profile}|{semantic_family.value}|{template_id}"
    )
    base_query = _query_for_family(state, semantic_family, stream)
    query = FoundationQuery(
        semantic_family=base_query.semantic_family,
        record_id=base_query.record_id,
        candidate_handle=base_query.candidate_handle,
        selected_action=base_query.selected_action,
        selected_payload=base_query.selected_payload,
        template_id=template_id,
    )
    answer = solve(state, query)
    choices, distractor_pattern = _choices(state, query, answer, stream)
    rendered_input = _render_formal_input(state, query, template_id)
    fingerprint = structural_fingerprint(state, query, distractor_pattern)
    example = TrainingExample(
        generator_version=GENERATOR_VERSION,
        seed=seed,
        state=state,
        query=query,
        rendered_input=rendered_input,
        choices=choices,
        answer=answer,
        distractor_pattern=distractor_pattern,
        hard_negative_tags=_formal_hard_negative_tags(state, choices, answer),
        structural_fingerprint=fingerprint,
        invariants=ExampleInvariants(),
    )
    validate_example(example, reserved_eval_fingerprints=reserved_eval_fingerprints)
    return example
