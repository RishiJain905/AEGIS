#!/usr/bin/env python3
"""Verify cross-language contract compatibility and manifest integrity."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from aegis_contracts.fixtures import FIXTURE_MODEL_MAP
from aegis_contracts.parsing import parse_contract

ROOT = Path(__file__).resolve().parents[1]
FIXTURES_VALID = ROOT / "tests" / "contract" / "fixtures" / "valid"
SCHEMAS_DIR = ROOT / "tests" / "contract" / "fixtures" / "schemas"
MANIFEST_PATH = ROOT / "tests" / "contract" / "fixtures" / "compatibility-manifest.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def load_manifest() -> dict[str, object]:
    if not MANIFEST_PATH.exists():
        print(f"ERROR: Missing compatibility manifest at {MANIFEST_PATH}", file=sys.stderr)
        sys.exit(1)
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def verify_manifest_hashes(manifest: dict[str, object]) -> None:
    entries = manifest.get("artifacts")
    if not isinstance(entries, list):
        print("ERROR: compatibility manifest missing artifacts list", file=sys.stderr)
        sys.exit(1)

    for entry in entries:
        if not isinstance(entry, dict):
            print("ERROR: invalid manifest entry", file=sys.stderr)
            sys.exit(1)
        relative_path = entry.get("path")
        expected_hash = entry.get("sha256")
        schema_version = entry.get("schemaVersion")
        if not isinstance(relative_path, str) or not isinstance(expected_hash, str):
            print("ERROR: manifest entry missing path or sha256", file=sys.stderr)
            sys.exit(1)
        file_path = ROOT / relative_path
        if not file_path.exists():
            print(f"ERROR: Manifest references missing file: {relative_path}", file=sys.stderr)
            sys.exit(1)
        actual_hash = sha256_file(file_path)
        if actual_hash != expected_hash:
            print(
                f"ERROR: Hash mismatch for {relative_path}. "
                "Update compatibility-manifest.json after intentional contract changes.",
                file=sys.stderr,
            )
            if schema_version is not None:
                print(
                    f"       Declared schemaVersion={schema_version!r}; bump if breaking.",
                    file=sys.stderr,
                )
            sys.exit(1)


def verify_python_fixtures() -> None:
    for fixture_name, model in sorted(FIXTURE_MODEL_MAP.items()):
        fixture_path = FIXTURES_VALID / f"{fixture_name}.json"
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        parse_contract(model, payload)


def verify_typescript_fixtures() -> None:
    result = subprocess.run(
        [
            "pnpm",
            "exec",
            "vitest",
            "run",
            "packages/contracts-ts/tests/cross-language-fixtures.test.ts",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("ERROR: TypeScript fixture validation failed", file=sys.stderr)
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)


def main() -> None:
    manifest = load_manifest()
    verify_manifest_hashes(manifest)
    verify_python_fixtures()
    verify_typescript_fixtures()
    print("Contract compatibility check passed.")


if __name__ == "__main__":
    main()
