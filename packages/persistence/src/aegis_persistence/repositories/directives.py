"""Standing-directive persistence (Phase 7).

A standing directive is a persistent operator tasking re-evaluated by the autonomy loop
when new matching evidence lands. The row's JSONB payload is the ``StandingDirectiveV1``
identity; ``run_id`` + ``active`` columns back the poller's per-run active query.
"""

from __future__ import annotations

from aegis_contracts import StandingDirectiveV1
from aegis_contracts.parsing import parse_contract
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_persistence.mappers import domain_to_payload
from aegis_persistence.orm.tables import AgentDirectiveRow


def _to_domain(row: AgentDirectiveRow) -> StandingDirectiveV1:
    return parse_contract(StandingDirectiveV1, row.payload)


class PostgresDirectiveRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, directive: StandingDirectiveV1) -> StandingDirectiveV1:
        row = AgentDirectiveRow(
            id=directive.id,
            run_id=directive.run_id,
            active=directive.active,
            created_by=directive.created_by,
            payload=domain_to_payload(directive),
            created_at=directive.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return directive

    async def get(self, directive_id: str) -> StandingDirectiveV1 | None:
        row = await self._session.get(AgentDirectiveRow, directive_id)
        return _to_domain(row) if row is not None else None

    async def list_for_run(self, run_id: str) -> list[StandingDirectiveV1]:
        result = await self._session.execute(
            select(AgentDirectiveRow)
            .where(AgentDirectiveRow.run_id == run_id)
            .order_by(AgentDirectiveRow.created_at)
        )
        return [_to_domain(row) for row in result.scalars().all()]

    async def list_active_for_run(self, run_id: str) -> list[StandingDirectiveV1]:
        result = await self._session.execute(
            select(AgentDirectiveRow)
            .where(AgentDirectiveRow.run_id == run_id, AgentDirectiveRow.active.is_(True))
            .order_by(AgentDirectiveRow.created_at)
        )
        return [_to_domain(row) for row in result.scalars().all()]

    async def deactivate(self, directive_id: str) -> StandingDirectiveV1 | None:
        row = await self._session.get(AgentDirectiveRow, directive_id)
        if row is None:
            return None
        updated = _to_domain(row).model_copy(update={"active": False})
        row.active = False
        row.payload = domain_to_payload(updated)
        await self._session.flush()
        return updated
