"""Authenticated, disposable evidence access. No simulation store constructors."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sqlite3
import tarfile
import tempfile

RUN_ID = "WORLD_EXP000_LIVE_GROUNDING_PILOT_V1_R1"
ARCHIVE_NAME = "WORLD_EXP000_LIVE_GROUNDING_PILOT_V1_3B1580D_R1_CANONICAL.tar.gz"
ARCHIVE_SHA = "dc7f904957a90be998df603b78c993b5ebdb55ccdd4d0aa20949dca80a9df227"
MANIFEST_SHA = "aa70c88392f52a018af2ea87f096360e0bfd362cb795668e0216215e57490320"
GROUNDING_SHA = "1cb4f18c2a4239f73d00c8065353a7f835b5d32abc446e29b70b24d3ecb4e281"
BASE_DIGEST = "9b8d4f63a3ae3311e6a3893928f3a971b3cfb6af20c80413f66cfbe0953af4d7"
GROUNDING_DIGEST = "e8dca7b47bb4239ec3210a6f0fbbb7a9bfe376a440634f3307e05fa9b95966b5"
DIGEST = re.compile(r"[0-9a-f]{64}\Z")


class EvidenceError(ValueError):
    """Required sealed evidence is absent or invalid; never repair it."""


class IntegrityConflict(EvidenceError):
    """Recorded sources disagree; no normal world projection is allowed."""


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise IntegrityConflict(message)


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"Missing or corrupt evidence: {path.name}") from exc


def verify_file(path: Path, expected: str) -> None:
    if not path.is_file() or path.is_symlink():
        raise EvidenceError(f"Missing sealed file: {path.name}")
    require(sha256(path) == expected, f"SHA-256 mismatch: {path.name}")


def safe_extract(archive: Path, destination: Path) -> None:
    """Preflight the complete archive before writing into a new empty directory."""
    destination = destination.resolve()
    if not destination.is_dir() or any(destination.iterdir()):
        raise EvidenceError("Extraction destination must be a new empty directory")
    try:
        with tarfile.open(archive, "r:gz") as bundle:
            members = bundle.getmembers()
            if len(members) > 10000 or sum(m.size for m in members) > 256 * 1024 * 1024:
                raise EvidenceError("Archive exceeds sealed evidence size limit")
            seen: set[str] = set()
            for member in members:
                name = member.name
                parts = PurePosixPath(name).parts
                key = name.rstrip("/").casefold()
                if (not parts or name.startswith(("/", "\\")) or "\\" in name
                        or any(p in ("..", ".") or ":" in p or p.endswith((".", " "))
                               or p.split(".")[0].upper() in
                               {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)),
                                *(f"LPT{i}" for i in range(10))} for p in parts)
                        or key in seen or not (member.isdir() or member.isfile())
                        or member.issym() or member.islnk()):
                    raise EvidenceError("Unsafe archive member")
                seen.add(key)
                if not (destination / name).resolve().is_relative_to(destination):
                    raise EvidenceError("Archive path escapes cache")
            for member in members:
                target = destination.joinpath(*PurePosixPath(member.name).parts)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    source = bundle.extractfile(member)
                    if source is None:
                        raise EvidenceError("Unreadable archive member")
                    with source, target.open("xb") as out:
                        while chunk := source.read(1024 * 1024):
                            out.write(chunk)
    except (tarfile.TarError, OSError) as exc:
        raise EvidenceError("Cannot read sealed archive") from exc


@contextmanager
def observation_connection(path: Path):
    """Real read-only SQLite; immutable is valid only for the sealed archive copy."""
    if not path.is_file() or path.is_symlink():
        raise EvidenceError("Missing observation database")
    if any(sidecar.exists() and sidecar.stat().st_size > 0
           for sidecar in (Path(str(path) + "-wal"), Path(str(path) + "-journal"))):
        raise EvidenceError("Only checkpointed sealed SQLite is supported")
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        yield connection
    finally:
        connection.close()


@dataclass(frozen=True)
class EvidenceBundle:
    root: Path
    archive: Path
    cache: Path

    def verify_cache(self) -> int:
        """Bind every disposable extracted byte back to the authenticated archive."""
        verify_file(self.archive, ARCHIVE_SHA)
        count = 0
        try:
            with tarfile.open(self.archive, "r:gz") as bundle:
                for member in bundle:
                    if not member.isfile():
                        continue
                    path = self.cache.joinpath(*PurePosixPath(member.name).parts)
                    require(path.resolve().is_relative_to(self.cache.resolve()), "Cache path escapes extraction")
                    stream = bundle.extractfile(member)
                    if stream is None:
                        raise EvidenceError("Unreadable sealed member")
                    with stream:
                        digest = hashlib.file_digest(stream, "sha256").hexdigest()
                    verify_file(path, digest)
                    count += 1
        except (tarfile.TarError, OSError) as exc:
            raise EvidenceError("Cannot verify extracted cache") from exc
        return count

    @classmethod
    def open(cls, data_root: Path, cache_root: Path) -> EvidenceBundle:
        archives = discover(data_root)
        if len(archives) != 1:
            raise EvidenceError("Expected exactly one preserved EXP-000 archive")
        archive = archives[0]
        verify_file(archive, ARCHIVE_SHA)
        for name, digest in (("manifest.json", MANIFEST_SHA), ("grounding_manifest.json", GROUNDING_SHA)):
            verify_file(archive.parent / name, digest)
        cache_root = cache_root.resolve()
        if cache_root == data_root.resolve() or cache_root.is_relative_to(data_root.resolve()):
            raise EvidenceError("Cache must be outside the preserved evidence directory")
        cache_root.mkdir(parents=True, exist_ok=True)
        cache = Path(tempfile.mkdtemp(prefix="sealed-", dir=cache_root))
        safe_extract(archive, cache)
        roots = list(cache.glob("*/evidence/manifest.json"))
        if len(roots) != 1:
            raise EvidenceError("Missing unique evidence root inside archive")
        root = roots[0].parent
        verify_file(root / "manifest.json", MANIFEST_SHA)
        verify_file(root / "grounding_manifest.json", GROUNDING_SHA)
        return cls(root=root, archive=archive, cache=cache)

    def artifact(self, digest: str) -> bytes:
        if not DIGEST.fullmatch(digest):
            raise EvidenceError("Invalid evidence digest")
        path = self.root / "cas" / digest[:2] / digest
        verify_file(path, digest)
        return path.read_bytes()


def discover(data_root: Path) -> list[Path]:
    if not data_root.is_dir():
        return []
    return sorted(set(data_root.glob(ARCHIVE_NAME)) | set(data_root.glob("*/" + ARCHIVE_NAME)))
