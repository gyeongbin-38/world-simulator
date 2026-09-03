from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys

from tools.world_p2_d3_targeted_adapter_scaling_r2 import _score_record_from_d1


@dataclass
class _Branch:
    internal_action: str
    model_label: str
    token_ids: tuple[int, ...]
    total_log_probability: float
    mean_log_probability: float
    total_rank: int
    mean_rank: int


class _D1LikeResult:
    common_prefix_token_ids = (1, 2)
    divergence_step = 3
    selector_prefix_forward_count = 1
    common_prefix_forward_count = 2
    branch_continuation_forward_count = 4
    branch_scores = (
        _Branch("WAIT", "NO_DIRECTED_ACTION", (10, 11), -2.0, -1.0, 2, 2),
        _Branch("SEND", "DIRECT_TEXT", (20, 21), -1.0, -0.5, 1, 1),
        _Branch("PROPOSE", "OPEN_BILATERAL_REQUEST", (30,), -3.0, -3.0, 3, 3),
        _Branch("ACCEPT", "CONFIRM_BILATERAL_REQUEST", (40,), -4.0, -4.0, 4, 4),
        _Branch("REJECT", "DECLINE_BILATERAL_REQUEST", (50,), -5.0, -5.0, 5, 5),
    )

    def total_scores(self):
        return {row.internal_action: row.total_log_probability for row in self.branch_scores}

    def mean_scores(self):
        return {row.internal_action: row.mean_log_probability for row in self.branch_scores}


def test_r2_serializer_accepts_d1_result_shape_without_d2_only_attributes():
    record = _score_record_from_d1(_D1LikeResult(), condition="TEST", layers=(9, 10))

    assert record["actions_scored"] == ["WAIT", "SEND", "PROPOSE", "ACCEPT", "REJECT"]
    assert record["wait_send_total_gap"] == -1.0
    assert record["wait_send_mean_gap"] == -0.5
    assert record["total_rank1"] == "SEND"
    assert record["mean_rank1"] == "SEND"
    assert record["patch_layers"] == [9, 10]


def test_r2_script_bootstraps_repo_imports_without_pythonpath():
    repo = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    completed = subprocess.run(
        [sys.executable, str(repo / "tools" / "world_p2_d3_targeted_adapter_scaling_r2.py"), "--help"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "WORLD P2-D3 targeted adapter scaling" in completed.stdout
