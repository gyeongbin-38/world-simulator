#!/usr/bin/env python3
"""Fail-closed preregistration wrapper for WORLD P2-D2."""

from __future__ import annotations

import subprocess

import world_p2_d2_kv_cache_causal_localization as base


_PROTOCOL_REL = "docs/research/world/WORLD_P2_D2_KV_CACHE_CAUSAL_LOCALIZATION_V1.md"
_CONFIG_REL = "docs/research/world/WORLD_P2_D2_KV_CACHE_CAUSAL_LOCALIZATION_CONFIG_V1.json"


def _git_bytes_at_prereg(relative_path: str) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "show", f"{base.PREREG_COMMIT}:{relative_path}"],
            cwd=base.REPOSITORY_ROOT,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise base.SmokePreflightError("P2-D2 cannot resolve preregistered scientific bytes") from error
    return completed.stdout


def _require_prereg_freeze() -> None:
    try:
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", base.PREREG_COMMIT, "HEAD"],
            cwd=base.REPOSITORY_ROOT,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise base.SmokePreflightError("P2-D2 HEAD is not descended from preregistration") from error

    for relative_path in (_PROTOCOL_REL, _CONFIG_REL):
        current = (base.REPOSITORY_ROOT / relative_path).read_bytes()
        frozen = _git_bytes_at_prereg(relative_path)
        if current != frozen:
            raise base.SmokePreflightError(f"P2-D2 preregistered scientific file drift: {relative_path}")


def main() -> int:
    _require_prereg_freeze()
    return int(base.main())


if __name__ == "__main__":
    raise SystemExit(main())
