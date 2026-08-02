"""Approval workflow HTTP routes."""

from __future__ import annotations

from typing import Annotated

from aegis_contracts import ApiErrorEnvelopeV1, AuthenticatedActorV1
from aegis_contracts.approvals import (
    ApproveProposalRequestV1,
    ApproveProposalResponseV1,
    CancelProposalRequestV1,
    CancelProposalResponseV1,
    ModifyProposalRequestV1,
    ModifyProposalResponseV1,
    RejectProposalRequestV1,
    RejectProposalResponseV1,
)
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from aegis_api.approvals.errors import ApprovalWorkflowError
from aegis_api.approvals.service import ApprovalWorkflowService
from aegis_api.auth.deps import require_actor
from aegis_api.db.session import get_db_session_maker
from aegis_api.runs.service import get_run_command_service

router = APIRouter(prefix="/api/v1", tags=["approvals"])
_service = ApprovalWorkflowService()
_run_service = get_run_command_service()


def _error_response(exc: ApprovalWorkflowError) -> JSONResponse:
    envelope = ApiErrorEnvelopeV1(
        schema_version=1,
        code=exc.code.value,
        message=exc.message,
        details=exc.details,
    )
    return JSONResponse(status_code=exc.status_code, content=envelope.model_dump(by_alias=True))


@router.post(
    "/action-proposals/{proposal_id}/approve",
    response_model=ApproveProposalResponseV1,
)
async def approve_proposal(
    proposal_id: str,
    request: ApproveProposalRequestV1,
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
) -> ApproveProposalResponseV1 | JSONResponse:
    if request.proposal_id != proposal_id:
        raise HTTPException(status_code=400, detail="proposalId mismatch")
    # Approving executes the command, which mutates the run's shared cached runtime — the
    # same object the tick engine steps. The run is resolved first (read-only) so the write
    # transaction can be serialized on that run's lock, exactly as the lifecycle routes and
    # the operator-action route are. A proposal whose run cannot be resolved never reaches
    # execution; the write path below reports the real error.
    async with PostgresUnitOfWork(get_db_session_maker()) as lookup_uow:
        run_id = await _service.resolve_run_id(lookup_uow, proposal_id)
    if run_id is None:
        try:
            return await _approve_in_transaction(request, actor)
        except ApprovalWorkflowError as exc:
            return _error_response(exc)
    async with _run_service.lock_for(run_id):
        try:
            return await _approve_in_transaction(request, actor)
        except ApprovalWorkflowError as exc:
            # A failed execution rolls the transaction back; the runtime it mutated must not
            # outlive it, and eviction stays inside the lock so no tick can see the interim.
            _run_service.evict(run_id)
            return _error_response(exc)
        except Exception:
            _run_service.evict(run_id)
            raise


async def _approve_in_transaction(
    request: ApproveProposalRequestV1,
    actor: AuthenticatedActorV1,
) -> ApproveProposalResponseV1:
    async with PostgresUnitOfWork(get_db_session_maker()) as uow:
        return await _service.approve(
            uow,
            request,
            authenticated_actor=actor,
        )


@router.post(
    "/action-proposals/{proposal_id}/reject",
    response_model=RejectProposalResponseV1,
)
async def reject_proposal(
    proposal_id: str,
    request: RejectProposalRequestV1,
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
) -> RejectProposalResponseV1 | JSONResponse:
    if request.proposal_id != proposal_id:
        raise HTTPException(status_code=400, detail="proposalId mismatch")
    try:
        async with PostgresUnitOfWork(get_db_session_maker()) as uow:
            return await _service.reject(
                uow,
                request,
                authenticated_actor=actor,
            )
    except ApprovalWorkflowError as exc:
        return _error_response(exc)


@router.post(
    "/action-proposals/{proposal_id}/modify",
    response_model=ModifyProposalResponseV1,
)
async def modify_proposal(
    proposal_id: str,
    request: ModifyProposalRequestV1,
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
) -> ModifyProposalResponseV1 | JSONResponse:
    if request.proposal_id != proposal_id:
        raise HTTPException(status_code=400, detail="proposalId mismatch")
    try:
        async with PostgresUnitOfWork(get_db_session_maker()) as uow:
            return await _service.modify(
                uow,
                request,
                authenticated_actor=actor,
            )
    except ApprovalWorkflowError as exc:
        return _error_response(exc)


@router.post(
    "/action-proposals/{proposal_id}/cancel",
    response_model=CancelProposalResponseV1,
)
async def cancel_proposal(
    proposal_id: str,
    request: CancelProposalRequestV1,
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
) -> CancelProposalResponseV1 | JSONResponse:
    if request.proposal_id != proposal_id:
        raise HTTPException(status_code=400, detail="proposalId mismatch")
    try:
        async with PostgresUnitOfWork(get_db_session_maker()) as uow:
            return await _service.cancel(
                uow,
                request,
                authenticated_actor=actor,
            )
    except ApprovalWorkflowError as exc:
        return _error_response(exc)
