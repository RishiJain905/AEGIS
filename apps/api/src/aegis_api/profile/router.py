"""Operator skill-telemetry profile routes (owner-scoped, read-only)."""

from __future__ import annotations

from typing import Annotated

from aegis_contracts import AuthenticatedActorV1, OperatorProfileV1
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from aegis_scoring.operator_profile import DEFAULT_MAX_RUNS, assemble_operator_profile
from fastapi import APIRouter, Depends, HTTPException, Query

from aegis_api.auth.deps import require_actor
from aegis_api.auth.run_authz import actor_is_admin
from aegis_api.db.session import get_db_session_maker

router = APIRouter(prefix="/api/v1", tags=["profile"])


@router.get("/profile/operator", response_model=OperatorProfileV1)
async def get_operator_profile(
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
    user_id: Annotated[str | None, Query(alias="userId")] = None,
    max_runs: Annotated[int, Query(alias="maxRuns", ge=1, le=DEFAULT_MAX_RUNS)] = DEFAULT_MAX_RUNS,
) -> OperatorProfileV1:
    """Return the caller's cross-run skill-telemetry profile.

    Ownership: a non-admin may only read their own profile. ``userId`` defaults to the
    caller; supplying another user's id is a 403 unless the caller is an admin. The
    aggregation only ever touches runs owned by the resolved ``userId``.
    """
    target_user_id = user_id or actor.user_id
    if target_user_id != actor.user_id and not actor_is_admin(actor):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to read another operator's profile",
        )

    session_maker = get_db_session_maker()
    async with PostgresUnitOfWork(session_maker) as uow:
        return await assemble_operator_profile(
            uow, owner_user_id=target_user_id, max_runs=max_runs
        )
