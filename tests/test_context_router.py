from pathlib import Path

import pytest

from alifelm.context_router import ContextRouter, RoutingError


def test_explicit_owner_routing_is_deduplicated_and_index_ordered(repository_root: Path) -> None:
    router = ContextRouter(repository_root)
    route = router.route(
        "lifecycle and reproduction",
        owner_ids=("LC-220", "LC-220", "LC-210"),
        include_foundation=True,
    )

    assert [doc.owner_id for doc in route.documents] == ["A00", "LC-210", "LC-220"]
    assert len(route.paths) == len(set(route.paths))


def test_supporting_document_is_routable_from_index(repository_root: Path) -> None:
    route = ContextRouter(repository_root).route("documentation context loading")
    assert len(route.documents) == 1
    assert route.documents[0].key == "SUPPORTING:docs/DOCS_POLICY.md"
    assert route.documents[0].path == (repository_root / "docs" / "DOCS_POLICY.md").resolve()


def test_self_send_decision_is_routable_from_index(repository_root: Path) -> None:
    route = ContextRouter(repository_root).route("self send addressing")
    assert len(route.documents) == 1
    assert route.documents[0].path == (
        repository_root / "architecture" / "decisions" / "ADR-300-001-self-send-addressing.md"
    ).resolve()


def test_unknown_query_does_not_fall_back_to_loading_everything(repository_root: Path) -> None:
    with pytest.raises(RoutingError):
        ContextRouter(repository_root).route("unrelated phrase with no owner match")


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("agent context fabric", ["ARC-300"]),
        ("ContextCompiler compilation", ["DF-310"]),
        ("exact context recall", ["SEQ-320"]),
        ("neural heredity genome", ["ARC-350"]),
    ],
)
def test_context_fabric_owner_routes_are_minimal(
    repository_root: Path, query: str, expected: list[str]
) -> None:
    route = ContextRouter(repository_root).route(query)
    assert [document.owner_id for document in route.documents] == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("reproduction acceptance bug", ["LC-220"]),
        ("newborn timing bug", ["LC-210", "SEQ-230"]),
        ("same-tick message visibility bug", ["ARC-010", "SEQ-230"]),
        ("EventEnvelope schema bug", ["ARC-240"]),
        ("sprite rendering task", [None]),
    ],
)
def test_audit_fixture_routes_are_minimal(
    repository_root: Path, query: str, expected: list[str | None]
) -> None:
    route = ContextRouter(repository_root).route(query)
    assert [document.owner_id for document in route.documents] == expected
