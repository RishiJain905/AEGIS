"""Operator console + ops-feed HTTP routes (Phase 7).

Ownership-gated (owner-or-admin, 404/403) run-scoped reads. The console gives the player
the agents' read surface; the feed is the unified live heartbeat of agent findings, player
actions, detections and reveals — a thin projection over the events table.
"""

from __future__ import annotations

from typing import Annotated

from aegis_contracts import (
    AuthenticatedActorV1,
    ConsoleAssetDetailV1,
    ConsoleEventSearchRequestV1,
    ConsoleEventSearchResultV1,
    HypothesisV1,
    OperatorHypothesisRequestV1,
    RunFeedPageV1,
)
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from aegis_api.auth.deps import require_actor
from aegis_api.auth.run_authz import require_run_access
from aegis_api.console.service import ConsoleService
from aegis_api.db.session import get_db_session_maker
from aegis_api.operator_actions.service import OperatorActionError, OperatorActionService

router = APIRouter(prefix="/api/v1", tags=["console"])
_service = ConsoleService()
_operator_service = OperatorActionService()


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


@router.get(
    "/runs/{run_id}/console/assets/{asset_id}",
    response_model=ConsoleAssetDetailV1,
)
async def get_console_asset(
    run_id: str,
    asset_id: str,
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
) -> ConsoleAssetDetailV1 | JSONResponse:
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        await require_run_access(uow, run_id, actor)
        detail = await _service.asset_detail(uow, run_id=run_id, asset_id=asset_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Asset not found for run")
    return detail


@router.post(
    "/runs/{run_id}/console/hypotheses",
    response_model=HypothesisV1,
)
async def create_console_hypothesis(
    run_id: str,
    request: OperatorHypothesisRequestV1,
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
) -> HypothesisV1 | JSONResponse:
    try:
        async with PostgresUnitOfWork(get_db_session_maker()) as uow:
            await require_run_access(uow, run_id, actor)
            return await _operator_service.create_hypothesis(
                uow, run_id=run_id, request=request, actor_id=actor.user_id
            )
    except OperatorActionError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.get("/runs/{run_id}/console/hypotheses")
async def list_console_hypotheses(
    run_id: str,
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
    incident_id: str | None = Query(default=None, alias="incidentId"),
) -> dict[str, object]:
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        await require_run_access(uow, run_id, actor)
        hypotheses = await _operator_service.list_hypotheses(
            uow, run_id=run_id, incident_id=incident_id
        )
    return {
        "hypotheses": [h.model_dump(by_alias=True, mode="json") for h in hypotheses]
    }


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
