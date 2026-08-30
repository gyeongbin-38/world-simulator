#!/usr/bin/env python3
"""Generate and freeze F0_DATASET_V2 without modifying F0_DATASET_V1."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from alifelm.model.foundation_data import canonical_digest, canonical_json  # noqa: E402
from alifelm.model.foundation_data_v2 import (  # noqa: E402
    DATASET_V2_GENERATOR_VERSION,
    DATASET_V2_ID,
    DATASET_V2_ROOT_SEED,
    LEAKAGE_SCHEMA_VERSION,
    NEURAL_FAMILIES,
    SCREENING_SCHEMA_VERSION,
    SCREENING_SIZES,
    V1_GENERATOR_VERSION,
    V2_SPLIT_SIZES,
    V2Record,
    build_sensor_invariant_records,
    build_v2_split,
    curriculum_counts,
    family_counts,
    screening_subset,
    validate_v2_split_isolation,
)


DEFAULT_OUTPUT_ROOT = Path("E:/WORLD/AI_CACHE/artifacts/F0_DATASET_V2")
MANIFEST_SCHEMA_VERSION = "1.0.0"
SENSOR_INVARIANT_SIZE = 512


def _record_dict(record: V2Record) -> dict[str, Any]:
    value = asdict(record)
    value["choices"] = list(record.choices)
    value["hard_negative_tags"] = list(record.hard_negative_tags)
    return value


def _jsonl_bytes(records: Iterable[dict[str, Any]]) -> bytes:
    return b"".join(
        (canonical_json(record) + "\n").encode("utf-8") for record in records
    )


def _artifact(payload: bytes, *, count: int) -> dict[str, Any]:
    return {
        "count": count,
        "file_sha256": hashlib.sha256(payload).hexdigest(),
    }


def build_dataset_v2() -> tuple[dict[str, bytes], dict[str, Any]]:
    records_by_split = {
        split: build_v2_split(split, size)
        for split, size in V2_SPLIT_SIZES.items()
    }
    isolation = validate_v2_split_isolation(records_by_split)

    files: dict[str, bytes] = {}
    split_manifest: dict[str, Any] = {}
    pair_groups_by_split: dict[str, int] = {}
    for split, records in records_by_split.items():
        encoded_records = [_record_dict(record) for record in records]
        payload = _jsonl_bytes(encoded_records)
        filename = split.lower() + ".jsonl"
        files[filename] = payload
        pair_groups = {
            record.pair_group_id
            for record in records
            if record.pair_group_id is not None
        }
        pair_groups_by_split[split] = len(pair_groups)
        split_manifest[split] = {
            **_artifact(payload, count=len(records)),
            "file": filename,
            "curriculum_counts": curriculum_counts(records),
            "semantic_family_counts": family_counts(records),
            "pair_group_count": len(pair_groups),
            "unique_identifier_tuple_digests": len(
                {record.identifier_tuple_digest for record in records}
            ),
            "unique_template_instance_digests": len(
                {record.template_instance_digest for record in records}
            ),
            "unique_exact_instance_digests": len(
                {record.exact_instance_digest for record in records}
            ),
        }

    screening_manifest: dict[str, Any] = {}
    for split, target_size in SCREENING_SIZES.items():
        selected = screening_subset(
            records_by_split[split],
            split=split,
            size=target_size,
        )
        filename = f"screening_{split.lower()}.jsonl"
        payload = _jsonl_bytes(_record_dict(record) for record in selected)
        files[filename] = payload
        screening_manifest[split] = {
            **_artifact(payload, count=len(selected)),
            "file": filename,
            "selection_schema": SCREENING_SCHEMA_VERSION,
            "curriculum_counts": curriculum_counts(selected),
            "semantic_family_counts": family_counts(selected),
            "pair_integrity": all(
                sum(
                    candidate.pair_group_id == record.pair_group_id
                    for candidate in selected
                )
                == 2
                for record in selected
                if record.pair_group_id is not None
            ),
        }

    sensor_records = build_sensor_invariant_records(SENSOR_INVARIANT_SIZE)
    sensor_payload = _jsonl_bytes(sensor_records)
    files["sensor_invariants.jsonl"] = sensor_payload

    neural_family_values = [family.value for family in NEURAL_FAMILIES]
    if "VISIBLE_PEER_COUNT" in neural_family_values:
        raise RuntimeError("deterministic sensor family leaked into neural family list")
    if any(
        record.semantic_family == "VISIBLE_PEER_COUNT"
        for records in records_by_split.values()
        for record in records
    ):
        raise RuntimeError("VISIBLE_PEER_COUNT leaked into F0_DATASET_V2 neural splits")

    manifest_core = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "dataset_id": DATASET_V2_ID,
        "status": "FROZEN",
        "dataset_generator_version": DATASET_V2_GENERATOR_VERSION,
        "composed_v1_generator_version": V1_GENERATOR_VERSION,
        "root_seed": DATASET_V2_ROOT_SEED,
        "neural_semantic_families": neural_family_values,
        "deterministic_sensor_families": ["VISIBLE_PEER_COUNT"],
        "split_sizes": dict(V2_SPLIT_SIZES),
        "splits": split_manifest,
        "screening": screening_manifest,
        "sensor_invariants": {
            **_artifact(sensor_payload, count=len(sensor_records)),
            "file": "sensor_invariants.jsonl",
            "gradient_target": False,
        },
        "leakage": {
            "schema": LEAKAGE_SCHEMA_VERSION,
            **isolation,
            "pair_groups_by_split": pair_groups_by_split,
        },
        "teacher_LM": False,
        "chain_of_thought": False,
        "immutability": "NEW_VERSION_REQUIRED_FOR_ANY_CONTENT_CHANGE",
        "screening_is_selection_only": True,
        "sealed_founder_evaluations_unchanged": True,
    }
    manifest = dict(manifest_core)
    manifest["manifest_digest_law"] = (
        "SHA-256(canonical JSON of manifest excluding manifest_digest)"
    )
    manifest["manifest_digest"] = canonical_digest(manifest)
    files["manifest.json"] = (canonical_json(manifest) + "\n").encode("utf-8")
    return files, manifest


def freeze(output_root: Path) -> dict[str, Any]:
    files, manifest = build_dataset_v2()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    if output_root.exists():
        for filename, expected in files.items():
            path = output_root / filename
            if not path.is_file() or path.read_bytes() != expected:
                raise RuntimeError(f"frozen F0_DATASET_V2 artifact mismatch: {path}")
        unexpected = {
            path.name for path in output_root.iterdir()
        } - set(files)
        if unexpected:
            raise RuntimeError(
                f"unexpected F0_DATASET_V2 artifacts: {sorted(unexpected)}"
            )
        return manifest

    output_root.mkdir()
    for filename, payload in files.items():
        (output_root / filename).write_bytes(payload)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Require an existing frozen directory and verify it byte-for-byte.",
    )
    args = parser.parse_args()
    if args.verify_only and not args.output.is_dir():
        raise SystemExit(f"frozen dataset does not exist: {args.output}")
    manifest = freeze(args.output)
    print(
        json.dumps(
            {
                "dataset_id": manifest["dataset_id"],
                "manifest_digest": manifest["manifest_digest"],
                "output": str(args.output),
                "screening": {
                    split: manifest["screening"][split]["count"]
                    for split in SCREENING_SIZES
                },
                "neural_families": len(manifest["neural_semantic_families"]),
                "sensor_invariants": manifest["sensor_invariants"]["count"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
