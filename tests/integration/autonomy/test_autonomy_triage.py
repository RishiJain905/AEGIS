"""Phase 7 autonomous triage loop tests (offline: enqueue-only, no model execution).

A new alert enqueues a bounded, RoE-gated WATCHTOWER auto-task attributed to autonomy.
Budgets (concurrency, per-run cap, per-asset cooldown) are enforced at enqueue time, so
these assert deterministically without running the local model.
"""

from __future__ import annotations

import os

import pytest
from aegis_agents.autonomy import AutonomyBudget, AutonomyTriageService
from aegis_agents.runtime.session_service import AgentSessionService
from aegis_contracts import AgentTaskStatus, AutonomyInitiatorV1, RulesOfEngagementV1
from aegis_persistence.engine import create_engine, get_session_maker
from aegis_persistence.unit_of_work import PostgresUnitOfWork

from tests.integration.agents.helpers import seed_investigation_run

pytestmark = pytest.mark.skipif(
    os.getenv("AEGIS_INTEGRATION_POSTGRES") != "1",
    reason="Requires PostgreSQL integration environment",
)


def _session_maker():
    from aegis_contracts import load_settings

    settings = load_settings()
    return get_session_maker(settings, engine=create_engine(settings))


async def _tasks_in_autonomy_session(uow, service, run_id, role="WATCHTOWER"):
    session_id = service._session_ids[(run_id, role)]
    return await uow.agent_tasks.list_for_session(session_id)


@pytest.mark.asyncio
async def test_new_alert_enqueues_autonomy_watchtower_task() -> None:
    service = AutonomyTriageService(budget=AutonomyBudget(max_concurrent=5, max_per_run=50))
    async with PostgresUnitOfWork(_session_maker()) as uow:
        _incident, run_id, alert_ids, _ev = await seed_investigation_run(uow)
        task_id = await service.on_new_alert(
            uow,
            run_id=run_id,
            alert_id=alert_ids[0],
            asset_id="asset:device-workstation-01",
            alert_title="Repeated authentication failures",
            roe=RulesOfEngagementV1.INVESTIGATE,
            now=1000.0,
        )
        assert task_id is not None
        tasks = await _tasks_in_autonomy_session(uow, service, run_id)
        assert len(tasks) == 1
        task = tasks[0]
        assert task.initiator == AutonomyInitiatorV1.AUTONOMY
        assert task.status == AgentTaskStatus.QUEUED
        assert task.instructions is not None and "NO_CHANGE" in task.instructions

        # The session itself is marked autonomy too, not just its tasks — that is what
        # keeps this background thread out of the operator's copilot.
        session = await uow.agent_sessions.get_by_id(service._session_ids[(run_id, "WATCHTOWER")])
        assert session is not None
        assert session.origin == AutonomyInitiatorV1.AUTONOMY

        operator_only = await AgentSessionService().list_details_for_run(
            uow, run_id, origin=AutonomyInitiatorV1.OPERATOR
        )
        assert all(detail.session.id != session.id for detail in operator_only)
        unfiltered = await AgentSessionService().list_details_for_run(uow, run_id)
        assert any(detail.session.id == session.id for detail in unfiltered)


@pytest.mark.asyncio
async def test_observe_roe_triages_but_forbids_chaining_in_instructions() -> None:
    service = AutonomyTriageService(budget=AutonomyBudget(max_concurrent=5, max_per_run=50))
    async with PostgresUnitOfWork(_session_maker()) as uow:
        _incident, run_id, alert_ids, _ev = await seed_investigation_run(uow)
        task_id = await service.on_new_alert(
            uow,
            run_id=run_id,
            alert_id=alert_ids[0],
            asset_id="asset:device-workstation-01",
            alert_title="Lateral movement",
            roe=RulesOfEngagementV1.OBSERVE,
            now=2000.0,
        )
        assert task_id is not None  # OBSERVE still triages.
        tasks = await _tasks_in_autonomy_session(uow, service, run_id)
        assert "Report only" in tasks[0].instructions


@pytest.mark.asyncio
async def test_per_asset_cooldown_denies_second_enqueue() -> None:
    service = AutonomyTriageService(
        budget=AutonomyBudget(max_concurrent=5, per_asset_cooldown_seconds=120.0, max_per_run=50)
    )
    async with PostgresUnitOfWork(_session_maker()) as uow:
        _incident, run_id, alert_ids, _ev = await seed_investigation_run(uow)
        first = await service.on_new_alert(
            uow,
            run_id=run_id,
            alert_id=alert_ids[0],
            asset_id="asset:device-workstation-01",
            alert_title="A",
            roe=RulesOfEngagementV1.INVESTIGATE,
            now=100.0,
        )
        # Same asset, 30s later (< 120s cooldown) -> denied.
        second = await service.on_new_alert(
            uow,
            run_id=run_id,
            alert_id=alert_ids[1],
            asset_id="asset:device-workstation-01",
            alert_title="B",
            roe=RulesOfEngagementV1.INVESTIGATE,
            now=130.0,
        )
        assert first is not None
        assert second is None


@pytest.mark.asyncio
async def test_per_run_cap_denies_when_exhausted() -> None:
    service = AutonomyTriageService(budget=AutonomyBudget(max_concurrent=5, max_per_run=1))
    async with PostgresUnitOfWork(_session_maker()) as uow:
        _incident, run_id, alert_ids, _ev = await seed_investigation_run(uow)
        first = await service.on_new_alert(
            uow,
            run_id=run_id,
            alert_id=alert_ids[0],
            asset_id="asset:device-workstation-01",
            alert_title="A",
            roe=RulesOfEngagementV1.INVESTIGATE,
            now=10.0,
        )
        # Different asset (no cooldown), but per-run cap of 1 is hit.
        second = await service.on_new_alert(
            uow,
            run_id=run_id,
            alert_id=alert_ids[1],
            asset_id="asset:svc-api-gateway",
            alert_title="B",
            roe=RulesOfEngagementV1.INVESTIGATE,
            now=20.0,
        )
        assert first is not None
        assert second is None


@pytest.mark.asyncio
async def test_max_concurrent_denies_second_active_task() -> None:
    service = AutonomyTriageService(budget=AutonomyBudget(max_concurrent=1, max_per_run=50))
    async with PostgresUnitOfWork(_session_maker()) as uow:
        _incident, run_id, alert_ids, _ev = await seed_investigation_run(uow)
        first = await service.on_new_alert(
            uow,
            run_id=run_id,
            alert_id=alert_ids[0],
            asset_id="asset:device-workstation-01",
            alert_title="A",
            roe=RulesOfEngagementV1.INVESTIGATE,
            now=10.0,
        )
        # First task stays QUEUED (active), so a second (different asset) is over concurrency.
        second = await service.on_new_alert(
            uow,
            run_id=run_id,
            alert_id=alert_ids[1],
            asset_id="asset:svc-api-gateway",
            alert_title="B",
            roe=RulesOfEngagementV1.INVESTIGATE,
            now=20.0,
        )
        assert first is not None
        assert second is None
