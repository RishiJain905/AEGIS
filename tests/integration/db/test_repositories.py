"""Integration tests proving repositories return domain contracts."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from aegis_contracts import (
    ObjectMetadataReferenceV1,
    RunV1,
    ScenarioV1,
    ScenarioVersionV1,
)
from aegis_contracts.versioning import (
    OBJECT_METADATA_REFERENCE_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
    SCENARIO_SCHEMA_VERSION,
    SCENARIO_VERSION_SCHEMA_VERSION,
)
from aegis_persistence.orm.tables import RunRow
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from pydantic import BaseModel


@pytest.mark.asyncio
async def test_run_repository_returns_pydantic_not_orm(
    unit_of_work: PostgresUnitOfWork,
) -> None:
    scenario = ScenarioV1(
        schema_version=SCENARIO_SCHEMA_VERSION,
        id="scenario:repo-test",
        name="Repo Test",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    version = ScenarioVersionV1(
        schema_version=SCENARIO_VERSION_SCHEMA_VERSION,
        id="scenario-version:repo-test-v1",
        scenario_id=scenario.id,
        version="1.0.0",
        required_platform_version="0.0.0-phase02",
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    run = RunV1(
        schema_version=RUN_SCHEMA_VERSION,
        id="run_01ARZ3NDEKTSV4RRFFQ69G5FBD",
        scenario_version_id=version.id,
        seed=5,
        status="running",
        started_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        sim_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        revision=0,
    )

    await unit_of_work.scenarios.add(scenario)
    await unit_of_work.scenario_versions.add(version)
    stored = await unit_of_work.runs.add(run)

    assert isinstance(stored, RunV1)
    assert not isinstance(stored, RunRow)
    assert isinstance(stored, BaseModel)

    fetched = await unit_of_work.runs.get_by_id(run.id)
    assert fetched is not None
    assert isinstance(fetched, RunV1)
    assert fetched.id == run.id


@pytest.mark.asyncio
async def test_object_repository_returns_metadata_contract(
    unit_of_work: PostgresUnitOfWork,
) -> None:
    reference = ObjectMetadataReferenceV1(
        schema_version=OBJECT_METADATA_REFERENCE_SCHEMA_VERSION,
        object_key="artifacts/test/object.bin",
        checksum="sha256:" + "a" * 64,
        content_type="application/octet-stream",
        size_bytes=128,
        created_at=datetime(2026, 6, 30, 12, 0, tzinfo=UTC),
    )
    stored = await unit_of_work.objects.add(reference)
    assert isinstance(stored, ObjectMetadataReferenceV1)

    fetched = await unit_of_work.objects.get_by_key(reference.object_key)
    assert fetched is not None
    assert fetched.checksum == reference.checksum
