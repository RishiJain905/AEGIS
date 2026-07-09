"""Replay projector compatibility pins."""

from __future__ import annotations

from typing import Final

from aegis_contracts.versioning import WORKSPACE_VERSION

REPLAY_PROJECTOR_VERSION: Final[str] = "0.0.0-phase25"
DEFAULT_RETENTION_CLASS: Final[str] = "standard"
DEFAULT_SNAPSHOT_INTERVAL: Final[int] = 50


def is_compatible_snapshot(
    *,
    projector_version: str,
    workspace_version: str,
    engine_version: str,
    expected_engine_version: str | None = None,
) -> bool:
    if projector_version != REPLAY_PROJECTOR_VERSION:
        return False
    if not workspace_version.startswith("0.0.0-phase"):
        return False
    # Workspace may be older than current; allow same major phase family.
    allowed = {WORKSPACE_VERSION, "0.0.0-phase24", "0.0.0-phase25"}
    if workspace_version not in allowed and workspace_version > WORKSPACE_VERSION:
        return False
    return not (
        expected_engine_version is not None and engine_version != expected_engine_version
    )
