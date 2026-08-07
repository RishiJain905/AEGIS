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
from aegis_contracts.entities import (
    AgentRole,
    AgentSessionState,
    AgentSessionV1,
    AutonomyInitiatorV1,
)
from aegis_contracts.versioning import AGENT_SESSION_SCHEMA_VERSION, INCIDENT_SCHEMA_VERSION

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


# --- the lane must never be stuck behind a terminal session -------------------


class _FakeSessionRepository:
    def __init__(self, sessions: dict[str, AgentSessionV1]) -> None:
        self._sessions = sessions

    async def get_by_id(self, session_id: str) -> AgentSessionV1 | None:
        return self._sessions.get(session_id)


class _SessionUnitOfWork:
    def __init__(self, sessions: dict[str, AgentSessionV1]) -> None:
        self.agent_sessions = _FakeSessionRepository(sessions)


class _RecordingSessionService:
    """Hands back a fresh GATHERING lane and counts how often it was asked for one."""

    def __init__(self) -> None:
        self.created = 0

    async def create_run_session(self, _uow: object, **_kwargs: object) -> AgentSessionV1:
        self.created += 1
        return _lane(f"agent-session:ags_fresh_{self.created}", AgentSessionState.GATHERING)


def _lane(session_id: str, state: AgentSessionState) -> AgentSessionV1:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return AgentSessionV1(
        schema_version=AGENT_SESSION_SCHEMA_VERSION,
        id=session_id,
        run_id=_RUN,
        role=AgentRole.WATCHTOWER,
        state=state,
        trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        origin=AutonomyInitiatorV1.AUTONOMY,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state",
    [AgentSessionState.COMPLETED, AgentSessionState.CANCELLED],
)
async def test_a_terminal_lane_is_replaced_rather_than_reused(
    state: AgentSessionState,
) -> None:
    """Nothing leaves COMPLETED or CANCELLED, so enqueueing onto one is enqueueing
    into a hole: every task dies at "-> gathering" and the run's autonomy is over
    with no failure anyone asked for. Open a new lane instead."""
    dead = _lane("agent-session:ags_dead", state)
    sessions = _RecordingSessionService()
    service = AutonomyTriageService(sessions=sessions)  # type: ignore[arg-type]
    service._session_ids[(_RUN, "WATCHTOWER")] = dead.id
    uow = _SessionUnitOfWork({dead.id: dead})

    resolved = await service._ensure_autonomy_session(
        uow,  # type: ignore[arg-type]
        _RUN,
        AgentRole.WATCHTOWER,
    )

    assert resolved != dead.id
    assert sessions.created == 1


@pytest.mark.asyncio
async def test_a_live_lane_is_reused_across_turns() -> None:
    """The shared lane is the point: one session hosts every triage in the run."""
    live = _lane("agent-session:ags_live", AgentSessionState.VERIFYING)
    sessions = _RecordingSessionService()
    service = AutonomyTriageService(sessions=sessions)  # type: ignore[arg-type]
    service._session_ids[(_RUN, "WATCHTOWER")] = live.id
    uow = _SessionUnitOfWork({live.id: live})

    resolved = await service._ensure_autonomy_session(
        uow,  # type: ignore[arg-type]
        _RUN,
        AgentRole.WATCHTOWER,
    )

    assert resolved == live.id
    assert sessions.created == 0
