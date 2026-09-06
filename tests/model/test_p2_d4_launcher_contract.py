from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "tools" / "run_p2_d4_r1.sh"


def test_d4_launcher_defaults_to_validate_and_binds_recovery_sources():
    text = LAUNCHER.read_text(encoding="utf-8")
    assert 'MODE="${1:-validate}"' in text
    assert "--validate-only" in text
    assert "--execute" in text

    for expected in (
        "WORLD_P2_D1_DECISION_BOUNDARY_LOCALIZATION_V1_R2",
        "WORLD_P2_D1_EXACT_SCIENTIFIC_REPRO_20260906.tar.gz",
        "WORLD_P2_D2_KV_CACHE_CAUSAL_LOCALIZATION_V1_RECOVERY_R1",
        "WORLD_P2_D2_EXACT_SCIENTIFIC_REPRO_20260906.tar.gz",
        "WORLD_P2_D3_TARGETED_ADAPTER_SCALING_V1_RECOVERY_R3",
        "WORLD_P2_D3_COMPLETE_R3_20260906.tar.gz",
        "WORLD_P2_D4_KV_COMPONENT_DECOMPOSITION_CONFIG_V1.json",
    ):
        assert expected in text


def test_d4_launcher_is_immutable_and_preserves_successful_artifacts():
    text = LAUNCHER.read_text(encoding="utf-8")
    assert 'test -z "$(git status --porcelain --untracked-files=all)"' in text
    assert 'test ! -e "$OUT"' in text
    assert 'test ! -e "$STDOUT"' in text
    assert 'test ! -e "$ARCHIVE"' in text
    assert "preservation_manifest.sha256" in text
    assert "gzip -t" in text
    assert "tar -tzf" in text
    assert "P2_D4_R1_CANONICAL_ARCHIVE_VERIFIED" in text
