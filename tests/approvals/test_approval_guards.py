"""Unit tests for Phase 24/30 approval workflow guards."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from aegis_api.approvals.errors import ApprovalWorkflowError
from aegis_api.approvals.service import ApprovalWorkflowService
from aegis_contracts import PlatformRoleV1
from aegis_contracts.approvals import ApprovalErrorCode
from aegis_contracts.entities import ProposalStatus
from aegis_policy.authz import build_actor


def test_stale_revision_fails_closed() -> None:
    service = ApprovalWorkflowService()
    proposal = SimpleNamespace(
        id="prp_01ARZ3NDEKTSV4RRFFQ69G5FAY",
        current_revision_id="prv_01ARZ3NDEKTSV4RRFFQ69G5FB1",
        revision=2,
        status=ProposalStatus.PENDING,
    )
    with pytest.raises(ApprovalWorkflowError) as exc:
        service._assert_revision_match(
            proposal,
            expected_revision_id="prv_01ARZ3NDEKTSV4RRFFQ69G5FB0",
            expected_revision=1,
        )
    assert exc.value.code == ApprovalErrorCode.STALE_PROPOSAL
    assert exc.value.status_code == 409


def test_non_pending_proposal_cannot_be_approved() -> None:
    service = ApprovalWorkflowService()
    proposal = SimpleNamespace(status=ProposalStatus.EXECUTED)
    with pytest.raises(ApprovalWorkflowError) as exc:
        service._assert_pending(proposal)
    assert exc.value.code == ApprovalErrorCode.ALREADY_DECIDED


def test_viewer_cannot_resolve_as_approver() -> None:
    service = ApprovalWorkflowService()
    viewer = build_actor(
        user_id="user:viewer-alpha",
        display_name="Viewer",
        roles=[PlatformRoleV1.VIEWER],
        session_id="sess_viewer",
        auth_method="dev",
    )
    with pytest.raises(ApprovalWorkflowError) as exc:
        service._resolve_authenticated_actor(viewer)
    assert exc.value.code == ApprovalErrorCode.UNAUTHORIZED


def test_operator_resolves_to_user_id_and_session_token() -> None:
    service = ApprovalWorkflowService()
    operator = build_actor(
        user_id="user:operator-alpha",
        display_name="Operator",
        roles=[PlatformRoleV1.OPERATOR],
        session_id="sess_operator",
        auth_method="dev",
    )
    actor_id, token = service._resolve_authenticated_actor(operator)
    assert actor_id == "user:operator-alpha"
    assert token == "session:sess_operator"
