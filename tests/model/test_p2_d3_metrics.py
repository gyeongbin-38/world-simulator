from __future__ import annotations

from alifelm.model.p2_d3_metrics import full_cohort_summary, matched_rank1_sensitivity, select_scale, summarize_scale


CONTEXTS = (
    "QUIET",
    "MESSAGE_RECEIVED",
    "PROPOSAL_RECEIVED",
    "OWN_PROPOSAL_PENDING",
    "RECENT_INTERACTION",
)


def _screen_records(actions_by_case, gap=0.0):
    rows = []
    for case, actions in actions_by_case.items():
        for context, action in zip(CONTEXTS, actions, strict=True):
            rows.append({
                "case_index": case,
                "context_class": context,
                "total_rank1": action,
                "wait_send_total_gap": gap,
            })
    return rows


def test_matched_sensitivity_counts_context_divergent_cases():
    records = _screen_records({
        4000: ["WAIT"] * 5,
        4001: ["SEND", "WAIT", "SEND", "SEND", "SEND"],
    })
    assert matched_rank1_sensitivity(records) == 1


def test_select_scale_uses_frozen_lexicographic_rule():
    summaries = {
        0.0: {"matched_sensitive_count": 1, "distinct_rank1_action_count": 2, "abs_median_wait_send_gap": 0.01},
        0.25: {"matched_sensitive_count": 2, "distinct_rank1_action_count": 2, "abs_median_wait_send_gap": 0.20},
        0.5: {"matched_sensitive_count": 2, "distinct_rank1_action_count": 3, "abs_median_wait_send_gap": 0.50},
        0.75: {"matched_sensitive_count": 2, "distinct_rank1_action_count": 3, "abs_median_wait_send_gap": 0.10},
        1.0: {"matched_sensitive_count": 2, "distinct_rank1_action_count": 3, "abs_median_wait_send_gap": 0.10},
    }
    assert select_scale(summaries) == 1.0


def test_summarize_scale_reports_gap_signs():
    records = _screen_records({4000: ["WAIT", "SEND", "SEND", "SEND", "SEND"]}, gap=-0.5)
    summary = summarize_scale(records, 0.5)
    assert summary["matched_sensitive_count"] == 1
    assert summary["distinct_rank1_action_count"] == 2
    assert summary["strict_send_gap_count"] == 5


def test_full_cohort_summary_reports_context_sensitivity_and_tvd():
    rows = []
    for case in range(4000, 4032):
        for context in CONTEXTS:
            action = "SEND" if context == "QUIET" else "WAIT"
            rows.append({
                "case_index": case,
                "context_class": context,
                "total_rank1": action,
                "wait_send_total_gap": -1.0 if action == "SEND" else 1.0,
            })
    summary = full_cohort_summary(rows)
    assert summary["matched_sensitive_count"] == 32
    assert summary["matched_sensitivity_rate"] == 1.0
    assert summary["tvd_passing_class_count_at_0_25"] == 4
    assert summary["score_proxy_g5_shape_pass"] is True
