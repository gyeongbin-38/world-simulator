#!/usr/bin/env python3
"""Print a deterministic canonical architecture context route."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from alifelm.context_router import ContextRouter, RoutingError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", default="", help="task text used for deterministic routing")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--owner", action="append", default=[], help="explicit owner ID; repeatable")
    parser.add_argument("--include-foundation", action="store_true")
    args = parser.parse_args()
    try:
        route = ContextRouter(args.repo_root).route(
            args.query,
            owner_ids=args.owner,
            include_foundation=args.include_foundation,
        )
    except RoutingError as exc:
        parser.error(str(exc))
    payload = {
        "query": route.query,
        "documents": [
            {
                "key": document.key,
                "owner_id": document.owner_id,
                "source": document.source,
                "path": document.path.relative_to(args.repo_root.resolve()).as_posix(),
                "index_order": document.index_order,
            }
            for document in route.documents
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
