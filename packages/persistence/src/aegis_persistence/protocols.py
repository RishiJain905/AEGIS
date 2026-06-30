"""Repository and unit-of-work protocol definitions."""

from __future__ import annotations

from typing import Protocol

from aegis_contracts import (
    DomainEventEnvelopeV1,
    IdempotencyRecordV1,
    IncidentV1,
    ObjectMetadataReferenceV1,
    RunV1,
    ScenarioV1,
    ScenarioVersionV1,
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


class EventRepository(Protocol):
    async def get_by_id(self, event_id: str) -> DomainEventEnvelopeV1 | None: ...

    async def append(self, envelope: DomainEventEnvelopeV1) -> DomainEventEnvelopeV1: ...


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


class ObjectRepository(Protocol):
    async def get_by_key(self, object_key: str) -> ObjectMetadataReferenceV1 | None: ...

    async def add(self, reference: ObjectMetadataReferenceV1) -> ObjectMetadataReferenceV1: ...


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
  def incidents(self) -> IncidentRepository: ...

  @property
  def idempotency(self) -> IdempotencyRepository: ...

  @property
  def objects(self) -> ObjectRepository: ...

  async def append_event(self, envelope: DomainEventEnvelopeV1) -> DomainEventEnvelopeV1: ...

  async def commit(self) -> None: ...

  async def rollback(self) -> None: ...
