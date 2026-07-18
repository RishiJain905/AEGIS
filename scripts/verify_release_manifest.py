#!/usr/bin/env python3
"""Validate an already-generated AEGIS release manifest.

Verification is two layered checks that both fail closed:

1. ``validate_manifest`` — internal self-consistency: required shape and every
   recorded checksum re-hashed against the file on disk.
2. ``verify_manifest_correspondence`` — the manifest still describes the current
   release state: ``source.revision`` matches ``git HEAD``, ``migration.head``
   matches ``alembic heads``, each image digest is present locally via
   ``docker inspect``, and the required artifact set is fully covered.

The correspondence providers can be skipped or overridden for detached/offline
builds via the ``--skip-*`` / ``--expected-*`` flags; skipping is explicit and
logged so a stale manifest never passes silently.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

try:
    from scripts.generate_release_manifest import (
        _docker_inspect,
        _git_revision,
        validate_manifest,
        verify_manifest_correspondence,
    )
except ModuleNotFoundError:  # direct `python scripts/verify_release_manifest.py`
    from generate_release_manifest import (  # type: ignore[no-redef]
        _docker_inspect,
        _git_revision,
        validate_manifest,
        verify_manifest_correspondence,
    )


def _alembic_head(repo_root: Path) -> str:
    completed = subprocess.run(
        ["uv", "run", "alembic", "heads"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "alembic heads failed"
        raise RuntimeError(f"could not resolve alembic head: {detail}")
    match = re.search(r"^([A-Za-z0-9_]+)\s+\(head\)", completed.stdout, re.MULTILINE)
    if not match:
        raise RuntimeError("alembic heads produced no head revision")
    return match.group(1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--expected-revision", default=None)
    parser.add_argument("--skip-revision-check", action="store_true")
    parser.add_argument("--expected-migration-head", default=None)
    parser.add_argument("--skip-migration-check", action="store_true")
    parser.add_argument("--skip-image-check", action="store_true")
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    path = args.manifest if args.manifest.is_absolute() else repo_root / args.manifest
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("manifest JSON must be an object")
        manifest: Mapping[str, object] = payload
        validate_manifest(manifest, repo_root=repo_root)

        if args.skip_revision_check:
            expected_revision: str | None = None
        elif args.expected_revision:
            expected_revision = args.expected_revision
        else:
            expected_revision = _git_revision(repo_root)

        if args.skip_migration_check:
            expected_migration_head: str | None = None
        elif args.expected_migration_head:
            expected_migration_head = args.expected_migration_head
        else:
            expected_migration_head = _alembic_head(repo_root)

        image_inspector = None if args.skip_image_check else _docker_inspect

        verify_manifest_correspondence(
            manifest,
            repo_root=repo_root,
            expected_revision=expected_revision,
            expected_migration_head=expected_migration_head,
            image_inspector=image_inspector,
        )
    except (OSError, RuntimeError, json.JSONDecodeError, ValueError) as exc:
        print(f"RELEASE MANIFEST: FAIL - {exc}")
        return 1
    print(f"Release manifest: {path.relative_to(repo_root).as_posix()}")
    print("RELEASE MANIFEST: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
