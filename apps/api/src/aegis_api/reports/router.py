"""SCRIBE after-action report HTTP routes."""

from __future__ import annotations

from aegis_agents.roles.scribe.coordinator import ScribeCoordinator
from aegis_agents.runtime.executor import TaskExecutor
from aegis_agents.runtime.factory import create_task_executor
from aegis_api.auth.deps import require_permission
from aegis_api.db.session import get_db_session_maker
from aegis_contracts import PermissionV1
from aegis_contracts.reports import (
    AfterActionReportV1,
    ReportExportFormatV1,
    ReportVersionV1,
    TriggerScribeRequestV1,
)
from aegis_contracts.versioning import AFTER_ACTION_REPORT_SCHEMA_VERSION
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from aegis_reports.errors import ReportError
from aegis_reports.service import ReportService
from fastapi import APIRouter, Depends, HTTPException, Response

router = APIRouter(prefix="/api/v1", tags=["reports"])
_report_service = ReportService()


@router.get("/runs/{run_id}/after-action-report", response_model=AfterActionReportV1)
async def get_after_action_report(
    run_id: str,
    version: int | None = None,
) -> AfterActionReportV1:
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        try:
            return await _report_service.get_report(uow, run_id=run_id, version_number=version)
        except ReportError as exc:
            raise HTTPException(status_code=404, detail=exc.message) from exc


@router.get("/runs/{run_id}/after-action-report/versions", response_model=list[ReportVersionV1])
async def list_after_action_report_versions(run_id: str) -> list[ReportVersionV1]:
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        return await _report_service.list_versions(uow, run_id=run_id)


@router.get(
    "/runs/{run_id}/after-action-report/exports/{export_format}",
    dependencies=[Depends(require_permission(PermissionV1.REPORTS_EXPORT))],
)
async def download_after_action_report_export(
    run_id: str,
    export_format: ReportExportFormatV1,
    version: int | None = None,
) -> Response:
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        try:
            artifact, content = await _report_service.get_export(
                uow,
                run_id=run_id,
                export_format=export_format,
                version_number=version,
            )
        except ReportError as exc:
            raise HTTPException(status_code=404, detail=exc.message) from exc
    headers = {
        "X-AEGIS-Report-Checksum": artifact.checksum,
        "X-AEGIS-Workspace-Version": artifact.workspace_version,
        "X-AEGIS-Report-Schema-Version": str(artifact.report_schema_version),
    }
    return Response(content=content, media_type=artifact.content_type, headers=headers)


@router.post(
    "/runs/{run_id}/investigation/trigger-scribe",
    dependencies=[Depends(require_permission(PermissionV1.REPORTS_TRIGGER))],
)
async def trigger_scribe(run_id: str, request: TriggerScribeRequestV1) -> dict[str, object]:
    if request.run_id != run_id:
        raise HTTPException(status_code=400, detail="runId mismatch")
    coordinator = ScribeCoordinator()
    executor: TaskExecutor = create_task_executor()
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        result = await coordinator.trigger_for_run(uow, request)
        task = await uow.agent_tasks.get_by_id(result.scribe_task_id)
        if task is not None and task.status.value == "queued":
            await executor.execute(uow, task_id=task.id)
        versions = await uow.reports.list_versions(run_id)
        latest = versions[-1] if versions else None
    return {
        "schemaVersion": AFTER_ACTION_REPORT_SCHEMA_VERSION,
        "incidentId": result.incident_id,
        "scribeSessionId": result.scribe_session_id,
        "scribeTaskId": result.scribe_task_id,
        "reportVersionId": latest.id if latest else result.report_version_id,
        "versionNumber": latest.version_number if latest else None,
    }
