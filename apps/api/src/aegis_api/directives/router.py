"""Standing-directive HTTP routes (Phase 7).

Ownership-gated (owner-or-admin, 404 on unknown run, 403 otherwise) like every other
run-scoped router. Create/delete are investigation write actions (they steer autonomous
tasking); listing is a read.
"""

from __future__ import annotations

from typing import Annotated

from aegis_contracts import (
    AuthenticatedActorV1,
    CreateDirectiveRequestV1,
    PermissionV1,
    StandingDirectiveV1,
)
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from fastapi import APIRouter, Depends, HTTPException

from aegis_api.auth.deps import require_actor, require_permission
from aegis_api.auth.run_authz import require_run_access
from aegis_api.db.session import get_db_session_maker
from aegis_api.directives.service import DirectiveNotFoundError, DirectiveService

router = APIRouter(prefix="/api/v1", tags=["directives"])
_service = DirectiveService()

_TRIGGER = [Depends(require_permission(PermissionV1.INVESTIGATION_TRIGGER))]
_READ = [Depends(require_permission(PermissionV1.INVESTIGATION_READ))]


@router.post(
    "/runs/{run_id}/directives",
    response_model=StandingDirectiveV1,
    dependencies=_TRIGGER,
)
async def create_directive(
    run_id: str,
    request: CreateDirectiveRequestV1,
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
) -> StandingDirectiveV1:
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        await require_run_access(uow, run_id, actor)
        return await _service.create(
            uow, run_id=run_id, request=request, actor_id=actor.user_id
        )


@router.get("/runs/{run_id}/directives", dependencies=_READ)
async def list_directives(
    run_id: str,
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
) -> dict[str, object]:
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        await require_run_access(uow, run_id, actor)
        directives = await _service.list_for_run(uow, run_id=run_id)
    return {
        "directives": [d.model_dump(by_alias=True, mode="json") for d in directives]
    }


@router.delete(
    "/runs/{run_id}/directives/{directive_id}",
    response_model=StandingDirectiveV1,
    dependencies=_TRIGGER,
)
async def delete_directive(
    run_id: str,
    directive_id: str,
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
) -> StandingDirectiveV1:
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        await require_run_access(uow, run_id, actor)
        try:
            return await _service.delete(
                uow, run_id=run_id, directive_id=directive_id, actor_id=actor.user_id
            )
        except DirectiveNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Directive not found") from exc
