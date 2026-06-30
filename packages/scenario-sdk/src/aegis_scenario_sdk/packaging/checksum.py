"""Deterministic checksum utilities for scenario packages."""

from __future__ import annotations

import hashlib
from pathlib import Path

from aegis_scenario_sdk.loader import canonical_json_bytes, load_raw_document


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checksum_for_bytes(data: bytes) -> str:
    return f"sha256:{sha256_hex(data)}"


def checksum_for_file(path: Path) -> str:
    return checksum_for_bytes(path.read_bytes())


def checksum_for_document(path: Path) -> str:
    raw = load_raw_document(path)
    return checksum_for_bytes(canonical_json_bytes(raw))


def checksum_for_manifest_document(path: Path) -> str:
    return checksum_for_document(path)
