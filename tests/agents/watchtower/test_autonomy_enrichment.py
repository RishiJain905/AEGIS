"""WATCHTOWER enriches an existing case; it never opens one (ADR 0037).

Incident creation moved to the detection engine so that it survives a provider outage. The
counterpart obligation lives here: the autonomy triage lane must *look up* the asset's open
case and must not fall back to creating one, or incident existence quietly becomes
model-dependent again. Offline — no database, no model.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime

import pytest
from aegis_agents.autonomy import AutonomyTriageService
from aegis_contracts import IncidentState, IncidentV1, deterministic_incident_id
from aegis_contracts.versioning import INCIDENT_SCHEMA_VERSION

_RUN = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
_ASSET = "asset:device-workstation-01"


class _FakeIncidentRepository:
    def __init__(self, incidents: list[IncidentV1]) -> None:
        self._incidents = incidents
        self.add_calls = 0

    async def get_by_id(self, incident_id: str) -> IncidentV1 | None:
        return next((item for item in self._incidents if item.id == incident_id), None)

    async def add(self, incident: IncidentV1) -> IncidentV1:  # pragma: no cover - guard
        self.add_calls += 1
        raise AssertionError("Triage must never open an incident")


class _FakeUnitOfWork:
    def __init__(self, incidents: list[IncidentV1]) -> None:
        self.incidents = _FakeIncidentRepository(incidents)


def _incident(run_id: str = _RUN, asset_id: str = _ASSET) -> IncidentV1:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return IncidentV1(
        schema_version=INCIDENT_SCHEMA_VERSION,
        id=deterministic_incident_id(run_id, asset_id),
        run_id=run_id,
        title="Confirmed compromise",
        state=IncidentState.OPEN,
        alert_ids=["alert:det-a"],
        revision=0,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_triage_finds_the_case_already_open_for_the_asset() -> None:
    uow = _FakeUnitOfWork([_incident()])

    resolved = await AutonomyTriageService._existing_incident_for_asset(
        uow,  # type: ignore[arg-type]
        _RUN,
        _ASSET,
    )

    assert resolved == deterministic_incident_id(_RUN, _ASSET)


@pytest.mark.asyncio
async def test_triage_returns_none_rather_than_opening_a_case() -> None:
    """No case yet simply means the alert has not crossed correlation — not "create one"."""
    uow = _FakeUnitOfWork([])

    resolved = await AutonomyTriageService._existing_incident_for_asset(
        uow,  # type: ignore[arg-type]
        _RUN,
        _ASSET,
    )

    assert resolved is None
    assert uow.incidents.add_calls == 0


@pytest.mark.asyncio
async def test_another_assets_case_is_not_borrowed() -> None:
    uow = _FakeUnitOfWork([_incident(asset_id="asset:svc-logistics-api")])

    resolved = await AutonomyTriageService._existing_incident_for_asset(
        uow,  # type: ignore[arg-type]
        _RUN,
        _ASSET,
    )

    assert resolved is None


def test_the_resolver_holds_no_creation_branch() -> None:
    """A source-level guard, because the regression would be a silent one-line change."""
    source = inspect.getsource(AutonomyTriageService._existing_incident_for_asset)
    assert "incidents.add(" not in source
    assert "IncidentV1(" not in source
