"""The autonomous pipeline fills a case, against real PostgreSQL.

The offline suites fake the unit of work, which means they cannot exercise the one thing
this chain most depends on: a stage guard that must see work enqueued by a *different*
session in an *earlier* turn. ``AgentTaskService.create_task`` dedupes within a session
only, so the guard is its own query against ``agent_tasks`` — and a query nobody runs
against a real database is a query nobody has tested.

Deterministic provider (``mock``), so this runs in core CI without an external model.
"""

from __future__ import annotations

import os

import pytest
from aegis_agents.autonomy import AutonomyBudget, AutonomyTriageService
from aegis_agents.providers.generation import AgentGenerationFacade
from aegis_agents.roles.registry import PostProcessContext
from aegis_agents.roles.watchtower.handler import WatchtowerRoleHandler
from aegis_agents.runtime.executor import TaskExecutor
from aegis_agents.runtime.session_service import AgentSessionService
from aegis_contracts import (
    AgentTaskStatus,
    AutonomyInitiatorV1,
    IncidentState,
    RulesOfEngagementV1,
)
from aegis_contracts.agent_runtime import CreateAgentSessionRequestV1
from aegis_contracts.entities import AgentRole, AgentSessionV1, RunLoadoutV1
from aegis_contracts.versioning import CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION
from aegis_model_provider import build_provider_registry, load_provider_settings
from aegis_model_provider.persistence import InMemoryGenerationArtifactRepository
from aegis_model_provider.service import GenerationService
from aegis_persistence.engine import create_engine, get_session_maker
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from tests.integration.agents.helpers import SEEDED_ASSET_ID, seed_investigation_run

pytestmark = pytest.mark.skipif(
    os.getenv("AEGIS_INTEGRATION_POSTGRES") != "1",
    reason="Requires PostgreSQL integration environment",
)


#: Pins every agent turn in the seeded run to the deterministic provider, so this suite
#: runs in core CI with no external model (architecture contract: core CI must pass without
#: an LLM). The loadout is the only provider lever autonomy-enqueued tasks respect — it
#: deliberately outranks a per-task ``providerId``.
_MOCK = RunLoadoutV1(roe=RulesOfEngagementV1.INVESTIGATE, provider_id="mock")


def _session_maker():
    from aegis_contracts import load_settings

    settings = load_settings()
    return get_session_maker(settings, engine=create_engine(settings))


def _executor() -> TaskExecutor:
    settings = load_provider_settings()
    return TaskExecutor(
        generation=AgentGenerationFacade(
            GenerationService(
                registry=build_provider_registry(settings),
                settings=settings,
                artifact_repository=InMemoryGenerationArtifactRepository(),
            )
        )
    )


async def _sessions_by_role(uow: PostgresUnitOfWork, run_id: str) -> dict[AgentRole, list[str]]:
    grouped: dict[AgentRole, list[str]] = {}
    for session in await uow.agent_sessions.list_for_run(run_id):
        grouped.setdefault(session.role, []).append(session.id)
    return grouped


async def _triage(
    uow: PostgresUnitOfWork,
    service: AutonomyTriageService,
    *,
    run_id: str,
    alert_id: str,
    asset_id: str,
    now: float,
) -> str:
    task_id = await service.on_new_alert(
        uow,
        run_id=run_id,
        alert_id=alert_id,
        asset_id=asset_id,
        alert_title="Repeated authentication failures",
        roe=RulesOfEngagementV1.INVESTIGATE,
        now=now,
    )
    assert task_id is not None
    await _executor().execute(uow, task_id)
    return task_id


@pytest.mark.asyncio
async def test_an_autonomous_triage_leaves_the_case_triaged_and_under_investigation() -> None:
    service = AutonomyTriageService(budget=AutonomyBudget(max_concurrent=5, max_per_run=50))
    async with PostgresUnitOfWork(_session_maker()) as uow:
        incident_id, run_id, alert_ids, _ev = await seed_investigation_run(uow, loadout=_MOCK)

        task_id = await _triage(
            uow,
            service,
            run_id=run_id,
            alert_id=alert_ids[0],
            asset_id=SEEDED_ASSET_ID,
            now=1000.0,
        )
        task = await uow.agent_tasks.get_by_id(task_id)
        assert task is not None and task.status == AgentTaskStatus.COMPLETED

        detail = await uow.investigation.get_detail(incident_id, run_id)
        assert detail.triage_results, "the turn's own artifact"

        incident = await uow.incidents.get_by_id(incident_id)
        assert incident is not None
        assert incident.state is IncidentState.TRIAGED, "the case no longer reads as untriaged"

        trace_sessions = (await _sessions_by_role(uow, run_id)).get(AgentRole.TRACE, [])
        assert len(trace_sessions) == 1, "triage handed the case on"
        trace_tasks = await uow.agent_tasks.list_for_session(trace_sessions[0])
        assert len(trace_tasks) == 1
        assert trace_tasks[0].incident_id == incident_id
        # Carries the chain forward and inherits the lane's fail-soft tool handling.
        assert trace_tasks[0].initiator is AutonomyInitiatorV1.AUTONOMY
        assert trace_tasks[0].idempotency_key == f"autonomy-chain:{incident_id}:trace"


@pytest.mark.asyncio
async def test_a_second_triage_on_the_same_case_reuses_the_investigation() -> None:
    """The guard the offline suite can only fake: an earlier turn's follow-up lives in a
    different session, so ``create_task``'s per-session dedupe would never see it."""
    service = AutonomyTriageService(
        budget=AutonomyBudget(max_concurrent=5, max_per_run=50, per_asset_cooldown_seconds=0.0)
    )
    async with PostgresUnitOfWork(_session_maker()) as uow:
        incident_id, run_id, alert_ids, _ev = await seed_investigation_run(uow, loadout=_MOCK)

        await _triage(
            uow, service, run_id=run_id, alert_id=alert_ids[0],
            asset_id=SEEDED_ASSET_ID, now=1000.0,
        )
        await _triage(
            uow, service, run_id=run_id, alert_id=alert_ids[1],
            asset_id=SEEDED_ASSET_ID, now=2000.0,
        )

        detail = await uow.investigation.get_detail(incident_id, run_id)
        assert len(detail.triage_results) == 2, "both alerts were triaged"
        trace_sessions = (await _sessions_by_role(uow, run_id)).get(AgentRole.TRACE, [])
        assert len(trace_sessions) == 1, "but the case gets one investigation, not one per alert"


@pytest.mark.asyncio
async def test_observe_triages_the_alert_and_stops_there() -> None:
    service = AutonomyTriageService(budget=AutonomyBudget(max_concurrent=5, max_per_run=50))
    async with PostgresUnitOfWork(_session_maker()) as uow:
        incident_id, run_id, alert_ids, _ev = await seed_investigation_run(
            uow,
            loadout=RunLoadoutV1(roe=RulesOfEngagementV1.OBSERVE, provider_id="mock"),
        )

        task_id = await service.on_new_alert(
            uow,
            run_id=run_id,
            alert_id=alert_ids[0],
            asset_id=SEEDED_ASSET_ID,
            alert_title="Repeated authentication failures",
            roe=RulesOfEngagementV1.OBSERVE,
            now=1000.0,
        )
        assert task_id is not None
        await _executor().execute(uow, task_id)

        detail = await uow.investigation.get_detail(incident_id, run_id)
        assert detail.triage_results, "OBSERVE still triages"
        assert AgentRole.TRACE not in await _sessions_by_role(uow, run_id)


@pytest.mark.asyncio
async def test_cited_evidence_reaches_the_panel_that_renders_it() -> None:
    """The mock model cites nothing, so the projection is driven with a payload of the
    shape the QA run's one successful autonomous triage actually returned."""
    async with PostgresUnitOfWork(_session_maker()) as uow:
        incident_id, run_id, alert_ids, evidence_id = await seed_investigation_run(uow)
        alert = await uow.alerts.get_by_id(alert_ids[0])
        assert alert is not None
        cited = alert.source_event_id

        lane = await _lane(uow, run_id)
        await WatchtowerRoleHandler().post_process(
            ctx=PostProcessContext(
                uow=uow,
                session_id=lane.id,
                task_id="atk_01ARZ3NDEKTSV4RRFFQ69G5FAV",
                incident_id=incident_id,
                run_id=run_id,
                trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
                idempotency_key="integration-citation-projection",
                visible_evidence_ids={cited, evidence_id},
                initiator=AutonomyInitiatorV1.OPERATOR,
            ),
            structured={
                "alertSummaries": [],
                "groupedAlertIds": [],
                "separatedAlertIds": [],
                "correlationDecisions": [],
                "escalation": "monitor",
                "escalationRationale": "Two successful authentications, nothing corroborating.",
                "confidence": 0.15,
                "evidenceCitations": [{"evidenceId": cited}],
                "toolRequests": [],
            },
        )

        detail = await uow.investigation.get_detail(incident_id, run_id)
        assert [item.evidence_id for item in detail.evidence_attachments] == [cited]
        assert detail.evidence_attachments[0].provenance.source_id == cited
        # A MONITOR verdict never chains, so this projection is the only thing standing
        # between a triaged false positive and a case that renders as untouched.
        assert AgentRole.TRACE not in await _sessions_by_role(uow, run_id)


async def _lane(uow: PostgresUnitOfWork, run_id: str) -> AgentSessionV1:
    return await AgentSessionService().create_run_session(
        uow,
        run_id=run_id,
        request=CreateAgentSessionRequestV1(
            schema_version=CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
            role=AgentRole.WATCHTOWER,
            trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            enqueue_initial_task=False,
        ),
        origin=AutonomyInitiatorV1.AUTONOMY,
    )
