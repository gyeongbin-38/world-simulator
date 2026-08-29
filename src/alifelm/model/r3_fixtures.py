"""Deterministic researcher fixtures for I-05R3 context sensitivity."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from alifelm.context import ContextCognitionPipeline, ContextPolicy
from alifelm.domain import (
    AgentId,
    AgentState,
    Duration,
    MessageId,
    MessageRecord,
    ProposalId,
    ReproductionProposal,
    RunId,
    StateVersion,
    Tick,
)
from alifelm.kernel import EqualOpportunityScheduler, Snapshot


class R3ContextClass(StrEnum):
    QUIET = "QUIET"
    MESSAGE_RECEIVED = "MESSAGE_RECEIVED"
    PROPOSAL_RECEIVED = "PROPOSAL_RECEIVED"
    OWN_PROPOSAL_PENDING = "OWN_PROPOSAL_PENDING"
    RECENT_INTERACTION = "RECENT_INTERACTION"


def compile_r3_fixture(
    context_class: R3ContextClass,
    case_index: int,
    *,
    policy: ContextPolicy,
    model_profile_id: str,
    generation_policy_id: str,
    generation_seed_id: str,
    artifact_store: Any,
):
    """Compile one immutable context without adding diagnostic wording."""

    if not isinstance(context_class, R3ContextClass):
        raise TypeError("context_class must be an R3ContextClass")
    if type(case_index) is not int or case_index < 0:
        raise ValueError("case_index must be a non-negative integer")
    agents = tuple(
        AgentState(
            agent_id=AgentId(value),
            birth_tick=Tick(0),
            first_active_tick=Tick(0),
            lifespan_ticks=Duration(100),
            maturity_delay_ticks=Duration(0),
        )
        for value in ("A", "B", "C")
    )
    messages: tuple[MessageRecord, ...] = ()
    proposals: tuple[ReproductionProposal, ...] = ()
    if context_class is R3ContextClass.MESSAGE_RECEIVED:
        messages = (
            MessageRecord(
                message_id=MessageId(f"received-{case_index}"),
                sender_id=AgentId("B"),
                recipient_id=AgentId("A"),
                body=f"signal-{case_index}",
                committed_tick=Tick(1),
                available_tick=Tick(2),
            ),
        )
    elif context_class is R3ContextClass.PROPOSAL_RECEIVED:
        proposals = (
            ReproductionProposal(
                proposal_id=ProposalId(f"incoming-{case_index}"),
                proposer_id=AgentId("B"),
                target_id=AgentId("A"),
                created_tick=Tick(1),
            ),
        )
    elif context_class is R3ContextClass.OWN_PROPOSAL_PENDING:
        proposals = (
            ReproductionProposal(
                proposal_id=ProposalId(f"outgoing-{case_index}"),
                proposer_id=AgentId("A"),
                target_id=AgentId("B"),
                created_tick=Tick(1),
            ),
        )
    elif context_class is R3ContextClass.RECENT_INTERACTION:
        messages = (
            MessageRecord(
                message_id=MessageId(f"history-{case_index}"),
                sender_id=AgentId("A"),
                recipient_id=AgentId("B"),
                body=f"record-{case_index}",
                committed_tick=Tick(0),
                available_tick=Tick(1),
            ),
        )
    snapshot = Snapshot(
        run_id=RunId(f"i05r3-{context_class.value.lower()}-{case_index}"),
        tick=Tick(2),
        state_version=StateVersion(2),
        agents=agents,
        messages=messages,
        proposals=proposals,
        events=(),
    )
    opportunity = next(
        value
        for value in EqualOpportunityScheduler().enumerate(snapshot)
        if value.agent_id == AgentId("A")
    )
    pipeline = ContextCognitionPipeline(
        policy,
        model_profile_id=model_profile_id,
        generation_policy_id=generation_policy_id,
        generation_seed_id=generation_seed_id,
        artifact_store=artifact_store,
    )
    return pipeline.compile_all((opportunity,))[0]
