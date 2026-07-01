"""Authoritative domain event history from PostgreSQL."""

from __future__ import annotations

from aegis_contracts import DomainEventEnvelopeV1
from aegis_persistence.repositories.streaming import PostgresEventQueryRepository
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from aegis_api.db.session import db_session

router = APIRouter(prefix="/api/v1/realtime", tags=["realtime"])


class RunEventsResponse(BaseModel):
    run_id: str = Field(alias="runId")
    event_count: int = Field(alias="eventCount")
    events: list[DomainEventEnvelopeV1]

    model_config = {"populate_by_name": True}


@router.get("/runs/{run_id}/events", response_model=RunEventsResponse)
async def list_run_events(
    run_id: str,
    request: Request,
    from_sequence: int | None = None,
    to_sequence: int | None = None,
    limit: int = 500,
) -> RunEventsResponse:
    _ = request
    async with db_session() as session:
        events = await PostgresEventQueryRepository(session).list_by_run(
            run_id,
            from_sequence=from_sequence,
            to_sequence=to_sequence,
            limit=limit,
        )
    return RunEventsResponse(run_id=run_id, event_count=len(events), events=events)
