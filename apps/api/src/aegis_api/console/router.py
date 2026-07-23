"""Operator console + ops-feed HTTP routes (Phase 7).

Ownership-gated (owner-or-admin, 404/403) run-scoped reads. The console gives the player
the agents' read surface; the feed is the unified live heartbeat of agent findings, player
actions, detections and reveals — a thin projection over the events table.
"""

from __future__ import annotations

from typing import Annotated

from aegis_contracts import (
    AuthenticatedActorV1,
    ConsoleEventSearchRequestV1,
    ConsoleEventSearchResultV1,
    RunFeedPageV1,
)
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from aegis_api.auth.deps import require_actor
from aegis_api.auth.run_authz import require_run_access
from aegis_api.console.service import ConsoleService
from aegis_api.db.session import get_db_session_maker

router = APIRouter(prefix="/api/v1", tags=["console"])
_service = ConsoleService()


@router.post(
    "/runs/{run_id}/console/events/search",
    response_model=ConsoleEventSearchResultV1,
)
async def search_console_events(
    run_id: str,
    request: ConsoleEventSearchRequestV1,
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
) -> ConsoleEventSearchResultV1 | JSONResponse:
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        await require_run_access(uow, run_id, actor)
        return await _service.search_events(uow, run_id=run_id, request=request)


@router.get("/runs/{run_id}/feed", response_model=RunFeedPageV1)
async def get_run_feed(
    run_id: str,
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
    cursor: int | None = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> RunFeedPageV1 | JSONResponse:
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        await require_run_access(uow, run_id, actor)
        return await _service.feed(uow, run_id=run_id, cursor=cursor, limit=limit)
