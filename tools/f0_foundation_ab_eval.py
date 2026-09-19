"""F0 Stage-1 post-training candidate evaluation.

Runs the frozen hard-rejection and review gates that the paired A/B trainer
does not cover:

- ``integrity``: reload the saved adapter and re-score the DEV split so the
  sealed artifact is verified against the training manifest's own metrics.
- ``serialization``: generative schema/semantic evaluation of
  ALREADY_SELECTED_ACTION_SERIALIZATION records via Evaluator v2.
- ``retention``: F0_NEUTRAL_RETENTION_SENTINEL_V1 exact-match scoring with the
  frozen noninferiority rule (RAW_RETENTION_BASELINE_V1 comparison).
- ``neutrality``: F0_NEUTRALITY_SUITE_V2 closed-set channels via the frozen
  teacher-forced candidate scorer, plus the predeclared review-for flags.

The tool is fail-closed: spec, suite, sentinel, dataset, tokenizer, and
adapter digests are verified before any model call; evidence is written once.
``--validate-only`` performs repository-side checks without loading a model.
``--compare`` aggregates completed eval manifests into a descriptive paired
report; the gate decision itself remains a research call, not an automated
verdict.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import platform
import statistics
import sys
from typing import Any, Iterable, Mapping


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))
sys.path.insert(0, str(REPOSITORY_ROOT / "tools"))

import f0_foundation_ab_gate as gate  # noqa: E402
import f0_foundation_ab_train as trainer  # noqa: E402

from alifelm.domain import ArtifactId, ArtifactRef, OpportunityId  # noqa: E402
from alifelm.model.foundation_data import canonical_digest  # noqa: E402
from alifelm.model.foundation_eval import (  # noqa: E402
    FOUNDATION_EVALUATOR_ID,
    FOUNDATION_EVALUATOR_VERSION,
    evaluate_foundation_scalar_record,
    evaluate_foundation_serialization_text,
    foundation_evaluation_bytes,
    score_foundation_candidates,
)
from alifelm.model.generation import (  # noqa: E402
    GenerationPolicy,
    GenerationRequest,
    generation_identity,
)
from alifelm.model.profile import ModelProfile  # noqa: E402
from alifelm.model.transformers_backend import (  # noqa: E402
    TransformersModelRuntime,
)
from alifelm.model.treatments import I0_STRICT_FREE_GENERATION  # noqa: E402


EVAL_ID = "F0_FOUNDATION_AB_EVAL_V1"
EVAL_VERSION = "1.0.0"

SENTINEL_SPEC_PATH = REPOSITORY_ROOT / "specs/experiments/F0-retention-sentinel.yaml"
NONINFERIORITY_SPEC_PATH = (
    REPOSITORY_ROOT / "specs/experiments/F0-retention-noninferiority-v1.yaml"
)
NEUTRALITY_SPEC_PATH = REPOSITORY_ROOT / "specs/experiments/F0-neutrality-suite-v2.yaml"
RAW_NEUTRALITY_SPEC_PATH = (
    REPOSITORY_ROOT / "specs/experiments/F0-raw-neutrality-baseline-v2.yaml"
)
RAW_BASELINES_SPEC_PATH = REPOSITORY_ROOT / "specs/experiments/F0-raw-baselines-v1.yaml"
UMBRELLA_SPEC_PATH = (
    REPOSITORY_ROOT / "specs/experiments/F0-neutral-foundation-adaptation.yaml"
)

NEUTRALITY_SUITE_PATH = Path(
    "E:/WORLD/AI_CACHE/evidence/f0-raw-neutrality-v2/neutrality_suite_v2.json"
)
RAW_RETENTION_PATH = Path(
    "E:/WORLD/AI_CACHE/evidence/f0-raw-baselines-v1/retention_raw.jsonl"
)

SENTINEL_ID = "F0_NEUTRAL_RETENTION_SENTINEL_V1"
SENTINEL_SHA256 = (
    "7b321d2676f6137aa8c46aa1dd94e819fa3fce37495a579481f0fcc8ef370ef0"
)
NEUTRALITY_SUITE_ID = "F0_NEUTRALITY_SUITE_V2"
NEUTRALITY_SUITE_DIGEST = (
    "238af6f8554ad523981783d5fb0ab6dcf5ea62e1c28a0a85e9607e9e529324dc"
)
NEUTRALITY_CASE_COUNT = 604
RAW_RETENTION_SCORE = 29
RAW_RETENTION_N = 60
RETENTION_PROVISIONAL_MINIMUM = 23
RETENTION_MARGIN_PP = 10

EVAL_SPLITS = trainer.EVAL_SPLITS
SERIALIZATION_FAMILY = "ALREADY_SELECTED_ACTION_SERIALIZATION"

ALL_SUITES = ("integrity", "serialization", "retention", "neutrality")


class EvalAbort(RuntimeError):
    """A required frozen invariant failed closed before or during evaluation."""


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sentinel_audit() -> dict[str, Any]:
    """Verify the frozen retention sentinel identity and digest law."""

    spec = _read_json(SENTINEL_SPEC_PATH)
    if spec.get("sentinel_id") != SENTINEL_ID:
        raise EvalAbort("retention sentinel identity mismatch")
    if spec.get("status") != "FROZEN":
        raise EvalAbort("retention sentinel is not FROZEN")
    law = spec.get("digest_law") or {}
    payload = {field: spec[field] for field in law.get("payload_fields", ())}
    digest = hashlib.sha256(
        (
            json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        ).encode("utf-8")
    ).hexdigest()
    if digest != SENTINEL_SHA256 or spec.get("sentinel_sha256") != SENTINEL_SHA256:
        raise EvalAbort("retention sentinel digest mismatch")
    cases = spec.get("cases") or []
    if len(cases) < 50 or len(cases) > 100:
        raise EvalAbort("retention sentinel case count outside frozen bounds")
    if spec.get("scoring", {}).get("mode") != (
        "EXACT_MATCH_AFTER_STRIPPING_ONE_TRAILING_NEWLINE"
    ):
        raise EvalAbort("retention scoring law mismatch")

    noninferiority = _read_json(NONINFERIORITY_SPEC_PATH)
    baseline = noninferiority.get("raw_baseline") or {}
    if baseline.get("score") != RAW_RETENTION_SCORE or baseline.get("n") != (
        RAW_RETENTION_N
    ):
        raise EvalAbort("raw retention baseline mismatch")
    minimum = noninferiority.get("provisional_minimum") or {}
    if minimum.get("score") != RETENTION_PROVISIONAL_MINIMUM or minimum.get(
        "n"
    ) != RAW_RETENTION_N:
        raise EvalAbort("retention provisional minimum mismatch")

    raw_family: dict[str, list[int]] = {}
    raw_score = 0
    if RAW_RETENTION_PATH.is_file():
        for row in _load_jsonl(RAW_RETENTION_PATH):
            family = str(row["family"])
            bucket = raw_family.setdefault(family, [0, 0])
            bucket[1] += 1
            bucket[0] += int(bool(row["exact_match"]))
            raw_score += int(bool(row["exact_match"]))
        if raw_score != RAW_RETENTION_SCORE:
            raise EvalAbort("raw retention per-case score disagrees with spec")
    return {
        "sentinel_id": SENTINEL_ID,
        "sentinel_sha256": SENTINEL_SHA256,
        "case_count": len(cases),
        "cases": cases,
        "raw_family_scores": raw_family,
        "raw_baseline_score": RAW_RETENTION_SCORE,
        "raw_baseline_n": RAW_RETENTION_N,
        "provisional_minimum": RETENTION_PROVISIONAL_MINIMUM,
        "absolute_margin_pp": RETENTION_MARGIN_PP,
    }


def _neutrality_audit() -> dict[str, Any]:
    """Verify the frozen neutrality suite identity, digest, and structure."""

    spec = _read_json(NEUTRALITY_SPEC_PATH)
    if spec.get("suite_id") != NEUTRALITY_SUITE_ID or spec.get("status") != "FROZEN":
        raise EvalAbort("neutrality suite v2 identity mismatch")
    if spec.get("suite_digest") != NEUTRALITY_SUITE_DIGEST:
        raise EvalAbort("neutrality suite v2 spec digest mismatch")
    if spec.get("case_count") != NEUTRALITY_CASE_COUNT:
        raise EvalAbort("neutrality suite v2 case count mismatch")

    suite = _read_json(NEUTRALITY_SUITE_PATH)
    if suite.get("suite_id") != NEUTRALITY_SUITE_ID:
        raise EvalAbort("neutrality suite artifact identity mismatch")
    if suite.get("suite_digest") != NEUTRALITY_SUITE_DIGEST:
        raise EvalAbort("neutrality suite artifact digest mismatch")
    cases = suite.get("cases") or []
    if len(cases) != NEUTRALITY_CASE_COUNT:
        raise EvalAbort("neutrality suite artifact case count mismatch")
    if suite.get("training_use") != "FORBIDDEN":
        raise EvalAbort("neutrality suite training firewall mismatch")

    expected_channels = spec.get("channels") or {}
    counts = Counter(str(case["channel"]) for case in cases)
    for channel, body in expected_channels.items():
        if counts.get(channel, 0) != body.get("count"):
            raise EvalAbort(f"neutrality channel count mismatch: {channel}")

    raw = _read_json(RAW_NEUTRALITY_SPEC_PATH)
    if raw.get("baseline_id") != "F0_RAW_NEUTRALITY_BASELINE_V2":
        raise EvalAbort("raw neutrality baseline identity mismatch")
    return {
        "suite_id": NEUTRALITY_SUITE_ID,
        "suite_digest": NEUTRALITY_SUITE_DIGEST,
        "case_count": len(cases),
        "cases": cases,
        "raw_baseline": raw,
    }


def _run_manifest(run_dir: Path) -> dict[str, Any]:
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        raise EvalAbort(f"training manifest missing: {manifest_path}")
    manifest = _read_json(manifest_path)
    if manifest.get("status") != "TRAIN_COMPLETE":
        raise EvalAbort(
            "training manifest status is not TRAIN_COMPLETE; "
            "evaluation requires a completed adapter artifact"
        )
    adapter_file = run_dir / "adapter" / "adapter_model.safetensors"
    if not adapter_file.is_file():
        raise EvalAbort(f"adapter artifact missing: {adapter_file}")
    adapter_digest = gate.sha256_file(adapter_file)
    recorded = (manifest.get("adapter") or {}).get(
        "adapter_model_safetensors_sha256"
    )
    if adapter_digest != recorded:
        raise EvalAbort("adapter artifact digest disagrees with training manifest")
    if manifest.get("experiment_id") != "F0_FOUNDATION_AB_V1":
        raise EvalAbort("training manifest experiment identity mismatch")
    return manifest


def validate_only() -> dict[str, Any]:
    """Repository-side checks; no model or adapter is loaded."""

    sentinel = _sentinel_audit()
    neutrality = _neutrality_audit()
    dataset = gate._dataset_audit()
    checks = {
        "sentinel": True,
        "neutrality": True,
        "dataset": True,
        "raw_retention_cases": bool(sentinel["raw_family_scores"]),
    }
    return {
        "eval_id": EVAL_ID,
        "eval_version": EVAL_VERSION,
        "status": "VALIDATE_ONLY_PASS",
        "checks": checks,
        "detail": {
            "sentinel": {
                "case_count": sentinel["case_count"],
                "raw_baseline": f"{RAW_RETENTION_SCORE}/{RAW_RETENTION_N}",
                "provisional_minimum": RETENTION_PROVISIONAL_MINIMUM,
                "raw_family_scores": sentinel["raw_family_scores"],
            },
            "neutrality": {
                "case_count": neutrality["case_count"],
                "channels": sorted(
                    {str(case["channel"]) for case in neutrality["cases"]}
                ),
            },
            "dataset": {"manifest_digest": dataset["manifest_digest"]},
        },
    }


def _generation_request(
    profile: ModelProfile,
    *,
    policy: GenerationPolicy,
    rendered: bytes,
    identity_namespace: str,
    index: int,
) -> GenerationRequest:
    rendered_hash = hashlib.sha256(rendered).hexdigest()
    context_hash = canonical_digest(
        {"eval_id": EVAL_ID, "namespace": identity_namespace, "index": index}
    )
    generation_id = generation_identity(
        context_hash=context_hash,
        profile=profile,
        policy=policy,
        generation_seed_id=policy.seed_id,
        generation_seed=0,
        rendered_input_hash=rendered_hash,
        interface_treatment_id=I0_STRICT_FREE_GENERATION.treatment_id,
        interface_treatment_version=I0_STRICT_FREE_GENERATION.version,
        interface_treatment_digest=I0_STRICT_FREE_GENERATION.digest,
        constraint_policy_id=None,
    )
    return GenerationRequest(
        opportunity_id=OpportunityId(f"F0EVAL-{identity_namespace}-{index:06d}"),
        generation_id=generation_id,
        context_pack_id=f"F0EVAL-{identity_namespace}-{index:06d}",
        context_hash=context_hash,
        rendered_input_hash=rendered_hash,
        rendered_input=rendered,
        interface_treatment_id=I0_STRICT_FREE_GENERATION.treatment_id,
        interface_treatment_version=I0_STRICT_FREE_GENERATION.version,
        interface_treatment_digest=I0_STRICT_FREE_GENERATION.digest,
        constraint_policy_id=None,
        model_profile=profile,
        generation_policy=policy,
        generation_seed_id=policy.seed_id or "F0EvalSeed",
        generation_seed=0,
        generator=None,
        stop_hooks=(),
        prefix_allowed_tokens_fn=None,
    )


def _greedy_text(
    runtime: TransformersModelRuntime,
    profile: ModelProfile,
    *,
    rendered: bytes,
    identity_namespace: str,
    index: int,
    max_new_tokens: int,
) -> str:
    policy = GenerationPolicy(
        policy_id=f"F0Eval{identity_namespace}",
        version="1.0.0",
        max_new_tokens=max_new_tokens,
        do_sample=False,
        temperature=None,
        top_p=None,
        top_k=1,
        repetition_penalty=1.0,
        seed_id="F0EvalSeed",
        stop_policy_id=None,
    )
    request = _generation_request(
        profile,
        policy=policy,
        rendered=rendered,
        identity_namespace=identity_namespace,
        index=index,
    )
    return runtime.generate(request).raw_text


def _serialization_suite(
    runtime: TransformersModelRuntime,
    profile: ModelProfile,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records = []
    for split_name in EVAL_SPLITS:
        for record in _load_jsonl(gate.DATASET_ROOT / split_name):
            if str(record["semantic_family"]) == SERIALIZATION_FAMILY:
                records.append(record)
    if not records:
        raise EvalAbort("no serialization records found in evaluation splits")

    rows: list[dict[str, Any]] = []
    schema_valid = semantic_correct = 0
    for index, record in enumerate(records):
        raw_text = _greedy_text(
            runtime,
            profile,
            rendered=str(record["input"]).encode("utf-8"),
            identity_namespace="SER",
            index=index,
            max_new_tokens=128,
        )
        result = evaluate_foundation_serialization_text(record, raw_text)
        schema_valid += int(result.schema_valid)
        semantic_correct += int(result.semantic_correct)
        rows.append(
            json.loads(foundation_evaluation_bytes(result).decode("utf-8"))
        )
    total = len(records)
    summary = {
        "family": SERIALIZATION_FAMILY,
        "count": total,
        "schema_valid": schema_valid,
        "semantic_correct": semantic_correct,
        "schema_validity": schema_valid / total,
        "semantic_correctness": semantic_correct / total,
        "transport": "GREEDY_DIRECT_COMPLETION_TOP_K_1",
    }
    return rows, summary


def _retention_suite(
    runtime: TransformersModelRuntime,
    profile: ModelProfile,
    sentinel: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    family_counts: dict[str, list[int]] = {}
    score = 0
    for index, case in enumerate(sentinel["cases"]):
        raw_text = _greedy_text(
            runtime,
            profile,
            rendered=str(case["input"]).encode("utf-8"),
            identity_namespace="RET",
            index=index,
            max_new_tokens=64,
        )
        stripped = raw_text[:-1] if raw_text.endswith("\n") else raw_text
        exact = stripped == str(case["expected"])
        score += int(exact)
        bucket = family_counts.setdefault(str(case["family"]), [0, 0])
        bucket[1] += 1
        bucket[0] += int(exact)
        rows.append(
            {
                "case_id": str(case["id"]),
                "family": str(case["family"]),
                "expected": str(case["expected"]),
                "raw_model_output": raw_text,
                "scored_output": stripped,
                "exact_match": exact,
            }
        )

    total = len(rows)
    raw_family = sentinel["raw_family_scores"]
    category_collapse = sorted(
        family
        for family, (raw_correct, _n) in raw_family.items()
        if raw_correct > 0 and family_counts.get(family, [0, 0])[0] == 0
    )
    raw_rate = RAW_RETENTION_SCORE / RAW_RETENTION_N
    adapted_rate = score / total
    delta_pp = (adapted_rate - raw_rate) * 100.0
    summary = {
        "sentinel_id": SENTINEL_ID,
        "score": score,
        "n": total,
        "rate": adapted_rate,
        "transport": "GREEDY_DIRECT_COMPLETION_TOP_K_1",
        "scoring_law": "EXACT_MATCH_AFTER_STRIPPING_ONE_TRAILING_NEWLINE",
        "per_family": {
            family: {"score": counts[0], "n": counts[1]}
            for family, counts in sorted(family_counts.items())
        },
        "raw_baseline": {
            "score": RAW_RETENTION_SCORE,
            "n": RAW_RETENTION_N,
            "rate": raw_rate,
            "per_family": {
                family: {"score": counts[0], "n": counts[1]}
                for family, counts in sorted(raw_family.items())
            },
            "transport": "CONSTRAINED_JSON",
        },
        "noninferiority": {
            "provisional_minimum": RETENTION_PROVISIONAL_MINIMUM,
            "provisional_minimum_met": score >= RETENTION_PROVISIONAL_MINIMUM,
            "absolute_margin_pp": RETENTION_MARGIN_PP,
            "delta_pp_vs_raw": delta_pp,
            "within_margin": delta_pp >= -float(RETENTION_MARGIN_PP),
            "category_collapse_flags": category_collapse,
        },
    }
    return rows, summary


def _choice_map(
    runtime: TransformersModelRuntime,
    case: Mapping[str, Any],
) -> dict[str, Any]:
    """Teacher-forced ranking over a case's closed option set."""

    options = [str(option) for option in case["options"]]
    scores = score_foundation_candidates(
        runtime,
        rendered_input=str(case["input"]),
        candidates=options,
    )
    predicted = scores[0].candidate
    by_total = sorted(
        scores, key=lambda score: (-score.total_log_probability, score.candidate)
    )[0].candidate
    expected = case.get("expected")
    return {
        "case_id": str(case["case_id"]),
        "channel": str(case["channel"]),
        "options": options,
        "predicted": predicted,
        "predicted_by_total_log_probability": by_total,
        "expected": None if expected is None else str(expected),
        "exact_match": None
        if expected is None
        else predicted == str(expected),
        "state_group": case.get("state_group"),
        "pair_id": case.get("pair_id"),
        "variant": case.get("variant"),
        "stratum": case.get("stratum"),
        "action_class": case.get("action_class"),
    }


def _order_sensitive_groups(
    rows: Iterable[Mapping[str, Any]],
) -> tuple[int, int]:
    groups: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        group = row.get("state_group")
        if group is not None:
            groups[str(group)].add(str(row["predicted"]))
    sensitive = sum(1 for predictions in groups.values() if len(predictions) > 1)
    return sensitive, len(groups)


def _neutrality_summary(
    rows: list[Mapping[str, Any]],
    raw: Mapping[str, Any],
) -> dict[str, Any]:
    """Aggregate per-case choice rows into the frozen neutrality metrics."""

    action_rows = [
        row for row in rows if row["channel"] == "ACTION_CLASS_CHOICE"
    ]
    action_distribution: dict[str, Any] = {}
    for stratum in sorted({str(row["stratum"]) for row in action_rows}):
        stratum_rows = [row for row in action_rows if row["stratum"] == stratum]
        counts = Counter(str(row["predicted"]) for row in stratum_rows)
        sensitive, groups = _order_sensitive_groups(stratum_rows)
        action_distribution[stratum] = {
            "n": len(stratum_rows),
            "counts": dict(sorted(counts.items())),
            "order_sensitive_state_groups": sensitive,
            "state_groups": groups,
        }

    partner_rows = [row for row in rows if row["channel"] == "PARTNER_CHOICE"]
    partner_counts = Counter(str(row["predicted"]) for row in partner_rows)
    first_target = lowest_handle = 0
    for row in partner_rows:
        options = [str(option) for option in row["options"]]
        first_target += int(row["predicted"] == options[0])
        lowest_handle += int(row["predicted"] == min(options))
    sensitive, groups = _order_sensitive_groups(partner_rows)
    partner_total = len(partner_rows)
    partner_summary = {
        "n": partner_total,
        "counts": dict(sorted(partner_counts.items())),
        "P0_rate": partner_counts.get("P0", 0) / partner_total
        if partner_total
        else None,
        "lowest_handle_rate": lowest_handle / partner_total
        if partner_total
        else None,
        "first_target_rate": first_target / partner_total
        if partner_total
        else None,
        "order_sensitive_state_groups": sensitive,
        "state_groups": groups,
    }

    grounding_rows = [
        row for row in rows if row["channel"] == "PROPOSAL_HANDLE_GROUNDING"
    ]
    grounding_exact = sum(1 for row in grounding_rows if row["exact_match"])
    grounding_summary = {
        "exact": grounding_exact,
        "n": len(grounding_rows),
        "rate": grounding_exact / len(grounding_rows) if grounding_rows else None,
        "policy_inference": "FORBIDDEN",
    }

    pair_summaries: dict[str, Any] = {}
    for channel, changed_key in (
        ("IDENTITY_PERMUTATION", "outputs_equivariantly_changed"),
        ("ORDER_PERMUTATION", "output_changed_pairs"),
        ("ROLE_REVERSAL", "output_changed_pairs"),
    ):
        pairs: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for row in rows:
            if row["channel"] == channel:
                pairs[str(row["pair_id"])].append(row)
        both_exact = changed = 0
        for pair_rows in pairs.values():
            if len(pair_rows) != 2:
                raise EvalAbort(f"neutrality pair is not binary: {channel}")
            both_exact += int(all(row["exact_match"] for row in pair_rows))
            changed += int(
                pair_rows[0]["predicted"] != pair_rows[1]["predicted"]
            )
        pair_count = len(pairs)
        pair_summaries[channel.lower()] = {
            "both_exact": both_exact,
            "pairs": pair_count,
            "rate": both_exact / pair_count if pair_count else None,
            changed_key: changed,
        }

    review_flags: list[dict[str, Any]] = []
    raw_pairs = {
        "identity_permutation": raw.get("identity_equivariance") or {},
        "order_permutation": raw.get("order_permutation") or {},
        "role_reversal": raw.get("role_reversal") or {},
    }
    for name, raw_body in raw_pairs.items():
        adapted_rate = pair_summaries[name]["rate"]
        if adapted_rate is None:
            continue
        raw_rate = float(raw_body.get("rate", 0.0))
        if adapted_rate < raw_rate:
            review_flags.append(
                {
                    "flag": "LOSS_OF_PERFORMANCE_VS_RAW",
                    "channel": name,
                    "raw_rate": raw_rate,
                    "adapted_rate": adapted_rate,
                }
            )
    for stratum, body in action_distribution.items():
        raw_counts = (
            raw.get("action_class_distribution", {}).get(stratum, {}).get("counts", {})
        )
        raw_total = sum(raw_counts.values()) or 1
        adapted_total = body["n"] or 1
        for label in ("WAIT", "SEND", "PROPOSE", "ACCEPT", "REJECT"):
            raw_share = raw_counts.get(label, 0) / raw_total
            adapted_share = body["counts"].get(label, 0) / adapted_total
            if abs(adapted_share - raw_share) > 0.25:
                review_flags.append(
                    {
                        "flag": "LARGE_ACTION_SHARE_SHIFT",
                        "stratum": stratum,
                        "label": label,
                        "raw_share": raw_share,
                        "adapted_share": adapted_share,
                    }
                )

    summary = {
        "suite_id": NEUTRALITY_SUITE_ID,
        "suite_digest": NEUTRALITY_SUITE_DIGEST,
        "case_count": len(rows),
        "transport": "TEACHER_FORCED_MEAN_TOKEN_LOG_PROBABILITY",
        "action_class_distribution": action_distribution,
        "partner_choice": partner_summary,
        "proposal_handle_grounding": grounding_summary,
        "identity_equivariance": pair_summaries["identity_permutation"],
        "order_permutation": pair_summaries["order_permutation"],
        "role_reversal": pair_summaries["role_reversal"],
        "invalid_label_count": 0,
        "malformed_count": 0,
        "raw_baseline_id": raw.get("baseline_id"),
        "review_flags": review_flags,
    }
    return summary


def _neutrality_suite(
    runtime: TransformersModelRuntime,
    neutrality: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cases = neutrality["cases"]
    rows = [
        _choice_map(runtime, case)
        for case in sorted(cases, key=lambda item: str(item["case_id"]))
    ]
    return rows, _neutrality_summary(rows, neutrality["raw_baseline"])


def _integrity_suite(
    runtime: TransformersModelRuntime,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Re-score DEV with the saved adapter and compare to the manifest."""

    records = _load_jsonl(gate.DATASET_ROOT / "dev.jsonl")
    correct = total = 0
    for record in records:
        if str(record["semantic_family"]) == SERIALIZATION_FAMILY:
            continue
        result = evaluate_foundation_scalar_record(runtime, record)
        total += 1
        correct += int(result.exact_match)
    nga = correct / total if total else 0.0
    manifest_eval = (manifest.get("evaluation_metrics") or {}).get(
        trainer.SELECTION_SPLIT
    ) or {}
    manifest_correct = int(manifest_eval.get("correct", -1))
    manifest_total = int(manifest_eval.get("scalar_records", -1))
    return {
        "dev_correct": correct,
        "dev_total": total,
        "dev_nga": nga,
        "manifest_correct": manifest_correct,
        "manifest_total": manifest_total,
        "matches_training_manifest": (
            correct == manifest_correct and total == manifest_total
        ),
    }


def _load_candidate(
    *,
    adapter_dir: Path | None,
) -> tuple[TransformersModelRuntime, ModelProfile, dict[str, Any]]:
    try:
        import torch
        import transformers
        from peft import PeftModel
    except ImportError as error:
        raise EvalAbort(
            "model stack unavailable; evaluation requires the admitted "
            "transformers/peft environment"
        ) from error
    if not torch.cuda.is_available():
        raise EvalAbort("CUDA device required for candidate evaluation")

    tokenizer = transformers.AutoTokenizer.from_pretrained(
        gate.MODEL_ROOT, local_files_only=True, use_fast=True
    )
    import f0_stage0_recovered_runner as stage0

    tokenizer_audit = stage0.audit_tokenizer(gate.MODEL_ROOT, tokenizer)
    model = transformers.AutoModelForCausalLM.from_pretrained(
        gate.MODEL_ROOT,
        local_files_only=True,
        dtype=torch.bfloat16,
    )
    if getattr(model.config, "model_type", None) != "olmo2":
        raise EvalAbort("loaded base is not the canonical OLMo-2 architecture")
    if adapter_dir is not None:
        model = PeftModel.from_pretrained(
            model, adapter_dir, is_trainable=False, local_files_only=True
        )
    model = model.to("cuda")
    model.eval()

    adapter_ref = None
    if adapter_dir is not None:
        adapter_ref = ArtifactRef(
            artifact_id=ArtifactId("F0-AB-CANDIDATE"),
            digest=gate.sha256_file(adapter_dir / "adapter_model.safetensors"),
        )
    profile = ModelProfile(
        profile_id="F0ABCandidateBF16",
        profile_version="1.0.0",
        model_identifier=str(gate.MODEL_ROOT),
        model_revision=trainer.BASE_REVISION,
        model_digest=trainer.BASE_CHECKPOINT_SHA256,
        tokenizer_identifier=str(gate.MODEL_ROOT),
        tokenizer_revision=trainer.BASE_REVISION,
        tokenizer_digest=tokenizer_audit["tokenizer_digest"],
        model_class=type(model).__name__,
        generation_policy_id="F0ABEval",
        device="cuda",
        dtype="bfloat16",
        adapter_ref=adapter_ref,
        trust_remote_code=False,
        add_special_tokens=True,
    )
    runtime = TransformersModelRuntime.from_components(
        profile, tokenizer=tokenizer, model=model, torch_module=torch
    )
    return runtime, profile, tokenizer_audit


def execute(
    run_dir: Path,
    suites: tuple[str, ...],
    *,
    base_only: bool = False,
) -> dict[str, Any]:
    if not run_dir.is_dir():
        raise EvalAbort(f"run directory missing: {run_dir}")
    unknown = set(suites) - set(ALL_SUITES)
    if unknown:
        raise EvalAbort(f"unknown suites: {sorted(unknown)}")

    manifest = None if base_only else _run_manifest(run_dir)
    sentinel = _sentinel_audit()
    neutrality = _neutrality_audit()
    adapter_dir = None if base_only else run_dir / "adapter"
    runtime, profile, tokenizer_audit = _load_candidate(adapter_dir=adapter_dir)

    eval_dir = run_dir / "eval"
    eval_dir.mkdir(exist_ok=True)
    summaries: dict[str, Any] = {}
    artifacts: dict[str, str] = {}

    if "integrity" in suites:
        if base_only:
            summaries["integrity"] = {"skipped": "BASE_ONLY_MODE"}
        else:
            summaries["integrity"] = _integrity_suite(runtime, manifest or {})
    if "serialization" in suites:
        rows, summaries["serialization"] = _serialization_suite(runtime, profile)
        path = eval_dir / "serialization.json"
        gate._write_new_evidence(path, {"records": rows})
        artifacts["serialization"] = gate.sha256_file(path)
    if "retention" in suites:
        rows, summaries["retention"] = _retention_suite(
            runtime, profile, sentinel
        )
        path = eval_dir / "retention.json"
        gate._write_new_evidence(path, {"records": rows})
        artifacts["retention"] = gate.sha256_file(path)
    if "neutrality" in suites:
        rows, summaries["neutrality"] = _neutrality_suite(runtime, neutrality)
        path = eval_dir / "neutrality.json"
        gate._write_new_evidence(path, {"records": rows})
        artifacts["neutrality"] = gate.sha256_file(path)

    summary_path = eval_dir / "summaries.json"
    gate._write_new_evidence(summary_path, summaries)
    artifacts["summaries"] = gate.sha256_file(summary_path)

    eval_manifest = {
        "eval_id": EVAL_ID,
        "eval_version": EVAL_VERSION,
        "experiment_id": "F0_FOUNDATION_AB_V1",
        "run_dir": str(run_dir),
        "base_only": base_only,
        "treatment": None if manifest is None else manifest.get("treatment"),
        "treatment_id": None if manifest is None else manifest.get("treatment_id"),
        "seed": None
        if manifest is None
        else (manifest.get("seed") or {}).get("value"),
        "seed_index": None
        if manifest is None
        else (manifest.get("seed") or {}).get("index"),
        "training_manifest_digest": None
        if manifest is None
        else manifest.get("manifest_digest"),
        "adapter_sha256": None
        if manifest is None
        else (manifest.get("adapter") or {}).get(
            "adapter_model_safetensors_sha256"
        ),
        "evaluator_id": FOUNDATION_EVALUATOR_ID,
        "evaluator_version": FOUNDATION_EVALUATOR_VERSION,
        "sentinel_sha256": SENTINEL_SHA256,
        "neutrality_suite_digest": NEUTRALITY_SUITE_DIGEST,
        "tokenizer": tokenizer_audit,
        "suites": sorted(summaries),
        "artifact_hashes": artifacts,
        "environment": _environment(),
        "git": gate.git_state(),
    }
    gate._write_new_evidence(eval_dir / "eval_manifest.json", eval_manifest)
    eval_manifest["eval_manifest_written"] = True
    return eval_manifest


def _environment() -> dict[str, Any]:
    body: dict[str, Any] = {
        "packages": gate.package_versions(),
        "platform": platform.platform(),
    }
    try:
        import torch

        body["cuda_available"] = bool(torch.cuda.is_available())
        if torch.cuda.is_available():
            body["gpu"] = torch.cuda.get_device_name(0)
    except ImportError:
        body["cuda_available"] = False
    return body


def compare(run_dirs: list[Path]) -> dict[str, Any]:
    """Aggregate completed eval manifests into a descriptive paired report."""

    runs: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        manifest_path = run_dir / "manifest.json"
        eval_path = run_dir / "eval" / "eval_manifest.json"
        summary_path = run_dir / "eval" / "summaries.json"
        for path in (manifest_path, eval_path, summary_path):
            if not path.is_file():
                raise EvalAbort(f"required evidence missing: {path}")
        runs.append(
            {
                "run_dir": str(run_dir),
                "training": _read_json(manifest_path),
                "eval": _read_json(eval_path),
                "summaries": _read_json(summary_path),
            }
        )

    by_treatment: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        by_treatment[str(run["training"]["treatment"])].append(run)

    treatments: dict[str, Any] = {}
    for treatment, bodies in sorted(by_treatment.items()):
        dev_nga = []
        for body in bodies:
            metrics = body["training"].get("evaluation_metrics") or {}
            split_metrics = metrics.get(trainer.SELECTION_SPLIT)
            if not split_metrics or split_metrics.get("nga") is None:
                raise EvalAbort(
                    f"training evaluation metrics missing in {body['run_dir']}"
                )
            dev_nga.append(split_metrics["nga"])
        retention = [
            body["summaries"]["retention"]["score"]
            for body in bodies
            if "retention" in body["summaries"]
        ]
        serialization = [
            body["summaries"]["serialization"]["semantic_correctness"]
            for body in bodies
            if "serialization" in body["summaries"]
        ]
        review_flags = sum(
            len(body["summaries"]["neutrality"]["review_flags"])
            for body in bodies
            if "neutrality" in body["summaries"]
        )
        treatments[treatment] = {
            "replicates": len(bodies),
            "dev_nga_mean": statistics.fmean(dev_nga),
            "dev_nga_stdev": statistics.stdev(dev_nga) if len(dev_nga) > 1 else 0.0,
            "dev_nga_values": dev_nga,
            "retention_scores": retention,
            "serialization_semantic_correctness": serialization,
            "neutrality_review_flag_total": review_flags,
        }

    paired: list[dict[str, Any]] = []
    seeds = sorted(
        {int(run["training"]["seed"]["index"]) for run in runs}
    )
    index = {
        (str(run["training"]["treatment"]), int(run["training"]["seed"]["index"])): run
        for run in runs
    }
    for seed_index in seeds:
        a = index.get(("A_NF4_QLORA", seed_index))
        b = index.get(("B_BF16_LORA", seed_index))
        if a is None or b is None:
            continue
        a_nga = (a["training"].get("evaluation_metrics") or {}).get(
            trainer.SELECTION_SPLIT, {}
        ).get("nga")
        b_nga = (b["training"].get("evaluation_metrics") or {}).get(
            trainer.SELECTION_SPLIT, {}
        ).get("nga")
        if a_nga is None or b_nga is None:
            raise EvalAbort(
                f"paired metrics incomplete at seed index {seed_index}"
            )
        paired.append(
            {
                "seed_index": seed_index,
                "seed": a["training"]["seed"]["value"],
                "dev_nga_delta_B_minus_A": b_nga - a_nga,
            }
        )
    return {
        "eval_id": EVAL_ID,
        "report": "F0_AB_PAIRED_DESCRIPTIVE_V1",
        "verdict": "RESEARCH_CALL_NOT_AUTOMATED",
        "treatments": treatments,
        "paired_seed_deltas": paired,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument(
        "--suites",
        type=str,
        default=",".join(ALL_SUITES),
        help="comma-separated subset of integrity,serialization,retention,neutrality",
    )
    parser.add_argument("--base-only", action="store_true")
    parser.add_argument(
        "--compare",
        type=Path,
        nargs="+",
        default=None,
        help="two or more run directories with completed eval manifests",
    )
    parser.add_argument("--output", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.validate_only:
            document = validate_only()
        elif args.compare:
            document = compare(list(args.compare))
            if args.output is not None:
                gate._write_new_evidence(args.output, document)
        else:
            if args.run_dir is None:
                raise EvalAbort("--run-dir is required for execution")
            suites = tuple(
                item.strip() for item in args.suites.split(",") if item.strip()
            )
            document = execute(
                args.run_dir, suites, base_only=bool(args.base_only)
            )
    except (EvalAbort, RuntimeError, ValueError, TypeError, OSError) as error:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "reason": f"{type(error).__name__}: {error}",
                }
            )
        )
        return 2
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
