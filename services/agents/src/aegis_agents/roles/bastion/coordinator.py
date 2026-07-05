"""BASTION coordinator — trigger response proposal generation."""

from __future__ import annotations

from dataclasses import dataclass

from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_agents.runtime.session_service import AgentSessionService
from aegis_agents.runtime.task_service import AgentTaskService
from aegis_contracts.agent_runtime import CreateAgentSessionRequestV1, CreateAgentTaskRequestV1
from aegis_contracts.entities import AgentRole
from aegis_contracts.proposals import TriggerBastionRequestV1
from aegis_persistence.orm.tables import AgentTaskRow, IncidentRow
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from sqlalchemy import select


@dataclass
class BastionTriggerResult:
    incident_id: str
    bastion_session_id: str
    bastion_task_id: str
    warden_session_id: str | None = None
    warden_task_id: str | None = None


class BastionCoordinator:
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
        request: TriggerBastionRequestV1,
    ) -> BastionTriggerResult:
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
        if not detail.hypotheses:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.TOOL_VALIDATION_FAILED,
                message="BASTION requires ORACLE hypothesis artifacts",
                trace_id=request.trace_id,
            )

        existing = await self._find_task_by_idempotency(uow, incident_id, request.idempotency_key)
        if existing is not None:
            session_id, task_id = existing
            warden = await self._find_warden_task(uow, incident_id, request.idempotency_key)
            return BastionTriggerResult(
                incident_id=incident_id,
                bastion_session_id=session_id,
                bastion_task_id=task_id,
                warden_session_id=warden[0] if warden else None,
                warden_task_id=warden[1] if warden else None,
            )

        bastion_session = await self._sessions.create_session(
            uow,
            incident_id=incident_id,
            request=CreateAgentSessionRequestV1(
                schema_version=1,
                role=AgentRole.BASTION,
                trace_id=request.trace_id,
                enqueue_initial_task=False,
                provider_id=request.provider_id,
            ),
        )
        bastion_task = await self._tasks.create_task(
            uow,
            session=bastion_session,
            request=CreateAgentTaskRequestV1(
                schema_version=1,
                idempotency_key=request.idempotency_key,
                provider_id=request.provider_id,
            ),
        )

        warden_session_id, warden_task_id = await self._enqueue_warden_followup(
            uow,
            incident_id=incident_id,
            trace_id=request.trace_id,
            provider_id=request.provider_id,
            idempotency_key=request.idempotency_key,
        )

        return BastionTriggerResult(
            incident_id=incident_id,
            bastion_session_id=bastion_session.id,
            bastion_task_id=bastion_task.id,
            warden_session_id=warden_session_id,
            warden_task_id=warden_task_id,
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

    async def _find_warden_task(
        self,
        uow: PostgresUnitOfWork,
        incident_id: str,
        idempotency_key: str,
    ) -> tuple[str, str] | None:
        followup_key = f"{idempotency_key}:warden-followup"
        result = await uow.session.execute(
            select(AgentTaskRow.session_id, AgentTaskRow.id).where(
                AgentTaskRow.incident_id == incident_id,
                AgentTaskRow.idempotency_key == followup_key,
            )
        )
        row = result.first()
        if row is None:
            return None
        return row[0], row[1]

    async def _enqueue_warden_followup(
        self,
        uow: PostgresUnitOfWork,
        *,
        incident_id: str,
        trace_id: str,
        provider_id: str,
        idempotency_key: str,
    ) -> tuple[str, str]:
        followup_key = f"{idempotency_key}:warden-followup"
        existing = await self._find_warden_task(uow, incident_id, idempotency_key)
        if existing is not None:
            return existing

        warden_session = await self._sessions.create_session(
            uow,
            incident_id=incident_id,
            request=CreateAgentSessionRequestV1(
                schema_version=1,
                role=AgentRole.WARDEN,
                trace_id=trace_id,
                enqueue_initial_task=False,
                provider_id=provider_id,
            ),
        )
        warden_task = await self._tasks.create_task(
            uow,
            session=warden_session,
            request=CreateAgentTaskRequestV1(
                schema_version=1,
                idempotency_key=followup_key,
                provider_id=provider_id,
            ),
        )
        return warden_session.id, warden_task.id
