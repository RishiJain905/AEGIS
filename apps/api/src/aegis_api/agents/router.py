"""Agent runtime HTTP routes."""

from __future__ import annotations

from aegis_agents.runtime.factory import create_task_executor
from aegis_agents.runtime.harness import seed_harness_incident
from aegis_agents.runtime.registry import DEFAULT_AGENT_REGISTRY
from aegis_agents.runtime.session_service import AgentSessionService
from aegis_agents.runtime.task_service import AgentTaskService
from aegis_agents.tools.registry import DEFAULT_TOOL_REGISTRY
from aegis_api.auth.deps import require_permission
from aegis_api.db.session import get_db_session_maker
from aegis_contracts import PermissionV1
from aegis_contracts.agent_runtime import (
    AgentSessionDetailV1,
    CreateAgentSessionRequestV1,
    CreateAgentTaskRequestV1,
)
from aegis_contracts.versioning import (
    CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
    CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
)
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from fastapi import APIRouter, Depends, Header, HTTPException

router = APIRouter(prefix="/api/v1", tags=["agents"])

# Agent seeding, session/task creation, cancel and retry all write authoritative
# state or execute an agent (bypassing the proposal/approval trust model if
# unguarded). They are investigation write actions — reuse investigation:trigger so
# a read-only VIEWER cannot enqueue/execute agents. GET routes stay investigation:read.
_TRIGGER = [Depends(require_permission(PermissionV1.INVESTIGATION_TRIGGER))]


@router.get("/agents/registry")
async def list_agent_registry() -> dict[str, object]:
    return {
        "definitions": [
            item.model_dump(by_alias=True, mode="json")
            for item in DEFAULT_AGENT_REGISTRY.list_definitions()
        ],
        "tools": [
            item.model_dump(by_alias=True, mode="json")
            for item in DEFAULT_TOOL_REGISTRY.list_definitions()
        ],
    }


@router.post("/agents/harness/seed", dependencies=_TRIGGER)
async def seed_agent_harness() -> dict[str, str]:
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        incident_id = await seed_harness_incident(uow)
    return {"incidentId": incident_id}


@router.post(
    "/incidents/{incident_id}/agent-sessions",
    response_model=AgentSessionDetailV1,
    dependencies=_TRIGGER,
)
async def create_agent_session(
    incident_id: str,
    request: CreateAgentSessionRequestV1,
) -> AgentSessionDetailV1:
    if request.schema_version != CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION:
        raise HTTPException(status_code=400, detail="Unsupported schema version")
    sessions = AgentSessionService()
    tasks = AgentTaskService()
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        session = await sessions.create_session(uow, incident_id=incident_id, request=request)
        if request.enqueue_initial_task:
            await tasks.create_task(
                uow,
                session=session,
                request=CreateAgentTaskRequestV1(
                    schema_version=CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
                    idempotency_key=f"initial-{session.id}",
                    provider_id=request.provider_id,
                ),
            )
        detail = await sessions.get_detail(uow, session.id)
    if request.enqueue_initial_task:
        queued = next(task for task in detail.tasks if task.status.value == "queued")
        executor = create_task_executor(force_in_memory=False)
        async with PostgresUnitOfWork(get_db_session_maker()) as uow:
            await executor.execute(uow, queued.id)
        async with PostgresUnitOfWork(get_db_session_maker()) as uow:
            return await sessions.get_detail(uow, session.id)
    return detail


@router.get("/agent-sessions/{session_id}", response_model=AgentSessionDetailV1)
async def get_agent_session(session_id: str) -> AgentSessionDetailV1:
    sessions = AgentSessionService()
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        return await sessions.get_detail(uow, session_id)


@router.post("/agent-sessions/{session_id}/tasks", dependencies=_TRIGGER)
async def create_agent_task(
    session_id: str,
    request: CreateAgentTaskRequestV1,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, object]:
    if request.schema_version != CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION:
        raise HTTPException(status_code=400, detail="Unsupported schema version")
    if idempotency_key:
        request = request.model_copy(update={"idempotency_key": idempotency_key})
    tasks = AgentTaskService()
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        session = await uow.agent_sessions.get_by_id(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Agent session not found")
        task = await tasks.create_task(uow, session=session, request=request)
        task_id = task.id
    executor = create_task_executor(force_in_memory=False)
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        await executor.execute(uow, task_id)
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        completed = await tasks.get_task(uow, task_id)
        return completed.model_dump(by_alias=True, mode="json")


@router.post("/agent-sessions/{session_id}/cancel", dependencies=_TRIGGER)
async def cancel_agent_session(session_id: str) -> dict[str, object]:
    sessions = AgentSessionService()
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        session = await sessions.cancel(uow, session_id)
        return session.model_dump(by_alias=True, mode="json")


@router.post("/agent-tasks/{task_id}/retry", dependencies=_TRIGGER)
async def retry_agent_task(task_id: str) -> dict[str, object]:
    tasks = AgentTaskService()
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        task = await tasks.retry_task(uow, task_id)
    executor = create_task_executor(force_in_memory=False)
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        await executor.execute(uow, task.id)
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        completed = await tasks.get_task(uow, task.id)
        return completed.model_dump(by_alias=True, mode="json")
