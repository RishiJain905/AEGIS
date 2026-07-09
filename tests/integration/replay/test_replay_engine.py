"""Integration tests for snapshot create/load/reconstruct against PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from aegis_contracts import (
    RunV1,
    ScenarioV1,
    ScenarioVersionV1,
    SnapshotTriggerReasonV1,
)
from aegis_contracts.replay import ReplayErrorCode
from aegis_contracts.versioning import (
    RUN_SCHEMA_VERSION,
    SCENARIO_SCHEMA_VERSION,
    SCENARIO_VERSION_SCHEMA_VERSION,
)
from aegis_persistence.object_storage import InMemoryObjectStorage
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from aegis_replay.errors import ReplayEngineError
from aegis_replay.service import ReplayService

from tests.replay.helpers import RUN_ID, sample_history

pytestmark = pytest.mark.asyncio


async def _seed_run_with_events(uow: PostgresUnitOfWork, *, count: int = 20) -> None:
    scenario = ScenarioV1.model_validate(
        {
            "schemaVersion": SCENARIO_SCHEMA_VERSION,
            "id": "scenario:operation-silent-relay",
            "name": "Operation Silent Relay",
            "description": "Replay integration fixture",
            "createdAt": "2026-01-01T00:00:00.000Z",
        }
    )
    version = ScenarioVersionV1.model_validate(
        {
            "schemaVersion": SCENARIO_VERSION_SCHEMA_VERSION,
            "id": "scenario-version:v1.0.0-synthetic",
            "scenarioId": "scenario:operation-silent-relay",
            "version": "v1.0.0-synthetic",
            "requiredPlatformVersion": "0.0.0-phase25",
            "publishedAt": "2026-01-01T00:00:00.000Z",
        }
    )
    run = RunV1.model_validate(
        {
            "schemaVersion": RUN_SCHEMA_VERSION,
            "id": RUN_ID,
            "scenarioVersionId": "scenario-version:v1.0.0-synthetic",
            "seed": 42,
            "status": "running",
            "startedAt": "2026-06-30T02:00:00.000Z",
            "simTime": "2026-01-01T18:00:00.000Z",
            "revision": 1,
        }
    )
    if await uow.scenarios.get_by_id(scenario.id) is None:
        await uow.scenarios.add(scenario)
    if await uow.scenario_versions.get_by_id(version.id) is None:
        await uow.scenario_versions.add(version)
    await uow.runs.add(run)
    for event in sample_history(count=count):
        await uow.append_event(event)


async def test_snapshot_create_reconstruct_and_equivalence(
    unit_of_work: PostgresUnitOfWork,
) -> None:
    storage = InMemoryObjectStorage.create()
    service = ReplayService(storage, snapshot_interval=10)
    await _seed_run_with_events(unit_of_work, count=20)

    from_events = await service.reconstruct(
        unit_of_work,
        run_id=RUN_ID,
        prefer_snapshot=False,
    )
    assert from_events.provenance.mode.value == "from_events"
    assert from_events.cursor.sequence == 20

    manifest = await service.create_snapshot(
        unit_of_work,
        run_id=RUN_ID,
        sequence=10,
        trigger_reason=SnapshotTriggerReasonV1.EXPLICIT_REQUEST,
    )
    assert manifest.sequence == 10
    assert manifest.checksum.startswith("sha256:")
    assert storage.exists(object_key=manifest.object_key)

    from_snapshot = await service.reconstruct(
        unit_of_work,
        run_id=RUN_ID,
        sequence=20,
        prefer_snapshot=True,
    )
    assert from_snapshot.provenance.mode.value == "from_snapshot_plus_events"
    assert from_snapshot.provenance.snapshot_id == manifest.snapshot_id
    assert from_snapshot.state_digest == from_events.state_digest

    equivalence = await service.check_equivalence(unit_of_work, run_id=RUN_ID)
    assert equivalence.equivalent is True


async def test_corrupt_snapshot_falls_back_to_events(
    unit_of_work: PostgresUnitOfWork,
) -> None:
    storage = InMemoryObjectStorage.create()
    service = ReplayService(storage)
    await _seed_run_with_events(unit_of_work, count=16)

    manifest = await service.create_snapshot(
        unit_of_work,
        run_id=RUN_ID,
        sequence=8,
    )
    original = storage.get_bytes(object_key=manifest.object_key)
    storage.put_bytes(
        object_key=manifest.object_key,
        data=original[:-8] + b"CORRUPTED",
        content_type=manifest.content_type,
    )

    with pytest.raises(ReplayEngineError) as load_exc:
        await service._store.load_snapshot(unit_of_work, manifest.snapshot_id)
    assert load_exc.value.code == ReplayErrorCode.SNAPSHOT_CHECKSUM_MISMATCH

    # Incompatible/corrupt manifests are marked and skipped; reconstruction
    # continues from authoritative events (safe fallback).
    state = await service.reconstruct(
        unit_of_work,
        run_id=RUN_ID,
        sequence=16,
        prefer_snapshot=True,
    )
    assert state.cursor.sequence == 16
    assert state.provenance.mode.value == "from_events"
    marked = await unit_of_work.replay_snapshots.get_by_id(manifest.snapshot_id)
    assert marked is not None
    assert marked.compatible is False


async def test_missing_snapshot_archive_falls_back(
    unit_of_work: PostgresUnitOfWork,
) -> None:
    storage = InMemoryObjectStorage.create()
    service = ReplayService(storage)
    await _seed_run_with_events(unit_of_work, count=12)
    manifest = await service.create_snapshot(unit_of_work, run_id=RUN_ID, sequence=6)
    storage.delete(object_key=manifest.object_key)

    state = await service.reconstruct(
        unit_of_work,
        run_id=RUN_ID,
        sequence=12,
        prefer_snapshot=True,
    )
    assert state.cursor.sequence == 12
    assert state.provenance.mode.value == "from_events"
    assert state.provenance.fallback_reason is not None


async def test_duplicate_persisted_event_ids_do_not_duplicate_state(
    unit_of_work: PostgresUnitOfWork,
) -> None:
    storage = InMemoryObjectStorage.create()
    service = ReplayService(storage)
    await _seed_run_with_events(unit_of_work, count=10)
    # Projector-level duplicate protection is covered in unit tests; here ensure
    # reconstruction from PG history remains stable across repeated calls.
    first = await service.reconstruct(unit_of_work, run_id=RUN_ID, prefer_snapshot=False)
    second = await service.reconstruct(unit_of_work, run_id=RUN_ID, prefer_snapshot=False)
    assert first.state_digest == second.state_digest
    assert len(first.incidents) == len(second.incidents)


async def test_replay_does_not_append_live_events(
    unit_of_work: PostgresUnitOfWork,
) -> None:
    storage = InMemoryObjectStorage.create()
    service = ReplayService(storage)
    await _seed_run_with_events(unit_of_work, count=8)
    before = await unit_of_work.events.next_sequence(RUN_ID)
    await service.reconstruct(unit_of_work, run_id=RUN_ID)
    await service.create_snapshot(unit_of_work, run_id=RUN_ID, sequence=8)
    after = await unit_of_work.events.next_sequence(RUN_ID)
    assert after == before


async def test_large_history_reconstructs_within_bounds(
    unit_of_work: PostgresUnitOfWork,
) -> None:
    storage = InMemoryObjectStorage.create()
    service = ReplayService(storage, page_size=50)
    # Seed a larger contiguous history using generated asset status events.
    from tests.replay.helpers import make_event

    scenario = ScenarioV1.model_validate(
        {
            "schemaVersion": SCENARIO_SCHEMA_VERSION,
            "id": "scenario:operation-silent-relay",
            "name": "Operation Silent Relay",
            "description": "Replay integration fixture",
            "createdAt": "2026-01-01T00:00:00.000Z",
        }
    )
    version = ScenarioVersionV1.model_validate(
        {
            "schemaVersion": SCENARIO_VERSION_SCHEMA_VERSION,
            "id": "scenario-version:v1.0.0-synthetic",
            "scenarioId": "scenario:operation-silent-relay",
            "version": "v1.0.0-synthetic",
            "requiredPlatformVersion": "0.0.0-phase25",
            "publishedAt": "2026-01-01T00:00:00.000Z",
        }
    )
    run = RunV1.model_validate(
        {
            "schemaVersion": RUN_SCHEMA_VERSION,
            "id": RUN_ID,
            "scenarioVersionId": "scenario-version:v1.0.0-synthetic",
            "seed": 42,
            "status": "running",
            "startedAt": "2026-06-30T02:00:00.000Z",
            "simTime": "2026-01-01T18:00:00.000Z",
            "revision": 1,
        }
    )
    if await unit_of_work.scenarios.get_by_id(scenario.id) is None:
        await unit_of_work.scenarios.add(scenario)
    if await unit_of_work.scenario_versions.get_by_id(version.id) is None:
        await unit_of_work.scenario_versions.add(version)
    await unit_of_work.runs.add(run)
    for seq in range(1, 251):
        if seq == 1:
            event = make_event(
                sequence=seq,
                event_type="sim.run.started",
                payload={
                    "schemaVersion": 1,
                    "scenarioVersionId": "scenario-version:v1.0.0-synthetic",
                    "seed": 42,
                },
                event_index=seq,
            )
        else:
            event = make_event(
                sequence=seq,
                event_type="sim.asset.status_changed",
                payload={
                    "schemaVersion": 1,
                    "assetId": "asset:svc-api-gateway",
                    "status": "suspicious" if seq % 17 == 0 else "normal",
                    "label": "API Gateway",
                    "assetType": "service",
                },
                event_index=seq,
            )
        await unit_of_work.append_event(event)

    started = datetime.now(tz=UTC)
    state = await service.reconstruct(unit_of_work, run_id=RUN_ID, prefer_snapshot=False)
    elapsed = (datetime.now(tz=UTC) - started).total_seconds()
    assert state.cursor.sequence == 250
    assert elapsed < 30.0
