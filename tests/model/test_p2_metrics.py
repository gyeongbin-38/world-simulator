from alifelm.model.p2_metrics import (
    P2_CONTEXT_CLASSES,
    P2_INVALID_LABEL,
    generated_context_sensitivity,
    paired_label_agreement,
    wait_escape_reversal,
)


def _valid():
    return {name: [True] * 32 for name in P2_CONTEXT_CLASSES}


def test_generated_sensitivity_passes_without_action_frequency_target():
    labels = {name: ["NO_DIRECTED_ACTION"] * 32 for name in P2_CONTEXT_CLASSES}
    labels["MESSAGE_RECEIVED"] = ["DIRECT_TEXT"] * 32
    labels["PROPOSAL_RECEIVED"] = ["OPEN_BILATERAL_REQUEST"] * 32
    result = generated_context_sensitivity(labels, _valid())
    assert result.passed is True
    assert result.matched_sensitive_count == 32
    assert result.matched_sensitivity_rate == 1.0
    assert dict(result.tvd_from_quiet)["MESSAGE_RECEIVED"] == 1.0
    assert dict(result.tvd_from_quiet)["PROPOSAL_RECEIVED"] == 1.0


def test_generated_sensitivity_requires_all_five_domain_valid_for_matched_case():
    labels = {name: ["NO_DIRECTED_ACTION"] * 32 for name in P2_CONTEXT_CLASSES}
    labels["MESSAGE_RECEIVED"] = ["DIRECT_TEXT"] * 32
    labels["PROPOSAL_RECEIVED"] = ["OPEN_BILATERAL_REQUEST"] * 32
    valid = _valid()
    valid["RECENT_INTERACTION"] = [False] * 32
    result = generated_context_sensitivity(labels, valid)
    assert result.matched_sensitive_count == 0
    assert result.passed is False


def test_invalid_attempts_use_explicit_distribution_sentinel():
    labels = {name: ["NO_DIRECTED_ACTION"] * 32 for name in P2_CONTEXT_CLASSES}
    valid = _valid()
    valid["MESSAGE_RECEIVED"] = [False] * 8 + [True] * 24
    result = generated_context_sensitivity(labels, valid)
    payload = result.as_dict()
    assert payload["domain_invalid_distribution_label"] == P2_INVALID_LABEL
    assert dict(result.tvd_from_quiet)["MESSAGE_RECEIVED"] == 0.25


def test_pairwise_diagnostics_are_descriptive_counts():
    left = ["NO_DIRECTED_ACTION", "DIRECT_TEXT", None, "DIRECT_TEXT"]
    right = ["DIRECT_TEXT", "DIRECT_TEXT", None, "NO_DIRECTED_ACTION"]
    agreement = paired_label_agreement(left, right)
    assert agreement == {"agreeing": 2, "total": 4, "rate": 0.5}
    wait = wait_escape_reversal(left, right)
    assert wait["c11_wait_to_c10_nonwait"] == 1
    assert wait["c11_nonwait_to_c10_wait"] == 1
    assert wait["total"] == 4
