"""Regression test for AEGIS-BUG-003 — approval serialized on proposal identity.

Two approvers holding ``approvals:decide`` submit ``approve`` for the same
PENDING proposal concurrently, each with a *different* idempotency key. The
``SELECT ... FOR UPDATE`` row lock on the proposal serializes them: exactly one
executes the containment; the other observes the terminal state and is rejected
with ALREADY_DECIDED. Without the lock both passed the PENDING/revision checks
and final WARDEN revalidation and executed the same action twice.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from aegis_api.approvals.errors import ApprovalWorkflowError
from aegis_api.approvals.service import ApprovalWorkflowService
from aegis_contracts import PlatformRoleV1
from aegis_contracts.approvals import (
    ApprovalErrorCode,
    ApproveProposalRequestV1,
    ApproveProposalResponseV1,
)
from aegis_contracts.entities import ProposalStatus
from aegis_contracts.versioning import APPROVE_PROPOSAL_REQUEST_SCHEMA_VERSION
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from aegis_policy.authz import build_actor
from aegis_simulation import run_command_service as run_command_module
from aegis_simulation.run_command_service import RunCommandService
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.integration.agents.helpers import seed_investigation_run
from tests.integration.approvals.test_approval_workflow import _seed_approval_required_proposal

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]


def _operator_actor(session_id: str):
    return build_actor(
        user_id="user:operator-alpha",
        display_name="Operator Alpha",
        roles=[PlatformRoleV1.OPERATOR],
        session_id=session_id,
        auth_method="dev",
    )


@pytest.mark.asyncio
async def test_concurrent_approve_distinct_keys_executes_once(
    session_maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    _ = db_session
    run_command_module.SCENARIO_PACKAGE_BY_VERSION[
        "scenario-version:watchtower-trace-test-v1"
    ] = "scenarios/_fixtures/valid-minimal"
    service = ApprovalWorkflowService(
        run_command_service=RunCommandService(workspace_root=WORKSPACE_ROOT)
    )

    async with PostgresUnitOfWork(session_maker) as uow:
        incident_id, run_id, _alert_ids, evidence_id = await seed_investigation_run(uow)
        proposal = await _seed_approval_required_proposal(
            uow, incident_id=incident_id, run_id=run_id, evidence_id=evidence_id
        )

    def _request(key: str) -> ApproveProposalRequestV1:
        return ApproveProposalRequestV1(
            schema_version=APPROVE_PROPOSAL_REQUEST_SCHEMA_VERSION,
            proposal_id=proposal.id,
            expected_revision_id=proposal.current_revision_id or "",
            expected_revision=proposal.revision,
            comment="concurrent approve",
            idempotency_key=key,
        )

    async def _approve(key: str, session_id: str) -> object:
        async with PostgresUnitOfWork(session_maker) as uow:
            return await service.approve(
                uow,
                _request(key),
                authenticated_actor=_operator_actor(session_id),
            )

    results = await asyncio.gather(
        _approve("approve-key-a", "sess_concurrent_a"),
        _approve("approve-key-b", "sess_concurrent_b"),
        return_exceptions=True,
    )

    successes = [r for r in results if isinstance(r, ApproveProposalResponseV1)]
    failures = [r for r in results if isinstance(r, ApprovalWorkflowError)]
    unexpected = [
        r for r in results if not isinstance(r, (ApproveProposalResponseV1, ApprovalWorkflowError))
    ]

    assert unexpected == [], f"unexpected results: {unexpected}"
    assert len(successes) == 1
    assert len(failures) == 1
    assert successes[0].execution is not None
    assert successes[0].execution.success is True
    assert successes[0].proposal_status == ProposalStatus.EXECUTED
    assert failures[0].code == ApprovalErrorCode.ALREADY_DECIDED

    async with PostgresUnitOfWork(session_maker) as uow:
        actions = await uow.executed_actions.list_for_proposal(proposal.id)
        events = await uow.events.list_by_run(run_id)
    assert len(actions) == 1
    executed_events = [event for event in events if event.type == "action.executed"]
    assert len(executed_events) == 1
