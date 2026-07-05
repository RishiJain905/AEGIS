# ruff: noqa: E501
"""Correlation logic tests for WATCHTOWER triage."""

from __future__ import annotations

from aegis_agents.roles.watchtower.correlation import (
    SEPARATED_DECISION,
    SHARED_ASSET_DECISION,
    TEMPORAL_PROXIMITY_DECISION,
    correlate_alerts,
    derive_grouped_and_separated_alert_ids,
)

from tests.agents.watchtower.helpers import alert_at


def test_empty_alerts_returns_no_decisions() -> None:
    assert correlate_alerts([]) == []


def test_shared_asset_alerts_are_grouped() -> None:
    alerts = [
        alert_at(alert_id="alert:alt_001", asset_id="asset:device-workstation-01", offset_minutes=0),
        alert_at(alert_id="alert:alt_002", asset_id="asset:device-workstation-01", offset_minutes=5),
    ]
    decisions = correlate_alerts(alerts)
    shared_asset = [
        item for item in decisions if item.decision == SHARED_ASSET_DECISION
    ]
    assert len(shared_asset) == 1
    assert set(shared_asset[0].alert_ids) == {"alert:alt_001", "alert:alt_002"}
    assert "shared_asset" in shared_asset[0].factors


def test_temporal_proximity_groups_different_assets() -> None:
    alerts = [
        alert_at(alert_id="alert:alt_010", asset_id="asset:device-workstation-01", offset_minutes=0),
        alert_at(alert_id="alert:alt_011", asset_id="asset:svc-api-gateway", offset_minutes=10),
    ]
    decisions = correlate_alerts(alerts)
    temporal = [
        item for item in decisions if item.decision == TEMPORAL_PROXIMITY_DECISION
    ]
    assert len(temporal) == 1
    assert set(temporal[0].alert_ids) == {"alert:alt_010", "alert:alt_011"}


def test_isolated_alert_is_separated() -> None:
    alerts = [
        alert_at(alert_id="alert:alt_020", asset_id="asset:device-workstation-01", offset_minutes=0),
    ]
    decisions = correlate_alerts(alerts)
    assert len(decisions) == 1
    assert decisions[0].decision == SEPARATED_DECISION
    assert decisions[0].alert_ids == ["alert:alt_020"]


def test_distant_alerts_on_different_assets_remain_separate() -> None:
    alerts = [
        alert_at(alert_id="alert:alt_030", asset_id="asset:device-workstation-01", offset_minutes=0),
        alert_at(alert_id="alert:alt_031", asset_id="asset:svc-api-gateway", offset_minutes=30),
    ]
    decisions = correlate_alerts(alerts)
    grouped, separated = derive_grouped_and_separated_alert_ids(alerts, decisions)
    assert grouped == []
    assert separated == ["alert:alt_030", "alert:alt_031"]


def test_derive_grouped_and_separated_partitions_all_alerts() -> None:
    alerts = [
        alert_at(alert_id="alert:alt_040", asset_id="asset:device-workstation-01", offset_minutes=0),
        alert_at(alert_id="alert:alt_041", asset_id="asset:device-workstation-01", offset_minutes=2),
        alert_at(alert_id="alert:alt_042", asset_id="asset:svc-api-gateway", offset_minutes=60),
    ]
    decisions = correlate_alerts(alerts)
    grouped, separated = derive_grouped_and_separated_alert_ids(alerts, decisions)
    assert set(grouped) == {"alert:alt_040", "alert:alt_041"}
    assert separated == ["alert:alt_042"]
