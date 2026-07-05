"""WARDEN coordinator — trigger policy evaluation for proposals."""

from __future__ import annotations

from dataclasses import dataclass

from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_agents.runtime.session_service import AgentSessionService
from aegis_agents.runtime.task_service import AgentTaskService
from aegis_contracts.agent_runtime import CreateAgentSessionRequestV1, CreateAgentTaskRequestV1
from aegis_contracts.entities import AgentRole
from aegis_contracts.proposals import TriggerWardenRequestV1
from aegis_persistence.orm.tables import AgentTaskRow, IncidentRow
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from sqlalchemy import select


@dataclass
class WardenTriggerResult:
    incident_id: str
    warden_session_id: str
    warden_task_id: str
    proposal_id: str | None = None


class WardenCoordinator:
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
        request: TriggerWardenRequestV1,
    ) -> WardenTriggerResult:
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

        proposals = await uow.proposals.list_proposals_for_incident(incident_id)
        if not proposals:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.TOOL_VALIDATION_FAILED,
                message="WARDEN requires at least one action proposal",
                trace_id=request.trace_id,
            )

        idempotency_key = request.idempotency_key
        if request.proposal_id:
            idempotency_key = f"{request.idempotency_key}:{request.proposal_id}"

        existing = await self._find_task_by_idempotency(uow, incident_id, idempotency_key)
        if existing is not None:
            session_id, task_id = existing
            return WardenTriggerResult(
                incident_id=incident_id,
                warden_session_id=session_id,
                warden_task_id=task_id,
                proposal_id=request.proposal_id,
            )

        warden_session = await self._sessions.create_session(
            uow,
            incident_id=incident_id,
            request=CreateAgentSessionRequestV1(
                schema_version=1,
                role=AgentRole.WARDEN,
                trace_id=request.trace_id,
                enqueue_initial_task=False,
                provider_id=request.provider_id,
            ),
        )
        warden_task = await self._tasks.create_task(
            uow,
            session=warden_session,
            request=CreateAgentTaskRequestV1(
                schema_version=1,
                idempotency_key=idempotency_key,
                provider_id=request.provider_id,
            ),
        )
        return WardenTriggerResult(
            incident_id=incident_id,
            warden_session_id=warden_session.id,
            warden_task_id=warden_task.id,
            proposal_id=request.proposal_id,
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
