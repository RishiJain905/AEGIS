#!/usr/bin/env python3
"""Verify cross-language contract compatibility and manifest integrity."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from aegis_contracts.events import EventTypeRegistry
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


def verify_event_type_registries() -> None:
    """The two event-type registries must name the same events at the same versions.

    Fixtures and manifest hashes do not cover this: both languages keep their own literal
    registry, and nothing compared them. Nine event types the API had been emitting for a
    while — ``autonomy.task.enqueued``, the ``directive.*`` family, the ``report.*`` family —
    were absent from the TypeScript side, and the console rejected every one of them with a
    ``ContractValidationError`` on an HTTP 200. Because a single unknown type aborts the whole
    catch-up page it appears in, that drift is what left live clients permanently unable to
    reach their run's head.
    """
    ts_source = (ROOT / "packages" / "contracts-ts" / "src" / "events.ts").read_text(
        encoding="utf-8"
    )
    match = re.search(
        r"EVENT_TYPE_REGISTRY:\s*Readonly<Record<string,\s*number>>\s*=\s*\{(.*?)\n\};",
        ts_source,
        re.DOTALL,
    )
    if match is None:
        print("ERROR: could not locate EVENT_TYPE_REGISTRY in contracts-ts", file=sys.stderr)
        sys.exit(1)
    ts_types = {
        name: int(version)
        for name, version in re.findall(r"'([^']+)'\s*:\s*(\d+)", match.group(1))
    }
    python_types = {
        name: EventTypeRegistry.payload_schema_version(name)
        for name in EventTypeRegistry.known_types()
    }

    missing_in_ts = sorted(set(python_types) - set(ts_types))
    missing_in_python = sorted(set(ts_types) - set(python_types))
    version_mismatch = sorted(
        name for name in set(ts_types) & set(python_types) if ts_types[name] != python_types[name]
    )
    if missing_in_ts or missing_in_python or version_mismatch:
        print("ERROR: event type registries disagree across languages", file=sys.stderr)
        for name in missing_in_ts:
            print(f"       missing from contracts-ts: {name}", file=sys.stderr)
        for name in missing_in_python:
            print(f"       missing from contracts-python: {name}", file=sys.stderr)
        for name in version_mismatch:
            print(
                f"       payload version mismatch for {name}: "
                f"python={python_types[name]} ts={ts_types[name]}",
                file=sys.stderr,
            )
        sys.exit(1)


def resolve_executable(name: str) -> str:
    # Windows CreateProcess only resolves .exe from PATH; pnpm ships as a
    # .cmd/.ps1 shim (plus an extensionless POSIX script Windows cannot spawn),
    # so resolve to a launchable executable explicitly.
    if os.name == "nt":
        for ext in (".exe", ".cmd", ".bat"):
            found = shutil.which(name + ext)
            if found is not None:
                return found
    found = shutil.which(name)
    if found is None:
        print(f"ERROR: required tool not found on PATH: {name}", file=sys.stderr)
        sys.exit(1)
    return found


def verify_typescript_fixtures() -> None:
    result = subprocess.run(
        [
            resolve_executable("pnpm"),
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
    verify_event_type_registries()
    verify_python_fixtures()
    verify_typescript_fixtures()
    print("Contract compatibility check passed.")


if __name__ == "__main__":
    main()
