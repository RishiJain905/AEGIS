"""Snapshot fallback and persisted replay equivalence through PostgreSQL/MinIO."""

from __future__ import annotations

import pytest
from aegis_persistence.object_storage import S3ObjectStorageAdapter
from aegis_replay.service import ReplayService
from tests.integration.replay.test_replay_engine import RUN_ID, _seed_run_with_events

pytestmark = [pytest.mark.failure_injection, pytest.mark.asyncio]


async def test_corrupt_and_missing_minio_snapshot_fall_back_safely(
    unit_of_work,
    settings,
) -> None:
    storage = S3ObjectStorageAdapter(settings)
    service = ReplayService(storage)
    await _seed_run_with_events(unit_of_work, count=16)
    corrupt = await service.create_snapshot(unit_of_work, run_id=RUN_ID, sequence=8)
    original = storage.get_bytes(object_key=corrupt.object_key)
    storage.put_bytes(
        object_key=corrupt.object_key,
        data=original[:-8] + b"CORRUPT!",
        content_type=corrupt.content_type,
    )
    state = await service.reconstruct(
        unit_of_work, run_id=RUN_ID, sequence=16, prefer_snapshot=True
    )
    assert state.provenance.mode.value == "from_events"
    rejected = await unit_of_work.replay_snapshots.get_by_id(corrupt.snapshot_id)
    assert rejected is not None and rejected.compatible is False

    missing = await service.create_snapshot(unit_of_work, run_id=RUN_ID, sequence=10)
    storage.delete(object_key=missing.object_key)
    state = await service.reconstruct(
        unit_of_work, run_id=RUN_ID, sequence=16, prefer_snapshot=True
    )
    assert state.cursor.sequence == 16
    assert state.provenance.fallback_reason is not None
    storage.delete(object_key=corrupt.object_key)


async def test_persisted_replay_reconstructs_identical_normalized_state(
    unit_of_work,
    settings,
) -> None:
    storage = S3ObjectStorageAdapter(settings)
    service = ReplayService(storage)
    await _seed_run_with_events(unit_of_work, count=20)
    live = await service.reconstruct(unit_of_work, run_id=RUN_ID, prefer_snapshot=False)
    manifest = await service.create_snapshot(unit_of_work, run_id=RUN_ID, sequence=10)
    replayed = await service.reconstruct(unit_of_work, run_id=RUN_ID, prefer_snapshot=True)
    equivalence = await service.check_equivalence(unit_of_work, run_id=RUN_ID)

    assert replayed.state_digest == live.state_digest
    assert equivalence.equivalent is True
    assert equivalence.diff is None
    storage.delete(object_key=manifest.object_key)
