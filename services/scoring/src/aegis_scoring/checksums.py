"""Checksum and fingerprint helpers for scoring integrity."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def sha256_hex(payload: str | bytes) -> str:
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def hash_payload(payload: Any) -> str:
    return sha256_hex(canonical_json(payload))
