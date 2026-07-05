"""ORACLE coordinator — trigger hypothesis generation after investigation."""

from __future__ import annotations

from dataclasses import dataclass

from aegis_contracts.agent_runtime import CreateAgentSessionRequestV1, CreateAgentTaskRequestV1
from aegis_contracts.entities import AgentRole
from aegis_contracts.hypothesis import TriggerOracleRequestV1
from aegis_persistence.orm.tables import AgentSessionRow, AgentTaskRow, IncidentRow
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from sqlalchemy import select

from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_agents.runtime.session_service import AgentSessionService
from aegis_agents.runtime.task_service import AgentTaskService


@dataclass
class OracleTriggerResult:
    incident_id: str
    oracle_session_id: str
    oracle_task_id: str
    trace_session_id: str | None = None


class OracleCoordinator:
    def __init__(
        self,
        *,
        session_service: AgentSessionService | None = None,
        task_service: AgentTaskService | None = None,
    ) -> None:
        self._sessions = session_service or AgentSessionService()
        self._tasks = task_service or AgentTaskService()

    async def trigger_for_run(
        self,
        uow: PostgresUnitOfWork,
        request: TriggerOracleRequestV1,
    ) -> OracleTriggerResult:
        incident_id = request.incident_id
        if incident_id is None:
            result = await uow.session.execute(
                select(IncidentRow).where(IncidentRow.run_id == request.run_id)
            )
            row = result.scalars().first()
            if row is None:
                raise AgentRuntimeError(
                    code=AgentRuntimeErrorCode.VALIDATION_FAILED,
                    message="No incident found for run",
                    trace_id=request.trace_id,
                )
            incident_id = row.id

        detail = await uow.investigation.get_detail(incident_id, request.run_id)
        if not detail.triage_results:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.VALIDATION_FAILED,
                message="ORACLE requires WATCHTOWER triage artifacts",
                trace_id=request.trace_id,
            )

        existing = await self._find_task_by_idempotency(uow, incident_id, request.idempotency_key)
        if existing is not None:
            session_id, task_id = existing
            trace_session_id = await self._find_trace_session_id(uow, incident_id)
            return OracleTriggerResult(
                incident_id=incident_id,
                oracle_session_id=session_id,
                oracle_task_id=task_id,
                trace_session_id=trace_session_id,
            )

        oracle_session = await self._sessions.create_session(
            uow,
            incident_id=incident_id,
            request=CreateAgentSessionRequestV1(
                schema_version=1,
                role=AgentRole.ORACLE,
                trace_id=request.trace_id,
                enqueue_initial_task=False,
                provider_id=request.provider_id,
            ),
        )
        oracle_task = await self._tasks.create_task(
            uow,
            session=oracle_session,
            request=CreateAgentTaskRequestV1(
                schema_version=1,
                idempotency_key=request.idempotency_key,
                provider_id=request.provider_id,
            ),
        )

        trace_session_id = await self._enqueue_trace_followup(
            uow,
            incident_id=incident_id,
            trace_id=request.trace_id,
            provider_id=request.provider_id,
            idempotency_key=request.idempotency_key,
        )

        return OracleTriggerResult(
            incident_id=incident_id,
            oracle_session_id=oracle_session.id,
            oracle_task_id=oracle_task.id,
            trace_session_id=trace_session_id,
        )

    async def _find_task_by_idempotency(
        self,
        uow: PostgresUnitOfWork,
        incident_id: str,
        idempotency_key: str,
    ) -> tuple[str, str] | None:
        result = await uow.session.execute(
            select(AgentTaskRow.session_id, AgentTaskRow.id).where(
                AgentTaskRow.incident_id == incident_id,
                AgentTaskRow.idempotency_key == idempotency_key,
            )
        )
        row = result.first()
        if row is None:
            return None
        return row[0], row[1]

    async def _find_trace_session_id(self, uow: PostgresUnitOfWork, incident_id: str) -> str | None:
        result = await uow.session.execute(
            select(AgentSessionRow.id).where(
                AgentSessionRow.incident_id == incident_id,
            )
        )
        for session_id in result.scalars().all():
            session = await uow.agent_sessions.get_by_id(session_id)
            if session is not None and session.role == AgentRole.TRACE:
                return session.id
        return None

    async def _enqueue_trace_followup(
        self,
        uow: PostgresUnitOfWork,
        *,
        incident_id: str,
        trace_id: str,
        provider_id: str,
        idempotency_key: str,
    ) -> str | None:
        existing_trace = await self._find_trace_session_id(uow, incident_id)
        followup_key = f"{idempotency_key}:trace-followup"
        if existing_trace is not None:
            existing_task = await uow.agent_tasks.get_by_idempotency(
                session_id=existing_trace,
                idempotency_key=followup_key,
            )
            if existing_task is not None:
                return existing_trace

        trace_session = await self._sessions.create_session(
            uow,
            incident_id=incident_id,
            request=CreateAgentSessionRequestV1(
                schema_version=1,
                role=AgentRole.TRACE,
                trace_id=trace_id,
                enqueue_initial_task=False,
                provider_id=provider_id,
            ),
        )
        await self._tasks.create_task(
            uow,
            session=trace_session,
            request=CreateAgentTaskRequestV1(
                schema_version=1,
                idempotency_key=followup_key,
                provider_id=provider_id,
            ),
        )
        return trace_session.id
