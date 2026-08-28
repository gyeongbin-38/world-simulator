from pathlib import Path

from alifelm.docs_lint import lint_repository


def test_canonical_documentation_is_integrity_clean(repository_root: Path) -> None:
    report = lint_repository(repository_root)
    assert report.ok, report.issues


def test_lint_detects_broken_markdown_link(tmp_path: Path) -> None:
    architecture = tmp_path / "architecture"
    views = architecture / "views"
    views.mkdir(parents=True)
    (architecture / "INDEX.md").write_text(
        """# Index\n\n## Active owner documents\n\n| ID | Owner document | Status | Owns |\n|---|---|---|---|\n| ARC-999 | `views/ARC-999-test.md` | REVIEWED | test |\n""",
        encoding="utf-8",
    )
    (views / "ARC-999-test.md").write_text(
        "# ARC-999 - test\n\n[missing](nope.md)\n", encoding="utf-8"
    )

    report = lint_repository(tmp_path)
    assert not report.ok
    assert any(issue.code == "BROKEN_MARKDOWN_LINK" for issue in report.issues)


def test_lint_detects_archive_registration_and_bootstrap_owner(tmp_path: Path) -> None:
    architecture = tmp_path / "architecture"
    views = architecture / "views"
    archive = architecture / "archive"
    views.mkdir(parents=True)
    archive.mkdir()
    (architecture / "INDEX.md").write_text(
        """# Index\n\n## Active owner documents\n\n| ID | Owner document | Status | Owns |\n|---|---|---|---|\n| ARC-999 | `archive/ARC-999-old.md` | REVIEWED | test |\n""",
        encoding="utf-8",
    )
    (archive / "ARC-999-old.md").write_text("# ARC-999 - old\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("Owner: ARC-999\n", encoding="utf-8")

    report = lint_repository(tmp_path)
    codes = {issue.code for issue in report.issues}
    assert "ARCHIVE_DOCUMENT_ROUTED" in codes
    assert "COMPETING_BOOTSTRAP_OWNER" in codes
