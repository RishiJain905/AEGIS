"""Shared helpers for WATCHTOWER agent tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aegis_contracts.entities import AlertV1
from aegis_contracts.versioning import ALERT_SCHEMA_VERSION


def make_alert(
    *,
    alert_id: str,
    asset_id: str,
    created_at: datetime,
    title: str = "Synthetic alert",
    severity: str = "high",
    run_id: str = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
) -> AlertV1:
    return AlertV1(
        schema_version=ALERT_SCHEMA_VERSION,
        id=alert_id,
        run_id=run_id,
        title=title,
        severity=severity,
        source_event_id="evt_01ARZ3NDEKTSV4RRFFQ69G5FAW",
        asset_id=asset_id,
        created_at=created_at,
    )


def alert_at(
    *,
    alert_id: str,
    asset_id: str,
    offset_minutes: int = 0,
    base: datetime | None = None,
    title: str = "Synthetic alert",
) -> AlertV1:
    start = base or datetime(2026, 6, 30, 2, 0, 0, tzinfo=UTC)
    return make_alert(
        alert_id=alert_id,
        asset_id=asset_id,
        created_at=start + timedelta(minutes=offset_minutes),
        title=title,
    )
