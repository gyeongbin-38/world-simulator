from __future__ import annotations

from alifelm.context import (
    ContextCognitionPipeline,
    ContextPolicy,
    DEFAULT_ACTION_PRESENTATION,
    OrderingPolicy,
    VisibleRecordCategory,
    action_presentation_digest,
)
from alifelm.live import LiveExperimentConfig, LiveExperimentController, observe_run
from alifelm.persistence import SQLiteReferenceStore


def _context_policy() -> ContextPolicy:
    return ContextPolicy.exp000(
        max_prior_visible_records=4,
        ordering=OrderingPolicy(
            policy_version="1.0.0",
            unordered_collection_algorithm="ALIFELM_CONTEXT_ORDER_V1",
            digest_algorithm="sha256",
            ordering_seed_id="live-exp000-test-order",
            ordering_seed_digest="3" * 64,
            cross_tick_order="COMMITTED_TICK_CHRONOLOGICAL",
            tie_breaker="FULL_STABLE_ITEM_KEY",
        ),
        action_presentation_digest=action_presentation_digest(DEFAULT_ACTION_PRESENTATION),
    )


def _pipeline(store: SQLiteReferenceStore) -> ContextCognitionPipeline:
    return ContextCognitionPipeline(
        _context_policy(),
        model_profile_id="live-exp000-test-model",
        generation_policy_id="live-exp000-test-generation",
        generation_seed_id="live-exp000-test-seed",
        artifact_store=store.artifact_store,
    )


class LifecycleScriptRuntime:
    """Model-shaped scripted candidate source used only to test composition."""

    def __init__(self) -> None:
        self.calls: list[tuple[int, str]] = []

    def infer(self, compiled):
        tick = int(compiled.opportunity.tick)
        actor = compiled.opportunity.agent_id.value
        self.calls.append((tick, actor))

        if tick == 0 and actor == "A":
            return {
                "action_label": "DIRECT_TEXT",
                "payload": {"target_agent_id": "B", "body": "hello"},
            }
        if tick == 1 and actor == "A":
            return {
                "action_label": "OPEN_BILATERAL_REQUEST",
                "payload": {"target_agent_id": "B"},
            }
        if tick == 2 and actor == "B":
            incoming = [
                record
                for record in compiled.context_pack.model_input.visible_protocol_state
                if record.category is VisibleRecordCategory.INCOMING_PROPOSAL
            ]
            assert len(incoming) == 1
            return {
                "action_label": "CONFIRM_BILATERAL_REQUEST",
                "payload": {"proposal_id": incoming[0].payload.proposal_id},
            }
        return {"action_label": "NO_DIRECTED_ACTION", "payload": {}}


def _config() -> LiveExperimentConfig:
    return LiveExperimentConfig(
        run_id="live-exp000-test-run",
        founders=("A", "B"),
        lifespan_ticks=4,
        maturity_delay_ticks=0,
        refractory_interval_ticks=0,
    )


def test_live_controller_commits_message_birth_and_natural_death(tmp_path) -> None:
    store = SQLiteReferenceStore(tmp_path / "run.sqlite", artifact_root=tmp_path / "cas")
    runtime = LifecycleScriptRuntime()
    try:
        controller = LiveExperimentController.create(
            _config(), runtime=runtime, context_pipeline=_pipeline(store), store=store
        )
        results = controller.run_until_stop(max_ticks=4)
        observation = controller.observe(recent_event_limit=100)

        assert len(results) == 4
        assert observation.tick == 4
        assert observation.state_version == 4
        assert observation.message_count == 1
        assert len(observation.alive_agents) == 1
        assert observation.alive_agents[0] not in {"A", "B"}

        event_types = [event_type for _, event_type in observation.recent_events]
        assert "MessageCommitted" in event_types
        assert "AgentBorn" in event_types
        assert event_types.count("AgentDied") == 2

        durable = store.load_run(controller.run.run_id)
        assert durable.state_hash() == controller.run.state_hash()
        assert durable.snapshot == controller.run.snapshot
    finally:
        store.close()


def test_live_controller_resume_continues_from_durable_boundary(tmp_path) -> None:
    db = tmp_path / "run.sqlite"
    cas = tmp_path / "cas"
    first_runtime = LifecycleScriptRuntime()
    first_store = SQLiteReferenceStore(db, artifact_root=cas)
    try:
        first = LiveExperimentController.create(
            _config(),
            runtime=first_runtime,
            context_pipeline=_pipeline(first_store),
            store=first_store,
        )
        first.run_until_stop(max_ticks=2)
        state_after_two = first.run.state_hash()
        assert int(first.run.snapshot.tick) == 2
    finally:
        first_store.close()

    second_runtime = LifecycleScriptRuntime()
    second_store = SQLiteReferenceStore(db, artifact_root=cas)
    try:
        resumed = LiveExperimentController.resume(
            "live-exp000-test-run",
            runtime=second_runtime,
            context_pipeline=_pipeline(second_store),
            store=second_store,
        )
        assert resumed.run.state_hash() == state_after_two
        assert int(resumed.run.snapshot.tick) == 2
        resumed.run_until_stop(max_ticks=2)
        assert int(resumed.run.snapshot.tick) == 4
        assert len(resumed.run.snapshot.agents) == 1
        assert all(tick >= 2 for tick, _ in second_runtime.calls)
    finally:
        second_store.close()


def test_observation_is_read_only(tmp_path) -> None:
    store = SQLiteReferenceStore(tmp_path / "run.sqlite", artifact_root=tmp_path / "cas")
    runtime = LifecycleScriptRuntime()
    try:
        controller = LiveExperimentController.create(
            _config(), runtime=runtime, context_pipeline=_pipeline(store), store=store
        )
        controller.run_until_stop(max_ticks=1)
        before_hash = controller.run.state_hash()
        before_version = controller.run.snapshot.state_version

        observation = observe_run(controller.run)

        assert observation.state_hash == before_hash
        assert controller.run.state_hash() == before_hash
        assert controller.run.snapshot.state_version == before_version
    finally:
        store.close()
