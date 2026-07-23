"""Unit tests for standing-directive scope matching (offline, no DB)."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_api.autonomy.poller import _directive_matches
from aegis_contracts import StandingDirectiveV1
from aegis_contracts.versioning import STANDING_DIRECTIVE_SCHEMA_VERSION


def _directive(*, asset_ids: list[str], zone_ids: list[str]) -> StandingDirectiveV1:
    return StandingDirectiveV1(
        schema_version=STANDING_DIRECTIVE_SCHEMA_VERSION,
        id="dir_test",
        run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        text="Monitor the logistics zone network",
        scope_asset_ids=asset_ids,
        scope_zone_ids=zone_ids,
        active=True,
        created_by="operator:op",
        created_at=datetime(2026, 6, 30, tzinfo=UTC),
    )


def test_unscoped_directive_matches_any_alert() -> None:
    directive = _directive(asset_ids=[], zone_ids=[])
    assert _directive_matches(directive, "asset:anything", None) is True


def test_asset_scope_matches_only_that_asset() -> None:
    directive = _directive(asset_ids=["asset:svc-api-gateway"], zone_ids=[])
    assert _directive_matches(directive, "asset:svc-api-gateway", None) is True
    assert _directive_matches(directive, "asset:other", "business-unit:bu-platform") is False


def test_zone_scope_matches_via_cluster() -> None:
    directive = _directive(asset_ids=[], zone_ids=["business-unit:bu-logistics"])
    assert _directive_matches(directive, "asset:x", "business-unit:bu-logistics") is True
    assert _directive_matches(directive, "asset:x", "business-unit:bu-platform") is False
    # No resolvable zone for the asset -> no zone match.
    assert _directive_matches(directive, "asset:x", None) is False
