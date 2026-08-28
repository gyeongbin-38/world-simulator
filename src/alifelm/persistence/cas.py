"""Filesystem content-addressed storage for required I-03 evidence bytes."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import tempfile
from typing import Iterable

from alifelm.domain import ArtifactId, ArtifactRef

from .contracts import (
    ArtifactIntegrityError,
    ArtifactMissingError,
    FaultInjector,
)


_DIGEST = re.compile(r"^[a-f0-9]{64}$")


class FileSystemArtifactStore:
    """Small CAS with immutable digest-named files and orphan inspection."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        self.staging_root = self.root / ".staging"
        self.staging_root.mkdir(parents=True, exist_ok=True)

    def put_bytes(
        self,
        data: bytes,
        *,
        media_type: str = "application/octet-stream",
        contract_id: str = "raw-bytes",
        fault_injector: FaultInjector | None = None,
    ) -> ArtifactRef:
        if not isinstance(data, bytes):
            raise TypeError("CAS data must be bytes")
        if not isinstance(media_type, str) or not media_type:
            raise ValueError("media_type must be non-empty")
        if not isinstance(contract_id, str) or not contract_id:
            raise ValueError("contract_id must be non-empty")
        if fault_injector is not None:
            fault_injector.check("F11_ARTIFACT_WRITE")
        digest = hashlib.sha256(data).hexdigest()
        if fault_injector is not None:
            fault_injector.check("F11_HASH_VERIFICATION")
        target = self._path_for_digest(digest)
        target.parent.mkdir(parents=True, exist_ok=True)

        if target.exists():
            self._verify_path(target, digest)
            return _reference(digest)

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=self.staging_root, prefix="artifact-", delete=False
            ) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(data)
                temporary.flush()
                os.fsync(temporary.fileno())
            if fault_injector is not None:
                fault_injector.check("F11_BEFORE_FINALIZATION")
            self._verify_path(temporary_path, digest)
            if not target.exists():
                os.replace(temporary_path, target)
                temporary_path = None
            else:
                self._verify_path(target, digest)
            if fault_injector is not None:
                fault_injector.check("F11_AFTER_FINALIZATION")
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except FileNotFoundError:
                    pass
        return _reference(digest)

    def resolve(self, reference: ArtifactRef) -> bytes:
        if not isinstance(reference, ArtifactRef):
            raise TypeError("reference must be an ArtifactRef")
        if not _DIGEST.fullmatch(reference.digest):
            raise ArtifactIntegrityError("ArtifactRef digest must be a lowercase SHA-256 digest")
        path = self._path_for_digest(reference.digest)
        if not path.is_file():
            raise ArtifactMissingError(f"artifact bytes are missing: {reference.digest}")
        data = path.read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if actual != reference.digest:
            raise ArtifactIntegrityError(
                f"artifact digest mismatch: expected {reference.digest}, got {actual}"
            )
        return data

    def is_durable(self, reference: ArtifactRef) -> bool:
        try:
            self.resolve(reference)
        except (ArtifactMissingError, ArtifactIntegrityError):
            return False
        return True

    def list_orphans(self, referenced: Iterable[ArtifactRef] = ()) -> tuple[ArtifactRef, ...]:
        referenced_digests = {reference.digest for reference in referenced}
        found: list[ArtifactRef] = []
        for path in self.root.glob("[0-9a-f][0-9a-f]/*"):
            if not path.is_file() or not _DIGEST.fullmatch(path.name):
                continue
            if path.name in referenced_digests:
                continue
            try:
                self._verify_path(path, path.name)
            except ArtifactIntegrityError:
                continue
            found.append(_reference(path.name))
        return tuple(sorted(found, key=lambda reference: reference.digest))

    def _path_for_digest(self, digest: str) -> Path:
        return self.root / digest[:2] / digest

    @staticmethod
    def _verify_path(path: Path, expected_digest: str) -> None:
        if not path.is_file():
            raise ArtifactMissingError(f"artifact bytes are missing: {expected_digest}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected_digest:
            raise ArtifactIntegrityError(
                f"artifact digest mismatch: expected {expected_digest}, got {actual}"
            )


def _reference(digest: str) -> ArtifactRef:
    return ArtifactRef(ArtifactId(f"artifact-{digest}"), digest)
