"""Phase 24 approval workflow application service."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aegis_agents.roles.warden.evaluation import build_policy_input
from aegis_agents.runtime.ids import new_runtime_id
from aegis_agents.runtime.proposal_events import (
    build_incident_state_changed_event,
    build_policy_evaluated_event,
)
from aegis_contracts import (
    ActorRef,
    ActorType,
    ApprovalDecision,
    ApprovalV1,
    ExecutedActionV1,
    IdempotencyRecordV1,
    SimulationCommandType,
    SimulationCommandV1,
)
from aegis_contracts.approvals import (
    ApprovalErrorCode,
    ApproveProposalRequestV1,
    ApproveProposalResponseV1,
    CancelProposalRequestV1,
    ExecutionResultV1,
    FinalPolicyCheckV1,
    ModifyProposalRequestV1,
    ModifyProposalResponseV1,
    ProposalModificationV1,
    RejectProposalRequestV1,
    RejectProposalResponseV1,
)
from aegis_contracts.entities import IncidentState, ProposalStatus
from aegis_contracts.proposals import (
    PolicyOutcomeV1,
    ProposalRevisionV1,
    ScenarioCommandTemplateV1,
)
from aegis_contracts.versioning import (
    APPROVAL_SCHEMA_VERSION,
    APPROVE_PROPOSAL_RESPONSE_SCHEMA_VERSION,
    EXECUTED_ACTION_SCHEMA_VERSION,
    EXECUTION_RESULT_SCHEMA_VERSION,
    FINAL_POLICY_CHECK_SCHEMA_VERSION,
    IDEMPOTENCY_RECORD_SCHEMA_VERSION,
    MODIFY_PROPOSAL_RESPONSE_SCHEMA_VERSION,
    PROPOSAL_MODIFICATION_SCHEMA_VERSION,
    PROPOSAL_REVISION_SCHEMA_VERSION,
    REJECT_PROPOSAL_RESPONSE_SCHEMA_VERSION,
    SIMULATION_COMMAND_SCHEMA_VERSION,
)
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from aegis_policy import PolicyEngine
from aegis_simulation.application import SimulationApplicationService
from aegis_simulation.run_command_service import RunCommandService
from aegis_simulation_domain.errors import SimulationError, SimulationErrorCode

from aegis_api.approvals.errors import ApprovalWorkflowError
from aegis_api.approvals.events import (
    build_action_executed_event,
    build_proposal_approved_event,
    build_proposal_cancelled_event,
    build_proposal_modified_event,
    build_proposal_rejected_event,
)
from aegis_api.commands.mapping import (
    APPROVAL_IDEMPOTENCY_SCOPE,
    DEFAULT_AUTHORIZATION_TOKEN,
    DEFAULT_OPERATOR_ACTOR_ID,
    map_scenario_command_to_authorized,
)

WORKSPACE_ROOT = Path(__file__).resolve().parents[5]


class ApprovalWorkflowService:
    def __init__(
        self,
        *,
        policy_engine: PolicyEngine | None = None,
        run_command_service: RunCommandService | None = None,
    ) -> None:
        self._policy = policy_engine or PolicyEngine()
        self._run_commands = run_command_service or RunCommandService(workspace_root=WORKSPACE_ROOT)

    async def approve(
        self,
        uow: PostgresUnitOfWork,
        request: ApproveProposalRequestV1,
        *,
        actor_id: str | None = None,
        authorization_token: str = DEFAULT_AUTHORIZATION_TOKEN,
        trace_id: str | None = None,
    ) -> ApproveProposalResponseV1:
        actor = self._resolve_actor(request.actor_id or actor_id)
        self._assert_operator_token(authorization_token)
        existing = await uow.idempotency.get(
            scope=APPROVAL_IDEMPOTENCY_SCOPE,
            idempotency_key=request.idempotency_key,
        )
        if existing is not None and existing.response_ref:
            return await self._replay_approve_response(uow, existing.response_ref)

        proposal = await self._require_proposal(uow, request.proposal_id)
        self._assert_pending(proposal)
        self._assert_revision_match(
            proposal,
            expected_revision_id=request.expected_revision_id,
            expected_revision=request.expected_revision,
        )
        revision = await self._require_current_revision(uow, proposal)
        incident = await self._require_incident(uow, proposal.incident_id)
        selected = self._selected_option(revision)
        scenario_command = selected.scenario_command
        if scenario_command in {
            ScenarioCommandTemplateV1.ISOLATE,
            ScenarioCommandTemplateV1.RESTRICT_ACCESS,
            ScenarioCommandTemplateV1.REVOKE_CREDENTIALS,
            ScenarioCommandTemplateV1.RESTART_SERVICE,
            ScenarioCommandTemplateV1.ROLLBACK_DEPLOYMENT,
        } and proposal.action_class.value in {"class_2", "class_3"}:
            # Class 2/3 always require an explicit human approval record before execute.
            pass

        final_check = await self._final_policy_check(
            uow,
            proposal=proposal,
            revision=revision,
            incident_state=incident.state,
            run_id=incident.run_id,
            actor_id=actor,
            trace_id=trace_id or new_runtime_id("trc"),
        )
        if not final_check.executable:
            raise ApprovalWorkflowError(
                code=ApprovalErrorCode.POLICY_BLOCKED,
                message="Final policy check blocked execution",
                details={
                    "outcome": final_check.outcome.value,
                    "reasonCodes": [code.value for code in final_check.decision.reason_codes],
                },
                status_code=409,
            )

        now = datetime.now(UTC)
        approval = ApprovalV1(
            schema_version=APPROVAL_SCHEMA_VERSION,
            id=new_runtime_id("apr"),
            proposal_id=proposal.id,
            decision=ApprovalDecision.APPROVED,
            approver_id=actor,
            proposal_revision=proposal.revision,
            decided_at=now,
        )
        await uow.approvals.add(approval)

        approved_proposal = proposal.model_copy(
            update={"status": ProposalStatus.APPROVED, "revision": proposal.revision + 1}
        )
        await uow.proposals.update_proposal(approved_proposal)

        next_sequence = await uow.events.next_sequence(incident.run_id)
        await uow.append_event(
            build_proposal_approved_event(
                event_id=new_runtime_id("evt"),
                run_id=incident.run_id,
                sequence=next_sequence,
                actor_id=actor,
                trace_id=trace_id or new_runtime_id("trc"),
                proposal_id=proposal.id,
                approval_id=approval.id,
                revision_id=revision.id,
                incident_id=incident.id,
                comment=request.comment,
            )
        )

        await self._transition_incident(
            uow,
            incident_id=incident.id,
            run_id=incident.run_id,
            new_state=IncidentState.CONTAINING,
            actor_id=actor,
            trace_id=trace_id or new_runtime_id("trc"),
        )

        execution = await self._execute_authorized(
            uow,
            proposal_id=proposal.id,
            approval_id=approval.id,
            run_id=incident.run_id,
            incident_id=incident.id,
            scenario_command=scenario_command,
            target_asset_id=selected.target_asset_id,
            idempotency_key=request.idempotency_key,
            actor_id=actor,
            authorization_token=authorization_token,
            trace_id=trace_id or new_runtime_id("trc"),
        )

        executed_proposal = approved_proposal.model_copy(
            update={
                "status": ProposalStatus.EXECUTED,
                "revision": approved_proposal.revision + 1,
            }
        )
        await uow.proposals.update_proposal(executed_proposal)

        response = ApproveProposalResponseV1(
            schema_version=APPROVE_PROPOSAL_RESPONSE_SCHEMA_VERSION,
            approval=approval,
            final_policy_check=final_check,
            execution=execution,
            proposal_status=ProposalStatus.EXECUTED,
            replayed=False,
        )
        await uow.idempotency.add(
            IdempotencyRecordV1(
                schema_version=IDEMPOTENCY_RECORD_SCHEMA_VERSION,
                scope=APPROVAL_IDEMPOTENCY_SCOPE,
                idempotency_key=request.idempotency_key,
                request_hash=None,
                response_ref=approval.id,
                replayed=False,
                created_at=now,
            )
        )
        return response

    async def reject(
        self,
        uow: PostgresUnitOfWork,
        request: RejectProposalRequestV1,
        *,
        actor_id: str | None = None,
        authorization_token: str = DEFAULT_AUTHORIZATION_TOKEN,
        trace_id: str | None = None,
    ) -> RejectProposalResponseV1:
        actor = self._resolve_actor(request.actor_id or actor_id)
        self._assert_operator_token(authorization_token)
        existing = await uow.idempotency.get(
            scope=APPROVAL_IDEMPOTENCY_SCOPE,
            idempotency_key=request.idempotency_key,
        )
        if existing is not None and existing.response_ref:
            return await self._replay_reject_response(uow, existing.response_ref)

        proposal = await self._require_proposal(uow, request.proposal_id)
        self._assert_pending(proposal)
        self._assert_revision_match(
            proposal,
            expected_revision_id=request.expected_revision_id,
            expected_revision=request.expected_revision,
        )
        revision = await self._require_current_revision(uow, proposal)
        incident = await self._require_incident(uow, proposal.incident_id)
        now = datetime.now(UTC)
        approval = ApprovalV1(
            schema_version=APPROVAL_SCHEMA_VERSION,
            id=new_runtime_id("apr"),
            proposal_id=proposal.id,
            decision=ApprovalDecision.REJECTED,
            approver_id=actor,
            proposal_revision=proposal.revision,
            decided_at=now,
        )
        await uow.approvals.add(approval)
        rejected = proposal.model_copy(
            update={"status": ProposalStatus.REJECTED, "revision": proposal.revision + 1}
        )
        await uow.proposals.update_proposal(rejected)
        next_sequence = await uow.events.next_sequence(incident.run_id)
        await uow.append_event(
            build_proposal_rejected_event(
                event_id=new_runtime_id("evt"),
                run_id=incident.run_id,
                sequence=next_sequence,
                actor_id=actor,
                trace_id=trace_id or new_runtime_id("trc"),
                proposal_id=proposal.id,
                approval_id=approval.id,
                revision_id=revision.id,
                incident_id=incident.id,
                reason=request.reason,
            )
        )
        await self._transition_incident(
            uow,
            incident_id=incident.id,
            run_id=incident.run_id,
            new_state=IncidentState.INVESTIGATING,
            actor_id=actor,
            trace_id=trace_id or new_runtime_id("trc"),
        )
        response = RejectProposalResponseV1(
            schema_version=REJECT_PROPOSAL_RESPONSE_SCHEMA_VERSION,
            approval=approval,
            proposal_status=ProposalStatus.REJECTED,
            replayed=False,
        )
        await uow.idempotency.add(
            IdempotencyRecordV1(
                schema_version=IDEMPOTENCY_RECORD_SCHEMA_VERSION,
                scope=APPROVAL_IDEMPOTENCY_SCOPE,
                idempotency_key=request.idempotency_key,
                request_hash=None,
                response_ref=approval.id,
                replayed=False,
                created_at=now,
            )
        )
        return response

    async def modify(
        self,
        uow: PostgresUnitOfWork,
        request: ModifyProposalRequestV1,
        *,
        actor_id: str | None = None,
        authorization_token: str = DEFAULT_AUTHORIZATION_TOKEN,
        trace_id: str | None = None,
    ) -> ModifyProposalResponseV1:
        actor = self._resolve_actor(request.actor_id or actor_id)
        self._assert_operator_token(authorization_token)
        existing = await uow.idempotency.get(
            scope=APPROVAL_IDEMPOTENCY_SCOPE,
            idempotency_key=request.idempotency_key,
        )
        if existing is not None and existing.response_ref:
            return await self._replay_modify_response(uow, existing.response_ref, request)

        proposal = await self._require_proposal(uow, request.proposal_id)
        self._assert_pending(proposal)
        self._assert_revision_match(
            proposal,
            expected_revision_id=request.expected_revision_id,
            expected_revision=request.expected_revision,
        )
        previous = await self._require_current_revision(uow, proposal)
        incident = await self._require_incident(uow, proposal.incident_id)
        now = datetime.now(UTC)
        options = request.response_options or previous.response_options
        option_ids = {option.option_id for option in options}
        if request.selected_option_id not in option_ids:
            raise ApprovalWorkflowError(
                code=ApprovalErrorCode.VALIDATION_FAILED,
                message="selectedOptionId must reference a response option",
                details={"selectedOptionId": request.selected_option_id},
            )
        selected = next(
            option for option in options if option.option_id == request.selected_option_id
        )
        new_revision = ProposalRevisionV1(
            schema_version=PROPOSAL_REVISION_SCHEMA_VERSION,
            id=new_runtime_id("prv"),
            proposal_id=proposal.id,
            incident_id=proposal.incident_id,
            session_id=previous.session_id,
            task_id=previous.task_id,
            revision_number=previous.revision_number + 1,
            response_options=options,
            selected_option_id=request.selected_option_id,
            rationale=request.rationale,
            risk_tradeoffs=request.risk_tradeoffs,
            linked_hypothesis_ids=previous.linked_hypothesis_ids,
            created_at=now,
        )
        await uow.proposals.add_revision(new_revision)
        updated = proposal.model_copy(
            update={
                "current_revision_id": new_revision.id,
                "scenario_command": selected.scenario_command.value,
                "action_class": selected.action_class,
                "target_asset_id": selected.target_asset_id,
                "command": selected.scenario_command.value,
                "rationale": request.rationale,
                "status": ProposalStatus.PENDING,
                "revision": proposal.revision + 1,
            }
        )
        await uow.proposals.update_proposal(updated)

        policy_input = build_policy_input(
            proposal=updated,
            revision=new_revision,
            incident_state=incident.state,
            asset_criticality=await self._asset_criticality(
                uow, incident.run_id, selected.target_asset_id
            ),
            scenario_restricted=True,
        )
        decision = self._policy.evaluate(
            policy_input,
            decision_id=new_runtime_id("pdc"),
            incident_id=incident.id,
            session_id=previous.session_id,
            task_id=previous.task_id,
            explanation_prose="Operator modification forced WARDEN re-evaluation.",
        )
        await uow.proposals.add_policy_decision(decision)
        if decision.outcome == PolicyOutcomeV1.BLOCK:
            blocked = updated.model_copy(update={"status": ProposalStatus.REJECTED})
            await uow.proposals.update_proposal(blocked)
            proposal_status = ProposalStatus.REJECTED
        elif decision.outcome == PolicyOutcomeV1.ALLOW:
            allowed = updated.model_copy(update={"status": ProposalStatus.APPROVED})
            await uow.proposals.update_proposal(allowed)
            proposal_status = ProposalStatus.APPROVED
        else:
            proposal_status = ProposalStatus.PENDING

        next_sequence = await uow.events.next_sequence(incident.run_id)
        await uow.append_event(
            build_proposal_modified_event(
                event_id=new_runtime_id("evt"),
                run_id=incident.run_id,
                sequence=next_sequence,
                actor_id=actor,
                trace_id=trace_id or new_runtime_id("trc"),
                proposal_id=proposal.id,
                previous_revision_id=previous.id,
                new_revision_id=new_revision.id,
                incident_id=incident.id,
            )
        )
        next_sequence = await uow.events.next_sequence(incident.run_id)
        await uow.append_event(
            build_policy_evaluated_event(
                event_id=new_runtime_id("evt"),
                run_id=incident.run_id,
                sequence=next_sequence,
                session_id=previous.session_id,
                task_id=previous.task_id,
                trace_id=trace_id or new_runtime_id("trc"),
                proposal_id=proposal.id,
                revision_id=new_revision.id,
                incident_id=incident.id,
                outcome=decision.outcome.value,
            )
        )
        if proposal_status == ProposalStatus.PENDING:
            await self._transition_incident(
                uow,
                incident_id=incident.id,
                run_id=incident.run_id,
                new_state=IncidentState.APPROVAL_PENDING,
                actor_id=actor,
                trace_id=trace_id or new_runtime_id("trc"),
            )
        elif proposal_status == ProposalStatus.REJECTED:
            await self._transition_incident(
                uow,
                incident_id=incident.id,
                run_id=incident.run_id,
                new_state=IncidentState.INVESTIGATING,
                actor_id=actor,
                trace_id=trace_id or new_runtime_id("trc"),
            )

        modification = ProposalModificationV1(
            schema_version=PROPOSAL_MODIFICATION_SCHEMA_VERSION,
            proposal_id=proposal.id,
            previous_revision_id=previous.id,
            new_revision_id=new_revision.id,
            selected_option_id=request.selected_option_id,
            response_options=request.response_options,
            rationale=request.rationale,
            risk_tradeoffs=request.risk_tradeoffs,
            comment=request.comment,
            modified_by=actor,
            modified_at=now,
        )
        response = ModifyProposalResponseV1(
            schema_version=MODIFY_PROPOSAL_RESPONSE_SCHEMA_VERSION,
            modification=modification,
            policy_decision=decision,
            proposal_status=proposal_status,
            replayed=False,
        )
        await uow.idempotency.add(
            IdempotencyRecordV1(
                schema_version=IDEMPOTENCY_RECORD_SCHEMA_VERSION,
                scope=APPROVAL_IDEMPOTENCY_SCOPE,
                idempotency_key=request.idempotency_key,
                request_hash=None,
                response_ref=new_revision.id,
                replayed=False,
                created_at=now,
            )
        )
        return response

    async def cancel(
        self,
        uow: PostgresUnitOfWork,
        request: CancelProposalRequestV1,
        *,
        actor_id: str | None = None,
        authorization_token: str = DEFAULT_AUTHORIZATION_TOKEN,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        actor = self._resolve_actor(request.actor_id or actor_id)
        self._assert_operator_token(authorization_token)
        existing = await uow.idempotency.get(
            scope=APPROVAL_IDEMPOTENCY_SCOPE,
            idempotency_key=request.idempotency_key,
        )
        if existing is not None:
            return {
                "schemaVersion": 1,
                "proposalId": request.proposal_id,
                "proposalStatus": ProposalStatus.CANCELLED.value,
                "replayed": True,
            }

        proposal = await self._require_proposal(uow, request.proposal_id)
        if proposal.status in {
            ProposalStatus.EXECUTED,
            ProposalStatus.CANCELLED,
            ProposalStatus.REJECTED,
        }:
            raise ApprovalWorkflowError(
                code=ApprovalErrorCode.ALREADY_DECIDED,
                message=f"Proposal cannot be cancelled from status {proposal.status.value}",
                details={"status": proposal.status.value},
                status_code=409,
            )
        self._assert_revision_match(
            proposal,
            expected_revision_id=request.expected_revision_id,
            expected_revision=request.expected_revision,
        )
        revision = await self._require_current_revision(uow, proposal)
        incident = await self._require_incident(uow, proposal.incident_id)
        cancelled = proposal.model_copy(
            update={"status": ProposalStatus.CANCELLED, "revision": proposal.revision + 1}
        )
        await uow.proposals.update_proposal(cancelled)
        next_sequence = await uow.events.next_sequence(incident.run_id)
        await uow.append_event(
            build_proposal_cancelled_event(
                event_id=new_runtime_id("evt"),
                run_id=incident.run_id,
                sequence=next_sequence,
                actor_id=actor,
                trace_id=trace_id or new_runtime_id("trc"),
                proposal_id=proposal.id,
                revision_id=revision.id,
                incident_id=incident.id,
                reason=request.reason,
            )
        )
        await self._transition_incident(
            uow,
            incident_id=incident.id,
            run_id=incident.run_id,
            new_state=IncidentState.INVESTIGATING,
            actor_id=actor,
            trace_id=trace_id or new_runtime_id("trc"),
        )
        now = datetime.now(UTC)
        await uow.idempotency.add(
            IdempotencyRecordV1(
                schema_version=IDEMPOTENCY_RECORD_SCHEMA_VERSION,
                scope=APPROVAL_IDEMPOTENCY_SCOPE,
                idempotency_key=request.idempotency_key,
                request_hash=None,
                response_ref=proposal.id,
                replayed=False,
                created_at=now,
            )
        )
        return {
            "schemaVersion": 1,
            "proposalId": proposal.id,
            "proposalStatus": ProposalStatus.CANCELLED.value,
            "replayed": False,
        }

    async def _final_policy_check(
        self,
        uow: PostgresUnitOfWork,
        *,
        proposal: Any,
        revision: ProposalRevisionV1,
        incident_state: IncidentState,
        run_id: str,
        actor_id: str,
        trace_id: str,
    ) -> FinalPolicyCheckV1:
        if proposal.current_revision_id != revision.id:
            raise ApprovalWorkflowError(
                code=ApprovalErrorCode.STALE_PROPOSAL,
                message="Proposal revision is stale",
                details={
                    "expectedRevisionId": revision.id,
                    "actualRevisionId": proposal.current_revision_id,
                },
                status_code=409,
            )
        selected = self._selected_option(revision)
        policy_input = build_policy_input(
            proposal=proposal,
            revision=revision,
            incident_state=incident_state,
            asset_criticality=await self._asset_criticality(uow, run_id, selected.target_asset_id),
            scenario_restricted=True,
        )
        decision = self._policy.evaluate(
            policy_input,
            decision_id=new_runtime_id("pdc"),
            incident_id=proposal.incident_id,
            session_id=revision.session_id,
            task_id=revision.task_id,
            explanation_prose="Final pre-execution WARDEN revalidation.",
        )
        await uow.proposals.add_policy_decision(decision)
        next_sequence = await uow.events.next_sequence(run_id)
        await uow.append_event(
            build_policy_evaluated_event(
                event_id=new_runtime_id("evt"),
                run_id=run_id,
                sequence=next_sequence,
                session_id=revision.session_id,
                task_id=revision.task_id,
                trace_id=trace_id,
                proposal_id=proposal.id,
                revision_id=revision.id,
                incident_id=proposal.incident_id,
                outcome=decision.outcome.value,
            )
        )
        executable = decision.outcome in {
            PolicyOutcomeV1.ALLOW,
            PolicyOutcomeV1.APPROVAL_REQUIRED,
        }
        if decision.outcome == PolicyOutcomeV1.BLOCK:
            executable = False
        now = datetime.now(UTC)
        return FinalPolicyCheckV1(
            schema_version=FINAL_POLICY_CHECK_SCHEMA_VERSION,
            proposal_id=proposal.id,
            proposal_revision_id=revision.id,
            current_revision_id=proposal.current_revision_id or revision.id,
            outcome=decision.outcome,
            decision=decision,
            executable=executable,
            checked_at=now,
        )

    async def _execute_authorized(
        self,
        uow: PostgresUnitOfWork,
        *,
        proposal_id: str,
        approval_id: str,
        run_id: str,
        incident_id: str,
        scenario_command: ScenarioCommandTemplateV1,
        target_asset_id: str,
        idempotency_key: str,
        actor_id: str,
        authorization_token: str,
        trace_id: str,
    ) -> ExecutionResultV1:
        existing_action = await uow.executed_actions.get_by_idempotency(
            run_id=run_id,
            idempotency_key=idempotency_key,
        )
        if existing_action is not None:
            return ExecutionResultV1(
                schema_version=EXECUTION_RESULT_SCHEMA_VERSION,
                executed_action=existing_action,
                result_event_id=existing_action.result_event_id,
                command_id=idempotency_key,
                success=True,
                replayed=True,
                message="Replayed prior authorized execution",
            )

        authorized = map_scenario_command_to_authorized(
            proposal_id=proposal_id,
            approval_id=approval_id,
            run_id=run_id,
            scenario_command=scenario_command,
            target_asset_id=target_asset_id,
            command_id=idempotency_key,
            actor_id=actor_id,
            authorization_token=authorization_token,
        )
        runtime = await self._run_commands._get_or_restore_runtime(uow, run_id)
        sim_service = SimulationApplicationService(uow)
        command = SimulationCommandV1(
            schema_version=SIMULATION_COMMAND_SCHEMA_VERSION,
            command_id=authorized.command_id,
            command_type=SimulationCommandType.EXECUTE,
            run_id=run_id,
            actor=ActorRef(type=ActorType.OPERATOR, id=actor_id),
            authorization_token=authorization_token,
            payload={
                "pluginId": authorized.plugin_id,
                "targetAssetId": authorized.target_asset_id,
                "config": authorized.config,
            },
        )
        try:
            emitted = await sim_service.execute_command(runtime, command)
        except SimulationError as exc:
            if exc.code == SimulationErrorCode.DUPLICATE_COMMAND:
                existing_action = await uow.executed_actions.get_by_idempotency(
                    run_id=run_id,
                    idempotency_key=idempotency_key,
                )
                if existing_action is not None:
                    return ExecutionResultV1(
                        schema_version=EXECUTION_RESULT_SCHEMA_VERSION,
                        executed_action=existing_action,
                        result_event_id=existing_action.result_event_id,
                        command_id=idempotency_key,
                        success=True,
                        replayed=True,
                        message="Replayed prior authorized execution",
                    )
            raise ApprovalWorkflowError(
                code=ApprovalErrorCode.EXECUTION_FAILED,
                message=exc.message,
                details=exc.details,
                status_code=500,
            ) from exc

        result_event_id = emitted[-1].event_id if emitted else new_runtime_id("evt")
        now = datetime.now(UTC)
        executed = ExecutedActionV1(
            schema_version=EXECUTED_ACTION_SCHEMA_VERSION,
            id=new_runtime_id("act"),
            proposal_id=proposal_id,
            run_id=run_id,
            result_event_id=result_event_id,
            idempotency_key=idempotency_key,
            executed_at=now,
        )
        await uow.executed_actions.add(executed)
        next_sequence = await uow.events.next_sequence(run_id)
        await uow.append_event(
            build_action_executed_event(
                event_id=new_runtime_id("evt"),
                run_id=run_id,
                sequence=next_sequence,
                actor_id=actor_id,
                trace_id=trace_id,
                proposal_id=proposal_id,
                approval_id=approval_id,
                executed_action_id=executed.id,
                command_id=authorized.command_id,
                incident_id=incident_id,
            )
        )
        return ExecutionResultV1(
            schema_version=EXECUTION_RESULT_SCHEMA_VERSION,
            executed_action=executed,
            result_event_id=result_event_id,
            command_id=authorized.command_id,
            success=True,
            replayed=False,
            message="Authorized simulation command executed",
        )

    async def _transition_incident(
        self,
        uow: PostgresUnitOfWork,
        *,
        incident_id: str,
        run_id: str,
        new_state: IncidentState,
        actor_id: str,
        trace_id: str,
    ) -> None:
        incident = await uow.incidents.get_by_id(incident_id)
        if incident is None or incident.state == new_state:
            return
        previous = incident.state
        updated = incident.model_copy(
            update={
                "state": new_state,
                "updated_at": datetime.now(UTC),
                "revision": incident.revision + 1,
            }
        )
        await uow.incidents.update_with_revision(updated, expected_revision=incident.revision)
        next_sequence = await uow.events.next_sequence(run_id)
        await uow.append_event(
            build_incident_state_changed_event(
                event_id=new_runtime_id("evt"),
                run_id=run_id,
                sequence=next_sequence,
                session_id=actor_id,
                trace_id=trace_id,
                incident_id=incident_id,
                previous_state=previous.value,
                new_state=new_state.value,
            )
        )

    async def _asset_criticality(
        self,
        uow: PostgresUnitOfWork,
        run_id: str,
        asset_id: str,
    ) -> float:
        scores = await uow.risk_scores.list_latest_by_run(run_id)
        for score in scores:
            if score.asset_id == asset_id:
                return float(score.total)
        return 0.5

    async def _require_proposal(self, uow: PostgresUnitOfWork, proposal_id: str) -> Any:
        proposal = await uow.proposals.get_proposal(proposal_id)
        if proposal is None:
            raise ApprovalWorkflowError(
                code=ApprovalErrorCode.NOT_FOUND,
                message=f"Proposal not found: {proposal_id}",
                status_code=404,
            )
        return proposal

    async def _require_incident(self, uow: PostgresUnitOfWork, incident_id: str) -> Any:
        incident = await uow.incidents.get_by_id(incident_id)
        if incident is None:
            raise ApprovalWorkflowError(
                code=ApprovalErrorCode.NOT_FOUND,
                message=f"Incident not found: {incident_id}",
                status_code=404,
            )
        return incident

    async def _require_current_revision(
        self,
        uow: PostgresUnitOfWork,
        proposal: Any,
    ) -> ProposalRevisionV1:
        if not proposal.current_revision_id:
            raise ApprovalWorkflowError(
                code=ApprovalErrorCode.VALIDATION_FAILED,
                message="Proposal is missing currentRevisionId",
                details={"proposalId": proposal.id},
            )
        revision = await uow.proposals.get_revision(proposal.current_revision_id)
        if revision is None:
            raise ApprovalWorkflowError(
                code=ApprovalErrorCode.NOT_FOUND,
                message=f"Proposal revision not found: {proposal.current_revision_id}",
                status_code=404,
            )
        return revision

    def _selected_option(self, revision: ProposalRevisionV1) -> Any:
        return next(
            option
            for option in revision.response_options
            if option.option_id == revision.selected_option_id
        )

    def _assert_pending(self, proposal: Any) -> None:
        if proposal.status != ProposalStatus.PENDING:
            raise ApprovalWorkflowError(
                code=ApprovalErrorCode.ALREADY_DECIDED,
                message=f"Proposal is not pending: {proposal.status.value}",
                details={"status": proposal.status.value},
                status_code=409,
            )

    def _assert_revision_match(
        self,
        proposal: Any,
        *,
        expected_revision_id: str,
        expected_revision: int,
    ) -> None:
        if (
            proposal.current_revision_id != expected_revision_id
            or proposal.revision != expected_revision
        ):
            raise ApprovalWorkflowError(
                code=ApprovalErrorCode.STALE_PROPOSAL,
                message="Proposal revision no longer matches the current revision",
                details={
                    "expectedRevisionId": expected_revision_id,
                    "actualRevisionId": proposal.current_revision_id,
                    "expectedRevision": expected_revision,
                    "actualRevision": proposal.revision,
                },
                status_code=409,
            )

    def _resolve_actor(self, actor_id: str | None) -> str:
        return actor_id or DEFAULT_OPERATOR_ACTOR_ID

    def _assert_operator_token(self, authorization_token: str | None) -> None:
        if not authorization_token:
            raise ApprovalWorkflowError(
                code=ApprovalErrorCode.UNAUTHORIZED,
                message="Authorization token required for approval workflow",
                status_code=401,
            )
        if authorization_token != DEFAULT_AUTHORIZATION_TOKEN:
            raise ApprovalWorkflowError(
                code=ApprovalErrorCode.UNAUTHORIZED,
                message="Invalid authorization token for approval workflow",
                status_code=401,
            )

    async def _replay_approve_response(
        self,
        uow: PostgresUnitOfWork,
        approval_id: str,
    ) -> ApproveProposalResponseV1:
        approval = await uow.approvals.get_by_id(approval_id)
        if approval is None:
            raise ApprovalWorkflowError(
                code=ApprovalErrorCode.CONFLICT,
                message="Idempotency record references missing approval",
                status_code=409,
            )
        proposal = await self._require_proposal(uow, approval.proposal_id)
        revision = await self._require_current_revision(uow, proposal)
        decisions = await uow.proposals.list_policy_decisions_for_incident(proposal.incident_id)
        decision = next(
            (item for item in reversed(decisions) if item.proposal_id == proposal.id),
            None,
        )
        if decision is None:
            raise ApprovalWorkflowError(
                code=ApprovalErrorCode.CONFLICT,
                message="Missing policy decision for replayed approval",
                status_code=409,
            )
        actions = await uow.executed_actions.list_for_proposal(proposal.id)
        execution = None
        if actions:
            action = actions[-1]
            execution = ExecutionResultV1(
                schema_version=EXECUTION_RESULT_SCHEMA_VERSION,
                executed_action=action,
                result_event_id=action.result_event_id,
                command_id=action.idempotency_key,
                success=True,
                replayed=True,
                message="Replayed prior authorized execution",
            )
        return ApproveProposalResponseV1(
            schema_version=APPROVE_PROPOSAL_RESPONSE_SCHEMA_VERSION,
            approval=approval,
            final_policy_check=FinalPolicyCheckV1(
                schema_version=FINAL_POLICY_CHECK_SCHEMA_VERSION,
                proposal_id=proposal.id,
                proposal_revision_id=revision.id,
                current_revision_id=proposal.current_revision_id or revision.id,
                outcome=decision.outcome,
                decision=decision,
                executable=True,
                checked_at=decision.evaluated_at,
            ),
            execution=execution,
            proposal_status=proposal.status,
            replayed=True,
        )

    async def _replay_reject_response(
        self,
        uow: PostgresUnitOfWork,
        approval_id: str,
    ) -> RejectProposalResponseV1:
        approval = await uow.approvals.get_by_id(approval_id)
        if approval is None:
            raise ApprovalWorkflowError(
                code=ApprovalErrorCode.CONFLICT,
                message="Idempotency record references missing approval",
                status_code=409,
            )
        proposal = await self._require_proposal(uow, approval.proposal_id)
        return RejectProposalResponseV1(
            schema_version=REJECT_PROPOSAL_RESPONSE_SCHEMA_VERSION,
            approval=approval,
            proposal_status=proposal.status,
            replayed=True,
        )

    async def _replay_modify_response(
        self,
        uow: PostgresUnitOfWork,
        revision_id: str,
        request: ModifyProposalRequestV1,
    ) -> ModifyProposalResponseV1:
        revision = await uow.proposals.get_revision(revision_id)
        if revision is None:
            raise ApprovalWorkflowError(
                code=ApprovalErrorCode.CONFLICT,
                message="Idempotency record references missing revision",
                status_code=409,
            )
        proposal = await self._require_proposal(uow, revision.proposal_id)
        decisions = await uow.proposals.list_policy_decisions_for_incident(proposal.incident_id)
        decision = next(
            (
                item
                for item in reversed(decisions)
                if item.proposal_id == proposal.id and item.proposal_revision_id == revision.id
            ),
            None,
        )
        if decision is None:
            raise ApprovalWorkflowError(
                code=ApprovalErrorCode.CONFLICT,
                message="Missing policy decision for replayed modification",
                status_code=409,
            )
        return ModifyProposalResponseV1(
            schema_version=MODIFY_PROPOSAL_RESPONSE_SCHEMA_VERSION,
            modification=ProposalModificationV1(
                schema_version=PROPOSAL_MODIFICATION_SCHEMA_VERSION,
                proposal_id=proposal.id,
                previous_revision_id=request.expected_revision_id,
                new_revision_id=revision.id,
                selected_option_id=revision.selected_option_id,
                response_options=None,
                rationale=revision.rationale,
                risk_tradeoffs=revision.risk_tradeoffs,
                comment=request.comment,
                modified_by=request.actor_id or DEFAULT_OPERATOR_ACTOR_ID,
                modified_at=revision.created_at,
            ),
            policy_decision=decision,
            proposal_status=proposal.status,
            replayed=True,
        )
