"""Phase 23 SCRIBE report persistence."""

from __future__ import annotations

from aegis_contracts.reports import (
    AfterActionReportV1,
    ReportExportArtifactV1,
    ReportVersionV1,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_persistence.mappers import (
    after_action_report_to_domain,
    domain_to_payload,
    report_export_artifact_to_domain,
    report_version_to_domain,
)
from aegis_persistence.orm.tables import ReportExportArtifactRow, ReportVersionRow


class PostgresReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def latest_version_number(self, run_id: str) -> int:
        result = await self._session.execute(
            select(ReportVersionRow.version_number)
            .where(ReportVersionRow.run_id == run_id)
            .order_by(ReportVersionRow.version_number.desc())
            .limit(1)
        )
        current = result.scalar_one_or_none()
        return 0 if current is None else int(current)

    async def add_version(
        self,
        version: ReportVersionV1,
        report: AfterActionReportV1,
    ) -> ReportVersionV1:
        payload = {
            "version": domain_to_payload(version),
            "report": domain_to_payload(report),
        }
        row = ReportVersionRow(
            id=version.id,
            run_id=version.run_id,
            incident_id=version.incident_id,
            version_number=version.version_number,
            report_id=version.report_id,
            checksum=version.checksum,
            payload=payload,
            created_at=version.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return version

    async def list_versions(self, run_id: str) -> list[ReportVersionV1]:
        result = await self._session.execute(
            select(ReportVersionRow)
            .where(ReportVersionRow.run_id == run_id)
            .order_by(ReportVersionRow.version_number.asc())
        )
        return [report_version_to_domain(row) for row in result.scalars().all()]

    async def get_report(
        self,
        run_id: str,
        *,
        version_number: int | None = None,
    ) -> AfterActionReportV1 | None:
        query = select(ReportVersionRow).where(ReportVersionRow.run_id == run_id)
        if version_number is not None:
            query = query.where(ReportVersionRow.version_number == version_number)
        else:
            query = query.order_by(ReportVersionRow.version_number.desc()).limit(1)
        result = await self._session.execute(query)
        row = result.scalars().first()
        if row is None:
            return None
        return after_action_report_to_domain(row)

    async def add_export(
        self,
        artifact: ReportExportArtifactV1,
        *,
        content: bytes,
    ) -> ReportExportArtifactV1:
        row = ReportExportArtifactRow(
            id=artifact.id,
            report_version_id=artifact.report_version_id,
            run_id=artifact.run_id,
            format=artifact.format.value,
            object_key=artifact.object_key,
            checksum=artifact.checksum,
            content_type=artifact.content_type,
            size_bytes=artifact.size_bytes,
            content=content,
            payload=domain_to_payload(artifact),
            created_at=artifact.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return artifact

    async def get_export(
        self,
        run_id: str,
        *,
        export_format: str,
        version_number: int | None = None,
    ) -> ReportExportArtifactRow | None:
        query = (
            select(ReportExportArtifactRow)
            .join(
                ReportVersionRow,
                ReportExportArtifactRow.report_version_id == ReportVersionRow.id,
            )
            .where(ReportExportArtifactRow.run_id == run_id)
            .where(ReportExportArtifactRow.format == export_format)
        )
        if version_number is not None:
            query = query.where(ReportVersionRow.version_number == version_number)
        else:
            query = query.order_by(ReportVersionRow.version_number.desc())
        result = await self._session.execute(query.limit(1))
        return result.scalars().first()

    async def get_export_content(self, object_key: str) -> bytes | None:
        result = await self._session.execute(
            select(ReportExportArtifactRow)
            .where(ReportExportArtifactRow.object_key == object_key)
            .limit(1)
        )
        row = result.scalars().first()
        return row.content if row else None

    async def list_exports_for_run(self, run_id: str) -> list[ReportExportArtifactV1]:
        result = await self._session.execute(
            select(ReportExportArtifactRow)
            .where(ReportExportArtifactRow.run_id == run_id)
            .order_by(ReportExportArtifactRow.created_at.asc())
        )
        return [report_export_artifact_to_domain(row) for row in result.scalars().all()]
