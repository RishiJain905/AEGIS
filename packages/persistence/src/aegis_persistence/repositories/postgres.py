"""PostgreSQL repository implementations."""

from __future__ import annotations

from aegis_contracts import (
    DomainEventEnvelopeV1,
    GraphSnapshotV1,
    IdempotencyRecordV1,
    IncidentV1,
    ObjectMetadataReferenceV1,
    RunV1,
    ScenarioV1,
    ScenarioVersionV1,
    SimulationCheckpointV1,
)
from sqlalchemy import CursorResult, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_persistence.errors import (
    DuplicateEventError,
    DuplicateIdempotencyKeyError,
    StaleRevisionError,
)
from aegis_persistence.mappers import (
    checkpoint_to_domain,
    domain_to_payload,
    event_to_domain,
    event_to_outbox_payload,
    graph_snapshot_to_domain,
    idempotency_record_to_domain,
    incident_to_domain,
    object_metadata_to_domain,
    run_to_domain,
    scenario_to_domain,
    scenario_version_to_domain,
)
from aegis_persistence.orm.tables import (
    DomainEventRow,
    GraphSnapshotRow,
    IdempotencyRecordRow,
    IncidentRow,
    OutboxRow,
    RunRow,
    ScenarioRow,
    ScenarioVersionRow,
    SimulationCheckpointRow,
    StoredObjectRow,
)


class PostgresScenarioRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[ScenarioV1]:
        result = await self._session.execute(select(ScenarioRow).order_by(ScenarioRow.id))
        return [scenario_to_domain(row) for row in result.scalars().all()]

    async def get_by_id(self, scenario_id: str) -> ScenarioV1 | None:
        row = await self._session.get(ScenarioRow, scenario_id)
        return scenario_to_domain(row) if row else None

    async def add(self, scenario: ScenarioV1) -> ScenarioV1:
        payload = domain_to_payload(scenario)
        row = ScenarioRow(
            id=scenario.id,
            name=scenario.name,
            payload=payload,
            created_at=scenario.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return scenario


class PostgresScenarioVersionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_scenario(self, scenario_id: str) -> list[ScenarioVersionV1]:
        result = await self._session.execute(
            select(ScenarioVersionRow)
            .where(ScenarioVersionRow.scenario_id == scenario_id)
            .order_by(ScenarioVersionRow.id)
        )
        return [scenario_version_to_domain(row) for row in result.scalars().all()]

    async def get_by_id(self, version_id: str) -> ScenarioVersionV1 | None:
        row = await self._session.get(ScenarioVersionRow, version_id)
        return scenario_version_to_domain(row) if row else None

    async def add(self, version: ScenarioVersionV1) -> ScenarioVersionV1:
        payload = domain_to_payload(version)
        row = ScenarioVersionRow(
            id=version.id,
            scenario_id=version.scenario_id,
            version=version.version,
            payload=payload,
            published_at=version.published_at,
        )
        self._session.add(row)
        await self._session.flush()
        return version


class PostgresRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[RunV1]:
        result = await self._session.execute(select(RunRow).order_by(RunRow.started_at.desc()))
        return [run_to_domain(row) for row in result.scalars().all()]

    async def get_by_id(self, run_id: str) -> RunV1 | None:
        row = await self._session.get(RunRow, run_id)
        return run_to_domain(row) if row else None

    async def add(self, run: RunV1) -> RunV1:
        payload = domain_to_payload(run)
        row = RunRow(
            id=run.id,
            scenario_version_id=run.scenario_version_id,
            seed=run.seed,
            status=run.status,
            sim_time=run.sim_time,
            revision=run.revision,
            payload=payload,
            started_at=run.started_at,
        )
        self._session.add(row)
        await self._session.flush()
        return run

    async def update_with_revision(
        self,
        run: RunV1,
        *,
        expected_revision: int,
    ) -> RunV1:
        payload = domain_to_payload(run)
        cursor_result = await self._session.execute(
            update(RunRow)
            .where(RunRow.id == run.id, RunRow.revision == expected_revision)
            .values(
                status=run.status,
                sim_time=run.sim_time,
                revision=run.revision,
                payload=payload,
            )
        )
        assert isinstance(cursor_result, CursorResult)
        if cursor_result.rowcount != 1:
            raise StaleRevisionError(
                entity_type="run",
                entity_id=run.id,
                expected_revision=expected_revision,
            )
        return run


class PostgresGraphSnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, snapshot: GraphSnapshotV1) -> GraphSnapshotV1:
        from datetime import UTC, datetime

        payload = domain_to_payload(snapshot)
        row = GraphSnapshotRow(
            run_id=snapshot.run_id,
            sequence=snapshot.sequence,
            payload=payload,
            created_at=datetime.now(tz=UTC),
        )
        self._session.add(row)
        await self._session.flush()
        return snapshot

    async def get_latest_for_run(self, run_id: str) -> GraphSnapshotV1 | None:
        result = await self._session.execute(
            select(GraphSnapshotRow)
            .where(GraphSnapshotRow.run_id == run_id)
            .order_by(GraphSnapshotRow.sequence.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return graph_snapshot_to_domain(row) if row else None

    async def get_at_sequence(self, run_id: str, sequence: int) -> GraphSnapshotV1 | None:
        result = await self._session.execute(
            select(GraphSnapshotRow).where(
                GraphSnapshotRow.run_id == run_id,
                GraphSnapshotRow.sequence == sequence,
            )
        )
        row = result.scalar_one_or_none()
        return graph_snapshot_to_domain(row) if row else None


class PostgresEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, event_id: str) -> DomainEventEnvelopeV1 | None:
        row = await self._session.get(DomainEventRow, event_id)
        return event_to_domain(row) if row else None

    async def append(self, envelope: DomainEventEnvelopeV1) -> DomainEventEnvelopeV1:
        row = DomainEventRow(
            event_id=envelope.event_id,
            run_id=envelope.run_id,
            sequence=envelope.sequence,
            event_type=envelope.type,
            sim_time=envelope.sim_time,
            recorded_at=envelope.recorded_at,
            trace_id=envelope.trace_id,
            envelope=domain_to_payload(envelope),
        )
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise DuplicateEventError(
                run_id=envelope.run_id,
                sequence=envelope.sequence,
                event_id=envelope.event_id,
            ) from exc
        return envelope


class PostgresIncidentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, incident_id: str) -> IncidentV1 | None:
        row = await self._session.get(IncidentRow, incident_id)
        return incident_to_domain(row) if row else None

    async def add(self, incident: IncidentV1) -> IncidentV1:
        payload = domain_to_payload(incident)
        row = IncidentRow(
            id=incident.id,
            run_id=incident.run_id,
            state=incident.state.value,
            revision=incident.revision,
            created_at=incident.created_at,
            updated_at=incident.updated_at,
            payload=payload,
        )
        self._session.add(row)
        await self._session.flush()
        return incident

    async def update_with_revision(
        self,
        incident: IncidentV1,
        *,
        expected_revision: int,
    ) -> IncidentV1:
        payload = domain_to_payload(incident)
        cursor_result = await self._session.execute(
            update(IncidentRow)
            .where(IncidentRow.id == incident.id, IncidentRow.revision == expected_revision)
            .values(
                state=incident.state.value,
                revision=incident.revision,
                updated_at=incident.updated_at,
                payload=payload,
            )
        )
        assert isinstance(cursor_result, CursorResult)
        if cursor_result.rowcount != 1:
            raise StaleRevisionError(
                entity_type="incident",
                entity_id=incident.id,
                expected_revision=expected_revision,
            )
        return incident


class PostgresIdempotencyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(
        self,
        *,
        scope: str,
        idempotency_key: str,
    ) -> IdempotencyRecordV1 | None:
        result = await self._session.execute(
            select(IdempotencyRecordRow).where(
                IdempotencyRecordRow.scope == scope,
                IdempotencyRecordRow.idempotency_key == idempotency_key,
            )
        )
        row = result.scalar_one_or_none()
        return idempotency_record_to_domain(row) if row else None

    async def add(self, record: IdempotencyRecordV1) -> IdempotencyRecordV1:
        payload = domain_to_payload(record)
        row = IdempotencyRecordRow(
            scope=record.scope,
            idempotency_key=record.idempotency_key,
            request_hash=record.request_hash,
            response_ref=record.response_ref,
            replayed=record.replayed,
            created_at=record.created_at,
            payload=payload,
        )
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise DuplicateIdempotencyKeyError(
                scope=record.scope,
                idempotency_key=record.idempotency_key,
            ) from exc
        return record


class PostgresObjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_key(self, object_key: str) -> ObjectMetadataReferenceV1 | None:
        row = await self._session.get(StoredObjectRow, object_key)
        return object_metadata_to_domain(row) if row else None

    async def add(self, reference: ObjectMetadataReferenceV1) -> ObjectMetadataReferenceV1:
        payload = domain_to_payload(reference)
        row = StoredObjectRow(
            object_key=reference.object_key,
            checksum=reference.checksum,
            content_type=reference.content_type,
            size_bytes=reference.size_bytes,
            payload=payload,
            created_at=reference.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return reference


class PostgresCheckpointRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, checkpoint_id: str) -> SimulationCheckpointV1 | None:
        row = await self._session.get(SimulationCheckpointRow, checkpoint_id)
        return checkpoint_to_domain(row) if row else None

    async def get_latest_for_run(self, run_id: str) -> SimulationCheckpointV1 | None:
        result = await self._session.execute(
            select(SimulationCheckpointRow)
            .where(SimulationCheckpointRow.run_id == run_id)
            .order_by(SimulationCheckpointRow.sequence_at_checkpoint.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return checkpoint_to_domain(row) if row else None

    async def add(self, checkpoint: SimulationCheckpointV1) -> SimulationCheckpointV1:
        payload = domain_to_payload(checkpoint)
        row = SimulationCheckpointRow(
            id=checkpoint.id,
            run_id=checkpoint.run_id,
            sequence_at_checkpoint=checkpoint.sequence_at_checkpoint,
            engine_version=checkpoint.engine_version,
            checksum=checkpoint.checksum,
            payload=payload,
            created_at=checkpoint.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return checkpoint


def create_outbox_row(envelope: DomainEventEnvelopeV1) -> OutboxRow:
    return OutboxRow(
        event_id=envelope.event_id,
        channel="events",
        payload=event_to_outbox_payload(envelope),
        created_at=envelope.recorded_at,
        published_at=None,
    )
