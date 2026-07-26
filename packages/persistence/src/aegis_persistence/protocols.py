"""Repository and unit-of-work protocol definitions."""

from __future__ import annotations

from typing import Protocol

from aegis_contracts import (
    AlertV1,
    DomainEventEnvelopeV1,
    IdempotencyRecordV1,
    IncidentV1,
    ObjectMetadataReferenceV1,
    RunV1,
    ScenarioV1,
    ScenarioVersionV1,
    SimulationCheckpointV1,
)


class ScenarioRepository(Protocol):
    async def get_by_id(self, scenario_id: str) -> ScenarioV1 | None: ...

    async def add(self, scenario: ScenarioV1) -> ScenarioV1: ...


class ScenarioVersionRepository(Protocol):
    async def get_by_id(self, version_id: str) -> ScenarioVersionV1 | None: ...

    async def add(self, version: ScenarioVersionV1) -> ScenarioVersionV1: ...


class RunRepository(Protocol):
    async def get_by_id(self, run_id: str) -> RunV1 | None: ...

    async def add(self, run: RunV1) -> RunV1: ...

    async def update_with_revision(
        self,
        run: RunV1,
        *,
        expected_revision: int,
    ) -> RunV1: ...

    async def delete(self, run_id: str) -> bool: ...


class EventRepository(Protocol):
    async def get_by_id(self, event_id: str) -> DomainEventEnvelopeV1 | None: ...

    async def append(self, envelope: DomainEventEnvelopeV1) -> DomainEventEnvelopeV1: ...


class AlertRepository(Protocol):
    async def get_by_id(self, alert_id: str) -> AlertV1 | None: ...

    async def list_by_run(self, run_id: str) -> list[AlertV1]: ...

    async def add(self, alert: AlertV1) -> AlertV1: ...

    async def exists_by_dedup_key(self, run_id: str, deduplication_key: str) -> bool: ...

    async def list_dedup_keys_for_run(self, run_id: str) -> set[str]: ...


class IncidentRepository(Protocol):
    async def get_by_id(self, incident_id: str) -> IncidentV1 | None: ...

    async def add(self, incident: IncidentV1) -> IncidentV1: ...

    async def update_with_revision(
        self,
        incident: IncidentV1,
        *,
        expected_revision: int,
    ) -> IncidentV1: ...


class IdempotencyRepository(Protocol):
    async def get(
        self,
        *,
        scope: str,
        idempotency_key: str,
    ) -> IdempotencyRecordV1 | None: ...

    async def add(self, record: IdempotencyRecordV1) -> IdempotencyRecordV1: ...

    async def delete_by_response_ref(self, *, scope: str, response_ref: str) -> int: ...


class ObjectRepository(Protocol):
    async def get_by_key(self, object_key: str) -> ObjectMetadataReferenceV1 | None: ...

    async def add(self, reference: ObjectMetadataReferenceV1) -> ObjectMetadataReferenceV1: ...


class CheckpointRepository(Protocol):
    async def get_by_id(self, checkpoint_id: str) -> SimulationCheckpointV1 | None: ...

    async def get_latest_for_run(self, run_id: str) -> SimulationCheckpointV1 | None: ...

    async def add(self, checkpoint: SimulationCheckpointV1) -> SimulationCheckpointV1: ...


class UnitOfWork(Protocol):
  @property
  def scenarios(self) -> ScenarioRepository: ...

  @property
  def scenario_versions(self) -> ScenarioVersionRepository: ...

  @property
  def runs(self) -> RunRepository: ...

  @property
  def events(self) -> EventRepository: ...

  @property
  def alerts(self) -> AlertRepository: ...

  @property
  def incidents(self) -> IncidentRepository: ...

  @property
  def idempotency(self) -> IdempotencyRepository: ...

  @property
  def objects(self) -> ObjectRepository: ...

  @property
  def checkpoints(self) -> CheckpointRepository: ...

  async def append_event(self, envelope: DomainEventEnvelopeV1) -> DomainEventEnvelopeV1: ...

  async def commit(self) -> None: ...

  async def rollback(self) -> None: ...
