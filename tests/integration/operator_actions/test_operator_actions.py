"""Phase 7 operator direct-action policy-path integration tests.

Exercise the "2v1" containment mechanic through the real policy engine:

* Class 0/1 (ALLOW)            -> auto-approve + execute.
* Class 2/3 (APPROVAL_REQUIRED) -> confirm required; without confirm the proposal is left
  PENDING with NO executed action (no bypass); with confirm the operator (incident
  commander) approves + executes.
* Scenario-restricted commands -> BLOCKED, never overridden.
* Confirming a Class 2/3 action without approvals:decide -> 403.

Execution itself is stubbed (the real ``_execute_authorized`` wiring is covered by the
approval-workflow integration test) so routing is asserted deterministically without a live
simulation runtime.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest
from aegis_agents.runtime.ids import new_runtime_id
from aegis_api.approvals.service import ApprovalWorkflowService
from aegis_api.operator_actions.service import OperatorActionError, OperatorActionService
from aegis_contracts import ExecutedActionV1, PermissionV1, PlatformRoleV1, ProposalStatus
from aegis_contracts.approvals import ExecutionResultV1
from aegis_contracts.operator import (
    OperatorActionRequestV1,
    OperatorActionStatusV1,
)
from aegis_contracts.proposals import PolicyOutcomeV1, ScenarioCommandTemplateV1
from aegis_contracts.versioning import (
    EXECUTED_ACTION_SCHEMA_VERSION,
    EXECUTION_RESULT_SCHEMA_VERSION,
    OPERATOR_ACTION_REQUEST_SCHEMA_VERSION,
)
from aegis_persistence.engine import create_engine, get_session_maker
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from aegis_policy.authz import build_actor

from tests.integration.agents.helpers import seed_investigation_run

pytestmark = pytest.mark.skipif(
    os.getenv("AEGIS_INTEGRATION_POSTGRES") != "1",
    reason="Requires PostgreSQL integration environment",
)


class _StubExecApprovals(ApprovalWorkflowService):
    """Real policy check, canned execution so routing is deterministic offline."""

    async def _execute_authorized(self, uow, **kwargs):  # type: ignore[override]
        now = datetime.now(UTC)
        result_event_id = new_runtime_id("evt")
        executed = ExecutedActionV1(
            schema_version=EXECUTED_ACTION_SCHEMA_VERSION,
            id=new_runtime_id("act"),
            proposal_id=kwargs["proposal_id"],
            run_id=kwargs["run_id"],
            result_event_id=result_event_id,
            idempotency_key=kwargs["idempotency_key"],
            executed_at=now,
        )
        return ExecutionResultV1(
            schema_version=EXECUTION_RESULT_SCHEMA_VERSION,
            executed_action=executed,
            result_event_id=result_event_id,
            command_id=kwargs["idempotency_key"],
            success=True,
            replayed=False,
            message="stub",
        )


def _operator():
    return build_actor(
        user_id="user:operator-p7",
        display_name="Operator P7",
        roles=[PlatformRoleV1.OPERATOR],
        session_id="sess_p7_operator",
        auth_method="dev",
    )


def _viewer():
    return build_actor(
        user_id="user:viewer-p7",
        display_name="Viewer P7",
        roles=[PlatformRoleV1.VIEWER],
        session_id="sess_p7_viewer",
        auth_method="dev",
    )


def _request(command: ScenarioCommandTemplateV1, *, confirm: bool, key: str):
    return OperatorActionRequestV1(
        schema_version=OPERATOR_ACTION_REQUEST_SCHEMA_VERSION,
        scenario_command=command,
        target_asset_id="asset:device-workstation-01",
        reason="Operator containment decision.",
        confirm=confirm,
        idempotency_key=key,
    )


def _session_maker():
    from aegis_contracts import load_settings

    settings = load_settings()
    return get_session_maker(settings, engine=create_engine(settings))


@pytest.mark.asyncio
async def test_class0_observe_auto_executes() -> None:
    service = OperatorActionService(approvals=_StubExecApprovals())
    async with PostgresUnitOfWork(_session_maker()) as uow:
        _incident, run_id, _alerts, _ev = await seed_investigation_run(uow)
        response = await service.submit_action(
            uow,
            run_id=run_id,
            request=_request(ScenarioCommandTemplateV1.OBSERVE, confirm=False, key="op-obs-1"),
            actor=_operator(),
        )
    assert response.policy_outcome == PolicyOutcomeV1.ALLOW
    assert response.status == OperatorActionStatusV1.EXECUTED
    assert response.executed is True


@pytest.mark.asyncio
async def test_class2_isolate_requires_confirmation() -> None:
    service = OperatorActionService(approvals=_StubExecApprovals())
    async with PostgresUnitOfWork(_session_maker()) as uow:
        _incident, run_id, _alerts, _ev = await seed_investigation_run(uow)
        response = await service.submit_action(
            uow,
            run_id=run_id,
            request=_request(ScenarioCommandTemplateV1.ISOLATE, confirm=False, key="op-iso-1"),
            actor=_operator(),
        )
        assert response.policy_outcome == PolicyOutcomeV1.APPROVAL_REQUIRED
        assert response.status == OperatorActionStatusV1.CONFIRMATION_REQUIRED
        assert response.executed is False
        # No bypass: proposal remains PENDING and nothing executed.
        proposal = await uow.proposals.get_proposal(response.proposal_id)
        assert proposal is not None
        assert proposal.status == ProposalStatus.PENDING
        assert await uow.executed_actions.list_for_proposal(response.proposal_id) == []


@pytest.mark.asyncio
async def test_class2_isolate_with_confirm_executes() -> None:
    service = OperatorActionService(approvals=_StubExecApprovals())
    async with PostgresUnitOfWork(_session_maker()) as uow:
        _incident, run_id, _alerts, _ev = await seed_investigation_run(uow)
        response = await service.submit_action(
            uow,
            run_id=run_id,
            request=_request(ScenarioCommandTemplateV1.ISOLATE, confirm=True, key="op-iso-2"),
            actor=_operator(),
        )
        assert response.status == OperatorActionStatusV1.EXECUTED
        assert response.executed is True
        proposal = await uow.proposals.get_proposal(response.proposal_id)
        assert proposal is not None
        assert proposal.status == ProposalStatus.EXECUTED


@pytest.mark.asyncio
async def test_confirm_without_approvals_decide_is_forbidden() -> None:
    service = OperatorActionService(approvals=_StubExecApprovals())
    async with PostgresUnitOfWork(_session_maker()) as uow:
        _incident, run_id, _alerts, _ev = await seed_investigation_run(uow)
        assert PermissionV1.APPROVALS_DECIDE not in _viewer().permissions
        with pytest.raises(OperatorActionError) as exc:
            await service.submit_action(
                uow,
                run_id=run_id,
                request=_request(
                    ScenarioCommandTemplateV1.ISOLATE, confirm=True, key="op-iso-3"
                ),
                actor=_viewer(),
            )
        assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_scenario_restricted_command_blocked() -> None:
    service = OperatorActionService(approvals=_StubExecApprovals())
    async with PostgresUnitOfWork(_session_maker()) as uow:
        _incident, run_id, _alerts, _ev = await seed_investigation_run(uow)
        response = await service.submit_action(
            uow,
            run_id=run_id,
            request=_request(
                ScenarioCommandTemplateV1.RESTART_SERVICE, confirm=True, key="op-rst-1"
            ),
            actor=_operator(),
        )
        assert response.policy_outcome == PolicyOutcomeV1.BLOCK
        assert response.status == OperatorActionStatusV1.BLOCKED
        assert response.executed is False
        proposal = await uow.proposals.get_proposal(response.proposal_id)
        assert proposal is not None
        assert proposal.status == ProposalStatus.REJECTED
