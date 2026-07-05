"""WATCHTOWER coordinator — trigger triage and enqueue TRACE."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from aegis_contracts import IncidentState, IncidentV1
from aegis_contracts.agent_runtime import CreateAgentSessionRequestV1, CreateAgentTaskRequestV1
from aegis_contracts.entities import AgentRole, AgentSessionV1, AlertV1
from aegis_contracts.investigation import (
    TriageEscalationLevel,
    TriggerWatchtowerRequestV1,
    WatchtowerTriageResultV1,
)
from aegis_contracts.versioning import (
    INCIDENT_SCHEMA_VERSION,
    WATCHTOWER_TRIAGE_RESULT_SCHEMA_VERSION,
)
from aegis_persistence.mappers import agent_session_to_domain, incident_to_domain
from aegis_persistence.orm.tables import AgentSessionRow, IncidentRow
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from sqlalchemy import select

from aegis_agents.roles.watchtower.correlation import (
    correlate_alerts,
    derive_grouped_and_separated_alert_ids,
)
from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_agents.runtime.ids import new_runtime_id
from aegis_agents.runtime.session_service import AgentSessionService
from aegis_agents.runtime.task_service import AgentTaskService


@dataclass
class WatchtowerTriggerResult:
    incident_id: str
    watchtower_session_id: str
    watchtower_task_id: str
    trace_session_id: str | None
    triage: WatchtowerTriageResultV1


class WatchtowerCoordinator:
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
        request: TriggerWatchtowerRequestV1,
        *,
        triage_output: dict[str, Any] | None = None,
    ) -> WatchtowerTriggerResult:
        alerts = await self._resolve_alerts(uow, request.run_id, request.alert_ids)
        incident = await self._resolve_incident(uow, request.run_id, alerts)

        existing = await uow.investigation.get_triage_by_idempotency(
            incident.id,
            request.idempotency_key,
        )
        if existing is not None:
            trace_session_id = await self._find_trace_session_id(uow, incident.id)
            return WatchtowerTriggerResult(
                incident_id=incident.id,
                watchtower_session_id=existing.session_id,
                watchtower_task_id=existing.task_id,
                trace_session_id=trace_session_id,
                triage=existing,
            )

        watchtower_session = await self._sessions.create_session(
            uow,
            incident_id=incident.id,
            request=CreateAgentSessionRequestV1(
                schema_version=1,
                role=AgentRole.WATCHTOWER,
                trace_id=request.trace_id,
                enqueue_initial_task=False,
                provider_id=request.provider_id,
            ),
        )
        watchtower_task = await self._tasks.create_task(
            uow,
            session=watchtower_session,
            request=CreateAgentTaskRequestV1(
                schema_version=1,
                idempotency_key=request.idempotency_key,
                provider_id=request.provider_id,
            ),
        )

        triage = await self._persist_triage(
            uow,
            incident=incident,
            alerts=alerts,
            session=watchtower_session,
            task_id=watchtower_task.id,
            idempotency_key=request.idempotency_key,
            triage_output=triage_output,
        )
        incident = await self._update_incident(uow, incident, alerts, triage)
        trace_session_id = await self._enqueue_trace_session(
            uow,
            incident_id=incident.id,
            trace_id=request.trace_id,
            provider_id=request.provider_id,
            triage=triage,
            idempotency_key=f"{request.idempotency_key}:trace",
        )

        return WatchtowerTriggerResult(
            incident_id=incident.id,
            watchtower_session_id=watchtower_session.id,
            watchtower_task_id=watchtower_task.id,
            trace_session_id=trace_session_id,
            triage=triage,
        )

    async def _resolve_alerts(
        self,
        uow: PostgresUnitOfWork,
        run_id: str,
        alert_ids: list[str],
    ) -> list[AlertV1]:
        if alert_ids:
            alerts: list[AlertV1] = []
            for alert_id in alert_ids:
                alert = await uow.alerts.get_by_id(alert_id)
                if alert is None or alert.run_id != run_id:
                    raise AgentRuntimeError(
                        code=AgentRuntimeErrorCode.TOOL_VALIDATION_FAILED,
                        message=f"Alert not found for run: {alert_id}",
                        details={"alertId": alert_id, "runId": run_id},
                    )
                alerts.append(alert)
            return sorted(alerts, key=lambda item: (item.created_at, item.id))

        return await uow.alerts.list_by_run(run_id)

    async def _resolve_incident(
        self,
        uow: PostgresUnitOfWork,
        run_id: str,
        alerts: list[AlertV1],
    ) -> IncidentV1:
        incidents = await self._list_incidents_for_run(uow, run_id)
        if incidents:
            return incidents[0]

        now = datetime.now(UTC)
        incident = IncidentV1(
            schema_version=INCIDENT_SCHEMA_VERSION,
            id=new_runtime_id("inc"),
            run_id=run_id,
            title=self._incident_title(alerts),
            state=IncidentState.OPEN,
            alert_ids=[alert.id for alert in alerts],
            revision=0,
            created_at=now,
            updated_at=now,
        )
        return await uow.incidents.add(incident)

    async def _list_incidents_for_run(
        self,
        uow: PostgresUnitOfWork,
        run_id: str,
    ) -> list[IncidentV1]:
        result = await uow.session.execute(
            select(IncidentRow)
            .where(IncidentRow.run_id == run_id)
            .order_by(IncidentRow.created_at.asc())
        )
        return [incident_to_domain(row) for row in result.scalars().all()]

    def _incident_title(self, alerts: list[AlertV1]) -> str:
        if not alerts:
            return "Investigation incident"
        if len(alerts) == 1:
            return alerts[0].title
        return f"Correlated incident ({len(alerts)} alerts)"

    async def _persist_triage(
        self,
        uow: PostgresUnitOfWork,
        *,
        incident: IncidentV1,
        alerts: list[AlertV1],
        session: AgentSessionV1,
        task_id: str,
        idempotency_key: str,
        triage_output: dict[str, Any] | None,
    ) -> WatchtowerTriageResultV1:
        correlation_decisions = correlate_alerts(alerts)
        grouped_alert_ids, separated_alert_ids = derive_grouped_and_separated_alert_ids(
            alerts,
            correlation_decisions,
        )
        output = triage_output or {}
        escalation = TriageEscalationLevel(output.get("escalation", "investigate"))
        evidence_ids = [
            item["evidenceId"]
            for item in output.get("evidenceCitations", [])
            if isinstance(item, dict) and "evidenceId" in item
        ]
        now = datetime.now(UTC)
        triage = WatchtowerTriageResultV1(
            schema_version=WATCHTOWER_TRIAGE_RESULT_SCHEMA_VERSION,
            id=new_runtime_id("wtri"),
            incident_id=incident.id,
            run_id=incident.run_id,
            session_id=session.id,
            task_id=task_id,
            alert_summaries=[
                {
                    "alertId": alert.id,
                    "title": alert.title,
                    "severity": alert.severity,
                    "assetId": alert.asset_id,
                }
                for alert in alerts
            ],
            grouped_alert_ids=grouped_alert_ids,
            separated_alert_ids=separated_alert_ids,
            correlation_decisions=correlation_decisions,
            escalation=escalation,
            escalation_rationale=output.get(
                "escalationRationale",
                "Deterministic correlation completed; investigation recommended.",
            ),
            confidence=float(output.get("confidence", 0.7)),
            evidence_ids=evidence_ids,
            idempotency_key=idempotency_key,
            created_at=now,
        )
        return await uow.investigation.add_triage(triage)

    async def _update_incident(
        self,
        uow: PostgresUnitOfWork,
        incident: IncidentV1,
        alerts: list[AlertV1],
        triage: WatchtowerTriageResultV1,
    ) -> IncidentV1:
        now = datetime.now(UTC)
        alert_ids = sorted({*incident.alert_ids, *(alert.id for alert in alerts)})
        next_state = IncidentState.TRIAGED
        if triage.escalation == TriageEscalationLevel.URGENT:
            next_state = IncidentState.INVESTIGATING
        updated = incident.model_copy(
            update={
                "alert_ids": alert_ids,
                "state": next_state,
                "revision": incident.revision + 1,
                "updated_at": now,
            }
        )
        return await uow.incidents.update_with_revision(
            updated,
            expected_revision=incident.revision,
        )

    async def _enqueue_trace_session(
        self,
        uow: PostgresUnitOfWork,
        *,
        incident_id: str,
        trace_id: str,
        provider_id: str,
        triage: WatchtowerTriageResultV1,
        idempotency_key: str,
    ) -> str | None:
        if triage.escalation == TriageEscalationLevel.MONITOR:
            return None

        trace_session = await self._sessions.create_session(
            uow,
            incident_id=incident_id,
            request=CreateAgentSessionRequestV1(
                schema_version=1,
                role=AgentRole.TRACE,
                trace_id=trace_id,
                enqueue_initial_task=True,
                provider_id=provider_id,
            ),
        )
        await self._tasks.create_task(
            uow,
            session=trace_session,
            request=CreateAgentTaskRequestV1(
                schema_version=1,
                idempotency_key=idempotency_key,
                provider_id=provider_id,
            ),
        )
        return trace_session.id

    async def _find_trace_session_id(
        self,
        uow: PostgresUnitOfWork,
        incident_id: str,
    ) -> str | None:
        result = await uow.session.execute(
            select(AgentSessionRow)
            .where(AgentSessionRow.incident_id == incident_id)
            .order_by(AgentSessionRow.created_at.asc())
        )
        sessions = [agent_session_to_domain(row) for row in result.scalars().all()]
        for session in reversed(sessions):
            if session.role == AgentRole.TRACE:
                return session.id
        return None
