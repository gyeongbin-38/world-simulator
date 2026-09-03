#!/usr/bin/env python3
"""Efficiency-preserving entrypoint for the frozen P2-D1 runner.

The scientific runner verifies three unpacked P2 source files against the known
canonical P2 archive. Re-opening a 5+ GiB gzip tar for each member would repeat
full decompression. This wrapper memoizes those member bytes after one archive
scan. The runner still re-hashes the compressed archive before and after D1, so
mid-run source mutation remains detectable. No model input, score, threshold,
or diagnostic interpretation is changed.
"""

from __future__ import annotations

from pathlib import Path
import tarfile

import world_p2_d1_decision_boundary_localization as base


_TARGET_SUFFIXES = (
    f"alifelm/evidence/{base.SOURCE_P2_ROOT_NAME}/summary.json",
    f"alifelm/evidence/{base.SOURCE_P2_ROOT_NAME}/details.json",
    base.SOURCE_P2_STDOUT_NAME,
)
_CACHE: dict[Path, dict[str, bytes]] = {}


def _scan_archive_once(archive: Path) -> dict[str, bytes]:
    archive = archive.resolve()
    cached = _CACHE.get(archive)
    if cached is not None:
        return cached
    found: dict[str, bytes] = {}
    with tarfile.open(archive, "r:gz") as handle:
        for member in handle:
            if not member.isfile():
                continue
            name = member.name.lstrip("./")
            matches = [suffix for suffix in _TARGET_SUFFIXES if name.endswith(suffix)]
            if not matches:
                continue
            if len(matches) != 1 or matches[0] in found:
                raise base.SmokePreflightError("P2-D1 canonical archive member is ambiguous")
            stream = handle.extractfile(member)
            if stream is None:
                raise base.SmokePreflightError("P2-D1 canonical archive member is unreadable")
            found[matches[0]] = stream.read()
    if set(found) != set(_TARGET_SUFFIXES):
        raise base.SmokePreflightError("P2-D1 canonical archive is missing required source members")
    _CACHE[archive] = found
    return found


def _cached_archive_member_bytes(archive: Path, suffix: str) -> bytes:
    if suffix not in _TARGET_SUFFIXES:
        raise base.SmokePreflightError("P2-D1 requested an unapproved canonical archive member")
    return _scan_archive_once(archive)[suffix]


def main() -> int:
    base._archive_member_bytes = _cached_archive_member_bytes
    return int(base.main())


if __name__ == "__main__":
    raise SystemExit(main())
