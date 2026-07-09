"""PostgreSQL repositories for Phase 25 replay snapshot manifests."""

from __future__ import annotations

from aegis_contracts import SnapshotManifestV1, parse_contract
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_persistence.mappers import domain_to_payload
from aegis_persistence.orm.tables import ReplaySnapshotManifestRow


def snapshot_manifest_to_domain(row: ReplaySnapshotManifestRow) -> SnapshotManifestV1:
    return parse_contract(SnapshotManifestV1, row.payload)


class PostgresReplaySnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, manifest: SnapshotManifestV1) -> SnapshotManifestV1:
        payload = domain_to_payload(manifest)
        row = ReplaySnapshotManifestRow(
            snapshot_id=manifest.snapshot_id,
            run_id=manifest.run_id,
            sequence=manifest.sequence,
            sim_time=manifest.sim_time,
            scenario_version_id=manifest.scenario_version_id,
            engine_version=manifest.engine_version,
            projector_version=manifest.projector_version,
            workspace_version=manifest.workspace_version,
            event_range_from=manifest.event_range_from,
            event_range_to=manifest.event_range_to,
            checksum=manifest.checksum,
            compression=manifest.compression.value,
            content_type=manifest.content_type,
            size_bytes=manifest.size_bytes,
            object_key=manifest.object_key,
            state_digest=manifest.state_digest,
            trigger_reason=manifest.trigger_reason.value,
            retention_class=manifest.retention_class,
            compatible=manifest.compatible,
            payload=payload,
            created_at=manifest.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return manifest

    async def get_by_id(self, snapshot_id: str) -> SnapshotManifestV1 | None:
        row = await self._session.get(ReplaySnapshotManifestRow, snapshot_id)
        return snapshot_manifest_to_domain(row) if row else None

    async def get_at_sequence(self, run_id: str, sequence: int) -> SnapshotManifestV1 | None:
        result = await self._session.execute(
            select(ReplaySnapshotManifestRow).where(
                ReplaySnapshotManifestRow.run_id == run_id,
                ReplaySnapshotManifestRow.sequence == sequence,
            )
        )
        row = result.scalar_one_or_none()
        return snapshot_manifest_to_domain(row) if row else None

    async def get_nearest_prior(
        self,
        run_id: str,
        sequence: int,
        *,
        compatible_only: bool = True,
    ) -> SnapshotManifestV1 | None:
        query = select(ReplaySnapshotManifestRow).where(
            ReplaySnapshotManifestRow.run_id == run_id,
            ReplaySnapshotManifestRow.sequence <= sequence,
        )
        if compatible_only:
            query = query.where(ReplaySnapshotManifestRow.compatible.is_(True))
        query = query.order_by(ReplaySnapshotManifestRow.sequence.desc()).limit(1)
        result = await self._session.execute(query)
        row = result.scalar_one_or_none()
        return snapshot_manifest_to_domain(row) if row else None

    async def list_for_run(
        self,
        run_id: str,
        *,
        limit: int = 1000,
    ) -> list[SnapshotManifestV1]:
        result = await self._session.execute(
            select(ReplaySnapshotManifestRow)
            .where(ReplaySnapshotManifestRow.run_id == run_id)
            .order_by(ReplaySnapshotManifestRow.sequence.asc())
            .limit(limit)
        )
        return [snapshot_manifest_to_domain(row) for row in result.scalars().all()]

    async def mark_incompatible(self, snapshot_id: str) -> None:
        row = await self._session.get(ReplaySnapshotManifestRow, snapshot_id)
        if row is None:
            return
        row.compatible = False
        payload = dict(row.payload)
        payload["compatible"] = False
        row.payload = payload
        await self._session.flush()
