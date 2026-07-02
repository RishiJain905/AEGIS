"""PostgreSQL unit-of-work with atomic state, event, and outbox commits."""

from __future__ import annotations

from types import TracebackType

from aegis_contracts import AegisSettings, DomainEventEnvelopeV1
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aegis_persistence.repositories.postgres import (
    PostgresAlertRepository,
    PostgresCheckpointRepository,
    PostgresEventRepository,
    PostgresIdempotencyRepository,
    PostgresIncidentRepository,
    PostgresModelRepository,
    PostgresObjectRepository,
    PostgresRiskScoreRepository,
    PostgresRunRepository,
    PostgresScenarioRepository,
    PostgresScenarioVersionRepository,
    create_outbox_row,
)


class PostgresUnitOfWork:
    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        *,
        settings: AegisSettings | None = None,
    ) -> None:
        self._session_maker = session_maker
        self._settings = settings
        self._session: AsyncSession | None = None
        self._owns_session = False

    async def __aenter__(self) -> PostgresUnitOfWork:
        if self._session is None:
            self._session = self._session_maker()
            self._owns_session = True
        self._scenarios = PostgresScenarioRepository(self._session)
        self._scenario_versions = PostgresScenarioVersionRepository(self._session)
        self._runs = PostgresRunRepository(self._session)
        self._events = PostgresEventRepository(self._session)
        self._incidents = PostgresIncidentRepository(self._session)
        self._alerts = PostgresAlertRepository(self._session)
        self._idempotency = PostgresIdempotencyRepository(self._session)
        self._objects = PostgresObjectRepository(self._session)
        self._models = PostgresModelRepository(self._session)
        self._risk_scores = PostgresRiskScoreRepository(self._session)
        self._checkpoints = PostgresCheckpointRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._session is None:
            return
        try:
            if exc_type is not None:
                await self._session.rollback()
            else:
                await self._session.commit()
        finally:
            if self._owns_session:
                await self._session.close()
                self._session = None

    @property
    def scenarios(self) -> PostgresScenarioRepository:
        return self._scenarios

    @property
    def scenario_versions(self) -> PostgresScenarioVersionRepository:
        return self._scenario_versions

    @property
    def runs(self) -> PostgresRunRepository:
        return self._runs

    @property
    def events(self) -> EventRepositoryProxy:
        return EventRepositoryProxy(self._events)

    @property
    def alerts(self) -> PostgresAlertRepository:
        return self._alerts

    @property
    def incidents(self) -> PostgresIncidentRepository:
        return self._incidents

    @property
    def idempotency(self) -> PostgresIdempotencyRepository:
        return self._idempotency

    @property
    def objects(self) -> PostgresObjectRepository:
        return self._objects

    @property
    def models(self) -> PostgresModelRepository:
        return self._models

    @property
    def risk_scores(self) -> PostgresRiskScoreRepository:
        return self._risk_scores

    @property
    def checkpoints(self) -> PostgresCheckpointRepository:
        return self._checkpoints

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            msg = "UnitOfWork is not active"
            raise RuntimeError(msg)
        return self._session

    async def append_event(self, envelope: DomainEventEnvelopeV1) -> DomainEventEnvelopeV1:
        stored = await self._events.append(envelope)
        self.session.add(create_outbox_row(stored))
        return stored

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()


class EventRepositoryProxy:
    """Events must be appended via UnitOfWork.append_event for outbox atomicity."""

    def __init__(self, repository: PostgresEventRepository) -> None:
        self._repository = repository

    async def get_by_id(self, event_id: str) -> DomainEventEnvelopeV1 | None:
        return await self._repository.get_by_id(event_id)

    async def append(self, envelope: DomainEventEnvelopeV1) -> DomainEventEnvelopeV1:
        msg = "Use UnitOfWork.append_event to persist events with outbox rows"
        raise RuntimeError(msg)
