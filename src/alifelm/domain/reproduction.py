"""Bilateral reproduction proposal contracts and conflict semantics."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .identifiers import AgentId, ProposalId
from .values import Tick


class ProposalState(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"


@dataclass(frozen=True, slots=True)
class ReproductionProposal:
    proposal_id: ProposalId
    proposer_id: AgentId
    target_id: AgentId
    created_tick: Tick
    state: ProposalState = ProposalState.PENDING
    expires_at_tick: Tick | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.proposal_id, ProposalId):
            raise TypeError("proposal_id must be a ProposalId")
        if not isinstance(self.proposer_id, AgentId):
            raise TypeError("proposer_id must be an AgentId")
        if not isinstance(self.target_id, AgentId):
            raise TypeError("target_id must be an AgentId")
        if not isinstance(self.created_tick, Tick):
            raise TypeError("created_tick must be a Tick")
        if not isinstance(self.state, ProposalState):
            raise TypeError("state must be a ProposalState")
        if self.proposer_id == self.target_id:
            raise ValueError("a reproduction proposal cannot target its proposer")
        if self.expires_at_tick is not None:
            if not isinstance(self.expires_at_tick, Tick):
                raise TypeError("expires_at_tick must be a Tick or None")
            if self.expires_at_tick < self.created_tick:
                raise ValueError("proposal expiry cannot precede proposal creation")

    def visible_at(self, tick: Tick) -> bool:
        """A proposal committed at ``t`` is visible starting in ``S_(t+1)``."""

        if not isinstance(tick, Tick):
            raise TypeError("tick must be a Tick")
        return self.created_tick < tick


@dataclass(frozen=True, slots=True)
class BirthCandidate:
    proposal_id: ProposalId
    proposer_id: AgentId
    target_id: AgentId
    acceptance_tick: Tick

    def __post_init__(self) -> None:
        if not isinstance(self.proposal_id, ProposalId):
            raise TypeError("proposal_id must be a ProposalId")
        if not isinstance(self.proposer_id, AgentId):
            raise TypeError("proposer_id must be an AgentId")
        if not isinstance(self.target_id, AgentId):
            raise TypeError("target_id must be an AgentId")
        if not isinstance(self.acceptance_tick, Tick):
            raise TypeError("acceptance_tick must be a Tick")
        if self.proposer_id == self.target_id:
            raise ValueError("a birth candidate requires two distinct parents")

    @property
    def parent_ids(self) -> frozenset[AgentId]:
        return frozenset((self.proposer_id, self.target_id))


class ConflictReason(StrEnum):
    MULTI_BIRTH_BOUNDARY_CONFLICT = "MULTI_BIRTH_BOUNDARY_CONFLICT"


def birth_candidate_from_acceptance(
    proposal: ReproductionProposal,
    accepting_agent_id: AgentId,
    acceptance_tick: Tick,
) -> BirthCandidate:
    """Create a candidate only for the exact visible pending proposal.

    Lifecycle eligibility is intentionally left to the validating snapshot;
    this helper enforces only proposal identity, target matching, and timing.
    """

    if not isinstance(proposal, ReproductionProposal):
        raise TypeError("proposal must be a ReproductionProposal")
    if not isinstance(accepting_agent_id, AgentId):
        raise TypeError("accepting_agent_id must be an AgentId")
    if not isinstance(acceptance_tick, Tick):
        raise TypeError("acceptance_tick must be a Tick")
    if proposal.state is not ProposalState.PENDING:
        raise ValueError("only a pending proposal can become a birth candidate")
    if accepting_agent_id != proposal.target_id:
        raise ValueError("acceptance must name the exact proposal target")
    if not proposal.visible_at(acceptance_tick):
        raise ValueError("a proposal cannot be accepted in its commit tick")
    return BirthCandidate(
        proposal_id=proposal.proposal_id,
        proposer_id=proposal.proposer_id,
        target_id=proposal.target_id,
        acceptance_tick=acceptance_tick,
    )


@dataclass(frozen=True, slots=True)
class BirthResolution:
    successful: tuple[BirthCandidate, ...]
    conflicted: tuple[BirthCandidate, ...]
    conflict_reason: ConflictReason | None = None


def resolve_same_boundary_births(
    candidates: tuple[BirthCandidate, ...],
) -> BirthResolution:
    """Reject every candidate sharing a parent with another candidate.

    This deliberately has no winner.  Sorting is used only for stable output
    serialization after social conflict classification, never for selection.
    """

    if candidates:
        boundary = candidates[0].acceptance_tick
        if any(candidate.acceptance_tick != boundary for candidate in candidates):
            raise ValueError("all candidates must belong to one commit boundary")

    parent_counts: dict[AgentId, int] = {}
    for candidate in candidates:
        for parent_id in candidate.parent_ids:
            parent_counts[parent_id] = parent_counts.get(parent_id, 0) + 1

    conflicted = tuple(
        sorted(
            (candidate for candidate in candidates if any(
                parent_counts[parent_id] > 1 for parent_id in candidate.parent_ids
            )),
            key=lambda candidate: candidate.proposal_id.value,
        )
    )
    conflicted_ids = {candidate.proposal_id for candidate in conflicted}
    successful = tuple(
        sorted(
            (candidate for candidate in candidates if candidate.proposal_id not in conflicted_ids),
            key=lambda candidate: candidate.proposal_id.value,
        )
    )
    return BirthResolution(
        successful=successful,
        conflicted=conflicted,
        conflict_reason=(
            ConflictReason.MULTI_BIRTH_BOUNDARY_CONFLICT if conflicted else None
        ),
    )
