"""Canonical checksum and digest helpers for replay snapshots."""

from __future__ import annotations

import gzip
import hashlib
import json
from typing import Any

from aegis_contracts import ReplaySnapshotV1, ReplayStateV1
from aegis_contracts.replay import ReplayErrorCode

from aegis_replay.errors import ReplayEngineError


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def sha256_digest(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def compute_state_digest(state: ReplayStateV1) -> str:
    """Digest over normalized projection fields.

    Provenance (mode, snapshot id, applied ranges, reconstructedAt) is excluded so
    event-only and snapshot+tail reconstructions of the same domain state compare equal.
    """
    payload = state.model_dump(mode="json", by_alias=True)
    payload.pop("stateDigest", None)
    payload.pop("provenance", None)
    # Cursor incident focus is a view filter, not domain state.
    cursor = dict(payload.get("cursor") or {})
    cursor.pop("incidentId", None)
    payload["cursor"] = cursor
    return sha256_digest(canonical_json_bytes(payload))


def serialize_snapshot_archive(snapshot: ReplaySnapshotV1) -> tuple[bytes, str]:
    """Return gzip-compressed archive bytes and checksum of the compressed payload."""
    payload = snapshot.model_dump(mode="json", by_alias=True)
    raw = canonical_json_bytes(payload)
    compressed = gzip.compress(raw, compresslevel=6, mtime=0)
    return compressed, sha256_digest(compressed)


def deserialize_snapshot_archive(data: bytes) -> ReplaySnapshotV1:
    raw = gzip.decompress(data)
    payload = json.loads(raw.decode("utf-8"))
    return ReplaySnapshotV1.model_validate(payload)


def verify_archive_checksum(*, data: bytes, expected_checksum: str) -> None:
    actual = sha256_digest(data)
    if actual != expected_checksum:
        raise ReplayEngineError(
            ReplayErrorCode.SNAPSHOT_CHECKSUM_MISMATCH,
            "Snapshot archive checksum mismatch",
            details={"expected": expected_checksum, "actual": actual},
        )
