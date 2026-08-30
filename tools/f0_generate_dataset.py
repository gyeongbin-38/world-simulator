"""Generate and freeze the formal F0 sensorimotor dataset.

The command is intentionally fail-closed: an existing F0_DATASET_V1 directory
is verified byte-for-byte and is never overwritten.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from alifelm.model.foundation_data import (  # noqa: E402
    FINGERPRINT_SCHEMA_VERSION,
    FORMAL_HOLDOUT_TEMPLATE_IDS,
    FORMAL_TRAIN_TEMPLATE_IDS,
    GENERATOR_VERSION,
    SPLIT_SIZES,
    SemanticFamily,
    canonical_digest,
    canonical_json,
    derive_split_seed,
    generate_formal_example,
    load_reserved_evaluation_fingerprints,
    solve,
    validate_example,
)


DATASET_ID = "F0_DATASET_V1"
SOLVER_VERSION = "F0_SYMBOLIC_SOLVER_V1"
ROOT_SEED = 350_202_608_30
DEFAULT_OUTPUT_ROOT = Path("E:/WORLD/AI_CACHE/artifacts/F0_DATASET_V1")

BASE_PROFILES = ("BASE_I2O1", "BASE_I1O2", "BASE_I2O2")
HOLDOUT_PROFILES = ("HOLDOUT_I3O1", "HOLDOUT_I1O3", "HOLDOUT_I3O2")


def _split_controls(split: str, index: int) -> tuple[str, str]:
    if split in {"TRAIN", "DEV", "TEMPLATE_HOLDOUT"}:
        profile = BASE_PROFILES[index % len(BASE_PROFILES)]
    elif split in {"STRUCTURAL_HOLDOUT", "DOUBLE_HOLDOUT"}:
        profile = HOLDOUT_PROFILES[index % len(HOLDOUT_PROFILES)]
    elif split == "ADVERSARIAL_HOLDOUT":
        profile = "ADVERSARIAL_I3O3"
    else:
        raise ValueError(split)

    if split in {"TEMPLATE_HOLDOUT", "DOUBLE_HOLDOUT", "ADVERSARIAL_HOLDOUT"}:
        templates = FORMAL_HOLDOUT_TEMPLATE_IDS
    else:
        templates = FORMAL_TRAIN_TEMPLATE_IDS
    return profile, templates[index % len(templates)]


def _accepted_seed(split: str, index: int, attempt: int) -> int:
    base = derive_split_seed(ROOT_SEED, split, index)
    if attempt == 0:
        return base
    material = f"F0_REGEN_V1|{base}|{attempt}".encode("ascii")
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")


def _record(split: str, index: int, seed: int, example: Any) -> dict[str, Any]:
    state = asdict(example.state)
    query = asdict(example.query)
    answer_format = (
        "CANONICAL_JSON"
        if example.query.semantic_family.value == "ALREADY_SELECTED_ACTION_SERIALIZATION"
        else "EXACT_SCALAR"
    )
    return {
        "example_id": f"F0-{split}-{index:06d}",
        "split": split,
        "generator_version": example.generator_version,
        "generator_seed": seed,
        "semantic_family": example.query.semantic_family.value,
        "visible_state": state,
        "input": example.rendered_input,
        "query": query,
        "choices": list(example.choices),
        "ground_truth": example.answer,
        "answer_format": answer_format,
        "structural_fingerprint": example.structural_fingerprint,
        "template_id": example.query.template_id,
        "hard_negative_tags": list(example.hard_negative_tags),
    }


def _jsonl_bytes(records: list[dict[str, Any]]) -> bytes:
    return b"".join(
        (canonical_json(record) + "\n").encode("utf-8") for record in records
    )


def build_dataset() -> tuple[dict[str, bytes], dict[str, Any]]:
    reservations = load_reserved_evaluation_fingerprints()
    families = tuple(SemanticFamily)
    split_records: dict[str, list[dict[str, Any]]] = {}
    exact_seen: set[str] = set()
    reserved_collisions = 0
    regeneration_count = 0

    for split, size in SPLIT_SIZES.items():
        records: list[dict[str, Any]] = []
        for index in range(size):
            family = families[index % len(families)]
            profile, template_id = _split_controls(split, index)
            for attempt in range(10_000):
                seed = _accepted_seed(split, index, attempt)
                try:
                    example = generate_formal_example(
                        seed,
                        family,
                        topology_profile=profile,
                        template_id=template_id,
                        reserved_eval_fingerprints=reservations,
                    )
                except Exception as exc:
                    if "reserved evaluation fingerprint" in str(exc):
                        reserved_collisions += 1
                        regeneration_count += 1
                        continue
                    raise
                validate_example(example, reserved_eval_fingerprints=reservations)
                if solve(example.state, example.query) != example.answer:
                    raise RuntimeError("symbolic solver disagreement")
                record = _record(split, index, seed, example)
                exact_key = canonical_digest(
                    {
                        "input": record["input"],
                        "choices": record["choices"],
                        "ground_truth": record["ground_truth"],
                    }
                )
                if exact_key in exact_seen:
                    regeneration_count += 1
                    continue
                exact_seen.add(exact_key)
                records.append(record)
                break
            else:
                raise RuntimeError(f"deterministic regeneration exhausted for {split}:{index}")
        split_records[split] = records

    train_fingerprints = {
        record["structural_fingerprint"] for record in split_records["TRAIN"]
    }
    structural_fingerprints = {
        record["structural_fingerprint"]
        for record in split_records["STRUCTURAL_HOLDOUT"]
    }
    double_fingerprints = {
        record["structural_fingerprint"]
        for record in split_records["DOUBLE_HOLDOUT"]
    }
    cross_split_violations = len(
        train_fingerprints & (structural_fingerprints | double_fingerprints)
    )
    train_templates = {
        record["template_id"] for record in split_records["TRAIN"]
    }
    holdout_templates = {
        record["template_id"]
        for split in ("TEMPLATE_HOLDOUT", "DOUBLE_HOLDOUT")
        for record in split_records[split]
    }
    template_violations = len(train_templates & holdout_templates)
    if cross_split_violations or template_violations:
        raise RuntimeError("split isolation failed")

    files: dict[str, bytes] = {}
    split_manifests: dict[str, Any] = {}
    total_semantic = Counter()
    total_hard_negative = Counter()
    for split, records in split_records.items():
        filename = split.lower() + ".jsonl"
        payload = _jsonl_bytes(records)
        files[filename] = payload
        semantic_counts = Counter(record["semantic_family"] for record in records)
        hard_counts = Counter(
            tag for record in records for tag in record["hard_negative_tags"]
        )
        total_semantic.update(semantic_counts)
        total_hard_negative.update(hard_counts)
        record_digests = [canonical_digest(record) for record in records]
        split_manifests[split] = {
            "dataset_id": DATASET_ID,
            "file": filename,
            "count": len(records),
            "file_sha256": hashlib.sha256(payload).hexdigest(),
            "aggregate_split_digest": canonical_digest(record_digests),
            "semantic_family_counts": dict(sorted(semantic_counts.items())),
            "hard_negative_counts": dict(sorted(hard_counts.items())),
            "unique_structural_fingerprints": len(
                {record["structural_fingerprint"] for record in records}
            ),
            "template_ids": sorted({record["template_id"] for record in records}),
        }

    manifest_core = {
        "manifest_schema_version": "1.0.0",
        "dataset_id": DATASET_ID,
        "status": "FROZEN",
        "generator_version": GENERATOR_VERSION,
        "symbolic_solver_version": SOLVER_VERSION,
        "fingerprint_version": FINGERPRINT_SCHEMA_VERSION,
        "root_seed": ROOT_SEED,
        "split_seed_derivation": "SHA-256(F0_SPLIT_SEED_V1|root_seed|split|index)",
        "reservation_set_id": "F0_RESERVED_EVALUATION_FINGERPRINTS_V1",
        "splits": split_manifests,
        "validation": {
            "examples_total": sum(SPLIT_SIZES.values()),
            "ambiguous": 0,
            "policy_examples": 0,
            "reserved_collisions_final": 0,
            "reserved_collision_regenerations": reserved_collisions,
            "exact_text_duplicates": 0,
            "cross_split_violations": cross_split_violations,
            "template_violations": template_violations,
            "regeneration_count": regeneration_count,
        },
        "aggregate_semantic_family_counts": dict(sorted(total_semantic.items())),
        "aggregate_hard_negative_counts": dict(sorted(total_hard_negative.items())),
        "teacher_LM": False,
        "chain_of_thought": False,
        "immutability": "NEW_VERSION_REQUIRED_FOR_ANY_CONTENT_CHANGE",
    }
    manifest = dict(manifest_core)
    manifest["manifest_digest_law"] = "SHA-256(canonical JSON of manifest excluding manifest_digest)"
    manifest["manifest_digest"] = canonical_digest(manifest)
    files["manifest.json"] = (canonical_json(manifest) + "\n").encode("utf-8")
    return files, manifest


def freeze(output_root: Path) -> dict[str, Any]:
    files, manifest = build_dataset()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    if output_root.exists():
        for filename, expected in files.items():
            path = output_root / filename
            if not path.is_file() or path.read_bytes() != expected:
                raise RuntimeError(f"frozen artifact mismatch: {path}")
        unexpected = {path.name for path in output_root.iterdir()} - set(files)
        if unexpected:
            raise RuntimeError(f"unexpected frozen artifacts: {sorted(unexpected)}")
        return manifest
    output_root.mkdir()
    for filename, payload in files.items():
        (output_root / filename).write_bytes(payload)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    resolved = args.output_root.resolve()
    if resolved.drive.upper() != "E:":
        raise RuntimeError("F0 formal dataset must be stored on E:")
    manifest = freeze(resolved)
    print(canonical_json(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
