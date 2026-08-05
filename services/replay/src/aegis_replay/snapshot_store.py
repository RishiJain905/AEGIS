"""Snapshot archive create/load with checksum validation and object storage."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_contracts import (
    ObjectMetadataReferenceV1,
    ReplaySnapshotV1,
    ReplayStateV1,
    SnapshotCompressionV1,
    SnapshotManifestV1,
    SnapshotTriggerReasonV1,
)
from aegis_contracts.replay import ReplayErrorCode
from aegis_contracts.versioning import (
    OBJECT_METADATA_REFERENCE_SCHEMA_VERSION,
    REPLAY_SNAPSHOT_SCHEMA_VERSION,
    SNAPSHOT_MANIFEST_SCHEMA_VERSION,
    WORKSPACE_VERSION,
)
from aegis_persistence.object_storage import ObjectStoragePort, sha256_hex
from aegis_persistence.unit_of_work import PostgresUnitOfWork

from aegis_replay.checksum import (
    deserialize_snapshot_archive,
    serialize_snapshot_archive,
    verify_archive_checksum,
)
from aegis_replay.errors import ReplayEngineError
from aegis_replay.ids import new_runtime_id
from aegis_replay.versioning import (
    DEFAULT_RETENTION_CLASS,
    REPLAY_PROJECTOR_VERSION,
    is_compatible_snapshot,
)


def build_object_key(*, run_id: str, sequence: int, snapshot_id: str) -> str:
    return f"snapshots/{run_id}/{sequence}/{snapshot_id}.json.gz"


class SnapshotStore:
    def __init__(self, storage: ObjectStoragePort) -> None:
        self._storage = storage

    async def create_snapshot(
        self,
        uow: PostgresUnitOfWork,
        *,
        state: ReplayStateV1,
        scenario_version_id: str,
        engine_version: str,
        trigger_reason: SnapshotTriggerReasonV1,
        event_range_from: int = 0,
    ) -> tuple[SnapshotManifestV1, ReplaySnapshotV1]:
        existing = await uow.replay_snapshots.get_at_sequence(state.run_id, state.cursor.sequence)
        if existing is not None:
            try:
                snapshot = await self.load_snapshot(uow, existing.snapshot_id)
            except ReplayEngineError:
                # A manifest whose archive is unreadable, or which an older projector wrote,
                # is not a usable acceleration artifact. Raising here would fail every
                # re-snapshot of that sequence forever — including the snapshot worker's
                # terminal snapshot, taking the worker down with it — so the dead manifest
                # is discarded and rebuilt from the authoritative event stream instead.
                await uow.replay_snapshots.delete(existing.snapshot_id)
            else:
                return existing, snapshot

        snapshot_id = new_runtime_id("rps")
        created_at = datetime.now(tz=UTC)
        sim_time = state.cursor.sim_time or created_at
        snapshot = ReplaySnapshotV1(
            schema_version=REPLAY_SNAPSHOT_SCHEMA_VERSION,
            id=snapshot_id,  # type: ignore[arg-type]
            run_id=state.run_id,
            sequence=state.cursor.sequence,
            sim_time=sim_time,
            scenario_version_id=scenario_version_id,
            engine_version=engine_version,
            projector_version=REPLAY_PROJECTOR_VERSION,
            workspace_version=WORKSPACE_VERSION,
            event_range_from=event_range_from,
            event_range_to=state.cursor.sequence,
            state=state,
            state_digest=state.state_digest,
            created_at=created_at,
        )
        archive_bytes, checksum = serialize_snapshot_archive(snapshot)
        object_key = build_object_key(
            run_id=state.run_id,
            sequence=state.cursor.sequence,
            snapshot_id=snapshot_id,
        )
        stored_checksum = self._storage.put_bytes(
            object_key=object_key,
            data=archive_bytes,
            content_type="application/gzip",
        )
        if stored_checksum != checksum:
            raise ReplayEngineError(
                ReplayErrorCode.SNAPSHOT_CHECKSUM_MISMATCH,
                "Stored archive checksum diverged from local checksum",
                details={"expected": checksum, "actual": stored_checksum},
            )
        manifest = SnapshotManifestV1(
            schema_version=SNAPSHOT_MANIFEST_SCHEMA_VERSION,
            snapshot_id=snapshot_id,  # type: ignore[arg-type]
            run_id=state.run_id,
            sequence=state.cursor.sequence,
            sim_time=sim_time,
            scenario_version_id=scenario_version_id,
            engine_version=engine_version,
            projector_version=REPLAY_PROJECTOR_VERSION,
            workspace_version=WORKSPACE_VERSION,
            event_range_from=event_range_from,
            event_range_to=state.cursor.sequence,
            checksum=checksum,
            compression=SnapshotCompressionV1.GZIP,
            content_type="application/gzip",
            size_bytes=len(archive_bytes),
            object_key=object_key,
            state_digest=state.state_digest,
            trigger_reason=trigger_reason,
            retention_class=DEFAULT_RETENTION_CLASS,
            created_at=created_at,
            compatible=True,
        )
        await uow.replay_snapshots.add(manifest)
        await uow.objects.add(
            ObjectMetadataReferenceV1(
                schema_version=OBJECT_METADATA_REFERENCE_SCHEMA_VERSION,
                object_key=object_key,
                checksum=checksum,
                content_type="application/gzip",
                size_bytes=len(archive_bytes),
                created_at=created_at,
            )
        )
        return manifest, snapshot

    async def load_snapshot(
        self,
        uow: PostgresUnitOfWork,
        snapshot_id: str,
        *,
        expected_engine_version: str | None = None,
        allow_incompatible: bool = False,
    ) -> ReplaySnapshotV1:
        manifest = await uow.replay_snapshots.get_by_id(snapshot_id)
        if manifest is None:
            raise ReplayEngineError(
                ReplayErrorCode.SNAPSHOT_MISSING,
                f"Snapshot manifest not found: {snapshot_id}",
                details={"snapshotId": snapshot_id},
            )
        if not self._storage.exists(object_key=manifest.object_key):
            await uow.replay_snapshots.mark_incompatible(snapshot_id)
            raise ReplayEngineError(
                ReplayErrorCode.SNAPSHOT_MISSING,
                f"Snapshot archive missing from object storage: {manifest.object_key}",
                details={"snapshotId": snapshot_id, "objectKey": manifest.object_key},
            )
        data = self._storage.get_bytes(object_key=manifest.object_key)
        try:
            verify_archive_checksum(data=data, expected_checksum=manifest.checksum)
        except ReplayEngineError:
            await uow.replay_snapshots.mark_incompatible(snapshot_id)
            raise
        # Detect tampering of uncompressed content via secondary digest.
        if sha256_hex(data) != manifest.checksum:
            await uow.replay_snapshots.mark_incompatible(snapshot_id)
            raise ReplayEngineError(
                ReplayErrorCode.SNAPSHOT_CHECKSUM_MISMATCH,
                "Snapshot archive checksum mismatch",
                details={"snapshotId": snapshot_id},
            )
        try:
            snapshot = deserialize_snapshot_archive(data)
        except Exception as exc:
            await uow.replay_snapshots.mark_incompatible(snapshot_id)
            raise ReplayEngineError(
                ReplayErrorCode.SNAPSHOT_CHECKSUM_MISMATCH,
                "Snapshot archive is corrupted or unreadable",
                details={"snapshotId": snapshot_id},
            ) from exc
        compatible = is_compatible_snapshot(
            projector_version=snapshot.projector_version,
            workspace_version=snapshot.workspace_version,
            engine_version=snapshot.engine_version,
            expected_engine_version=expected_engine_version,
        )
        if not compatible and not allow_incompatible:
            await uow.replay_snapshots.mark_incompatible(snapshot_id)
            raise ReplayEngineError(
                ReplayErrorCode.SNAPSHOT_INCOMPATIBLE,
                "Snapshot is incompatible with current replay projector",
                details={
                    "snapshotId": snapshot_id,
                    "projectorVersion": snapshot.projector_version,
                    "workspaceVersion": snapshot.workspace_version,
                    "engineVersion": snapshot.engine_version,
                },
            )
        if snapshot.state_digest != manifest.state_digest:
            await uow.replay_snapshots.mark_incompatible(snapshot_id)
            raise ReplayEngineError(
                ReplayErrorCode.SNAPSHOT_CHECKSUM_MISMATCH,
                "Snapshot state digest does not match manifest",
                details={
                    "snapshotId": snapshot_id,
                    "manifestDigest": manifest.state_digest,
                    "snapshotDigest": snapshot.state_digest,
                },
            )
        return snapshot
