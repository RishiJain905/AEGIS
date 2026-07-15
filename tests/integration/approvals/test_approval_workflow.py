"""Integration tests for Phase 24 approval workflow."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from aegis_agents.runtime.ids import new_runtime_id
from aegis_api.approvals.errors import ApprovalWorkflowError
from aegis_api.approvals.service import ApprovalWorkflowService
from aegis_contracts import ActionClass, AgentRole, PlatformRoleV1, ProposalStatus
from aegis_contracts.approvals import (
    ApprovalErrorCode,
    ApproveProposalRequestV1,
    ModifyProposalRequestV1,
    RejectProposalRequestV1,
)
from aegis_contracts.entities import ActionProposalV1, IncidentState
from aegis_contracts.proposals import (
    PolicyInputV1,
    PolicyOutcomeV1,
    ProposalRevisionV1,
    ResponseOptionV1,
    ScenarioCommandTemplateV1,
)
from aegis_contracts.versioning import (
    ACTION_PROPOSAL_SCHEMA_VERSION,
    APPROVE_PROPOSAL_REQUEST_SCHEMA_VERSION,
    MODIFY_PROPOSAL_REQUEST_SCHEMA_VERSION,
    POLICY_INPUT_SCHEMA_VERSION,
    PROPOSAL_REVISION_SCHEMA_VERSION,
    REJECT_PROPOSAL_REQUEST_SCHEMA_VERSION,
    RESPONSE_OPTION_SCHEMA_VERSION,
)
from aegis_persistence.engine import create_engine, dispose_engine, get_session_maker
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from aegis_policy import PolicyEngine
from aegis_policy.authz import build_actor
from aegis_simulation import run_command_service as run_command_module
from aegis_simulation.run_command_service import RunCommandService

from tests.integration.agents.helpers import seed_investigation_run


def _operator_actor():
    return build_actor(
        user_id="user:operator-alpha",
        display_name="Operator Alpha",
        roles=[PlatformRoleV1.OPERATOR],
        session_id="sess_phase24_operator",
        auth_method="dev",
    )


def _viewer_actor():
    return build_actor(
        user_id="user:viewer-alpha",
        display_name="Viewer Alpha",
        roles=[PlatformRoleV1.VIEWER],
        session_id="sess_phase24_viewer",
        auth_method="dev",
    )

pytestmark = pytest.mark.skipif(
    os.getenv("AEGIS_INTEGRATION_POSTGRES") != "1",
    reason="Requires PostgreSQL integration environment",
)

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]


async def _seed_approval_required_proposal(
    uow: PostgresUnitOfWork,
    *,
    incident_id: str,
    run_id: str,
    evidence_id: str,
) -> ActionProposalV1:
    now = datetime.now(UTC)
    proposal_id = new_runtime_id("prp")
    revision_id = new_runtime_id("prv")
    session_id = "agent-session:ags_bastion_phase24"
    task_id = new_runtime_id("atk")
    option = ResponseOptionV1(
        schema_version=RESPONSE_OPTION_SCHEMA_VERSION,
        option_id="opt-isolate-primary",
        scenario_command=ScenarioCommandTemplateV1.ISOLATE,
        action_class=ActionClass.OPERATIONAL,
        target_asset_id="asset:svc-api-gateway",
        affected_asset_ids=["asset:svc-api-gateway"],
        evidence_ids=[evidence_id],
        hypothesis_ids=[],
        expected_benefit="Stops suspected credential abuse path.",
        operational_cost="Moderate service disruption.",
        reversibility="Reversible after approval and verification.",
        prerequisites=["Notify operations bridge"],
        monitoring_plan="Track auth failures post-isolation.",
        expected_consequences="Short-term API unavailability.",
        confidence=0.84,
        uncertainty="Collateral coupling requires approval.",
        rationale="Best containment option for class 2 isolate.",
    )
    proposal = ActionProposalV1(
        schema_version=ACTION_PROPOSAL_SCHEMA_VERSION,
        id=proposal_id,
        incident_id=incident_id,
        agent_session_id=session_id,
        action_class=ActionClass.OPERATIONAL,
        target_asset_id="asset:svc-api-gateway",
        command="isolate",
        scenario_command="isolate",
        current_revision_id=revision_id,
        status=ProposalStatus.PENDING,
        rationale="Seeded Phase 24 approval-required proposal.",
        revision=1,
        created_at=now,
    )
    revision = ProposalRevisionV1(
        schema_version=PROPOSAL_REVISION_SCHEMA_VERSION,
        id=revision_id,
        proposal_id=proposal_id,
        incident_id=incident_id,
        session_id=session_id,
        task_id=task_id,
        revision_number=1,
        response_options=[option],
        selected_option_id=option.option_id,
        rationale="Seeded Phase 24 approval-required proposal.",
        risk_tradeoffs="Containment speed versus service disruption.",
        linked_hypothesis_ids=[],
        created_at=now,
    )
    await uow.proposals.add_proposal(proposal)
    await uow.proposals.add_revision(revision)

    policy_input = PolicyInputV1(
        schema_version=POLICY_INPUT_SCHEMA_VERSION,
        proposal_id=proposal_id,
        proposal_revision_id=revision_id,
        proposal_revision_number=1,
        current_revision_id=revision_id,
        action_class=ActionClass.OPERATIONAL,
        scenario_command=ScenarioCommandTemplateV1.ISOLATE,
        agent_role=AgentRole.BASTION,
        target_asset_id="asset:svc-api-gateway",
        asset_criticality=0.7,
        reversibility=option.reversibility,
        incident_state=IncidentState.APPROVAL_PENDING,
        scenario_restricted=True,
    )
    decision = PolicyEngine().evaluate(
        policy_input,
        decision_id=new_runtime_id("pdc"),
        incident_id=incident_id,
        session_id=session_id,
        task_id=task_id,
        explanation_prose="Seeded WARDEN approval_required decision.",
    )
    assert decision.outcome == PolicyOutcomeV1.APPROVAL_REQUIRED
    await uow.proposals.add_policy_decision(decision)

    incident = await uow.incidents.get_by_id(incident_id)
    assert incident is not None
    updated = incident.model_copy(
        update={
            "state": IncidentState.APPROVAL_PENDING,
            "updated_at": now,
            "revision": incident.revision + 1,
        }
    )
    await uow.incidents.update_with_revision(updated, expected_revision=incident.revision)
    _ = run_id
    return proposal


@pytest.mark.asyncio
async def test_approval_workflow_accept_criteria() -> None:
    from aegis_contracts import load_settings

    settings = load_settings()
    engine = create_engine(settings)
    session_maker = get_session_maker(settings, engine=engine)
    run_service = RunCommandService(workspace_root=WORKSPACE_ROOT)
    run_command_module.SCENARIO_PACKAGE_BY_VERSION[
        "scenario-version:watchtower-trace-test-v1"
    ] = "scenarios/_fixtures/valid-minimal"
    approval_service = ApprovalWorkflowService(run_command_service=run_service)
    suite_key = new_runtime_id("act")

    async with PostgresUnitOfWork(session_maker) as uow:
        incident_id, run_id, _alert_ids, evidence_id = await seed_investigation_run(uow)
        proposal = await _seed_approval_required_proposal(
            uow, incident_id=incident_id, run_id=run_id, evidence_id=evidence_id
        )
        assert proposal.current_revision_id is not None

        # Class 2/3 cannot execute without approval.
        assert await uow.executed_actions.list_for_proposal(proposal.id) == []

        with pytest.raises(ApprovalWorkflowError) as stale_exc:
            await approval_service.approve(
                uow,
                ApproveProposalRequestV1(
                    schema_version=APPROVE_PROPOSAL_REQUEST_SCHEMA_VERSION,
                    proposal_id=proposal.id,
                    expected_revision_id="prv_01ARZ3NDEKTSV4RRFFQ69G5FB0",
                    expected_revision=999,
                    comment="stale",
                    idempotency_key=f"{suite_key}-stale-approve",
                ),
                authenticated_actor=_operator_actor(),
            )
        assert stale_exc.value.code == ApprovalErrorCode.STALE_PROPOSAL

        with pytest.raises(ApprovalWorkflowError) as auth_exc:
            await approval_service.approve(
                uow,
                ApproveProposalRequestV1(
                    schema_version=APPROVE_PROPOSAL_REQUEST_SCHEMA_VERSION,
                    proposal_id=proposal.id,
                    expected_revision_id=proposal.current_revision_id,
                    expected_revision=proposal.revision,
                    comment="bypass",
                    idempotency_key=f"{suite_key}-unauth-approve",
                ),
                authenticated_actor=_viewer_actor(),
            )
        assert auth_exc.value.code == ApprovalErrorCode.UNAUTHORIZED

        current_revision = await uow.proposals.get_revision(proposal.current_revision_id)
        assert current_revision is not None

        modify_response = await approval_service.modify(
            uow,
            ModifyProposalRequestV1(
                schema_version=MODIFY_PROPOSAL_REQUEST_SCHEMA_VERSION,
                proposal_id=proposal.id,
                expected_revision_id=proposal.current_revision_id,
                expected_revision=proposal.revision,
                selected_option_id=current_revision.selected_option_id,
                rationale="Operator narrowed containment scope for Phase 24 validation.",
                risk_tradeoffs="Lower disruption with renewed policy evaluation.",
                comment="modify-before-approve",
                idempotency_key=f"{suite_key}-modify",
            ),
            authenticated_actor=_operator_actor(),
        )
        assert (
            modify_response.modification.new_revision_id
            != modify_response.modification.previous_revision_id
        )
        assert modify_response.policy_decision.proposal_revision_id == (
            modify_response.modification.new_revision_id
        )
        assert modify_response.proposal_status == ProposalStatus.PENDING

        updated = await uow.proposals.get_proposal(proposal.id)
        assert updated is not None
        assert updated.current_revision_id == modify_response.modification.new_revision_id

        approve_response = await approval_service.approve(
            uow,
            ApproveProposalRequestV1(
                schema_version=APPROVE_PROPOSAL_REQUEST_SCHEMA_VERSION,
                proposal_id=updated.id,
                expected_revision_id=updated.current_revision_id or "",
                expected_revision=updated.revision,
                comment="approve-after-modify",
                idempotency_key=f"{suite_key}-approve",
            ),
            authenticated_actor=_operator_actor(),
        )
        assert approve_response.approval.decision.value == "approved"
        assert approve_response.execution is not None
        assert approve_response.execution.success is True
        assert approve_response.proposal_status == ProposalStatus.EXECUTED

        replay = await approval_service.approve(
            uow,
            ApproveProposalRequestV1(
                schema_version=APPROVE_PROPOSAL_REQUEST_SCHEMA_VERSION,
                proposal_id=updated.id,
                expected_revision_id=updated.current_revision_id or "",
                expected_revision=updated.revision,
                comment="approve-after-modify",
                idempotency_key=f"{suite_key}-approve",
            ),
            authenticated_actor=_operator_actor(),
        )
        assert replay.replayed is True
        actions = await uow.executed_actions.list_for_proposal(updated.id)
        assert len(actions) == 1

        detail_after = await uow.investigation.get_detail(incident_id, run_id)
        assert detail_after.approvals
        assert detail_after.executed_actions
        event_types = {event.type for event in await uow.events.list_by_run(run_id)}
        assert "action.proposal.approved" in event_types
        assert "action.executed" in event_types
        assert "action.proposal.modified" in event_types

        # Reject path on a second pending proposal.
        reject_proposal = await _seed_approval_required_proposal(
            uow, incident_id=incident_id, run_id=run_id, evidence_id=evidence_id
        )
        assert reject_proposal.current_revision_id is not None
        reject_response = await approval_service.reject(
            uow,
            RejectProposalRequestV1(
                schema_version=REJECT_PROPOSAL_REQUEST_SCHEMA_VERSION,
                proposal_id=reject_proposal.id,
                expected_revision_id=reject_proposal.current_revision_id,
                expected_revision=reject_proposal.revision,
                reason="Collateral impact too high for current evidence.",
                comment="reject-path",
                idempotency_key=f"{suite_key}-reject",
            ),
            authenticated_actor=_operator_actor(),
        )
        assert reject_response.proposal_status == ProposalStatus.REJECTED
        assert await uow.executed_actions.list_for_proposal(reject_proposal.id) == []
        event_types = {event.type for event in await uow.events.list_by_run(run_id)}
        assert "action.proposal.rejected" in event_types

    await dispose_engine(engine)
