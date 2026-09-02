import pytest

from alifelm.model.autonomous_admission import A0TreatmentMetrics
from alifelm.model.p2_hardening import (
    P2_BRANCH_AUDIT_ATTEMPTS,
    canonical_allowed_tokens,
    evaluate_p2_i3_branch_order_audit,
    phase_execution_identity,
    require_clean_git_status,
    stable_allowed_argmax,
)
from alifelm.model.p2_metrics import P2_CONTEXT_CLASSES


def _summary(index: int, *, attempts: int = 160) -> A0TreatmentMetrics:
    per_class = attempts // len(P2_CONTEXT_CLASSES)
    return A0TreatmentMetrics(
        treatment=f"I3_ORDER_{index}",
        attempts=attempts,
        codec_valid=attempts,
        domain_valid=attempts,
        first_token_eos=0,
        evidence_complete=attempts,
        infrastructure_failures=0,
        exact_repeat_equal=True,
        context_class_domain_valid=tuple(
            (name, per_class, per_class) for name in P2_CONTEXT_CLASSES
        ),
    )


def test_p2_g3_accepts_complete_160_context_pass_path():
    summaries = [_summary(index) for index in range(4)]
    labels = [["NO_DIRECTED_ACTION"] * P2_BRANCH_AUDIT_ATTEMPTS for _ in range(4)]
    result = evaluate_p2_i3_branch_order_audit(summaries, labels)
    assert result["pass"] is True
    assert result["candidate_agreement_count"] == 160
    assert result["candidate_agreement_total"] == 160
    assert result["candidate_agreement_rate"] == 1.0


def test_p2_g3_rejects_wrong_label_cardinality():
    summaries = [_summary(index) for index in range(4)]
    labels = [["NO_DIRECTED_ACTION"] * 159 for _ in range(4)]
    with pytest.raises(ValueError, match="160 labels"):
        evaluate_p2_i3_branch_order_audit(summaries, labels)


def test_phase_execution_identity_distinguishes_conditions_without_model_input_change():
    common = dict(
        study_id="WORLD_P2_PHASE_DECOUPLED_BEHAVIORAL_ADMISSION_V1",
        protocol_commit="2" * 40,
        config_sha256="3" * 64,
        audit_index=None,
        branch_order=None,
        context_class="QUIET",
        case_index=4000,
        generation_id="4" * 64,
        rendered_context_sha256="5" * 64,
        raw_generation_ref="6" * 64,
    )
    c00 = phase_execution_identity(
        **common,
        condition="C00",
        prefill_adapter=False,
        selector_adapter=False,
    )
    c10 = phase_execution_identity(
        **common,
        condition="C10",
        prefill_adapter=True,
        selector_adapter=False,
    )
    assert c00 != c10


def test_allowed_token_order_is_canonical_and_duplicate_free():
    assert canonical_allowed_tokens([9, 3, 7]) == (3, 7, 9)
    with pytest.raises(ValueError, match="duplicate"):
        canonical_allowed_tokens([3, 3])


def test_constrained_greedy_tie_breaks_to_lowest_allowed_token_id():
    torch = pytest.importorskip("torch")
    logits = torch.zeros(12)
    assert stable_allowed_argmax(torch, logits, [9, 3, 7]) == 3


def test_dirty_worktree_is_fail_closed():
    require_clean_git_status("")
    with pytest.raises(RuntimeError, match="clean git worktree"):
        require_clean_git_status(" M tools/example.py\n")
