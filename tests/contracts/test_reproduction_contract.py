from alifelm.domain import (
    AgentId,
    BirthCandidate,
    ConflictReason,
    ProposalId,
    ProposalState,
    ReproductionProposal,
    Tick,
    birth_candidate_from_acceptance,
    resolve_same_boundary_births,
)
import pytest


def candidate(name: str, proposer: str, target: str) -> BirthCandidate:
    return BirthCandidate(ProposalId(name), AgentId(proposer), AgentId(target), Tick(5))


def test_proposal_is_visible_only_after_its_commit_tick() -> None:
    proposal = ReproductionProposal(
        ProposalId("proposal-1"), AgentId("agent-1"), AgentId("agent-2"), Tick(4)
    )
    assert not proposal.visible_at(Tick(4))
    assert proposal.visible_at(Tick(5))
    assert proposal.state is ProposalState.PENDING


def test_acceptance_must_match_visible_pending_proposal() -> None:
    proposal = ReproductionProposal(
        ProposalId("proposal-1"), AgentId("agent-1"), AgentId("agent-2"), Tick(4)
    )
    birth = birth_candidate_from_acceptance(proposal, AgentId("agent-2"), Tick(5))
    assert birth.proposal_id == ProposalId("proposal-1")

    try:
        birth_candidate_from_acceptance(proposal, AgentId("agent-3"), Tick(5))
    except ValueError as exc:
        assert "exact proposal target" in str(exc)
    else:
        raise AssertionError("an unrelated agent must not accept the proposal")


def test_shared_parent_conflict_rejects_all_candidates_without_a_winner() -> None:
    first = candidate("proposal-a", "agent-1", "agent-2")
    second = candidate("proposal-b", "agent-1", "agent-3")

    result = resolve_same_boundary_births((second, first))

    assert result.successful == ()
    assert result.conflicted == (first, second)
    assert result.conflict_reason is ConflictReason.MULTI_BIRTH_BOUNDARY_CONFLICT


def test_failed_acceptance_does_not_fabricate_accepted_proposal_state() -> None:
    first = ReproductionProposal(
        ProposalId("proposal-a"), AgentId("agent-1"), AgentId("agent-2"), Tick(4)
    )
    second = ReproductionProposal(
        ProposalId("proposal-b"), AgentId("agent-1"), AgentId("agent-3"), Tick(4)
    )
    candidates = (
        birth_candidate_from_acceptance(first, AgentId("agent-2"), Tick(5)),
        birth_candidate_from_acceptance(second, AgentId("agent-3"), Tick(5)),
    )

    result = resolve_same_boundary_births(candidates)

    assert result.successful == ()
    assert first.state is ProposalState.PENDING
    assert second.state is ProposalState.PENDING


def test_disjoint_candidates_can_succeed_and_have_stable_output_order() -> None:
    first = candidate("proposal-b", "agent-1", "agent-2")
    second = candidate("proposal-a", "agent-3", "agent-4")

    result = resolve_same_boundary_births((first, second))

    assert result.conflicted == ()
    assert tuple(item.proposal_id.value for item in result.successful) == (
        "proposal-a",
        "proposal-b",
    )


def test_conflict_resolution_does_not_cross_commit_boundaries() -> None:
    first = candidate("proposal-a", "agent-1", "agent-2")
    later = BirthCandidate(
        ProposalId("proposal-b"), AgentId("agent-1"), AgentId("agent-3"), Tick(6)
    )

    with pytest.raises(ValueError, match="one commit boundary"):
        resolve_same_boundary_births((first, later))
