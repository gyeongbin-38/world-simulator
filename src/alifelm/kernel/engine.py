"""One deterministic in-memory vertical slice from S_t to S_(t+1)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

from alifelm.domain import (
    ActionKind,
    ActionIntent,
    AgentId,
    AgentState,
    BirthCandidate,
    FragmentId,
    IntentBatch,
    MessageId,
    MessageRecord,
    ProposalId,
    ProposalState,
    ReproductionProposal,
    SendAction,
    Tick,
    birth_candidate_from_acceptance,
    resolve_same_boundary_births,
    should_die_after_tick,
)

from .commit import CommitRequest, CommitResult, InMemoryCommitCoordinator
from .opportunities import CognitionOpportunity, EqualOpportunityScheduler
from .run import SimulationRun
from .runtime import FakeDeterministicModelRuntime
from .state import Snapshot
from .transitions import (
    BirthConflictTransition,
    BirthTransition,
    MessageTransition,
    NaturalDeathTransition,
    ProposalCreatedTransition,
    ProposalRejectedTransition,
    TransitionFragment,
    TransitionKind,
)
from .validation import LawValidator


@dataclass(frozen=True, slots=True)
class TickResult:
    snapshot_before: Snapshot
    opportunities: tuple[CognitionOpportunity, ...]
    intent_batch: IntentBatch
    validated_intents: tuple
    fragments: tuple[TransitionFragment, ...]
    commit_request: CommitRequest
    commit_result: CommitResult
    context_packs: tuple = ()
    context_artifact_refs: tuple = ()
    cognition_attempts: tuple = ()


class DeterministicKernel:
    """Coordinate phases while reserving canonical mutation for the committer."""

    def __init__(
        self,
        run: SimulationRun,
        runtime: FakeDeterministicModelRuntime,
        scheduler: EqualOpportunityScheduler | None = None,
        validator: LawValidator | None = None,
        committer: InMemoryCommitCoordinator | None = None,
        context_pipeline=None,
    ) -> None:
        self.run = run
        self.runtime = runtime
        self.scheduler = scheduler or EqualOpportunityScheduler()
        self.validator = validator or LawValidator()
        self.committer = committer or InMemoryCommitCoordinator()
        self.context_pipeline = context_pipeline

    def run_tick(
        self,
        completion_order: tuple[AgentId, ...] | None = None,
        *,
        fault_injector=None,
        artifact_refs: tuple = (),
    ) -> TickResult:
        if fault_injector is not None:
            fault_injector.check("F1_COGNITION_START")
        snapshot = self.run.snapshot
        opportunities = self.scheduler.enumerate(snapshot)
        context_packs: tuple = ()
        context_artifact_refs: tuple = ()
        cognition_attempts: tuple = ()
        if self.context_pipeline is not None:
            # P3 completes every ContextPack (and optional durable evidence)
            # before P4 invokes any candidate runtime.
            context_result = self.context_pipeline.run(
                opportunities, self.runtime, completion_order
            )
            intent_batch = context_result.intent_batch
            context_packs = tuple(
                item.context_pack for item in context_result.compiled_contexts
            )
            context_artifact_refs = context_result.artifact_refs
            cognition_attempts = context_result.attempts
        else:
            by_agent = {
                opportunity.agent_id: opportunity for opportunity in opportunities
            }
            if completion_order is None:
                ordered_opportunities = opportunities
            else:
                if set(completion_order) != set(by_agent) or len(completion_order) != len(by_agent):
                    raise ValueError("completion_order must contain every active agent exactly once")
                ordered_opportunities = tuple(
                    by_agent[agent_id] for agent_id in completion_order
                )

            # Collection is deliberately local. No runtime completion can publish state.
            collected_intents = []
            for opportunity in ordered_opportunities:
                if fault_injector is not None:
                    fault_injector.check("F2_INFERENCE")
                collected_intents.append(self.runtime.infer(opportunity))
                if fault_injector is not None:
                    fault_injector.check("F3_RAW_OUTPUT_BEFORE_PARSE")
            collected = tuple(collected_intents)
            if len(collected) != len(opportunities):
                raise ValueError("every cognition opportunity must produce one intent")
            if any(
                intent.actor_id != opportunity.agent_id or intent.tick != snapshot.tick
                for intent, opportunity in zip(collected, ordered_opportunities)
            ):
                raise ValueError("runtime output must match its cognition opportunity")

            intent_batch = IntentBatch(
                tick=snapshot.tick,
                intents=tuple(
                    sorted(collected, key=lambda intent: str(intent.actor_id))
                ),
            )
        if fault_injector is not None:
            fault_injector.check("F4_AFTER_VALIDATION_INPUT")
        validated = self.validator.validate(intent_batch, snapshot, self.run)
        fragments = _plan_fragments(snapshot, self.run, validated)
        request = CommitRequest(
            run_id=self.run.run_id,
            tick=snapshot.tick,
            expected_state_version=snapshot.state_version,
            fragments=fragments,
        )
        all_artifact_refs = tuple(
            sorted(
                set((*artifact_refs, *context_artifact_refs)),
                key=lambda ref: (ref.artifact_id.value, ref.digest),
            )
        )
        commit_result = self.committer.commit(
            self.run,
            request,
            artifact_refs=all_artifact_refs,
            fault_injector=fault_injector,
        )
        return TickResult(
            snapshot_before=snapshot,
            opportunities=opportunities,
            intent_batch=intent_batch,
            validated_intents=validated,
            fragments=fragments,
            commit_request=request,
            commit_result=commit_result,
            context_packs=context_packs,
            context_artifact_refs=context_artifact_refs,
            cognition_attempts=cognition_attempts,
        )


def _plan_fragments(
    snapshot: Snapshot,
    run: SimulationRun,
    validated_intents: tuple,
) -> tuple[TransitionFragment, ...]:
    fragments: list[TransitionFragment] = []
    candidates: list[BirthCandidate] = []

    for validated in validated_intents:
        intent = validated.intent
        if intent.kind is ActionKind.WAIT:
            continue
        if intent.kind is ActionKind.SEND:
            assert isinstance(intent.payload, SendAction)
            message_id = _message_id(snapshot.run_id, snapshot.tick, intent)
            message = MessageRecord(
                message_id=message_id,
                sender_id=intent.actor_id,
                recipient_id=intent.payload.target_agent_id,
                body=intent.payload.body,
                committed_tick=snapshot.tick,
                available_tick=Tick(snapshot.tick + 1),
            )
            fragments.append(
                _fragment(
                    snapshot.tick,
                    TransitionKind.MESSAGE,
                    f"message|{message_id.value}",
                    MessageTransition(message),
                )
            )
        elif intent.kind is ActionKind.PROPOSE:
            target_id = intent.payload.target_agent_id
            proposal_id = _proposal_id(snapshot.run_id, snapshot.tick, intent)
            proposal = ReproductionProposal(
                proposal_id=proposal_id,
                proposer_id=intent.actor_id,
                target_id=target_id,
                created_tick=snapshot.tick,
                state=ProposalState.PENDING,
            )
            fragments.append(
                _fragment(
                    snapshot.tick,
                    TransitionKind.PROPOSAL_CREATED,
                    f"proposal|{proposal_id.value}",
                    ProposalCreatedTransition(proposal),
                )
            )
        elif intent.kind is ActionKind.ACCEPT:
            proposal = _proposal(snapshot, intent.payload.proposal_id)
            if proposal is not None:
                candidates.append(
                    birth_candidate_from_acceptance(
                        proposal,
                        accepting_agent_id=intent.actor_id,
                        acceptance_tick=snapshot.tick,
                    )
                )
        elif intent.kind is ActionKind.REJECT:
            fragments.append(
                _fragment(
                    snapshot.tick,
                    TransitionKind.PROPOSAL_REJECTED,
                    f"reject|{intent.payload.proposal_id.value}",
                    ProposalRejectedTransition(
                        proposal_id=intent.payload.proposal_id,
                        actor_id=intent.actor_id,
                    ),
                )
            )

    resolution = resolve_same_boundary_births(tuple(candidates))
    for candidate in resolution.conflicted:
        fragments.append(
            _fragment(
                snapshot.tick,
                TransitionKind.BIRTH_CONFLICT_REJECTED,
                f"birth-conflict|{candidate.proposal_id.value}",
                BirthConflictTransition(
                    proposal_id=candidate.proposal_id,
                    reason=resolution.conflict_reason,
                ),
            )
        )
    for candidate in resolution.successful:
        proposal = _proposal(snapshot, candidate.proposal_id)
        if proposal is None:
            continue
        child = AgentState(
            agent_id=_child_id(snapshot.run_id, candidate),
            birth_tick=snapshot.tick,
            first_active_tick=Tick(snapshot.tick + 1),
            lifespan_ticks=run.lifespan_ticks,
            maturity_delay_ticks=run.maturity_delay_ticks,
        )
        fragments.append(
            _fragment(
                snapshot.tick,
                TransitionKind.BIRTH,
                f"birth|{candidate.proposal_id.value}",
                BirthTransition(
                    proposal_id=candidate.proposal_id,
                    child=child,
                    parent_ids=(candidate.proposer_id, candidate.target_id),
                    refractory_until_tick=Tick(
                        snapshot.tick + run.refractory_interval_ticks
                    ),
                ),
            )
        )

    for agent in snapshot.agents:
        if should_die_after_tick(agent, snapshot.tick):
            fragments.append(
                _fragment(
                    snapshot.tick,
                    TransitionKind.NATURAL_DEATH,
                    f"death|{agent.agent_id.value}",
                    NaturalDeathTransition(agent.agent_id),
                )
            )
    return tuple(sorted(fragments, key=lambda fragment: fragment.fragment_id.value))


def _proposal(snapshot: Snapshot, proposal_id: ProposalId) -> ReproductionProposal | None:
    return next(
        (proposal for proposal in snapshot.proposals if proposal.proposal_id == proposal_id),
        None,
    )


def _fragment(tick: Tick, kind: TransitionKind, key: str, payload) -> TransitionFragment:
    material = f"{int(tick)}|{kind.value}|{key}"
    fragment_id = FragmentId(hashlib.sha256(material.encode("utf-8")).hexdigest())
    return TransitionFragment(fragment_id=fragment_id, tick=tick, kind=kind, payload=payload)


def _message_id(run_id, tick: Tick, intent: ActionIntent) -> MessageId:
    value = f"message|{run_id.value}|{int(tick)}|{intent.intent_id.value}"
    return MessageId(hashlib.sha256(value.encode("utf-8")).hexdigest())


def _proposal_id(run_id, tick: Tick, intent: ActionIntent) -> ProposalId:
    value = f"proposal|{run_id.value}|{int(tick)}|{intent.intent_id.value}"
    return ProposalId(hashlib.sha256(value.encode("utf-8")).hexdigest())


def _child_id(run_id, candidate: BirthCandidate) -> AgentId:
    value = (
        f"child|{run_id.value}|{candidate.proposal_id.value}|"
        f"{int(candidate.acceptance_tick)}"
    )
    return AgentId(hashlib.sha256(value.encode("utf-8")).hexdigest())
