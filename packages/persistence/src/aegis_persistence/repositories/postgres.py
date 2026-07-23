"""PostgreSQL repository implementations."""

from __future__ import annotations

import hashlib

from aegis_contracts import (
    ActionProposalV1,
    AgentArtifactV1,
    AgentBudgetV1,
    AgentSessionV1,
    AgentStateTransitionV1,
    AgentTaskV1,
    AlertV1,
    AssetRiskScoreV1,
    DomainEventEnvelopeV1,
    EvidenceV1,
    GenerationArtifactV1,
    GraphSnapshotV1,
    HypothesisV1,
    IdempotencyRecordV1,
    IncidentV1,
    ModelManifestV1,
    ModelScoreV1,
    ObjectMetadataReferenceV1,
    RunV1,
    ScenarioV1,
    ScenarioVersionV1,
    SimulationCheckpointV1,
    ToolInvocationV1,
)
from sqlalchemy import CursorResult, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_persistence.errors import (
    DuplicateEventError,
    DuplicateIdempotencyKeyError,
    StaleRevisionError,
)
from aegis_persistence.mappers import (
    agent_artifact_to_domain,
    agent_budget_from_row,
    agent_session_to_domain,
    agent_state_transition_to_domain,
    agent_task_to_domain,
    alert_to_domain,
    asset_risk_score_to_domain,
    checkpoint_to_domain,
    domain_to_payload,
    event_to_domain,
    event_to_outbox_payload,
    evidence_to_domain,
    generation_artifact_to_domain,
    graph_snapshot_to_domain,
    idempotency_record_to_domain,
    incident_to_domain,
    model_manifest_to_domain,
    model_score_to_domain,
    object_metadata_to_domain,
    run_to_domain,
    scenario_to_domain,
    scenario_version_to_domain,
    tool_invocation_to_domain,
)
from aegis_persistence.orm.tables import (
    ActionProposalRow,
    AgentArtifactRow,
    AgentSessionRow,
    AgentStateTransitionRow,
    AgentTaskRow,
    AlertRow,
    AssetRiskScoreRow,
    DomainEventRow,
    EvidenceRow,
    GenerationArtifactRow,
    GraphSnapshotRow,
    HypothesisRow,
    IdempotencyRecordRow,
    IncidentRow,
    ModelManifestRow,
    ModelScoreRow,
    OutboxRow,
    RunRow,
    ScenarioRow,
    ScenarioVersionRow,
    SimulationCheckpointRow,
    StoredObjectRow,
    ToolInvocationRow,
)


def _advisory_lock_key(run_id: str) -> int:
    """Stable signed 64-bit key for a per-run Postgres transaction advisory lock.

    Uses a hash (not Python ``hash()``, which is process-salted) so the key is
    deterministic across processes. Signed to fit Postgres ``bigint``.
    """
    digest = hashlib.blake2b(run_id.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big", signed=True)


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

    async def list_for_owner(self, owner_user_id: str) -> list[RunV1]:
        result = await self._session.execute(
            select(RunRow)
            .where(RunRow.owner_user_id == owner_user_id)
            .order_by(RunRow.started_at.desc())
        )
        return [run_to_domain(row) for row in result.scalars().all()]

    async def list_running(self) -> list[RunV1]:
        """Return RUNNING runs (oldest first) for the tick engine to advance.

        Ordered by ``started_at`` ascending so long-lived runs are serviced before newer
        ones each cycle; status is the authoritative RUNNING/paused/stopped signal, so this
        is restart-safe (the ticker rediscovers live runs from the DB after any restart).
        """
        result = await self._session.execute(
            select(RunRow).where(RunRow.status == "running").order_by(RunRow.started_at.asc())
        )
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
            owner_user_id=run.owner_user_id,
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

    async def next_sequence(self, run_id: str) -> int:
        # Serialize sequence assignment per run so concurrent appending
        # transactions cannot read the same max and collide on the unique
        # (run_id, sequence) constraint. pg_advisory_xact_lock is held for the
        # remainder of the current transaction (through the event+outbox
        # commit), so the max read below and the subsequent append are atomic
        # with respect to any other writer on the same run. Reentrant within a
        # transaction, so multiple next_sequence calls in one command are safe.
        bind = self._session.bind
        dialect_name = getattr(getattr(bind, "dialect", None), "name", "")
        if dialect_name == "postgresql":
            await self._session.execute(
                text("SELECT pg_advisory_xact_lock(:lock_key)"),
                {"lock_key": _advisory_lock_key(run_id)},
            )
        result = await self._session.execute(
            select(DomainEventRow.sequence)
            .where(DomainEventRow.run_id == run_id)
            .order_by(DomainEventRow.sequence.desc())
            .limit(1)
        )
        current = result.scalar_one_or_none()
        return 0 if current is None else int(current) + 1

    async def list_by_run(
        self,
        run_id: str,
        *,
        limit: int = 10_000,
    ) -> list[DomainEventEnvelopeV1]:
        result = await self._session.execute(
            select(DomainEventRow)
            .where(DomainEventRow.run_id == run_id)
            .order_by(DomainEventRow.sequence.asc())
            .limit(limit)
        )
        return [event_to_domain(row) for row in result.scalars().all()]


class PostgresAlertRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, alert_id: str) -> AlertV1 | None:
        row = await self._session.get(AlertRow, alert_id)
        return alert_to_domain(row) if row else None

    async def list_by_run(self, run_id: str) -> list[AlertV1]:
        result = await self._session.execute(
            select(AlertRow).where(AlertRow.run_id == run_id).order_by(AlertRow.created_at)
        )
        return [alert_to_domain(row) for row in result.scalars().all()]

    async def add(self, alert: AlertV1) -> AlertV1:
        payload = domain_to_payload(alert)
        row = AlertRow(
            id=alert.id,
            run_id=alert.run_id,
            asset_id=alert.asset_id,
            source_event_id=alert.source_event_id,
            created_at=alert.created_at,
            payload=payload,
        )
        self._session.add(row)
        await self._session.flush()
        return alert

    async def exists_by_dedup_key(self, run_id: str, deduplication_key: str) -> bool:
        keys = await self.list_dedup_keys_for_run(run_id)
        return deduplication_key in keys

    async def list_dedup_keys_for_run(self, run_id: str) -> set[str]:
        result = await self._session.execute(
            select(AlertRow.payload).where(AlertRow.run_id == run_id)
        )
        keys: set[str] = set()
        for payload in result.scalars().all():
            if isinstance(payload, dict):
                key = payload.get("deduplicationKey")
                if isinstance(key, str):
                    keys.add(key)
        return keys


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


class PostgresModelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_manifest_by_id(self, model_id: str) -> ModelManifestV1 | None:
        row = await self._session.get(ModelManifestRow, model_id)
        return model_manifest_to_domain(row) if row else None

    async def add_manifest(self, manifest: ModelManifestV1) -> ModelManifestV1:
        payload = domain_to_payload(manifest)
        row = ModelManifestRow(
            id=manifest.id,
            artifact_object_key=manifest.artifact_object_key,
            artifact_checksum=manifest.artifact_checksum,
            payload=payload,
            created_at=manifest.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return manifest

    async def add_score(self, score: ModelScoreV1, *, deduplication_key: str) -> ModelScoreV1:
        payload = domain_to_payload(score)
        payload["deduplicationKey"] = deduplication_key
        row = ModelScoreRow(
            model_version_id=score.model_version_id,
            entity_id=score.entity_id,
            score=score.score,
            payload=payload,
            scored_at=score.scored_at,
        )
        self._session.add(row)
        await self._session.flush()
        return score

    async def score_exists(self, deduplication_key: str) -> bool:
        result = await self._session.execute(select(ModelScoreRow.payload))
        for payload in result.scalars().all():
            if isinstance(payload, dict) and payload.get("deduplicationKey") == deduplication_key:
                return True
        return False

    async def list_scores_for_run_entity(
        self,
        *,
        model_version_id: str,
        entity_id: str,
    ) -> list[ModelScoreV1]:
        result = await self._session.execute(
            select(ModelScoreRow)
            .where(
                ModelScoreRow.model_version_id == model_version_id,
                ModelScoreRow.entity_id == entity_id,
            )
            .order_by(ModelScoreRow.scored_at)
        )
        return [model_score_to_domain(row) for row in result.scalars().all()]


class PostgresRiskScoreRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        score: AssetRiskScoreV1,
        *,
        deduplication_key: str | None = None,
    ) -> AssetRiskScoreV1:
        from datetime import UTC, datetime

        payload = domain_to_payload(score)
        row = AssetRiskScoreRow(
            run_id=score.run_id,
            asset_id=score.asset_id,
            sequence=score.computed_at_sequence,
            deduplication_key=deduplication_key,
            payload=payload,
            scored_at=datetime.now(tz=UTC),
        )
        self._session.add(row)
        await self._session.flush()
        return score

    async def list_by_run(self, run_id: str) -> list[AssetRiskScoreV1]:
        result = await self._session.execute(
            select(AssetRiskScoreRow)
            .where(AssetRiskScoreRow.run_id == run_id)
            .order_by(AssetRiskScoreRow.sequence, AssetRiskScoreRow.asset_id)
        )
        return [asset_risk_score_to_domain(row) for row in result.scalars().all()]

    async def exists_by_dedup_key(self, run_id: str, deduplication_key: str) -> bool:
        result = await self._session.execute(
            select(AssetRiskScoreRow.id).where(
                AssetRiskScoreRow.run_id == run_id,
                AssetRiskScoreRow.deduplication_key == deduplication_key,
            )
        )
        return result.scalar_one_or_none() is not None

    async def list_latest_by_run(self, run_id: str) -> list[AssetRiskScoreV1]:
        rows = await self.list_by_run(run_id)
        latest_by_asset: dict[str, AssetRiskScoreV1] = {}
        for row in rows:
            current = latest_by_asset.get(row.asset_id)
            if current is None or row.computed_at_sequence >= current.computed_at_sequence:
                latest_by_asset[row.asset_id] = row
        return sorted(latest_by_asset.values(), key=lambda item: item.asset_id)


class PostgresGenerationArtifactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, artifact: GenerationArtifactV1) -> GenerationArtifactV1:
        payload = domain_to_payload(artifact)
        row = GenerationArtifactRow(
            request_id=artifact.request_id,
            trace_id=artifact.trace_id,
            provider_id=artifact.provider_id,
            model_id=artifact.model_id,
            prompt_version=artifact.prompt_version,
            latency_ms=artifact.latency_ms,
            usage=artifact.usage.model_dump(by_alias=True, mode="json") if artifact.usage else None,
            error=artifact.error.model_dump(by_alias=True, mode="json") if artifact.error else None,
            artifact_ref=artifact.object_storage_ref,
            payload=payload,
            recorded_at=artifact.recorded_at,
        )
        self._session.add(row)
        await self._session.flush()
        return artifact

    async def get_by_request_id(self, request_id: str) -> GenerationArtifactV1 | None:
        row = await self._session.get(GenerationArtifactRow, request_id)
        return generation_artifact_to_domain(row) if row else None


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


class PostgresAgentSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, session_id: str) -> AgentSessionV1 | None:
        row = await self._session.get(AgentSessionRow, session_id)
        return agent_session_to_domain(row) if row else None

    async def get_budget(self, session_id: str) -> AgentBudgetV1 | None:
        row = await self._session.get(AgentSessionRow, session_id)
        return agent_budget_from_row(row) if row else None

    async def add(
        self,
        session: AgentSessionV1,
        *,
        budget: AgentBudgetV1 | None = None,
    ) -> AgentSessionV1:
        payload = domain_to_payload(session)
        row = AgentSessionRow(
            id=session.id,
            run_id=session.run_id,
            incident_id=session.incident_id,
            trace_id=session.trace_id,
            payload=payload,
            budget=domain_to_payload(budget) if budget else None,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )
        self._session.add(row)
        await self._session.flush()
        return session

    async def list_for_run(self, run_id: str) -> list[AgentSessionV1]:
        result = await self._session.execute(
            select(AgentSessionRow)
            .where(AgentSessionRow.run_id == run_id)
            .order_by(AgentSessionRow.created_at.asc())
        )
        return [agent_session_to_domain(row) for row in result.scalars().all()]

    async def update(
        self,
        session: AgentSessionV1,
        *,
        budget: AgentBudgetV1 | None = None,
    ) -> AgentSessionV1:
        row = await self._session.get(AgentSessionRow, session.id)
        if row is None:
            msg = f"Agent session not found: {session.id}"
            raise KeyError(msg)
        row.payload = domain_to_payload(session)
        row.updated_at = session.updated_at
        if budget is not None:
            row.budget = domain_to_payload(budget)
        await self._session.flush()
        return session


class PostgresAgentTaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, task_id: str) -> AgentTaskV1 | None:
        row = await self._session.get(AgentTaskRow, task_id)
        return agent_task_to_domain(row) if row else None

    async def get_by_idempotency(
        self,
        *,
        session_id: str,
        idempotency_key: str,
    ) -> AgentTaskV1 | None:
        result = await self._session.execute(
            select(AgentTaskRow).where(
                AgentTaskRow.session_id == session_id,
                AgentTaskRow.idempotency_key == idempotency_key,
            )
        )
        row = result.scalar_one_or_none()
        return agent_task_to_domain(row) if row else None

    async def list_for_session(self, session_id: str) -> list[AgentTaskV1]:
        result = await self._session.execute(
            select(AgentTaskRow)
            .where(AgentTaskRow.session_id == session_id)
            .order_by(AgentTaskRow.created_at.asc())
        )
        return [agent_task_to_domain(row) for row in result.scalars().all()]

    async def list_queued(self, *, limit: int = 20) -> list[AgentTaskV1]:
        result = await self._session.execute(
            select(AgentTaskRow)
            .where(AgentTaskRow.status == "queued")
            .order_by(AgentTaskRow.created_at.asc())
            .limit(limit)
        )
        return [agent_task_to_domain(row) for row in result.scalars().all()]

    async def list_running(self) -> list[AgentTaskV1]:
        result = await self._session.execute(
            select(AgentTaskRow).where(AgentTaskRow.status == "running")
        )
        return [agent_task_to_domain(row) for row in result.scalars().all()]

    async def add(self, task: AgentTaskV1) -> AgentTaskV1:
        payload = domain_to_payload(task)
        row = AgentTaskRow(
            id=task.id,
            session_id=task.session_id,
            run_id=task.run_id,
            incident_id=task.incident_id,
            idempotency_key=task.idempotency_key,
            status=task.status.value,
            attempt=task.attempt,
            payload=payload,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise DuplicateIdempotencyKeyError(
                scope="agent-task",
                idempotency_key=task.idempotency_key,
            ) from exc
        return task

    async def update(self, task: AgentTaskV1) -> AgentTaskV1:
        row = await self._session.get(AgentTaskRow, task.id)
        if row is None:
            msg = f"Agent task not found: {task.id}"
            raise KeyError(msg)
        row.status = task.status.value
        row.attempt = task.attempt
        row.payload = domain_to_payload(task)
        row.updated_at = task.updated_at
        await self._session.flush()
        return task

    async def claim_transition(
        self,
        task: AgentTaskV1,
        *,
        from_statuses: tuple[str, ...],
    ) -> bool:
        """Atomically transition a task out of ``from_statuses`` into ``task.status``.

        The status guard is applied in a single ``UPDATE ... WHERE id=? AND
        status IN (...)`` so exactly one concurrent caller can win the claim.
        Returns True if this caller performed the transition, False if the task
        was already claimed/advanced by another writer (zero rows updated).
        """
        cursor_result = await self._session.execute(
            update(AgentTaskRow)
            .where(
                AgentTaskRow.id == task.id,
                AgentTaskRow.status.in_(from_statuses),
            )
            .values(
                status=task.status.value,
                attempt=task.attempt,
                payload=domain_to_payload(task),
                updated_at=task.updated_at,
            )
        )
        assert isinstance(cursor_result, CursorResult)
        return cursor_result.rowcount == 1


class PostgresAgentStateTransitionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, transition: AgentStateTransitionV1) -> AgentStateTransitionV1:
        payload = domain_to_payload(transition)
        row = AgentStateTransitionRow(
            id=transition.id,
            session_id=transition.session_id,
            task_id=transition.task_id,
            from_state=transition.from_state.value,
            to_state=transition.to_state.value,
            reason=transition.reason,
            payload=payload,
            created_at=transition.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return transition

    async def list_for_session(self, session_id: str) -> list[AgentStateTransitionV1]:
        result = await self._session.execute(
            select(AgentStateTransitionRow)
            .where(AgentStateTransitionRow.session_id == session_id)
            .order_by(AgentStateTransitionRow.created_at.asc())
        )
        return [agent_state_transition_to_domain(row) for row in result.scalars().all()]


class PostgresToolInvocationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, invocation: ToolInvocationV1) -> ToolInvocationV1:
        payload = domain_to_payload(invocation)
        row = ToolInvocationRow(
            id=invocation.id,
            task_id=invocation.task_id,
            session_id=invocation.session_id,
            tool_name=invocation.tool_name,
            tool_class=invocation.tool_class.value,
            status=invocation.status.value,
            duration_ms=invocation.duration_ms,
            input_payload=invocation.input_payload,
            output_payload=invocation.output_payload,
            error_code=invocation.error_code,
            error_message=invocation.error_message,
            payload=payload,
            created_at=invocation.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return invocation

    async def list_for_session(self, session_id: str, *, limit: int = 50) -> list[ToolInvocationV1]:
        result = await self._session.execute(
            select(ToolInvocationRow)
            .where(ToolInvocationRow.session_id == session_id)
            .order_by(ToolInvocationRow.created_at.desc())
            .limit(limit)
        )
        return [tool_invocation_to_domain(row) for row in result.scalars().all()]


class PostgresAgentArtifactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, artifact: AgentArtifactV1) -> AgentArtifactV1:
        payload = domain_to_payload(artifact)
        row = AgentArtifactRow(
            id=artifact.id,
            task_id=artifact.task_id,
            session_id=artifact.session_id,
            artifact_type=artifact.artifact_type.value,
            generation_artifact_id=artifact.generation_artifact_id,
            payload=payload,
            created_at=artifact.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return artifact

    async def list_for_session(self, session_id: str) -> list[AgentArtifactV1]:
        result = await self._session.execute(
            select(AgentArtifactRow)
            .where(AgentArtifactRow.session_id == session_id)
            .order_by(AgentArtifactRow.created_at.asc())
        )
        return [agent_artifact_to_domain(row) for row in result.scalars().all()]


class PostgresEvidenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_ids(self, evidence_ids: list[str]) -> list[EvidenceV1]:
        if not evidence_ids:
            return []
        result = await self._session.execute(
            select(EvidenceRow).where(EvidenceRow.id.in_(evidence_ids))
        )
        return [evidence_to_domain(row) for row in result.scalars().all()]

    async def list_for_run(self, run_id: str) -> list[EvidenceV1]:
        result = await self._session.execute(
            select(EvidenceRow)
            .where(EvidenceRow.run_id == run_id)
            .order_by(EvidenceRow.created_at.asc())
        )
        return [evidence_to_domain(row) for row in result.scalars().all()]


class PostgresHypothesisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, hypothesis: HypothesisV1) -> HypothesisV1:
        payload = domain_to_payload(hypothesis)
        row = HypothesisRow(
            id=hypothesis.id,
            incident_id=hypothesis.incident_id,
            payload=payload,
            created_at=hypothesis.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return hypothesis


class PostgresActionProposalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, proposal: ActionProposalV1) -> ActionProposalV1:
        payload = domain_to_payload(proposal)
        row = ActionProposalRow(
            id=proposal.id,
            incident_id=proposal.incident_id,
            revision=proposal.revision,
            status=proposal.status.value,
            payload=payload,
            created_at=proposal.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return proposal


def create_outbox_row(envelope: DomainEventEnvelopeV1) -> OutboxRow:
    return OutboxRow(
        event_id=envelope.event_id,
        channel="events",
        payload=event_to_outbox_payload(envelope),
        created_at=envelope.recorded_at,
        published_at=None,
    )
