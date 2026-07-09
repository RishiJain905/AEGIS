"""Unit tests for Phase 24 approval workflow guards."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from aegis_api.approvals.errors import ApprovalWorkflowError
from aegis_api.approvals.service import ApprovalWorkflowService
from aegis_contracts.approvals import ApprovalErrorCode
from aegis_contracts.entities import ProposalStatus


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


def test_missing_authorization_token_rejected() -> None:
    service = ApprovalWorkflowService()
    with pytest.raises(ApprovalWorkflowError) as exc:
        service._assert_operator_token(None)
    assert exc.value.code == ApprovalErrorCode.UNAUTHORIZED


def test_invalid_authorization_token_rejected() -> None:
    service = ApprovalWorkflowService()
    with pytest.raises(ApprovalWorkflowError) as exc:
        service._assert_operator_token("agent-self-approve")
    assert exc.value.code == ApprovalErrorCode.UNAUTHORIZED


def test_default_actor_hook() -> None:
    service = ApprovalWorkflowService()
    assert service._resolve_actor(None) == "asset:operator-console"
    assert service._resolve_actor("asset:operator-alt") == "asset:operator-alt"
