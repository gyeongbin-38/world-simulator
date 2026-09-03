from alifelm.model.p2_d1_boundary import (
    D1_ACTION_ORDER,
    legal_sets_identical,
    survivors_after_token,
)
from alifelm.model.p2_d1_metrics import (
    exact_repeat_deltas,
    localization_tag,
    matched_nonquiet_vs_quiet,
    paired_condition_shift,
)


def _row(context: str, case: int, *, wait: float, send: float, rank1: str = "WAIT"):
    totals = {
        "WAIT": wait,
        "SEND": send,
        "PROPOSE": -8.0,
        "ACCEPT": -9.0,
        "REJECT": -10.0,
    }
    order = sorted(D1_ACTION_ORDER, key=lambda action: (-totals[action], D1_ACTION_ORDER.index(action)))
    ranks = {action: index + 1 for index, action in enumerate(order)}
    return {
        "condition": "C10",
        "context_class": context,
        "case_index": case,
        "context_token_ids": [1],
        "prefix_token_ids": [2],
        "combined_token_ids": [1, 2],
        "common_prefix_token_ids": [3],
        "divergence_step": 1,
        "total_scores": totals,
        "mean_scores": totals.copy(),
        "total_ranks": ranks,
        "mean_ranks": ranks.copy(),
        "total_rank1": rank1,
        "mean_rank1": rank1,
        "nda_total_margin": wait - max(value for action, value in totals.items() if action != "WAIT"),
    }


def _cohort(*, message_send: float = -4.0):
    rows = []
    for case in range(4000, 4032):
        rows.append(_row("QUIET", case, wait=-1.0, send=-6.0))
        rows.append(_row("MESSAGE_RECEIVED", case, wait=-1.0, send=message_send))
        rows.append(_row("PROPOSAL_RECEIVED", case, wait=-1.0, send=-5.0))
        rows.append(_row("OWN_PROPOSAL_PENDING", case, wait=-1.0, send=-5.5))
        rows.append(_row("RECENT_INTERACTION", case, wait=-1.0, send=-4.5))
    return rows


def test_legal_set_divergence_uses_frozen_branch_order():
    same = {action: (1, 2, 3) for action in D1_ACTION_ORDER}
    assert legal_sets_identical(same) is True
    split = dict(same)
    split["SEND"] = (1, 2)
    assert legal_sets_identical(split) is False


def test_survivors_after_token_filters_counterfactual_branches():
    legal = {
        "WAIT": (7, 8),
        "SEND": (8, 9),
        "PROPOSE": (9,),
        "ACCEPT": (10,),
        "REJECT": (11,),
    }
    assert survivors_after_token(D1_ACTION_ORDER, legal, 8) == ("WAIT", "SEND")


def test_matched_metrics_detect_rank_stable_score_movement():
    rows = _cohort(message_send=-1.2)
    matched = matched_nonquiet_vs_quiet(rows)
    repeat = exact_repeat_deltas(rows, rows.copy())
    assert matched["MESSAGE_RECEIVED"]["max_abs_total_score_vector_delta_summary"]["max_abs"] > 0
    assert repeat["serialized_equal"] is True
    assert localization_tag(rows, matched, repeat) == "RANK_STABLE_SCORE_SENSITIVE_NDA_DOMINANCE"


def test_context_insensitive_tag_when_scores_equal_within_zero_repeat_noise():
    rows = []
    for case in range(4000, 4032):
        for context in (
            "QUIET",
            "MESSAGE_RECEIVED",
            "PROPOSAL_RECEIVED",
            "OWN_PROPOSAL_PENDING",
            "RECENT_INTERACTION",
        ):
            rows.append(_row(context, case, wait=-1.0, send=-6.0))
    matched = matched_nonquiet_vs_quiet(rows)
    repeat = exact_repeat_deltas(rows, rows.copy())
    assert localization_tag(rows, matched, repeat) == "ACTION_SCORE_CONTEXT_INSENSITIVE"


def test_paired_condition_shift_uses_identical_keys():
    c10 = _cohort(message_send=-2.0)
    c00 = [dict(row, total_scores={**row["total_scores"], "WAIT": row["total_scores"]["WAIT"] - 2.0}, nda_total_margin=row["nda_total_margin"] - 2.0) for row in c10]
    result = paired_condition_shift(c10, c00)
    assert result["QUIET"]["total_score_shift_summary"]["WAIT"]["median"] == 2.0
