"""Structural state diff between two reconstructed replay states."""

from __future__ import annotations

from typing import Any

from aegis_contracts import ReplayStateV1, StateDiffEntryV1, StateDiffV1
from aegis_contracts.versioning import STATE_DIFF_SCHEMA_VERSION


def _normalize_for_diff(state: ReplayStateV1) -> dict[str, Any]:
    payload = state.model_dump(mode="json", by_alias=True)
    payload.pop("stateDigest", None)
    payload.pop("provenance", None)
    cursor = dict(payload.get("cursor") or {})
    cursor.pop("incidentId", None)
    payload["cursor"] = cursor
    return payload


def _walk_diff(
    before: Any,
    after: Any,
    *,
    path: str,
    entries: list[StateDiffEntryV1],
) -> None:
    if before == after:
        return
    if isinstance(before, dict) and isinstance(after, dict):
        keys = sorted(set(before) | set(after))
        for key in keys:
            child_path = f"{path}.{key}" if path else key
            if key not in before:
                entries.append(
                    StateDiffEntryV1(
                        path=child_path,
                        change_type="added",
                        before=None,
                        after=after[key],
                    )
                )
            elif key not in after:
                entries.append(
                    StateDiffEntryV1(
                        path=child_path,
                        change_type="removed",
                        before=before[key],
                        after=None,
                    )
                )
            else:
                _walk_diff(before[key], after[key], path=child_path, entries=entries)
        return
    if isinstance(before, list) and isinstance(after, list):
        if before != after:
            entries.append(
                StateDiffEntryV1(
                    path=path or "$",
                    change_type="updated",
                    before=before,
                    after=after,
                )
            )
        return
    entries.append(
        StateDiffEntryV1(
            path=path or "$",
            change_type="updated",
            before=before,
            after=after,
        )
    )


def diff_states(from_state: ReplayStateV1, to_state: ReplayStateV1) -> StateDiffV1:
    before = _normalize_for_diff(from_state)
    after = _normalize_for_diff(to_state)
    entries: list[StateDiffEntryV1] = []
    _walk_diff(before, after, path="", entries=entries)
    equivalent = not entries and from_state.state_digest == to_state.state_digest
    if not entries and from_state.state_digest != to_state.state_digest:
        # Digests differ only due to excluded fields; treat as equivalent.
        equivalent = True
    return StateDiffV1(
        schema_version=STATE_DIFF_SCHEMA_VERSION,
        run_id=from_state.run_id,
        from_cursor=from_state.cursor,
        to_cursor=to_state.cursor,
        entries=entries,
        from_digest=from_state.state_digest,
        to_digest=to_state.state_digest,
        equivalent=equivalent,
    )
