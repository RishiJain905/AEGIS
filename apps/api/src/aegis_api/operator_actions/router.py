"""Operator direct-action and rules-of-engagement HTTP routes (Phase 7).

Ownership-gated: every route resolves + authorizes ``run_id`` (owner-or-admin, 404 on
unknown run, 403 otherwise) before doing any work, exactly like the other run-scoped
routers. State-changing player actions flow through the policy engine; RoE changes are
audited via a ``run.roe_changed`` domain event.
"""

from __future__ import annotations

from typing import Annotated

from aegis_agents.runtime.ids import new_runtime_id
from aegis_contracts import (
    ApiErrorEnvelopeV1,
    AuthenticatedActorV1,
    OperatorActionRequestV1,
    OperatorActionResponseV1,
    PermissionV1,
    RoeChangeRequestV1,
    RunLoadoutV1,
    RunV1,
)
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from aegis_api.auth.deps import require_actor, require_permission
from aegis_api.auth.run_authz import require_run_access
from aegis_api.db.session import get_db_session_maker
from aegis_api.operator_actions.events import build_run_roe_changed_event
from aegis_api.operator_actions.service import OperatorActionError, OperatorActionService
from aegis_api.runs.service import get_run_command_service

router = APIRouter(prefix="/api/v1", tags=["operator"])
_service = OperatorActionService()
_run_service = get_run_command_service()

_WRITE = [Depends(require_permission(PermissionV1.RUNS_WRITE))]


def _error_response(exc: OperatorActionError) -> JSONResponse:
    envelope = ApiErrorEnvelopeV1(
        schema_version=1,
        code=exc.code,
        message=exc.message,
    )
    return JSONResponse(status_code=exc.status_code, content=envelope.model_dump(by_alias=True))


@router.post(
    "/runs/{run_id}/operator-actions",
    response_model=OperatorActionResponseV1,
    dependencies=_WRITE,
)
async def submit_operator_action(
    run_id: str,
    request: OperatorActionRequestV1,
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
) -> OperatorActionResponseV1 | JSONResponse:
    # An executed action mutates the run's shared cached runtime, so it serializes with the
    # tick engine and the manual lifecycle routes on the same per-run lock, held across the
    # commit. Eviction on failure happens inside the lock too: a rolled-back transaction may
    # have left a control on the in-memory world that no event stream records, and a tick
    # that observed it would checkpoint the divergence.
    async with _run_service.lock_for(run_id):
        try:
            async with PostgresUnitOfWork(get_db_session_maker()) as uow:
                await require_run_access(uow, run_id, actor)
                return await _service.submit_action(
                    uow, run_id=run_id, request=request, actor=actor
                )
        except OperatorActionError as exc:
            _run_service.evict(run_id)
            return _error_response(exc)
        except Exception:
            _run_service.evict(run_id)
            raise


@router.patch("/runs/{run_id}/roe", response_model=RunV1, dependencies=_WRITE)
async def change_run_roe(
    run_id: str,
    request: RoeChangeRequestV1,
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
) -> RunV1 | JSONResponse:
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        run = await require_run_access(uow, run_id, actor)
        current = run.loadout or RunLoadoutV1()
        previous_roe = current.roe.value
        if current.roe == request.roe:
            return run
        updated_loadout = current.model_copy(update={"roe": request.roe})
        updated = run.model_copy(
            update={"loadout": updated_loadout, "revision": run.revision + 1}
        )
        await uow.runs.update_with_revision(updated, expected_revision=run.revision)
        next_sequence = await uow.events.next_sequence(run_id)
        await uow.append_event(
            build_run_roe_changed_event(
                event_id=new_runtime_id("evt"),
                run_id=run_id,
                sequence=next_sequence,
                actor_id=actor.user_id,
                trace_id=new_runtime_id("trc"),
                previous_roe=previous_roe,
                new_roe=request.roe.value,
            )
        )
        return updated
