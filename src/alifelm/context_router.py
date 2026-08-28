"""Deterministic architecture context routing.

The router reads only ``architecture/INDEX.md`` to choose documents.  It
returns paths and metadata; callers may load the selected owner documents
afterward.  It never scans or concatenates all Markdown as implicit context.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

_ACTIVE_ROW = re.compile(
    r"^\|\s*([^|]+?)\s*\|\s*`([^`]+)`\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$"
)
_SUPPORTING_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*([^|]+?)\s*\|\s*$")
_TOKEN = re.compile(r"[a-z0-9]+")
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_ARCH_ID = re.compile(r"\b(?:A00|ARC-\d+|LC-\d+|SEQ-\d+|DF-\d+)\b", re.I)
_QUERY_ALIASES = {
    "newborn": "birth",
    "newborns": "birth",
    "offspring": "birth",
    "child": "birth",
    "children": "birth",
    "acceptance": "accept",
    "accepted": "accept",
    "timing": "tick",
    "compile": "compilation",
    "compiler": "compilation",
}
_ROUTING_STOPWORDS = {"context"}


class RoutingError(ValueError):
    """Raised when a route cannot be resolved from the canonical index."""


@dataclass(frozen=True, slots=True)
class RoutedDocument:
    key: str
    path: Path
    source: str
    owner_id: str | None
    owns: str
    index_order: int


def _parse_index(index_path: Path) -> tuple[RoutedDocument, ...]:
    lines = index_path.read_text(encoding="utf-8").splitlines()
    documents: list[RoutedDocument] = []
    section: str | None = None
    for line in lines:
        if line.startswith("## Active owner documents"):
            section = "active"
            continue
        if line.startswith("## Supporting domain documents"):
            section = "supporting"
            continue
        if line.startswith("## "):
            section = None
            continue
        if section == "active":
            match = _ACTIVE_ROW.match(line)
            if not match or match.group(1).strip() == "ID":
                continue
            owner_id, raw_path, status, owns = (part.strip() for part in match.groups())
            documents.append(
                RoutedDocument(
                    key=owner_id,
                    path=(index_path.parent / raw_path).resolve(),
                    source="active-owner",
                    owner_id=owner_id,
                    owns=owns,
                    index_order=len(documents),
                )
            )
        elif section == "supporting":
            match = _SUPPORTING_ROW.match(line)
            if not match or match.group(1).strip() == "Document":
                continue
            raw_path, owns = (part.strip() for part in match.groups())
            path = (index_path.parent / raw_path).resolve()
            repository_root = index_path.parent.parent.resolve()
            try:
                stable_path = path.relative_to(repository_root).as_posix()
            except ValueError:
                stable_path = Path(raw_path).as_posix()
            documents.append(
                RoutedDocument(
                    key=f"SUPPORTING:{stable_path}",
                    path=path,
                    source="supporting-domain",
                    owner_id=None,
                    owns=owns,
                    index_order=len(documents),
                )
            )
    if not documents:
        raise RoutingError(f"no routable documents found in {index_path}")
    return tuple(documents)


def _tokens(value: str) -> set[str]:
    expanded = _CAMEL_BOUNDARY.sub(" ", value)
    return {
        _QUERY_ALIASES.get(token, token)
        for token in _TOKEN.findall(expanded.lower())
        if token not in _ROUTING_STOPWORDS
    }


@dataclass(frozen=True, slots=True)
class ContextRoute:
    query: str
    documents: tuple[RoutedDocument, ...]

    @property
    def paths(self) -> tuple[Path, ...]:
        return tuple(document.path for document in self.documents)


class ContextRouter:
    """Resolve the smallest deterministic document set for a task."""

    def __init__(self, repository_root: Path) -> None:
        self.repository_root = repository_root.resolve()
        self.index_path = self.repository_root / "architecture" / "INDEX.md"
        self._documents = _parse_index(self.index_path)

    @property
    def documents(self) -> tuple[RoutedDocument, ...]:
        return self._documents

    def route(
        self,
        query: str,
        *,
        owner_ids: Iterable[str] = (),
        include_foundation: bool = False,
    ) -> ContextRoute:
        explicit_ids = {owner_id.upper() for owner_id in owner_ids}
        explicit_ids.update(match.upper() for match in _ARCH_ID.findall(query))
        query_tokens = _tokens(query)
        selected: set[Path] = set()

        if explicit_ids:
            for document in self._documents:
                if document.owner_id and document.owner_id.upper() in explicit_ids:
                    selected.add(document.path)
        else:
            scored = tuple(
                (
                    document,
                    len(
                        query_tokens
                        & _tokens(f"{document.key} {document.path.name} {document.owns}")
                    ),
                )
                for document in self._documents
            )
            highest_score = max((score for _, score in scored), default=0)
            selected.update(
                document.path
                for document, score in scored
                if score == highest_score and score > 0
            )

        if include_foundation:
            constitution = next(
                (doc for doc in self._documents if doc.owner_id == "A00"), None
            )
            if constitution is None:
                raise RoutingError("A00/CONSTITUTION.md is not registered in INDEX.md")
            selected.add(constitution.path)

        if not selected:
            available = ", ".join(
                doc.owner_id or doc.key for doc in self._documents
            )
            raise RoutingError(
                f"query did not match a canonical owner document; available: {available}"
            )

        ordered = tuple(
            document for document in self._documents if document.path in selected
        )
        return ContextRoute(query=query, documents=ordered)
