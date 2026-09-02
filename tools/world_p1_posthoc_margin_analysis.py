#!/usr/bin/env python3
"""Post-hoc exploratory analysis of frozen WORLD P1 latent action scores.

This script performs NO model inference and writes nothing into the primary P1
output root. It reads the immutable P1 summary plus its CAS detail artifact and
summarizes sub-rank action-score movement that was deliberately not part of the
preregistered P1-G2 gate.

Interpretation is descriptive only. It must not retroactively alter P1 gates.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics
from typing import Any, Iterable


P1_STUDY_ID = "WORLD_P1_CONTEXT_SENSITIVE_POLICY_V1"
WAIT_LABEL = "NO_DIRECTED_ACTION"
EXPECTED_ATTEMPTS = 80
EXPECTED_SUMMARY_SHA256 = "3d0627c3dbe874a3da512c2a1273f1bfb8069cbf0cab069a79de5b7858a07bc1"
CANONICAL_ARCHIVE_SHA256 = "240f372f2733b69413c6f161a48ef54f99fcba656ec341501ad059f5be2281d0"
QUIET = "QUIET"
CONTEXT_ORDER = (
    "QUIET",
    "MESSAGE_RECEIVED",
    "PROPOSAL_RECEIVED",
    "OWN_PROPOSAL_PENDING",
    "RECENT_INTERACTION",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def _stats(values: Iterable[float]) -> dict[str, float | int]:
    data = tuple(float(value) for value in values)
    if not data:
        raise ValueError("cannot summarize an empty sequence")
    return {
        "count": len(data),
        "mean": statistics.fmean(data),
        "median": statistics.median(data),
        "min": min(data),
        "max": max(data),
        "pstdev": statistics.pstdev(data),
    }


def _signed_counts(values: Iterable[float], *, eps: float = 1e-12) -> dict[str, int]:
    counts = {"negative": 0, "zero": 0, "positive": 0}
    for value in values:
        if value < -eps:
            counts["negative"] += 1
        elif value > eps:
            counts["positive"] += 1
        else:
            counts["zero"] += 1
    return counts


def _cas_bytes(cas_root: Path, digest: str) -> bytes:
    if len(digest) != 64:
        raise ValueError("CAS digest must be SHA-256")
    path = cas_root / digest[:2] / digest
    data = path.read_bytes()
    actual = _sha256(data)
    if actual != digest:
        raise ValueError(f"CAS digest mismatch: expected {digest}, got {actual}")
    return data


def _attempt_row(attempt: dict[str, Any]) -> dict[str, Any]:
    ranking = attempt["latent_ranking"]
    if len(ranking) != 5:
        raise ValueError("each P1 latent ranking must contain five labels")
    by_label = {entry["label"]: entry for entry in ranking}
    if len(by_label) != 5 or WAIT_LABEL not in by_label:
        raise ValueError("unexpected P1 action-label set")
    rank_order = tuple(
        entry["label"] for entry in sorted(ranking, key=lambda entry: entry["rank"])
    )
    if rank_order[0] != attempt["latent_rank1_label"]:
        raise ValueError("latent rank-1 label does not match ranking")

    wait_total = float(by_label[WAIT_LABEL]["total_log_probability"])
    wait_mean = float(by_label[WAIT_LABEL]["mean_log_probability"])
    directed = tuple(label for label in by_label if label != WAIT_LABEL)
    best_total_label = max(
        directed, key=lambda label: float(by_label[label]["total_log_probability"])
    )
    best_mean_label = max(
        directed, key=lambda label: float(by_label[label]["mean_log_probability"])
    )
    best_total = float(by_label[best_total_label]["total_log_probability"])
    best_mean = float(by_label[best_mean_label]["mean_log_probability"])

    return {
        "context_class": attempt["context_class"],
        "case_index": int(attempt["case_index"]),
        "rank_order": rank_order,
        "wait_total": wait_total,
        "wait_mean": wait_mean,
        "best_directed_total_label": best_total_label,
        "best_directed_mean_label": best_mean_label,
        "wait_margin_total": wait_total - best_total,
        "wait_margin_mean": wait_mean - best_mean,
        "relative_total": {
            label: float(by_label[label]["total_log_probability"]) - wait_total
            for label in directed
        },
        "relative_mean": {
            label: float(by_label[label]["mean_log_probability"]) - wait_mean
            for label in directed
        },
        "rank_by_label": {label: int(by_label[label]["rank"]) for label in by_label},
    }


def _group_summary(rows: list[dict[str, Any]], directed_labels: tuple[str, ...]) -> dict[str, Any]:
    return {
        "attempts": len(rows),
        "wait_margin_total": _stats(row["wait_margin_total"] for row in rows),
        "wait_margin_mean": _stats(row["wait_margin_mean"] for row in rows),
        "best_directed_total_distribution": dict(
            sorted(Counter(row["best_directed_total_label"] for row in rows).items())
        ),
        "best_directed_mean_distribution": dict(
            sorted(Counter(row["best_directed_mean_label"] for row in rows).items())
        ),
        "relative_total_by_label": {
            label: _stats(row["relative_total"][label] for row in rows)
            for label in directed_labels
        },
        "relative_mean_by_label": {
            label: _stats(row["relative_mean"][label] for row in rows)
            for label in directed_labels
        },
        "rank_by_label": {
            label: _stats(row["rank_by_label"][label] for row in rows)
            for label in (WAIT_LABEL, *directed_labels)
        },
    }


def _matched_summary(
    rows_by_key: dict[tuple[str, int], dict[str, Any]],
    directed_labels: tuple[str, ...],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    matched: dict[str, Any] = {}
    movements: list[dict[str, Any]] = []
    for context in CONTEXT_ORDER:
        if context == QUIET:
            continue
        margin_total_deltas = []
        margin_mean_deltas = []
        rank_changed = 0
        relative_total: dict[str, list[float]] = {label: [] for label in directed_labels}
        relative_mean: dict[str, list[float]] = {label: [] for label in directed_labels}
        rank_delta: dict[str, list[float]] = {
            label: [] for label in (WAIT_LABEL, *directed_labels)
        }
        for case_index in range(16):
            quiet = rows_by_key[(QUIET, case_index)]
            current = rows_by_key[(context, case_index)]
            delta_total = current["wait_margin_total"] - quiet["wait_margin_total"]
            delta_mean = current["wait_margin_mean"] - quiet["wait_margin_mean"]
            margin_total_deltas.append(delta_total)
            margin_mean_deltas.append(delta_mean)
            rank_changed += int(current["rank_order"] != quiet["rank_order"])
            for label in directed_labels:
                dt = current["relative_total"][label] - quiet["relative_total"][label]
                dm = current["relative_mean"][label] - quiet["relative_mean"][label]
                relative_total[label].append(dt)
                relative_mean[label].append(dm)
                movements.append(
                    {
                        "context_class": context,
                        "case_index": case_index,
                        "label": label,
                        "delta_relative_total_vs_quiet": dt,
                        "delta_relative_mean_vs_quiet": dm,
                        "abs_delta_relative_total_vs_quiet": abs(dt),
                    }
                )
            for label in (WAIT_LABEL, *directed_labels):
                rank_delta[label].append(
                    float(current["rank_by_label"][label] - quiet["rank_by_label"][label])
                )
        matched[context] = {
            "full_ranking_changed_count": rank_changed,
            "full_ranking_changed_rate": rank_changed / 16,
            "delta_wait_margin_total_vs_quiet": {
                "stats": _stats(margin_total_deltas),
                "sign_counts": _signed_counts(margin_total_deltas),
                "direction_note": "negative means the best directed action became closer to WAIT",
            },
            "delta_wait_margin_mean_vs_quiet": {
                "stats": _stats(margin_mean_deltas),
                "sign_counts": _signed_counts(margin_mean_deltas),
                "direction_note": "negative means the best directed action became closer to WAIT",
            },
            "delta_relative_total_by_label_vs_quiet": {
                label: {
                    "stats": _stats(relative_total[label]),
                    "sign_counts": _signed_counts(relative_total[label]),
                    "direction_note": "positive means this label became more competitive with WAIT",
                }
                for label in directed_labels
            },
            "delta_relative_mean_by_label_vs_quiet": {
                label: {
                    "stats": _stats(relative_mean[label]),
                    "sign_counts": _signed_counts(relative_mean[label]),
                    "direction_note": "positive means this label became more competitive with WAIT",
                }
                for label in directed_labels
            },
            "rank_delta_by_label_vs_quiet": {
                label: {
                    "stats": _stats(rank_delta[label]),
                    "sign_counts": _signed_counts(rank_delta[label]),
                    "direction_note": "negative means the label moved upward in rank",
                }
                for label in (WAIT_LABEL, *directed_labels)
            },
        }
    movements.sort(
        key=lambda item: (
            -item["abs_delta_relative_total_vs_quiet"],
            item["context_class"],
            item["case_index"],
            item["label"],
        )
    )
    return matched, movements[:20]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--p1-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    summary_path = args.p1_root / "summary.json"
    summary_bytes = summary_path.read_bytes()
    summary_sha = _sha256(summary_bytes)
    if summary_sha != EXPECTED_SUMMARY_SHA256:
        raise SystemExit(
            f"refusing noncanonical P1 summary: expected {EXPECTED_SUMMARY_SHA256}, got {summary_sha}"
        )
    summary = json.loads(summary_bytes.decode("utf-8"))
    if summary.get("study_id") != P1_STUDY_ID:
        raise SystemExit("unexpected P1 study identity")
    if summary.get("gates") != {"P1-G0": True, "P1-G1": False, "P1-G2": False}:
        raise SystemExit("unexpected frozen P1 gate result")

    detail_digest = summary["detail_ref"]
    detail_bytes = _cas_bytes(args.p1_root / "cas", detail_digest)
    detail = json.loads(detail_bytes.decode("utf-8"))
    attempts = detail["attempts"]
    if len(attempts) != EXPECTED_ATTEMPTS:
        raise SystemExit(f"expected {EXPECTED_ATTEMPTS} attempts, got {len(attempts)}")

    rows = [_attempt_row(attempt) for attempt in attempts]
    rows_by_key = {(row["context_class"], row["case_index"]): row for row in rows}
    expected_keys = {(context, index) for context in CONTEXT_ORDER for index in range(16)}
    if set(rows_by_key) != expected_keys:
        raise SystemExit("P1 context/case grid is incomplete or duplicated")

    labels = set(rows[0]["rank_by_label"])
    if any(set(row["rank_by_label"]) != labels for row in rows):
        raise SystemExit("action-label set changed within P1 evidence")
    directed_labels = tuple(sorted(labels - {WAIT_LABEL}))

    by_context: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_context[row["context_class"]].append(row)
    group_summary = {
        context: _group_summary(by_context[context], directed_labels)
        for context in CONTEXT_ORDER
    }
    matched_summary, strongest_movements = _matched_summary(rows_by_key, directed_labels)

    result = {
        "analysis_id": "WORLD_P1_POSTHOC_LATENT_MARGIN_V1",
        "classification": "POSTHOC_EXPLORATORY_NO_GATE",
        "source": {
            "study_id": P1_STUDY_ID,
            "summary_sha256": summary_sha,
            "source_result_digest": summary["result_digest"],
            "detail_ref": detail_digest,
            "detail_sha256": _sha256(detail_bytes),
            "canonical_archive_sha256": CANONICAL_ARCHIVE_SHA256,
            "p1_gates_unchanged": summary["gates"],
        },
        "method": {
            "model_inference_calls": 0,
            "primary_evidence_mutated": False,
            "wait_label": WAIT_LABEL,
            "directed_labels": list(directed_labels),
            "total_log_probability_note": "same frozen teacher-forced score used for P1 ranking; label token-length effects remain possible",
            "mean_log_probability_note": "reported as a secondary descriptive normalization; it was not a P1 gate",
            "interpretation_boundary": "sub-rank movement may motivate a new preregistered study but cannot change P1-G1/P1-G2",
        },
        "by_context": group_summary,
        "matched_vs_quiet": matched_summary,
        "strongest_absolute_relative_total_movements_vs_quiet": strongest_movements,
    }
    result["analysis_digest"] = _sha256(_canonical_bytes(result))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(_canonical_bytes(result))

    compact = {
        "status": "P1_POSTHOC_MARGIN_ANALYSIS_COMPLETE",
        "analysis_digest": result["analysis_digest"],
        "output": str(args.output),
        "p1_gates_unchanged": summary["gates"],
        "full_ranking_changed_rate_vs_quiet": {
            context: matched_summary[context]["full_ranking_changed_rate"]
            for context in matched_summary
        },
        "mean_delta_wait_margin_total_vs_quiet": {
            context: matched_summary[context]["delta_wait_margin_total_vs_quiet"]["stats"]["mean"]
            for context in matched_summary
        },
        "mean_delta_relative_total_by_label_vs_quiet": {
            context: {
                label: matched_summary[context]["delta_relative_total_by_label_vs_quiet"][label]["stats"]["mean"]
                for label in directed_labels
            }
            for context in matched_summary
        },
    }
    print(json.dumps(compact, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
