"""Ghost branch — post-run counterfactual replay routes (after-action).

Read-only from the run's perspective: the engine reconstructs throwaway runtimes and never
writes to the run's event stream, snapshots, alerts, or outbox. Both routes are ownership
gated (``require_run_access``) and refuse until the run is terminal (fog of war + honest
scoring): a counterfactual only makes sense once the real timeline is settled.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from aegis_contracts import (
    AuthenticatedActorV1,
    GhostBranchRequestV1,
    GhostBranchResultV1,
    GhostDecisionPointsV1,
    RunV1,
)
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from aegis_simulation.disclosure_resolver import ACTIVE_RUN_STATUSES
from aegis_simulation.ghost_engine import GhostBranchEngine, GhostBranchError
from fastapi import APIRouter, Depends, HTTPException

from aegis_api.auth.deps import require_actor
from aegis_api.auth.run_authz import require_run_access
from aegis_api.db.session import get_db_session_maker

# apps/api/src/aegis_api/ghost/router.py → repo root.
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]

router = APIRouter(prefix="/api/v1", tags=["ghost"])
_ghost_engine = GhostBranchEngine(workspace_root=WORKSPACE_ROOT)


def _require_terminal(run: RunV1) -> None:
    """Ghost branch is post-run only: refuse while the run is still active."""
    if run.status in ACTIVE_RUN_STATUSES:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "RUN_NOT_TERMINAL",
                "message": "Ghost branch is available only after the run ends",
                "details": {"status": str(run.status)},
            },
        )


def _http_error(exc: GhostBranchError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.message},
    )


@router.get(
    "/runs/{run_id}/ghost/decision-points",
    response_model=GhostDecisionPointsV1,
)
async def list_decision_points(
    run_id: str,
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
) -> GhostDecisionPointsV1:
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        run = await require_run_access(uow, run_id, actor)
        _require_terminal(run)
        try:
            return await _ghost_engine.enumerate_decision_points(uow, run_id)
        except GhostBranchError as exc:
            raise _http_error(exc) from exc


@router.post(
    "/runs/{run_id}/ghost",
    response_model=GhostBranchResultV1,
)
async def run_ghost_branch(
    run_id: str,
    request: GhostBranchRequestV1,
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
) -> GhostBranchResultV1:
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        run = await require_run_access(uow, run_id, actor)
        _require_terminal(run)
        try:
            return await _ghost_engine.run_ghost(uow, run_id, request)
        except GhostBranchError as exc:
            raise _http_error(exc) from exc
