#!/usr/bin/env python3
"""Validate an already-generated AEGIS release manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts.generate_release_manifest import validate_manifest
except ModuleNotFoundError:  # direct `python scripts/verify_release_manifest.py`
    from generate_release_manifest import validate_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    path = args.manifest if args.manifest.is_absolute() else repo_root / args.manifest
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("manifest JSON must be an object")
        validate_manifest(payload, repo_root=repo_root)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"RELEASE MANIFEST: FAIL - {exc}")
        return 1
    print(f"Release manifest: {path.relative_to(repo_root).as_posix()}")
    print("RELEASE MANIFEST: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
