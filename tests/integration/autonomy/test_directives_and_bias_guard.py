"""Phase 7 standing-directive matching + bias-guard autonomy tests (offline, enqueue-only).

Directives enqueue a WATCHTOWER task carrying the directive text; bias guard enqueues an
ORACLE re-examination when a new alert overlaps assets referenced by existing hypotheses.
Both reuse the single ``enqueue_auto_task`` path, so these assert deterministically without
running the local model.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest
from aegis_agents.autonomy import AutonomyBudget, AutonomyTriageService
from aegis_agents.runtime.ids import new_runtime_id
from aegis_api.autonomy.poller import AutonomyPoller
from aegis_contracts import (
    AgentRole,
    HypothesisV1,
    RulesOfEngagementV1,
    StandingDirectiveV1,
    load_settings,
)
from aegis_contracts.versioning import STANDING_DIRECTIVE_SCHEMA_VERSION
from aegis_persistence.engine import create_engine, get_session_maker
from aegis_persistence.unit_of_work import PostgresUnitOfWork

from tests.integration.agents.helpers import seed_investigation_run

pytestmark = pytest.mark.skipif(
    os.getenv("AEGIS_INTEGRATION_POSTGRES") != "1",
    reason="Requires PostgreSQL integration environment",
)

_ASSET = "asset:device-workstation-01"


def _session_maker():
    settings = load_settings()
    return get_session_maker(settings, engine=create_engine(settings))


async def _tasks(uow, service, run_id, role):
    session_id = service._session_ids[(run_id, role)]
    return await uow.agent_tasks.list_for_session(session_id)


@pytest.mark.asyncio
async def test_on_directive_match_enqueues_watchtower_with_directive_text() -> None:
    service = AutonomyTriageService(budget=AutonomyBudget(max_concurrent=10, max_per_run=50))
    async with PostgresUnitOfWork(_session_maker()) as uow:
        _incident, run_id, alert_ids, _ev = await seed_investigation_run(uow)
        task_id = await service.on_directive_match(
            uow,
            run_id=run_id,
            directive_id="dir_logistics",
            directive_text="Monitor the logistics zone network for lateral movement",
            alert_id=alert_ids[0],
            asset_id=_ASSET,
            alert_title="Lateral movement attempt",
        )
        assert task_id is not None
        tasks = await _tasks(uow, service, run_id, "WATCHTOWER")
        assert len(tasks) == 1
        assert "Monitor the logistics zone network" in tasks[0].instructions
        assert "NO_CHANGE" in tasks[0].instructions


@pytest.mark.asyncio
async def test_bias_guard_uses_a_distinct_oracle_session() -> None:
    service = AutonomyTriageService(budget=AutonomyBudget(max_concurrent=10, max_per_run=50))
    async with PostgresUnitOfWork(_session_maker()) as uow:
        _incident, run_id, alert_ids, _ev = await seed_investigation_run(uow)
        watchtower_task = await service.on_new_alert(
            uow,
            run_id=run_id,
            alert_id=alert_ids[0],
            asset_id=_ASSET,
            alert_title="Repeated authentication failures",
            roe=RulesOfEngagementV1.INVESTIGATE,
            now=10.0,
        )
        oracle_task = await service.on_bias_guard(
            uow,
            run_id=run_id,
            alert_id=alert_ids[0],
            asset_id=_ASSET,
            alert_title="Repeated authentication failures",
            now=10.0,
        )
        assert watchtower_task is not None
        assert oracle_task is not None
        # Distinct per-role sessions with the correct agent roles.
        wt_session_id = service._session_ids[(run_id, "WATCHTOWER")]
        oracle_session_id = service._session_ids[(run_id, "ORACLE")]
        assert wt_session_id != oracle_session_id
        oracle_session = await uow.agent_sessions.get_by_id(oracle_session_id)
        assert oracle_session is not None
        assert oracle_session.role == AgentRole.ORACLE
        oracle_tasks = await _tasks(uow, service, run_id, "ORACLE")
        assert "contradicts" in oracle_tasks[0].instructions


@pytest.mark.asyncio
async def test_poller_matches_directive_and_bias_guard_end_to_end() -> None:
    settings = load_settings()
    service = AutonomyTriageService(budget=AutonomyBudget(max_concurrent=10, max_per_run=50))
    session_maker = _session_maker()

    async with PostgresUnitOfWork(session_maker) as uow:
        incident_id, run_id, alert_ids, evidence_id = await seed_investigation_run(uow)
        # Active asset-scoped directive that intersects the alert asset.
        await uow.directives.add(
            StandingDirectiveV1(
                schema_version=STANDING_DIRECTIVE_SCHEMA_VERSION,
                id=new_runtime_id("dir"),
                run_id=run_id,
                text="Watch the primary workstation",
                scope_asset_ids=[_ASSET],
                scope_zone_ids=[],
                active=True,
                created_by="operator:op",
                created_at=datetime(2026, 6, 30, tzinfo=UTC),
            )
        )
        # A hypothesis referencing the seeded evidence (asset:device-workstation-01), so a
        # new alert on that asset overlaps a leading hypothesis and trips the bias guard.
        await uow.oracle_hypotheses.add_hypothesis(
            HypothesisV1(
                schema_version=1,
                id=new_runtime_id("hyp"),
                incident_id=incident_id,
                status="active",
                statement="Workstation is the initial access point",
                confidence=0.6,
                evidence_ids=[evidence_id],
                created_at=datetime(2026, 6, 30, tzinfo=UTC),
            )
        )

    poller = AutonomyPoller(session_maker=session_maker, settings=settings, service=service)
    await poller._poll_run(run_id, RulesOfEngagementV1.INVESTIGATE)

    async with PostgresUnitOfWork(session_maker) as uow:
        watchtower_tasks = await _tasks(uow, service, run_id, "WATCHTOWER")
        oracle_tasks = await _tasks(uow, service, run_id, "ORACLE")
        events = await uow.events.list_by_run(run_id)

    # WATCHTOWER lane carries both triage and the matched directive; ORACLE carries the
    # bias-guard re-examination.
    assert any("Watch the primary workstation" in t.instructions for t in watchtower_tasks)
    assert len(oracle_tasks) >= 1
    assert any("contradicts" in t.instructions for t in oracle_tasks)
    assert any(e.type == "directive.triggered" for e in events)
