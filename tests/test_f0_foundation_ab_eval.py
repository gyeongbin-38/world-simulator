from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/f0_foundation_ab_eval.py"


def _tool_module():
    spec = importlib.util.spec_from_file_location("f0_foundation_ab_eval", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _action_row(
    group: str, stratum: str, predicted: str, permutation: int = 0
) -> dict:
    return {
        "case_id": f"{group}-{permutation:02d}",
        "channel": "ACTION_CLASS_CHOICE",
        "options": ["WAIT", "SEND", "PROPOSE"],
        "predicted": predicted,
        "exact_match": None,
        "state_group": group,
        "pair_id": None,
        "stratum": stratum,
    }


def _pair_row(
    channel: str, pair: str, variant: str, predicted: str, exact: bool
) -> dict:
    return {
        "case_id": f"{pair}-{variant}",
        "channel": channel,
        "options": ["X", "Y"],
        "predicted": predicted,
        "exact_match": exact,
        "state_group": None,
        "pair_id": pair,
        "variant": variant,
        "stratum": None,
    }


def test_validate_only_passes_repository_side_checks() -> None:
    module = _tool_module()
    document = module.validate_only()
    assert document["status"] == "VALIDATE_ONLY_PASS"
    assert all(document["checks"].values())
    assert document["detail"]["sentinel"]["case_count"] == 60
    assert document["detail"]["sentinel"]["raw_baseline"] == "29/60"
    assert document["detail"]["sentinel"]["provisional_minimum"] == 23
    assert document["detail"]["neutrality"]["case_count"] == 604
    assert set(document["detail"]["neutrality"]["channels"]) == {
        "ACTION_CLASS_CHOICE",
        "PARTNER_CHOICE",
        "PROPOSAL_HANDLE_GROUNDING",
        "IDENTITY_PERMUTATION",
        "ORDER_PERMUTATION",
        "ROLE_REVERSAL",
    }


def test_sentinel_digest_law_reproduces_pinned_sha() -> None:
    module = _tool_module()
    audit = module._sentinel_audit()
    assert audit["sentinel_sha256"] == module.SENTINEL_SHA256
    assert audit["raw_family_scores"]["GENERIC_JSON_FORMATTING"] == [0, 12]
    assert audit["raw_family_scores"]["SIMPLE_ARITHMETIC"] == [10, 12]


def test_neutrality_audit_verifies_artifact_and_channels() -> None:
    module = _tool_module()
    audit = module._neutrality_audit()
    assert audit["suite_digest"] == module.NEUTRALITY_SUITE_DIGEST
    assert audit["case_count"] == 604
    assert audit["raw_baseline"]["baseline_id"] == "F0_RAW_NEUTRALITY_BASELINE_V2"


def test_order_sensitive_groups_detects_permutation_shift() -> None:
    module = _tool_module()
    rows = [
        _action_row("G1", "S", "WAIT", 0),
        _action_row("G1", "S", "WAIT", 1),
        _action_row("G2", "S", "WAIT", 0),
        _action_row("G2", "S", "SEND", 1),
    ]
    sensitive, total = module._order_sensitive_groups(rows)
    assert (sensitive, total) == (1, 2)


def test_neutrality_summary_pairs_and_review_flags() -> None:
    module = _tool_module()
    rows = [
        _action_row("A1", "STRATUM_NO_INCOMING_PROPOSAL", "SEND", 0),
        _action_row("A1", "STRATUM_NO_INCOMING_PROPOSAL", "SEND", 1),
        _pair_row("IDENTITY_PERMUTATION", "P1", "BASE", "X", True),
        _pair_row("IDENTITY_PERMUTATION", "P1", "RENAMED", "Y", True),
        _pair_row("ORDER_PERMUTATION", "P2", "BASE", "X", True),
        _pair_row("ORDER_PERMUTATION", "P2", "REORDERED", "X", True),
        _pair_row("ROLE_REVERSAL", "P3", "INCOMING", "X", False),
        _pair_row("ROLE_REVERSAL", "P3", "OUTGOING", "X", False),
    ]
    raw = {
        "baseline_id": "F0_RAW_NEUTRALITY_BASELINE_V2",
        "action_class_distribution": {
            "STRATUM_NO_INCOMING_PROPOSAL": {
                "counts": {"WAIT": 30, "SEND": 90, "PROPOSE": 0}
            }
        },
        "identity_equivariance": {"rate": 0.84375},
        "order_permutation": {"rate": 1.0},
        "role_reversal": {"rate": 0.0},
    }
    summary = module._neutrality_summary(rows, raw)
    assert summary["identity_equivariance"] == {
        "both_exact": 1,
        "pairs": 1,
        "rate": 1.0,
        "outputs_equivariantly_changed": 1,
    }
    assert summary["order_permutation"]["output_changed_pairs"] == 0
    assert summary["order_permutation"]["rate"] == 1.0
    assert summary["role_reversal"]["rate"] == 0.0
    # identity improved over raw (no flag); order matched raw (no flag);
    # role reversal rate equal to raw (0.0, no flag); SEND share 1.0 vs
    # raw 0.75 -> delta 0.25 not > 0.25 (no flag).
    assert summary["review_flags"] == []


def test_neutrality_summary_flags_large_action_shift() -> None:
    module = _tool_module()
    rows = [
        _action_row("A1", "STRATUM_NO_INCOMING_PROPOSAL", "ACCEPT", 0),
        _action_row("A1", "STRATUM_NO_INCOMING_PROPOSAL", "ACCEPT", 1),
    ] + [
        _pair_row(channel, "P", "BASE", "X", True)
        for channel in ("IDENTITY_PERMUTATION", "ORDER_PERMUTATION")
    ] + [
        _pair_row(channel, "P", "ALT", "X", True)
        for channel in ("IDENTITY_PERMUTATION", "ORDER_PERMUTATION")
    ] + [
        _pair_row("ROLE_REVERSAL", "P", "IN", "X", True),
        _pair_row("ROLE_REVERSAL", "P", "OUT", "Y", True),
    ]
    raw = {
        "baseline_id": "F0_RAW_NEUTRALITY_BASELINE_V2",
        "action_class_distribution": {
            "STRATUM_NO_INCOMING_PROPOSAL": {
                "counts": {"WAIT": 30, "SEND": 90, "PROPOSE": 0}
            }
        },
        "identity_equivariance": {"rate": 0.84375},
        "order_permutation": {"rate": 1.0},
        "role_reversal": {"rate": 0.0},
    }
    summary = module._neutrality_summary(rows, raw)
    flags = {(flag["flag"], flag.get("label")) for flag in summary["review_flags"]}
    assert ("LARGE_ACTION_SHARE_SHIFT", "ACCEPT") in flags
    assert ("LARGE_ACTION_SHARE_SHIFT", "SEND") in flags


def test_neutrality_summary_flags_equivariance_loss() -> None:
    module = _tool_module()
    rows = [
        _pair_row("IDENTITY_PERMUTATION", "P1", "BASE", "X", True),
        _pair_row("IDENTITY_PERMUTATION", "P1", "RENAMED", "Y", False),
        _pair_row("ORDER_PERMUTATION", "P2", "BASE", "X", True),
        _pair_row("ORDER_PERMUTATION", "P2", "REORDERED", "X", True),
        _pair_row("ROLE_REVERSAL", "P3", "INCOMING", "X", True),
        _pair_row("ROLE_REVERSAL", "P3", "OUTGOING", "Y", True),
    ]
    raw = {
        "baseline_id": "B",
        "action_class_distribution": {},
        "identity_equivariance": {"rate": 0.84375},
        "order_permutation": {"rate": 1.0},
        "role_reversal": {"rate": 0.0},
    }
    summary = module._neutrality_summary(rows, raw)
    flags = {flag["flag"] for flag in summary["review_flags"]}
    assert "LOSS_OF_PERFORMANCE_VS_RAW" in flags


def _fake_run_dir(tmp_path: Path, treatment: str, seed_index: int, nga: float) -> Path:
    run_dir = tmp_path / f"{treatment}_SEED{seed_index}"
    adapter_dir = run_dir / "adapter"
    adapter_dir.mkdir(parents=True)
    weights = adapter_dir / "adapter_model.safetensors"
    weights.write_bytes(f"weights-{treatment}-{seed_index}".encode())
    digest = hashlib.sha256(weights.read_bytes()).hexdigest()
    manifest = {
        "experiment_id": "F0_FOUNDATION_AB_V1",
        "status": "TRAIN_COMPLETE",
        "treatment": treatment,
        "treatment_id": f"F0_AB_{treatment}",
        "seed": {"index": seed_index, "value": 1000 + seed_index},
        "adapter": {"adapter_model_safetensors_sha256": digest},
        "evaluation_metrics": {"dev.jsonl": {"nga": nga}},
        "manifest_digest": "x" * 64,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest))
    eval_dir = run_dir / "eval"
    eval_dir.mkdir()
    (eval_dir / "eval_manifest.json").write_text(json.dumps({"eval": True}))
    (eval_dir / "summaries.json").write_text(
        json.dumps({"retention": {"score": 30}, "serialization": {"semantic_correctness": 0.9}})
    )
    return run_dir


def test_run_manifest_refuses_incomplete_and_digest_drift(tmp_path: Path) -> None:
    module = _tool_module()
    run_dir = _fake_run_dir(tmp_path, "A_NF4_QLORA", 0, 0.9)

    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "manifest.json").write_text(
        json.dumps({"status": "TRAIN_ABORT"})
    )
    with pytest.raises(module.EvalAbort, match="TRAIN_COMPLETE"):
        module._run_manifest(broken)

    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["adapter"]["adapter_model_safetensors_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(module.EvalAbort, match="digest"):
        module._run_manifest(run_dir)


def test_compare_pairs_seed_deltas(tmp_path: Path) -> None:
    module = _tool_module()
    dirs = [
        _fake_run_dir(tmp_path, "A_NF4_QLORA", 0, 0.90),
        _fake_run_dir(tmp_path, "A_NF4_QLORA", 1, 0.92),
        _fake_run_dir(tmp_path, "B_BF16_LORA", 0, 0.95),
        _fake_run_dir(tmp_path, "B_BF16_LORA", 1, 0.96),
    ]
    report = module.compare(dirs)
    assert report["treatments"]["A_NF4_QLORA"]["replicates"] == 2
    assert report["treatments"]["B_BF16_LORA"]["dev_nga_mean"] == pytest.approx(0.955)
    deltas = {item["seed_index"]: item["dev_nga_delta_B_minus_A"] for item in report["paired_seed_deltas"]}
    assert deltas[0] == pytest.approx(0.05)
    assert deltas[1] == pytest.approx(0.04)


def test_founder_c0_audit_verifies_digest_law_and_firewall() -> None:
    module = _tool_module()
    audit = module._founder_c0_audit()
    assert audit["corpus_sha256"] == module.C0V2_CORPUS_SHA256
    assert audit["probe_order"] == [
        "VC00",
        "VC02R",
        "VC09",
        "VC12",
        "VC15",
        "VC01",
        "VC11",
        "VC05",
        "VC10",
        "VC16",
    ]
    assert audit["scoring"]["critical_core_error_policy"] == (
        "FAIL_REGARDLESS_OF_AGGREGATE"
    )


def test_founder_c20_audit_verifies_artifact_and_admission_rule() -> None:
    module = _tool_module()
    audit = module._founder_c20_audit()
    assert audit["artifact_sha256"] == module.C20_ARTIFACT_SHA256
    assert len(audit["probe_order"]) == 20
    assert audit["overall_minimum"] == 0.90
    assert audit["binding_id"] == "FOUNDER_C20_CRITICAL_BINDING_V1"
    assert tuple(audit["critical_categories"]) == (
        module.C20_CRITICAL_CATEGORIES
    )
    # Every admission-spec critical tag must be bound; SELF_IDENTITY binds
    # nominally to peer (no dedicated self-identity probe exists).
    for tag in (
        "SELF_IDENTITY",
        "PEER_IDENTITY_REFERENCE",
        "TARGET_REFERENCE",
        "INCOMING_PROPOSAL_OWNERSHIP",
        "OUTGOING_PROPOSAL_OWNERSHIP",
        "PROPOSAL_DIRECTION",
        "PROPOSAL_TARGET",
        "REPRODUCTION_PROPOSAL_HANDLE_GROUNDING",
    ):
        assert f"{tag}->" in audit["critical_mapping_basis"]


def test_founder_probe_renderer_matches_v1_raw_context_bytes() -> None:
    module = _tool_module()
    probe = {
        "visible_facts": [
            "Own visible age: 4",
            "Visible peer handles: P0, P1",
        ],
        "question": (
            "Select the option exactly supported by the visible peer directory."
        ),
        "choices": ["P0", "P8", "SELF"],
    }
    rendered = module._render_founder_probe(probe)
    assert rendered == (
        "Visible facts:\n"
        "Own visible age: 4\n"
        "Visible peer handles: P0, P1\n"
        "Question: Select the option exactly supported by the visible peer "
        "directory.\n"
        "Choices:\n"
        "- P0\n"
        "- P8\n"
        "- SELF"
    )


def _c0_row(probe_id: str, critical: bool, exact: bool) -> dict:
    return {
        "probe_id": probe_id,
        "critical_core": critical,
        "exact_match": exact,
        "reference_structure_valid": True,
    }


def test_founder_c0_scoring_law_critical_failure_dominates() -> None:
    module = _tool_module()
    scoring = {
        "factual_correct_minimum": 9,
        "reference_structure_valid_required": 10,
        "malformed_maximum": 0,
        "critical_core_accuracy_required": 1.0,
    }
    passing = [_c0_row(f"VC{i:02d}", i < 8, True) for i in range(10)]
    assert module._founder_c0_summary(passing, scoring)["verdict"] == (
        "ADMISSION_PASS"
    )
    # One critical miss -> FAIL regardless of 9/10 aggregate.
    critical_miss = [dict(row) for row in passing]
    critical_miss[0]["exact_match"] = False
    assert module._founder_c0_summary(critical_miss, scoring)["verdict"] == (
        "ADMISSION_FAIL"
    )
    # One non-critical miss -> 9 factual, critical 1.0 -> PASS.
    noncritical_miss = [dict(row) for row in passing]
    noncritical_miss[9]["exact_match"] = False
    assert module._founder_c0_summary(noncritical_miss, scoring)[
        "verdict"
    ] == "ADMISSION_PASS"


def _c20_row(category: str, exact: bool) -> dict:
    return {
        "category": category,
        "critical_core": category in (
            "peer",
            "incoming_proposal",
            "proposal_direction",
            "reference",
        ),
        "exact_match": exact,
        "reference_structure_valid": True,
    }


def test_founder_c20_scoring_law_and_category_mapping() -> None:
    module = _tool_module()
    # 20 probes: 11 critical categories + 9 non-critical, mirroring corpus.
    categories = (
        ["peer"] * 3
        + ["incoming_proposal"] * 3
        + ["proposal_direction"] * 3
        + ["reference"] * 2
        + ["message_sender"] * 2
        + ["message_body"] * 2
        + ["history"] * 3
        + ["peer_count"] * 2
    )
    assert len(categories) == 20
    kwargs = {
        "critical_categories": module.C20_CRITICAL_CATEGORIES,
        "mapping_basis": "test basis",
    }
    passing = [_c20_row(category, True) for category in categories]
    summary = module._founder_c20_summary(passing, **kwargs)
    assert summary["verdict"] == "ADMISSION_PASS"
    assert summary["critical_core_total"] == 11
    assert summary["critical_categories"] == list(
        module.C20_CRITICAL_CATEGORIES
    )
    # Two non-critical misses -> 18/20 = 0.90 exactly -> PASS.
    borderline = [dict(row) for row in passing]
    borderline[11]["exact_match"] = False
    borderline[12]["exact_match"] = False
    assert module._founder_c20_summary(borderline, **kwargs)["verdict"] == (
        "ADMISSION_PASS"
    )
    # A single critical miss -> FAIL even with 19/20.
    critical_miss = [dict(row) for row in passing]
    critical_miss[0]["exact_match"] = False
    assert module._founder_c20_summary(critical_miss, **kwargs)[
        "verdict"
    ] == "ADMISSION_FAIL"


def test_founder_suites_are_opt_in_and_never_in_defaults() -> None:
    module = _tool_module()
    assert not set(module.FOUNDER_SUITES) & set(module.ALL_SUITES)
    assert set(module.FOUNDER_SUITES) == {
        "founder_c0_v2",
        "founder_c20_v1",
    }
    default_suites = module._parser().parse_args([]).suites
    assert not any(
        founder in default_suites for founder in module.FOUNDER_SUITES
    )


def test_generation_request_identity_uses_frozen_treatment() -> None:
    module = _tool_module()
    profile = module.ModelProfile(
        profile_id="t",
        profile_version="1.0.0",
        model_identifier="m",
        model_revision=None,
        model_digest=None,
        tokenizer_identifier="t",
        tokenizer_revision=None,
        tokenizer_digest=None,
        model_class="C",
        generation_policy_id="g",
        device="cuda",
        dtype="bfloat16",
        adapter_ref=None,
        trust_remote_code=False,
        add_special_tokens=True,
    )
    policy = module.GenerationPolicy(
        policy_id="F0EvalRET",
        version="1.0.0",
        max_new_tokens=64,
        do_sample=False,
        temperature=None,
        top_p=None,
        top_k=1,
        repetition_penalty=1.0,
        seed_id="F0EvalSeed",
        stop_policy_id=None,
    )
    rendered = b"Return exactly the token cedar."
    request = module._generation_request(
        profile,
        policy=policy,
        rendered=rendered,
        identity_namespace="RET",
        index=3,
    )
    assert request.rendered_input == rendered
    assert request.rendered_input_hash == hashlib.sha256(rendered).hexdigest()
    assert request.interface_treatment_id == module.I0_STRICT_FREE_GENERATION.treatment_id
    assert request.generation_policy.do_sample is False
    assert request.generation_seed == 0
