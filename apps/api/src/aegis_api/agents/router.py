"""Agent runtime HTTP routes."""

from __future__ import annotations

import contextlib
from typing import Annotated

from aegis_agents.runtime.errors import AgentRuntimeError
from aegis_agents.runtime.factory import create_task_executor
from aegis_agents.runtime.harness import seed_harness_incident
from aegis_agents.runtime.registry import DEFAULT_AGENT_REGISTRY
from aegis_agents.runtime.session_service import AgentSessionService
from aegis_agents.runtime.task_service import AgentTaskService
from aegis_agents.tools.registry import DEFAULT_TOOL_REGISTRY
from aegis_api.auth.deps import require_actor, require_permission
from aegis_api.auth.run_authz import require_run_access
from aegis_api.db.session import get_db_session_maker
from aegis_contracts import AuthenticatedActorV1, PermissionV1
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
# Read-only listing (restores the chat thread on reload); owner-or-admin still
# enforced in-handler via require_run_access.
_READ = [Depends(require_permission(PermissionV1.INVESTIGATION_READ))]


async def _execute_committing_failure(task_id: str) -> None:
    """Run a task inline and persist terminal failures for these interactive routes.

    ``TaskExecutor.execute`` writes a FAILED/TIMED_OUT task and then re-raises so
    the worker/CLI can react, but a raised exception rolls the UnitOfWork back
    (losing the failed status) and surfaces as a 500. The chat needs the failed
    turn to persist and be returned, so here we swallow the runtime error inside
    the UnitOfWork — the executor already wrote the terminal state into it, and the
    context manager commits it on clean exit. Non-runtime errors still propagate.
    """
    executor = create_task_executor(force_in_memory=False)
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        with contextlib.suppress(AgentRuntimeError):
            await executor.execute(uow, task_id)


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
        await _execute_committing_failure(queued.id)
        async with PostgresUnitOfWork(get_db_session_maker()) as uow:
            return await sessions.get_detail(uow, session.id)
    return detail


@router.post(
    "/runs/{run_id}/agent-sessions",
    response_model=AgentSessionDetailV1,
    dependencies=_TRIGGER,
)
async def create_run_agent_session(
    run_id: str,
    request: CreateAgentSessionRequestV1,
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
) -> AgentSessionDetailV1:
    """Create a run-scoped agent session (operator tasking, no incident). ADR 0035.

    Ownership-gated like every other run-scoped route: 404 on unknown run, 403
    when the caller is neither owner nor admin.
    """
    if request.schema_version != CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION:
        raise HTTPException(status_code=400, detail="Unsupported schema version")
    sessions = AgentSessionService()
    tasks = AgentTaskService()
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        await require_run_access(uow, run_id, actor)
        session = await sessions.create_run_session(uow, run_id=run_id, request=request)
        if request.enqueue_initial_task:
            await tasks.create_task(
                uow,
                session=session,
                request=CreateAgentTaskRequestV1(
                    schema_version=CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
                    idempotency_key=f"initial-{session.id}",
                    provider_id=request.provider_id,
                    instructions=request.instructions,
                ),
            )
        detail = await sessions.get_detail(uow, session.id)
    if request.enqueue_initial_task:
        queued = next(task for task in detail.tasks if task.status.value == "queued")
        await _execute_committing_failure(queued.id)
        async with PostgresUnitOfWork(get_db_session_maker()) as uow:
            return await sessions.get_detail(uow, session.id)
    return detail


@router.get("/runs/{run_id}/agent-sessions", dependencies=_READ)
async def list_run_agent_sessions(
    run_id: str,
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
) -> dict[str, object]:
    """List every agent session anchored to ``run_id`` (restores chat threads)."""
    sessions = AgentSessionService()
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        await require_run_access(uow, run_id, actor)
        details = await sessions.list_details_for_run(uow, run_id)
    return {
        "sessions": [detail.model_dump(by_alias=True, mode="json") for detail in details]
    }


@router.get("/agent-sessions/{session_id}", response_model=AgentSessionDetailV1)
async def get_agent_session(session_id: str) -> AgentSessionDetailV1:
    sessions = AgentSessionService()
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        return await sessions.get_detail(uow, session_id)


@router.post("/agent-sessions/{session_id}/tasks", dependencies=_TRIGGER)
async def create_agent_task(
    session_id: str,
    request: CreateAgentTaskRequestV1,
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
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
        # Tasking an agent writes state / runs the model; gate it on ownership of
        # the session's run (owner-or-admin) as the run-scoped routes do.
        await require_run_access(uow, session.run_id, actor)
        task = await tasks.create_task(uow, session=session, request=request)
        task_id = task.id
    await _execute_committing_failure(task_id)
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
    await _execute_committing_failure(task.id)
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        completed = await tasks.get_task(uow, task.id)
        return completed.model_dump(by_alias=True, mode="json")
