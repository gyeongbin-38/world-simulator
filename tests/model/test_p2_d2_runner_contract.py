from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "tools" / "world_p2_d2_kv_cache_causal_localization.py"
HARDENED = ROOT / "tools" / "world_p2_d2_hardened_entry.py"
LAUNCHER = ROOT / "tools" / "run_p2_d2.sh"


def test_runner_is_bound_to_preregistered_d2_and_canonical_d1():
    text = RUNNER.read_text(encoding="utf-8")
    assert 'PREREG_COMMIT = "9bce60555f1dbb9c2bd9ec4d9fae279ab0f61761"' in text
    assert 'SOURCE_D1_RESULT_DIGEST = "865616cdb65e5f4c969a9302c02bb285167db06a905e1497b05e4e0912935c20"' in text
    assert 'SOURCE_D1_DETAILS_SHA256 = "0e5e62709d58168c9922645c1d05d54a7f5c417b68b3f461b4558d3706ca3b17"' in text
    assert 'SOURCE_D1_ARCHIVE_SHA256 = "c42999e001c789a4a43fa14962119315066b2df6c66e3b472ce76a6f27cad2f1"' in text
    assert '"C10_NOT_BEHAVIORALLY_ADMITTED"' in text


def test_runner_freezes_screening_blocks_and_bidirectional_patch_design():
    text = RUNNER.read_text(encoding="utf-8")
    for block in (
        '"Q0": (0, 1, 2, 3)',
        '"Q1": (4, 5, 6, 7)',
        '"Q2": (8, 9, 10, 11)',
        '"Q3": (12, 13, 14, 15)',
    ):
        assert block in text
    assert "transplant_cache_layers(pair.fa_cache, pair.base_cache" not in text or "_patch_score" in text
    assert "select_top_blocks" in text
    assert "select_top_layers" in text
    assert "repeat_union=True" in text


def test_hardened_entry_checks_prereg_bytes_and_ancestry():
    text = HARDENED.read_text(encoding="utf-8")
    assert 'git", "show"' in text
    assert 'git", "merge-base", "--is-ancestor"' in text
    assert "WORLD_P2_D2_KV_CACHE_CAUSAL_LOCALIZATION_V1.md" in text
    assert "WORLD_P2_D2_KV_CACHE_CAUSAL_LOCALIZATION_CONFIG_V1.json" in text


def test_launcher_defaults_to_validate_and_preserves_successful_artifacts():
    text = LAUNCHER.read_text(encoding="utf-8")
    assert 'MODE="${1:-validate}"' in text
    assert "--validate-only" in text
    assert "--execute" in text
    assert 'test ! -e "$OUT"' in text
    assert 'preservation_manifest.sha256' in text
    assert "P2_D2_CANONICAL_ARCHIVE_VERIFIED" in text
