"""Report generation orchestration service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aegis_contracts.persistence import ObjectMetadataReferenceV1
from aegis_contracts.reports import (
    AfterActionReportV1,
    ReportExportArtifactV1,
    ReportExportFormatV1,
    ReportGenerationStatusV1,
    ReportVersionV1,
)
from aegis_contracts.versioning import (
    OBJECT_METADATA_REFERENCE_SCHEMA_VERSION,
    REPORT_EXPORT_ARTIFACT_SCHEMA_VERSION,
    REPORT_VERSION_SCHEMA_VERSION,
    WORKSPACE_VERSION,
)
from aegis_persistence.mappers import report_export_artifact_to_domain
from aegis_persistence.unit_of_work import PostgresUnitOfWork

from aegis_reports.assembler import assemble_report_source
from aegis_reports.errors import ReportError, ReportErrorCode
from aegis_reports.events import (
    build_report_generation_completed_event,
    build_report_version_created_event,
)
from aegis_reports.export import checksum_bytes, render_export
from aegis_reports.grounding import ground_narrative_claims
from aegis_reports.ids import new_runtime_id
from aegis_reports.template import build_template_report


def _default_new_report_id(prefix: str = "aar") -> str:
    return new_runtime_id(prefix)


class ReportService:
    async def generate_report(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        incident_id: str,
        session_id: str | None = None,
        task_id: str | None = None,
        trace_id: str,
        provider_id: str | None = None,
        prompt_version: str | None = None,
        narrative_claims: list[dict[str, Any]] | None = None,
        regenerate: bool = False,
        new_runtime_id_fn=_default_new_report_id,
    ) -> tuple[AfterActionReportV1, ReportVersionV1, list[ReportExportArtifactV1]]:
        incident = await uow.incidents.get_by_id(incident_id)
        if incident is None:
            raise ReportError(
                code=ReportErrorCode.INCIDENT_NOT_FOUND,
                message=f"Incident not found: {incident_id}",
                trace_id=trace_id,
            )

        source, _events = await assemble_report_source(
            uow,
            run_id=run_id,
            incident_id=incident_id,
        )
        investigation = await uow.investigation.get_detail(incident_id, run_id)
        latest_version = await uow.reports.latest_version_number(run_id)
        version_number = latest_version + 1

        grounding_fallback = False
        report_id = new_runtime_id_fn("aar")
        template_report = build_template_report(
            report_id=report_id,
            version_number=version_number,
            source=source,
            investigation=investigation,
            session_id=session_id,
            task_id=task_id,
            provider_id=provider_id,
            prompt_version=prompt_version,
        )

        if narrative_claims:
            grounding = ground_narrative_claims(
                structured_claims=narrative_claims,
                source=source,
            )
            if grounding.grounding_failed or grounding.rejected_claim_count > 0:
                grounding_fallback = True
                report = template_report.model_copy(update={"grounding_fallback": True})
            else:
                report = template_report.model_copy(
                    update={
                        "claims": template_report.claims + grounding.claims,
                        "grounding_fallback": False,
                    }
                )
        else:
            report = template_report

        status = (
            ReportGenerationStatusV1.GROUNDING_FALLBACK
            if grounding_fallback
            else ReportGenerationStatusV1.COMPLETED
        )
        version_id = new_runtime_id_fn("rpv")
        version = ReportVersionV1(
            schema_version=REPORT_VERSION_SCHEMA_VERSION,
            id=version_id,
            run_id=run_id,
            incident_id=incident_id,
            version_number=version_number,
            report_id=report.id,
            status=status,
            source_sequence_from=source.source_sequence_from,
            source_sequence_to=source.source_sequence_to,
            provider_id=provider_id,
            prompt_version=prompt_version,
            session_id=session_id,
            task_id=task_id,
            checksum=report.checksum,
            grounding_fallback=grounding_fallback,
            created_at=datetime.now(UTC),
        )

        await uow.reports.add_version(version, report)
        exports = await self._persist_exports(
            uow,
            report=report,
            version=version,
            new_runtime_id_fn=new_runtime_id_fn,
        )

        next_sequence = await uow.events.next_sequence(run_id)
        await uow.append_event(
            build_report_version_created_event(
                event_id=new_runtime_id_fn("evt"),
                run_id=run_id,
                sequence=next_sequence,
                session_id=session_id,
                task_id=task_id,
                trace_id=trace_id,
                incident_id=incident_id,
                report_version_id=version.id,
                version_number=version.version_number,
                checksum=version.checksum,
            )
        )
        next_sequence = await uow.events.next_sequence(run_id)
        await uow.append_event(
            build_report_generation_completed_event(
                event_id=new_runtime_id_fn("evt"),
                run_id=run_id,
                sequence=next_sequence,
                session_id=session_id,
                task_id=task_id,
                trace_id=trace_id,
                incident_id=incident_id,
                report_version_id=version.id,
                grounding_fallback=grounding_fallback,
            )
        )
        return report, version, exports

    async def get_report(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        version_number: int | None = None,
    ) -> AfterActionReportV1:
        report = await uow.reports.get_report(run_id, version_number=version_number)
        if report is None:
            raise ReportError(
                code=ReportErrorCode.REPORT_NOT_FOUND,
                message=f"No report found for run {run_id}",
            )
        return report

    async def list_versions(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
    ) -> list[ReportVersionV1]:
        return await uow.reports.list_versions(run_id)

    async def get_export(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        export_format: ReportExportFormatV1,
        version_number: int | None = None,
    ) -> tuple[ReportExportArtifactV1, bytes]:
        artifact_row = await uow.reports.get_export(
            run_id,
            export_format=export_format.value,
            version_number=version_number,
        )
        if artifact_row is None:
            raise ReportError(
                code=ReportErrorCode.EXPORT_NOT_FOUND,
                message=f"No {export_format.value} export for run {run_id}",
            )
        artifact = report_export_artifact_to_domain(artifact_row)
        content = artifact_row.content
        return artifact, content

    async def _persist_exports(
        self,
        uow: PostgresUnitOfWork,
        *,
        report: AfterActionReportV1,
        version: ReportVersionV1,
        new_runtime_id_fn,
    ) -> list[ReportExportArtifactV1]:
        exports: list[ReportExportArtifactV1] = []
        for export_format in ReportExportFormatV1:
            content, content_type = render_export(report, export_format)
            checksum = checksum_bytes(content)
            object_key = (
                f"reports/{report.run_id}/v{version.version_number}/{export_format.value}"
            )
            now = datetime.now(UTC)
            await uow.objects.add(
                ObjectMetadataReferenceV1(
                    schema_version=OBJECT_METADATA_REFERENCE_SCHEMA_VERSION,
                    object_key=object_key,
                    checksum=checksum,
                    content_type=content_type,
                    size_bytes=len(content),
                    created_at=now,
                )
            )
            artifact = ReportExportArtifactV1(
                schema_version=REPORT_EXPORT_ARTIFACT_SCHEMA_VERSION,
                id=new_runtime_id_fn("rex"),
                report_version_id=version.id,
                run_id=report.run_id,
                format=export_format,
                object_key=object_key,
                checksum=checksum,
                content_type=content_type,
                size_bytes=len(content),
                workspace_version=WORKSPACE_VERSION,
                report_schema_version=report.schema_version,
                created_at=now,
            )
            await uow.reports.add_export(artifact, content=content)
            exports.append(artifact)
        return exports
