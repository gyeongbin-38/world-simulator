#!/usr/bin/env python3
"""Check canonical Markdown architecture integrity."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from alifelm.docs_lint import lint_repository  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true", help="emit a machine-readable report")
    args = parser.parse_args()
    report = lint_repository(args.repo_root)
    if args.json:
        print(json.dumps({
            "ok": report.ok,
            "issues": [
                {
                    "code": issue.code,
                    "path": issue.path,
                    "line": issue.line,
                    "message": issue.message,
                }
                for issue in report.issues
            ],
        }, ensure_ascii=False, indent=2))
    else:
        if report.ok:
            print("docs lint: OK")
        else:
            for issue in report.issues:
                location = f"{issue.path}:{issue.line}" if issue.line else issue.path
                print(f"{issue.code} {location} {issue.message}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
