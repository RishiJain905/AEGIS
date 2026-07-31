"""SCRIBE coordinator — trigger after-action report generation.

Two entry points, deliberately separated:

* :meth:`ScribeCoordinator.trigger_for_run` is the **strict** path used by the explicit
  operator action (``POST /runs/{id}/investigation/trigger-scribe``). It refuses to run
  when the incident has no WATCHTOWER / ORACLE / BASTION artifacts, because an operator
  asking for an agent narrative should be told the investigation is incomplete rather than
  handed something the agents never wrote.
* :meth:`ScribeCoordinator.ensure_report_for_run` is the **best-effort** path used by run
  finalization. When the strict prerequisites hold it delegates to the strict path
  unchanged; when they do not it falls back to a deterministic report assembled from
  persisted run state (events, alerts, evidence, proposals, policy decisions), labelled
  ``generation_mode = deterministic`` so nothing reads as agent-authored.

The split exists so the fallback cannot weaken the strict path by accident: loosening
``trigger_for_run`` would have made the operator-facing trigger silently produce
template-only reports too.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum

from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_agents.runtime.session_service import AgentSessionService
from aegis_agents.runtime.task_service import AgentTaskService
from aegis_contracts.agent_runtime import CreateAgentSessionRequestV1, CreateAgentTaskRequestV1
from aegis_contracts.entities import AgentRole
from aegis_contracts.investigation import InvestigationDetailV1
from aegis_contracts.reports import TriggerScribeRequestV1
from aegis_persistence.orm.tables import AgentTaskRow, IncidentRow
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from aegis_reports.service import ReportService
from sqlalchemy import select

logger = logging.getLogger(__name__)


@dataclass
class ScribeTriggerResult:
    incident_id: str
    scribe_session_id: str
    scribe_task_id: str
    report_version_id: str | None = None


class ScribeReportOutcome(StrEnum):
    """What :meth:`ScribeCoordinator.ensure_report_for_run` actually did."""

    #: Prerequisites held; a SCRIBE agent task was queued for the caller to execute.
    AGENT_TASK_QUEUED = "agent_task_queued"
    #: Prerequisites missing; a deterministic report was written from persisted state.
    DETERMINISTIC = "deterministic"
    #: A report already existed for this run; nothing was written (idempotent re-run).
    ALREADY_REPORTED = "already_reported"
    #: The run never produced an incident, so there is nothing to report on.
    SKIPPED_NO_INCIDENT = "skipped_no_incident"


@dataclass
class ScribeEnsureResult:
    outcome: ScribeReportOutcome
    incident_id: str | None = None
    scribe_session_id: str | None = None
    scribe_task_id: str | None = None
    report_version_id: str | None = None


def _has_full_investigation(detail: InvestigationDetailV1) -> bool:
    """The artifacts the LLM narrative path grounds against."""
    return bool(detail.triage_results and detail.hypotheses and detail.proposals)


class ScribeCoordinator:
    def __init__(
        self,
        *,
        session_service: AgentSessionService | None = None,
        task_service: AgentTaskService | None = None,
        report_service: ReportService | None = None,
    ) -> None:
        self._sessions = session_service or AgentSessionService()
        self._tasks = task_service or AgentTaskService()
        self._reports = report_service or ReportService()

    async def ensure_report_for_run(
        self,
        uow: PostgresUnitOfWork,
        request: TriggerScribeRequestV1,
    ) -> ScribeEnsureResult:
        """Guarantee a stopped run ends with *some* after-action report.

        Never raises for the ordinary "nothing to narrate" shapes — a run with no
        incident, or no agent artifacts, is a normal outcome of an unattended run, not an
        error. Genuine faults (a broken repository, a contract violation) still propagate;
        the finalization caller keeps its own best-effort guard around those.
        """
        incident_id = await self._resolve_incident_id(uow, request)
        if incident_id is None:
            logger.info(
                "After-action report skipped for run %s: no incident was ever raised",
                request.run_id,
            )
            return ScribeEnsureResult(outcome=ScribeReportOutcome.SKIPPED_NO_INCIDENT)

        detail = await uow.investigation.get_detail(incident_id, request.run_id)
        if _has_full_investigation(detail):
            # Prerequisites hold: use the strict path untouched, including its own
            # idempotency-key dedup, so the LLM narrative is still what gets produced.
            result = await self.trigger_for_run(uow, request)
            return ScribeEnsureResult(
                outcome=ScribeReportOutcome.AGENT_TASK_QUEUED,
                incident_id=result.incident_id,
                scribe_session_id=result.scribe_session_id,
                scribe_task_id=result.scribe_task_id,
                report_version_id=result.report_version_id,
            )

        return await self.ensure_deterministic_report(uow, request, incident_id=incident_id)

    async def ensure_deterministic_report(
        self,
        uow: PostgresUnitOfWork,
        request: TriggerScribeRequestV1,
        *,
        incident_id: str | None = None,
    ) -> ScribeEnsureResult:
        """Write a deterministic report for the run unless one already exists.

        Also usable as a safety net after the agent path: finalization calls it once more
        when a queued SCRIBE task failed, so an unreachable provider degrades to a
        template report instead of leaving the after-action surface empty.
        """
        resolved = incident_id or await self._resolve_incident_id(uow, request)
        if resolved is None:
            return ScribeEnsureResult(outcome=ScribeReportOutcome.SKIPPED_NO_INCIDENT)

        # Idempotency: the deterministic fallback exists only to stop the after-action
        # surface being empty. If any version already exists — an earlier finalization, or
        # a real SCRIBE narrative — re-running must add nothing.
        existing = await uow.reports.list_versions(request.run_id)
        if existing:
            return ScribeEnsureResult(
                outcome=ScribeReportOutcome.ALREADY_REPORTED,
                incident_id=resolved,
                report_version_id=existing[-1].id,
            )

        _report, version, _exports = await self._reports.generate_report(
            uow,
            run_id=request.run_id,
            incident_id=resolved,
            session_id=None,
            task_id=None,
            trace_id=request.trace_id,
            provider_id=None,
            prompt_version=None,
            narrative_claims=None,
        )
        logger.info(
            "Deterministic after-action report %s written for run %s",
            version.id,
            request.run_id,
        )
        return ScribeEnsureResult(
            outcome=ScribeReportOutcome.DETERMINISTIC,
            incident_id=resolved,
            report_version_id=version.id,
        )

    async def _resolve_incident_id(
        self,
        uow: PostgresUnitOfWork,
        request: TriggerScribeRequestV1,
    ) -> str | None:
        if request.incident_id is not None:
            return request.incident_id
        # Oldest-first so repeated finalizations of a multi-incident run pick the same one.
        incidents = await uow.incidents.list_by_run(request.run_id)
        return incidents[0].id if incidents else None

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
