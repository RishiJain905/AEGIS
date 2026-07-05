"""Investigation HTTP routes for Phase 20 WATCHTOWER and TRACE."""

from __future__ import annotations

from aegis_agents.roles.bastion.coordinator import BastionCoordinator
from aegis_agents.roles.oracle.coordinator import OracleCoordinator
from aegis_agents.roles.warden.coordinator import WardenCoordinator
from aegis_agents.roles.watchtower.coordinator import WatchtowerCoordinator
from aegis_api.db.session import db_session, get_db_session_maker
from aegis_contracts import IncidentV1, InvestigationDetailV1
from aegis_contracts.hypothesis import TriggerOracleRequestV1
from aegis_contracts.investigation import TriggerWatchtowerRequestV1
from aegis_contracts.proposals import TriggerBastionRequestV1, TriggerWardenRequestV1
from aegis_contracts.versioning import INVESTIGATION_DETAIL_SCHEMA_VERSION
from aegis_persistence.mappers import incident_to_domain
from aegis_persistence.orm.tables import IncidentRow
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v1", tags=["investigation"])


@router.get("/incidents/{incident_id}", response_model=IncidentV1)
async def get_incident(incident_id: str) -> IncidentV1:
    async with db_session() as session:
        row = await session.get(IncidentRow, incident_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"Incident not found: {incident_id}")
        return incident_to_domain(row)


@router.get("/incidents/{incident_id}/investigation", response_model=InvestigationDetailV1)
async def get_investigation_detail(incident_id: str) -> InvestigationDetailV1:
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        incident = await uow.incidents.get_by_id(incident_id)
        if incident is None:
            raise HTTPException(status_code=404, detail=f"Incident not found: {incident_id}")
        return await uow.investigation.get_detail(incident_id, incident.run_id)


@router.post("/runs/{run_id}/investigation/trigger-watchtower")
async def trigger_watchtower(run_id: str, request: TriggerWatchtowerRequestV1) -> dict[str, object]:
    if request.run_id != run_id:
        raise HTTPException(status_code=400, detail="runId mismatch")
    coordinator = WatchtowerCoordinator()
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        if not request.alert_ids:
            alerts = await uow.alerts.list_by_run(run_id)
            request = request.model_copy(update={"alert_ids": [alert.id for alert in alerts]})
        result = await coordinator.trigger_for_run(uow, request)
    return {
        "schemaVersion": INVESTIGATION_DETAIL_SCHEMA_VERSION,
        "incidentId": result.incident_id,
        "watchtowerSessionId": result.watchtower_session_id,
        "traceSessionId": result.trace_session_id,
        "triageResultId": result.triage.id,
    }


@router.post("/runs/{run_id}/investigation/trigger-oracle")
async def trigger_oracle(run_id: str, request: TriggerOracleRequestV1) -> dict[str, object]:
    if request.run_id != run_id:
        raise HTTPException(status_code=400, detail="runId mismatch")
    coordinator = OracleCoordinator()
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        result = await coordinator.trigger_for_run(uow, request)
    return {
        "schemaVersion": INVESTIGATION_DETAIL_SCHEMA_VERSION,
        "incidentId": result.incident_id,
        "oracleSessionId": result.oracle_session_id,
        "oracleTaskId": result.oracle_task_id,
        "traceSessionId": result.trace_session_id,
    }


@router.post("/runs/{run_id}/investigation/trigger-bastion")
async def trigger_bastion(run_id: str, request: TriggerBastionRequestV1) -> dict[str, object]:
    if request.run_id != run_id:
        raise HTTPException(status_code=400, detail="runId mismatch")
    coordinator = BastionCoordinator()
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        result = await coordinator.trigger_for_run(uow, request)
    return {
        "schemaVersion": INVESTIGATION_DETAIL_SCHEMA_VERSION,
        "incidentId": result.incident_id,
        "bastionSessionId": result.bastion_session_id,
        "bastionTaskId": result.bastion_task_id,
        "wardenSessionId": result.warden_session_id,
        "wardenTaskId": result.warden_task_id,
    }


@router.post("/runs/{run_id}/investigation/trigger-warden")
async def trigger_warden(run_id: str, request: TriggerWardenRequestV1) -> dict[str, object]:
    if request.run_id != run_id:
        raise HTTPException(status_code=400, detail="runId mismatch")
    coordinator = WardenCoordinator()
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        result = await coordinator.trigger_for_run(uow, request)
    return {
        "schemaVersion": INVESTIGATION_DETAIL_SCHEMA_VERSION,
        "incidentId": result.incident_id,
        "wardenSessionId": result.warden_session_id,
        "wardenTaskId": result.warden_task_id,
        "proposalId": result.proposal_id,
    }
