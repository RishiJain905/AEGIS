"""SCRIBE coordinator — trigger after-action report generation."""

from __future__ import annotations

from dataclasses import dataclass

from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_agents.runtime.session_service import AgentSessionService
from aegis_agents.runtime.task_service import AgentTaskService
from aegis_contracts.agent_runtime import CreateAgentSessionRequestV1, CreateAgentTaskRequestV1
from aegis_contracts.entities import AgentRole
from aegis_contracts.reports import TriggerScribeRequestV1
from aegis_persistence.orm.tables import AgentTaskRow, IncidentRow
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from sqlalchemy import select


@dataclass
class ScribeTriggerResult:
    incident_id: str
    scribe_session_id: str
    scribe_task_id: str
    report_version_id: str | None = None


class ScribeCoordinator:
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
        request: TriggerScribeRequestV1,
    ) -> ScribeTriggerResult:
        incident_id = request.incident_id
        if incident_id is None:
            result = await uow.session.execute(
                select(IncidentRow).where(IncidentRow.run_id == request.run_id)
            )
            row = result.scalars().first()
            if row is None:
                raise AgentRuntimeError(
                    code=AgentRuntimeErrorCode.INCIDENT_NOT_FOUND,
                    message="No incident found for run",
                    trace_id=request.trace_id,
                )
            incident_id = row.id

        detail = await uow.investigation.get_detail(incident_id, request.run_id)
        if not detail.triage_results:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.TOOL_VALIDATION_FAILED,
                message="SCRIBE requires WATCHTOWER triage artifacts",
                trace_id=request.trace_id,
            )
        if not detail.hypotheses:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.TOOL_VALIDATION_FAILED,
                message="SCRIBE requires ORACLE hypothesis artifacts",
                trace_id=request.trace_id,
            )
        if not detail.proposals:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.TOOL_VALIDATION_FAILED,
                message="SCRIBE requires BASTION proposal artifacts",
                trace_id=request.trace_id,
            )

        existing = await self._find_task_by_idempotency(uow, incident_id, request.idempotency_key)
        if existing is not None:
            session_id, task_id = existing
            versions = await uow.reports.list_versions(request.run_id)
            latest = versions[-1] if versions else None
            return ScribeTriggerResult(
                incident_id=incident_id,
                scribe_session_id=session_id,
                scribe_task_id=task_id,
                report_version_id=latest.id if latest else None,
            )

        scribe_session = await self._sessions.create_session(
            uow,
            incident_id=incident_id,
            request=CreateAgentSessionRequestV1(
                schema_version=1,
                role=AgentRole.SCRIBE,
                trace_id=request.trace_id,
                enqueue_initial_task=False,
                provider_id=request.provider_id,
            ),
        )
        scribe_task = await self._tasks.create_task(
            uow,
            session=scribe_session,
            request=CreateAgentTaskRequestV1(
                schema_version=1,
                idempotency_key=request.idempotency_key,
                provider_id=request.provider_id,
            ),
        )
        return ScribeTriggerResult(
            incident_id=incident_id,
            scribe_session_id=scribe_session.id,
            scribe_task_id=scribe_task.id,
        )

    async def _find_task_by_idempotency(
        self,
        uow: PostgresUnitOfWork,
        incident_id: str,
        idempotency_key: str,
    ) -> tuple[str, str] | None:
        result = await uow.session.execute(
            select(AgentTaskRow)
            .where(AgentTaskRow.incident_id == incident_id)
            .where(AgentTaskRow.idempotency_key == idempotency_key)
            .limit(1)
        )
        row = result.scalars().first()
        if row is None:
            return None
        return row.session_id, row.id
