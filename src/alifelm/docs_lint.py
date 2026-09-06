"""Architecture/documentation integrity checks for the canonical repository."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from .context_router import _parse_index

_LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)")
_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")
_ARCH_ID = re.compile(r"\b(?:A00|ARC-\d+|LC-\d+|SEQ-\d+|DF-\d+)\b", re.I)
_BOOTSTRAP_OWNER = re.compile(
    r"\b(?:owner|owns|canonical owner|source of truth)\b\s*[:=]?\s*"
    r"\b(?:A00|ARC-\d+|LC-\d+|SEQ-\d+|DF-\d+)\b",
    re.I,
)
_ARCHIVE_PARTS = {"archive", "archives", "history", "historical", "superseded"}


@dataclass(frozen=True, slots=True)
class LintIssue:
    code: str
    path: str
    line: int | None
    message: str


@dataclass(frozen=True, slots=True)
class LintReport:
    issues: tuple[LintIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues


def _markdown_files(root: Path) -> tuple[Path, ...]:
    ignored = {
        ".git", ".venv", "__pycache__", ".pytest_cache", "node_modules",
        ".observatory-cache", "dist", "build", "test-results", "playwright-report",
    }
    files: list[Path] = []
    for directory, subdirectories, names in root.walk():
        # Prune generated/dependency trees before traversal. Their README links
        # are not repository documentation and their evidence may be sealed.
        subdirectories[:] = [name for name in subdirectories if name not in ignored]
        files.extend(directory / name for name in names if name.lower().endswith(".md"))
    return tuple(sorted(files))


def _content_lines(lines: list[str]):
    in_fence = False
    for line_number, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if not in_fence:
            yield line_number, line


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def lint_repository(repository_root: Path) -> LintReport:
    root = repository_root.resolve()
    issues: list[LintIssue] = []
    index_path = root / "architecture" / "INDEX.md"

    if not index_path.is_file():
        return LintReport((LintIssue("INDEX_MISSING", "architecture/INDEX.md", None, "canonical architecture index is missing"),))

    try:
        documents = _parse_index(index_path)
    except (OSError, ValueError) as exc:
        return LintReport((LintIssue("INDEX_UNREADABLE", "architecture/INDEX.md", None, str(exc)),))

    ids = [doc.owner_id for doc in documents if doc.owner_id is not None]
    for owner_id in sorted({value for value in ids if ids.count(value) > 1}):
        issues.append(LintIssue("DUPLICATE_OWNER_ID", "architecture/INDEX.md", None, f"owner ID is registered more than once: {owner_id}"))

    seen_paths: set[Path] = set()
    active_paths: set[Path] = set()
    for document in documents:
        try:
            _relative(root, document.path)
        except ValueError:
            issues.append(LintIssue("OWNER_PATH_OUTSIDE_REPOSITORY", _relative(root, index_path), None, f"registered document escapes repository root: {document.path}"))
            continue
        if document.path in seen_paths:
            issues.append(LintIssue("DUPLICATE_OWNER_PATH", _relative(root, index_path), None, f"document is routed more than once: {_relative(root, document.path)}"))
        seen_paths.add(document.path)
        if any(part.lower() in _ARCHIVE_PARTS for part in document.path.parts):
            issues.append(LintIssue("ARCHIVE_DOCUMENT_ROUTED", _relative(root, index_path), None, f"archive/history document is registered for routing: {_relative(root, document.path)}"))
        if not document.path.is_file():
            issues.append(LintIssue("OWNER_DOCUMENT_MISSING", _relative(root, index_path), None, f"registered document does not exist: {_relative(root, document.path)}"))
        if document.source == "active-owner":
            active_paths.add(document.path)
            if document.path.is_file():
                first_heading = next((line for line in document.path.read_text(encoding="utf-8").splitlines() if line.startswith("# ")), "")
                heading_id = _ARCH_ID.search(first_heading)
                if not heading_id or heading_id.group(0).upper() != document.owner_id:
                    issues.append(LintIssue("OWNER_HEADING_MISMATCH", _relative(root, document.path), None, f"first heading must identify {document.owner_id}"))

    for view in sorted((root / "architecture" / "views").glob("*.md")):
        if view.resolve() not in active_paths:
            issues.append(LintIssue("ORPHAN_ARCHITECTURE_VIEW", _relative(root, view), None, "architecture view is not registered in INDEX.md"))

    architecture_ids: dict[str, str] = {}
    for markdown in _markdown_files(root):
        relative = _relative(root, markdown)
        lines = markdown.read_text(encoding="utf-8").splitlines()
        for line_number, line in _content_lines(lines):
            if markdown.name.upper() in {"AGENTS.MD", "DESIGN.MD"} and _BOOTSTRAP_OWNER.search(line):
                issues.append(LintIssue("COMPETING_BOOTSTRAP_OWNER", relative, line_number, "AGENTS.md/DESIGN.md must not declare an architecture owner or source of truth"))
            heading = _HEADING.match(line)
            if heading:
                match = _ARCH_ID.search(heading.group(1))
                if match:
                    identifier = match.group(0).upper()
                    previous = architecture_ids.get(identifier)
                    if previous is not None:
                        issues.append(LintIssue("DUPLICATE_ARCHITECTURE_ID", relative, line_number, f"{identifier} already appears in {previous}"))
                    else:
                        architecture_ids[identifier] = relative

            for target in _LINK.findall(line):
                target = target.strip().strip("<>")
                parsed = urlsplit(target)
                if parsed.scheme or target.startswith("//") or target.startswith("#"):
                    continue
                target_path = (markdown.parent / unquote(parsed.path)).resolve()
                if not target_path.is_file():
                    issues.append(LintIssue("BROKEN_MARKDOWN_LINK", relative, line_number, f"linked path does not exist: {parsed.path}"))

    return LintReport(tuple(issues))
