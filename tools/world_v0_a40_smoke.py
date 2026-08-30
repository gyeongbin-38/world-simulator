"""Prepare/execute the first WORLD v0 A40 headless deployment smoke.

The default is intentionally no mode: callers must select ``--validate-only``
or ``--execute``.  Validate-only performs no PyTorch/CUDA import and no model
load.  Execute repeats static checks before loading the accepted runtime.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from alifelm.model.world_v0_smoke import (  # noqa: E402
    DeploymentPaths,
    SmokePreflightError,
    build_smoke_manifest,
    ensure_execute_environment,
    manifest_with_result,
    verify_static_deployment,
    write_immutable_manifest,
    run_headless_smoke,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--validate-only", action="store_true")
    modes.add_argument("--execute", action="store_true")
    parser.add_argument("--base-model-dir", required=True, type=Path)
    parser.add_argument("--adapter-path", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--base-checkpoint-file", type=Path, default=None)
    parser.add_argument("--expected-git-commit", default=None)
    return parser


def _current_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        paths = DeploymentPaths(
            base_model_dir=args.base_model_dir,
            adapter_path=args.adapter_path,
            output_root=args.output_root,
            base_checkpoint_file=args.base_checkpoint_file,
        )
        expected_commit = args.expected_git_commit or _current_commit()
        static = verify_static_deployment(
            paths,
            expected_git_commit=expected_commit,
            repository_root=REPOSITORY_ROOT,
        )
        if args.validate_only:
            print(json.dumps(static, sort_keys=True, separators=(",", ":")))
            return 0

        if static.get("existing_manifest_status") == "ALREADY_COMPLETE":
            print(json.dumps({**static, "status": "ALREADY_COMPLETE"}, sort_keys=True, separators=(",", ":")))
            return 0
        environment = ensure_execute_environment()
        result = run_headless_smoke(
            paths=paths,
            git_commit=expected_commit,
            environment=environment,
        )
        planned = verify_static_deployment(
            paths,
            expected_git_commit=expected_commit,
            repository_root=REPOSITORY_ROOT,
        )
        # The second preflight is intentionally before finalization so static
        # identities are checked again after runtime execution.
        manifest_path = paths.output_root / "manifest.json"
        planned_manifest = build_smoke_manifest(
            paths=paths,
            git_commit=expected_commit,
            tokenizer_hashes=static["tokenizer_file_hashes"],
            config_hashes=static["config_file_hashes"],
            adapter_config_sha256=static["adapter_config_sha256"],
        )
        final = manifest_with_result(planned_manifest, result)
        write_status = write_immutable_manifest(paths.output_root, final)
        print(
            json.dumps(
                {"status": write_status, "manifest": str(manifest_path), "manifest_digest": final["manifest_digest"], "preflight": planned},
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    except (SmokePreflightError, ValueError, OSError, subprocess.CalledProcessError) as error:
        print(json.dumps({"status": "BLOCKED", "error": str(error)}, sort_keys=True, separators=(",", ":")), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
