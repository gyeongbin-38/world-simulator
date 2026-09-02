from alifelm.model.p1b_metrics import (
    ACTION_LABELS,
    P1B_CONTEXT_CLASSES,
    WAIT_LABEL,
    evaluate_adapter_structural_gain,
    evaluate_label_sensitivity,
    evaluate_positive_rule,
    evaluate_structural_presence,
    evaluate_wait_amplification,
    evaluate_wait_dominance,
    score_structure,
    structural_contrasts,
)


def _scores(wait=0.0, direct=-2.0, open_req=-3.0, confirm=-4.0, decline=-5.0):
    return {
        WAIT_LABEL: wait,
        "DIRECT_TEXT": direct,
        "OPEN_BILATERAL_REQUEST": open_req,
        "CONFIRM_BILATERAL_REQUEST": confirm,
        "DECLINE_BILATERAL_REQUEST": decline,
    }


def test_score_structure_matches_frozen_definitions():
    result = score_structure(_scores())
    assert result.wait_margin == 2.0
    relative = result.relative_dict()
    centered = result.centered_dict()
    assert relative["DIRECT_TEXT"] == -2.0
    assert relative["DECLINE_BILATERAL_REQUEST"] == -5.0
    assert abs(sum(centered.values())) < 1e-12


def test_structural_contrasts_isolate_action_specific_changes():
    quiet = _scores()
    message = _scores(direct=-1.0)
    proposal = _scores(confirm=-2.0, decline=-3.0)
    own = _scores(confirm=-5.0, decline=-6.0)
    contexts = {
        "QUIET": quiet,
        "MESSAGE_RECEIVED": message,
        "PROPOSAL_RECEIVED": proposal,
        "OWN_PROPOSAL_PENDING": own,
        "RECENT_INTERACTION": quiet,
    }
    values = structural_contrasts(contexts)
    assert values["S_msg"] > 0.0
    assert values["S_prop"] > 0.0
    assert values["S_owner"] > 0.0


def test_positive_rule_requires_median_and_fraction():
    assert evaluate_positive_rule([1.0] * 24 + [-1.0] * 8).passed
    assert not evaluate_positive_rule([1.0] * 23 + [-1.0] * 9).passed
    assert not evaluate_positive_rule([0.0] * 32).passed


def test_wait_amplification_uses_matched_fa_minus_base():
    result, effects = evaluate_wait_amplification([1.0] * 32, [2.0] * 32)
    assert effects == (1.0,) * 32
    assert result.passed


def test_structural_presence_and_adapter_gain_require_two_of_three():
    fa = {
        "S_msg": [1.0] * 32,
        "S_prop": [1.0] * 32,
        "S_owner": [-1.0] * 32,
    }
    presence, presence_pass = evaluate_structural_presence(fa)
    assert presence_pass
    assert presence["S_msg"].passed
    assert presence["S_prop"].passed
    assert not presence["S_owner"].passed

    base = {name: [0.0] * 32 for name in ("S_msg", "S_prop", "S_owner")}
    gains, raw, gain_pass = evaluate_adapter_structural_gain(base, fa)
    assert gain_pass
    assert raw["S_msg"] == (1.0,) * 32
    assert gains["S_msg"].passed


def test_label_sensitivity_matches_p1b_g5_thresholds():
    labels = {name: [WAIT_LABEL] * 32 for name in P1B_CONTEXT_CLASSES}
    labels["MESSAGE_RECEIVED"] = ["DIRECT_TEXT"] * 8 + [WAIT_LABEL] * 24
    labels["PROPOSAL_RECEIVED"] = ["CONFIRM_BILATERAL_REQUEST"] * 8 + [WAIT_LABEL] * 24
    result = evaluate_label_sensitivity(labels)
    assert result.matched_sensitivity_rate == 0.25
    assert result.tvd_passing_class_count == 2
    assert result.passed


def test_wait_dominance_matches_paired_interface_gate():
    labels = {name: [WAIT_LABEL] * 16 for name in P1B_CONTEXT_CLASSES}
    result = evaluate_wait_dominance(labels)
    assert result.overall_wait_rate == 1.0
    assert result.passed

    labels["MESSAGE_RECEIVED"][0] = "DIRECT_TEXT"
    labels["MESSAGE_RECEIVED"][1] = "DIRECT_TEXT"
    result = evaluate_wait_dominance(labels)
    assert result.overall_wait_rate >= 0.95
    assert result.as_dict()["per_context"]["MESSAGE_RECEIVED"]["wait_rate"] == 0.875
    assert not result.passed


def test_unknown_label_is_rejected():
    labels = {name: [WAIT_LABEL] * 32 for name in P1B_CONTEXT_CLASSES}
    labels["QUIET"][0] = "UNKNOWN"
    try:
        evaluate_label_sensitivity(labels)
    except ValueError as error:
        assert "unknown action label" in str(error)
    else:
        raise AssertionError("unknown label must be rejected")


def test_action_label_set_is_frozen():
    assert ACTION_LABELS == (
        "NO_DIRECTED_ACTION",
        "DIRECT_TEXT",
        "OPEN_BILATERAL_REQUEST",
        "CONFIRM_BILATERAL_REQUEST",
        "DECLINE_BILATERAL_REQUEST",
    )
