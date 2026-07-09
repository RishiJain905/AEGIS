"""Approval workflow HTTP routes."""

from __future__ import annotations

from aegis_contracts import ApiErrorEnvelopeV1
from aegis_contracts.approvals import (
    ApproveProposalRequestV1,
    ApproveProposalResponseV1,
    CancelProposalRequestV1,
    ModifyProposalRequestV1,
    ModifyProposalResponseV1,
    RejectProposalRequestV1,
    RejectProposalResponseV1,
)
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse

from aegis_api.approvals.errors import ApprovalWorkflowError
from aegis_api.approvals.service import ApprovalWorkflowService
from aegis_api.commands.mapping import DEFAULT_AUTHORIZATION_TOKEN
from aegis_api.db.session import get_db_session_maker

router = APIRouter(prefix="/api/v1", tags=["approvals"])
_service = ApprovalWorkflowService()


def _error_response(exc: ApprovalWorkflowError) -> JSONResponse:
    envelope = ApiErrorEnvelopeV1(
        schema_version=1,
        code=exc.code.value,
        message=exc.message,
        details=exc.details,
    )
    return JSONResponse(status_code=exc.status_code, content=envelope.model_dump(by_alias=True))


def _resolve_actor_header(x_actor_id: str | None) -> str | None:
    return x_actor_id


def _resolve_auth_token(authorization: str | None) -> str:
    if authorization is None:
        return DEFAULT_AUTHORIZATION_TOKEN
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return authorization


@router.post(
    "/action-proposals/{proposal_id}/approve",
    response_model=ApproveProposalResponseV1,
)
async def approve_proposal(
    proposal_id: str,
    request: ApproveProposalRequestV1,
    x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> ApproveProposalResponseV1 | JSONResponse:
    if request.proposal_id != proposal_id:
        raise HTTPException(status_code=400, detail="proposalId mismatch")
    try:
        async with PostgresUnitOfWork(get_db_session_maker()) as uow:
            return await _service.approve(
                uow,
                request,
                actor_id=_resolve_actor_header(x_actor_id),
                authorization_token=_resolve_auth_token(authorization),
            )
    except ApprovalWorkflowError as exc:
        return _error_response(exc)


@router.post(
    "/action-proposals/{proposal_id}/reject",
    response_model=RejectProposalResponseV1,
)
async def reject_proposal(
    proposal_id: str,
    request: RejectProposalRequestV1,
    x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> RejectProposalResponseV1 | JSONResponse:
    if request.proposal_id != proposal_id:
        raise HTTPException(status_code=400, detail="proposalId mismatch")
    try:
        async with PostgresUnitOfWork(get_db_session_maker()) as uow:
            return await _service.reject(
                uow,
                request,
                actor_id=_resolve_actor_header(x_actor_id),
                authorization_token=_resolve_auth_token(authorization),
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
    x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> ModifyProposalResponseV1 | JSONResponse:
    if request.proposal_id != proposal_id:
        raise HTTPException(status_code=400, detail="proposalId mismatch")
    try:
        async with PostgresUnitOfWork(get_db_session_maker()) as uow:
            return await _service.modify(
                uow,
                request,
                actor_id=_resolve_actor_header(x_actor_id),
                authorization_token=_resolve_auth_token(authorization),
            )
    except ApprovalWorkflowError as exc:
        return _error_response(exc)


@router.post("/action-proposals/{proposal_id}/cancel")
async def cancel_proposal(
    proposal_id: str,
    request: CancelProposalRequestV1,
    x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, object] | JSONResponse:
    if request.proposal_id != proposal_id:
        raise HTTPException(status_code=400, detail="proposalId mismatch")
    try:
        async with PostgresUnitOfWork(get_db_session_maker()) as uow:
            return await _service.cancel(
                uow,
                request,
                actor_id=_resolve_actor_header(x_actor_id),
                authorization_token=_resolve_auth_token(authorization),
            )
    except ApprovalWorkflowError as exc:
        return _error_response(exc)
