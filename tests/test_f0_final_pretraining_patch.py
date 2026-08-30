from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import re

from alifelm.model.foundation_data import load_reserved_evaluation_fingerprints
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = REPOSITORY_ROOT / "specs/experiments"
DATASET_ROOT = Path("E:/WORLD/AI_CACHE/artifacts/F0_DATASET_V1")
V1_ROOT = Path("E:/WORLD/AI_CACHE/evidence/f0-raw-baselines-v1")
V2_ROOT = Path("E:/WORLD/AI_CACHE/evidence/f0-raw-neutrality-v2")

_TOOL_SPEC = importlib.util.spec_from_file_location(
    "f0_neutrality_v2", REPOSITORY_ROOT / "tools/f0_neutrality_v2.py"
)
assert _TOOL_SPEC is not None and _TOOL_SPEC.loader is not None
_TOOL_MODULE = importlib.util.module_from_spec(_TOOL_SPEC)
_TOOL_SPEC.loader.exec_module(_TOOL_MODULE)
build_suite = _TOOL_MODULE.build_suite


def _load(path: Path) -> dict:
    return json.loads(path.read_text("utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def test_v1_evidence_is_preserved_and_policy_comparison_retired() -> None:
    """F0-NEUTRALITY-V1-001."""

    spec = _load(EXPERIMENTS / "F0-neutrality-suite-v1.yaml")
    assert spec["free_action_policy_comparison_status"] == "UNSUITABLE"
    assert spec["ACCEPT_100_interpretation"] == "MUST_NOT_BE_INTERPRETED_AS_REPRODUCTIVE_PREFERENCE"
    assert _sha256(V1_ROOT / "neutrality_suite.json") == "5b7394c040a047c70200b36297b32fa13a3367073ad48488e0b54951c9f4f2ba"
    assert _sha256(V1_ROOT / "neutrality_raw.jsonl") == "a57ae583bb875a3c7bbbb2d428b3300be14ff5f09deb1e3e10f18ce4430ac00a"
    assert _sha256(V1_ROOT / "retention_raw.jsonl") == "dc7fe07c2a218b5efc19747adbf89f99a1a496db0bc147a6c6df08404a689ed4"


def test_v2_suite_deterministic_regeneration_and_digest() -> None:
    """F0-NEUTRALITY-V2-001."""

    artifact = _load(V2_ROOT / "neutrality_suite_v2.json")
    regenerated = build_suite()
    assert regenerated == artifact
    assert artifact["suite_digest"] == "238af6f8554ad523981783d5fb0ab6dcf5ea62e1c28a0a85e9607e9e529324dc"
    assert len(artifact["cases"]) == 604


def test_action_class_options_are_valid_and_position_balanced() -> None:
    """F0-NEUTRALITY-V2-002; F0-NEUTRALITY-V2-003."""

    suite = _load(V2_ROOT / "neutrality_suite_v2.json")
    by_stratum: dict[str, list[dict]] = defaultdict(list)
    for case in suite["cases"]:
        if case["channel"] == "ACTION_CLASS_CHOICE":
            by_stratum[case["stratum"]].append(case)
    expected = {
        "STRATUM_NO_INCOMING_PROPOSAL": (120, {"WAIT", "SEND", "PROPOSE"}),
        "STRATUM_WITH_INCOMING_PROPOSAL": (100, {"WAIT", "SEND", "PROPOSE", "ACCEPT", "REJECT"}),
    }
    for stratum, (count, labels) in expected.items():
        cases = by_stratum[stratum]
        assert len(cases) == count
        assert all(set(case["options"]) == labels for case in cases)
        position_counts = Counter(
            (position, option)
            for case in cases
            for position, option in enumerate(case["options"])
        )
        per_position = count // len(labels)
        assert all(position_counts[position, label] == per_position for position in range(len(labels)) for label in labels)


def test_v2_prompts_have_no_social_value_language_and_partner_targets_are_visible() -> None:
    """F0-NEUTRALITY-V2-004; F0-POLICY-FIREWALL-003."""

    suite = _load(V2_ROOT / "neutrality_suite_v2.json")
    forbidden = re.compile(
        r"\b(reward|prefer|better|worse|good|bad|friendly|hostile|cooperat\w*|"
        r"compet\w*|trust|distrust|surviv\w*|resource|obligation|quota|should|ought|desirable)\b",
        re.IGNORECASE,
    )
    assert all(not forbidden.search(case["input"]) for case in suite["cases"])
    partner_cases = [case for case in suite["cases"] if case["channel"] == "PARTNER_CHOICE"]
    assert len(partner_cases) == 144
    assert all(all(option in case["input"] for option in case["options"]) for case in partner_cases)
    assert all(case["action_class"] in {"SEND", "PROPOSE"} for case in partner_cases)


def test_v2_has_no_reserved_fingerprint_collision() -> None:
    """F0-CONTAMINATION-004."""

    suite = _load(V2_ROOT / "neutrality_suite_v2.json")
    reserved = load_reserved_evaluation_fingerprints()
    assert all(case["structural_fingerprint"] not in reserved for case in suite["cases"])
    assert suite["reserved_fingerprint_collisions"] == 0


def test_f0_dataset_v1_remains_byte_identical() -> None:
    """F0-DATASET-IMMUTABILITY-001."""

    manifest = _load(EXPERIMENTS / "F0-dataset-v1-manifest.yaml")
    artifact_manifest = _load(DATASET_ROOT / "manifest.json")
    assert artifact_manifest["manifest_digest"] == manifest["manifest_digest"] == "418873b65e9a8903a595d6a8359ce778dd588b9cedb0e3c5ac54d178528e5e18"
    for split in manifest["splits"].values():
        assert _sha256(DATASET_ROOT / split["file"]) == split["file_sha256"]


def test_raw_v2_provenance_and_single_label_validity_are_frozen() -> None:
    """F0-RAW-NEUTRALITY-V2-001."""

    manifest = _load(V2_ROOT / "manifest_v2.json")
    assert manifest["status"] == "FROZEN"
    assert manifest["model"]["revision"] == "48d788eca847d4d7548f375ad03d3c9312f6139e"
    assert manifest["model"]["adapter_loaded"] is False
    assert manifest["runtime"]["transport"] == "GRAMMAR_CONSTRAINED_SINGLE_LABEL_NO_JSON"
    assert manifest["summary"]["invalid"] == 0
    assert manifest["summary"]["malformed"] == 0
    assert manifest["dataset_digest_before"] == manifest["dataset_digest_after"]


def test_retention_noninferiority_was_predeclared() -> None:
    """F0-RETENTION-002."""

    criterion = _load(EXPERIMENTS / "F0-retention-noninferiority-v1.yaml")
    assert criterion["status"] == "FROZEN_PRE_TRAINING"
    assert criterion["raw_baseline"]["score"] == 29
    assert criterion["absolute_percentage_point_margin"] == 10
    assert criterion["provisional_minimum"] == {"score": 23, "n": 60, "comparison": "GREATER_THAN_OR_EQUAL"}
    assert "nonzero RAW competence" in criterion["category_collapse_policy"]
