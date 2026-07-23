"""Operator direct-action application service.

The player acts directly as an operator alongside the AI. A player-initiated containment
is modelled as a *proposal attributed to the operator* that flows through the **same**
policy engine and execution path an agent proposal uses — nothing here bypasses policy:

* Class 0/1 (policy ``ALLOW``) auto-approve and execute immediately.
* Class 2/3 (policy ``APPROVAL_REQUIRED``) require ``confirm: true`` — the confirm-with-
  consequences step — because the operator is the incident commander approving their own
  call. Without confirm the proposal is created and left PENDING (surfaced for the UI).
* Policy ``BLOCK`` (e.g. scenario-restricted commands) is refused, never overridden.

Execution reuses :class:`ApprovalWorkflowService` internals (``_final_policy_check`` and
``_execute_authorized``) so the audit trail — ``policy.evaluated``, ``action.executed``,
``ExecutedActionV1`` rows — is byte-for-byte the same shape as an approver-authorized one,
and replay / after-action treat operator and agent actions identically.
"""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_agents.runtime.ids import new_runtime_id
from aegis_contracts import (
    ActionClass,
    ApprovalDecision,
    ApprovalV1,
    AuthenticatedActorV1,
    HypothesisV1,
    IncidentState,
    IncidentV1,
    OperatorActionRequestV1,
    OperatorActionResponseV1,
    OperatorActionStatusV1,
    OperatorHypothesisRequestV1,
    PermissionV1,
)
from aegis_contracts.entities import ActionProposalV1, ProposalStatus
from aegis_contracts.proposals import (
    PolicyOutcomeV1,
    ProposalRevisionV1,
    ResponseOptionV1,
    ScenarioCommandTemplateV1,
)
from aegis_contracts.versioning import (
    ACTION_PROPOSAL_SCHEMA_VERSION,
    APPROVAL_SCHEMA_VERSION,
    INCIDENT_SCHEMA_VERSION,
    OPERATOR_ACTION_RESPONSE_SCHEMA_VERSION,
    PROPOSAL_REVISION_SCHEMA_VERSION,
    RESPONSE_OPTION_SCHEMA_VERSION,
)
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from aegis_policy.authz import actor_has_permission
from aegis_policy.commands import COMMAND_TO_ACTION_CLASS

from aegis_api.approvals.errors import ApprovalWorkflowError
from aegis_api.approvals.service import ApprovalWorkflowService
from aegis_api.operator_actions.events import build_operator_action_proposed_event

# Stable identifiers anchoring operator-initiated work. session_id / task_id on
# proposals/revisions are plain columns (no FK), so these synthetic operator identifiers
# are safe and let the UI attribute the proposal to the operator rather than an agent.
_OPERATOR_SESSION_ID = "agent-session:operator-console"

# Deterministic per-run incident that anchors operator proposals + hypotheses when the
# operator acts without pointing at a specific incident. Proposals/hypotheses FK to
# incidents, so a real anchor row is required; this keeps FK integrity while reusing all
# existing machinery unchanged.
_OPERATOR_INCIDENT_TITLE = "Operator Console"


class OperatorActionError(Exception):
    def __init__(self, *, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class OperatorActionService:
    def __init__(self, approvals: ApprovalWorkflowService | None = None) -> None:
        self._approvals = approvals or ApprovalWorkflowService()

    async def submit_action(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        request: OperatorActionRequestV1,
        actor: AuthenticatedActorV1,
    ) -> OperatorActionResponseV1:
        command = request.scenario_command
        action_class = COMMAND_TO_ACTION_CLASS[command]
        trace_id = new_runtime_id("trc")
        actor_id = actor.user_id
        authorization_token = f"session:{actor.session_id}"

        incident = await self._resolve_incident(uow, run_id, request.incident_id)

        proposal, revision = self._build_operator_proposal(
            incident_id=incident.id,
            command=command,
            action_class=action_class,
            target_asset_id=request.target_asset_id,
            reason=request.reason,
        )
        await uow.proposals.add_proposal(proposal)
        await uow.proposals.add_revision(revision)

        next_sequence = await uow.events.next_sequence(run_id)
        await uow.append_event(
            build_operator_action_proposed_event(
                event_id=new_runtime_id("evt"),
                run_id=run_id,
                sequence=next_sequence,
                actor_id=actor_id,
                trace_id=trace_id,
                proposal_id=proposal.id,
                incident_id=incident.id,
                scenario_command=command.value,
                action_class=action_class.value,
                target_asset_id=request.target_asset_id,
            )
        )

        # Reuse the approval workflow's WARDEN revalidation exactly as an approver would.
        final_check = await self._approvals._final_policy_check(
            uow,
            proposal=proposal,
            revision=revision,
            incident_state=incident.state,
            run_id=run_id,
            actor_id=actor_id,
            trace_id=trace_id,
        )
        reason_codes = [code.value for code in final_check.decision.reason_codes]
        outcome = final_check.outcome

        if outcome == PolicyOutcomeV1.BLOCK or not final_check.executable:
            blocked = proposal.model_copy(
                update={"status": ProposalStatus.REJECTED, "revision": proposal.revision + 1}
            )
            await uow.proposals.update_proposal(blocked)
            return self._response(
                proposal_id=proposal.id,
                incident_id=incident.id,
                action_class=action_class,
                status=OperatorActionStatusV1.BLOCKED,
                outcome=outcome,
                reason_codes=reason_codes,
            )

        if outcome == PolicyOutcomeV1.APPROVAL_REQUIRED and not request.confirm:
            # Confirm-with-consequences gate: leave the proposal PENDING and tell the UI
            # to show consequences and re-submit with confirm=true.
            return self._response(
                proposal_id=proposal.id,
                incident_id=incident.id,
                action_class=action_class,
                status=OperatorActionStatusV1.CONFIRMATION_REQUIRED,
                outcome=outcome,
                reason_codes=reason_codes,
            )

        # ALLOW (Class 0/1) or APPROVAL_REQUIRED + confirm (operator is the approving
        # incident commander): approve-and-execute in one call.
        if outcome == PolicyOutcomeV1.APPROVAL_REQUIRED and not actor_has_permission(
            actor, PermissionV1.APPROVALS_DECIDE
        ):
            raise OperatorActionError(
                status_code=403,
                code="FORBIDDEN",
                message="Confirming a Class 2/3 action requires approvals:decide permission",
            )

        execution = await self._approve_and_execute(
            uow,
            proposal=proposal,
            revision=revision,
            incident=incident,
            command=command,
            target_asset_id=request.target_asset_id,
            idempotency_key=request.idempotency_key,
            actor_id=actor_id,
            authorization_token=authorization_token,
            trace_id=trace_id,
        )
        return self._response(
            proposal_id=proposal.id,
            incident_id=incident.id,
            action_class=action_class,
            status=OperatorActionStatusV1.EXECUTED,
            outcome=outcome,
            reason_codes=reason_codes,
            executed=True,
            executed_action_id=execution[0],
            approval_id=execution[1],
        )

    async def create_hypothesis(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        request: OperatorHypothesisRequestV1,
        actor_id: str,
    ) -> HypothesisV1:
        """Pin an operator hypothesis into the shared (agent) hypothesis storage.

        Anchored to the deterministic operator incident (same anchor pattern operator
        actions use) so it lives in the same evidence pool the agents work. Note: asset_ids
        on the request are advisory scope for the operator; HypothesisV1 carries evidence
        grounding, not asset ids, so they are not persisted on the row.
        """
        incident = await self._resolve_incident(uow, run_id, request.incident_id)
        hypothesis = HypothesisV1(
            schema_version=1,
            id=new_runtime_id("hyp"),
            incident_id=incident.id,
            status="active",
            statement=request.statement,
            confidence=request.confidence,
            evidence_ids=[],
            created_at=datetime.now(UTC),
        )
        _ = actor_id  # attribution is via the operator incident anchor
        await uow.hypotheses.add(hypothesis)
        return hypothesis

    async def list_hypotheses(
        self,
        uow: PostgresUnitOfWork,
        *,
        run_id: str,
        incident_id: str | None = None,
    ) -> list[HypothesisV1]:
        if incident_id is not None:
            incident = await self._resolve_incident(uow, run_id, incident_id)
            return await uow.oracle_hypotheses.list_hypotheses_for_incident(incident.id)
        # No explicit incident: read the operator anchor if it exists, without creating one
        # (this is a read path).
        operator_incident = await uow.incidents.get_by_id(_operator_incident_id(run_id))
        if operator_incident is None:
            return []
        return await uow.oracle_hypotheses.list_hypotheses_for_incident(operator_incident.id)

    async def _approve_and_execute(
        self,
        uow: PostgresUnitOfWork,
        *,
        proposal: ActionProposalV1,
        revision: ProposalRevisionV1,
        incident: IncidentV1,
        command: ScenarioCommandTemplateV1,
        target_asset_id: str,
        idempotency_key: str,
        actor_id: str,
        authorization_token: str,
        trace_id: str,
    ) -> tuple[str, str]:
        now = datetime.now(UTC)
        approval = ApprovalV1(
            schema_version=APPROVAL_SCHEMA_VERSION,
            id=new_runtime_id("apr"),
            proposal_id=proposal.id,
            decision=ApprovalDecision.APPROVED,
            approver_id=actor_id,
            proposal_revision=proposal.revision,
            decided_at=now,
        )
        await uow.approvals.add(approval)
        approved = proposal.model_copy(
            update={"status": ProposalStatus.APPROVED, "revision": proposal.revision + 1}
        )
        await uow.proposals.update_proposal(approved)

        try:
            execution = await self._approvals._execute_authorized(
                uow,
                proposal_id=proposal.id,
                approval_id=approval.id,
                run_id=incident.run_id,
                incident_id=incident.id,
                scenario_command=command,
                target_asset_id=target_asset_id,
                idempotency_key=idempotency_key,
                actor_id=actor_id,
                authorization_token=authorization_token,
                trace_id=trace_id,
            )
        except ApprovalWorkflowError as exc:
            raise OperatorActionError(
                status_code=exc.status_code,
                code=exc.code.value,
                message=exc.message,
            ) from exc

        executed = approved.model_copy(
            update={"status": ProposalStatus.EXECUTED, "revision": approved.revision + 1}
        )
        await uow.proposals.update_proposal(executed)
        return execution.executed_action.id, approval.id

    async def _resolve_incident(
        self,
        uow: PostgresUnitOfWork,
        run_id: str,
        incident_id: str | None,
    ) -> IncidentV1:
        if incident_id is not None:
            incident = await uow.incidents.get_by_id(incident_id)
            if incident is None or incident.run_id != run_id:
                raise OperatorActionError(
                    status_code=404,
                    code="NOT_FOUND",
                    message=f"Incident not found for run: {incident_id}",
                )
            return incident
        return await self._ensure_operator_incident(uow, run_id)

    async def _ensure_operator_incident(
        self, uow: PostgresUnitOfWork, run_id: str
    ) -> IncidentV1:
        operator_incident_id = _operator_incident_id(run_id)
        existing = await uow.incidents.get_by_id(operator_incident_id)
        if existing is not None:
            return existing
        now = datetime.now(UTC)
        incident = IncidentV1(
            schema_version=INCIDENT_SCHEMA_VERSION,
            id=operator_incident_id,
            run_id=run_id,
            title=_OPERATOR_INCIDENT_TITLE,
            state=IncidentState.INVESTIGATING,
            alert_ids=[],
            revision=0,
            created_at=now,
            updated_at=now,
        )
        return await uow.incidents.add(incident)

    def _build_operator_proposal(
        self,
        *,
        incident_id: str,
        command: ScenarioCommandTemplateV1,
        action_class: ActionClass,
        target_asset_id: str,
        reason: str,
    ) -> tuple[ActionProposalV1, ProposalRevisionV1]:
        now = datetime.now(UTC)
        proposal_id = new_runtime_id("prp")
        revision_id = new_runtime_id("prv")
        task_id = new_runtime_id("atk")
        option = ResponseOptionV1(
            schema_version=RESPONSE_OPTION_SCHEMA_VERSION,
            option_id="operator-direct",
            scenario_command=command,
            action_class=action_class,
            target_asset_id=target_asset_id,
            affected_asset_ids=[target_asset_id],
            evidence_ids=[],
            hypothesis_ids=[],
            expected_benefit="Operator-directed containment.",
            operational_cost="Operator accepts operational impact.",
            reversibility="See command reversibility.",
            prerequisites=[],
            monitoring_plan="Operator monitors effect post-execution.",
            expected_consequences=reason,
            confidence=1.0,
            uncertainty="Operator judgement.",
            rationale=reason,
        )
        revision = ProposalRevisionV1(
            schema_version=PROPOSAL_REVISION_SCHEMA_VERSION,
            id=revision_id,
            proposal_id=proposal_id,
            incident_id=incident_id,
            session_id=_OPERATOR_SESSION_ID,
            task_id=task_id,
            revision_number=1,
            response_options=[option],
            selected_option_id=option.option_id,
            rationale=reason,
            risk_tradeoffs=reason,
            linked_hypothesis_ids=[],
            created_at=now,
        )
        proposal = ActionProposalV1(
            schema_version=ACTION_PROPOSAL_SCHEMA_VERSION,
            id=proposal_id,
            incident_id=incident_id,
            agent_session_id=_OPERATOR_SESSION_ID,
            action_class=action_class,
            target_asset_id=target_asset_id,
            command=command.value,
            scenario_command=command.value,
            current_revision_id=revision_id,
            status=ProposalStatus.PENDING,
            rationale=reason,
            revision=1,
            created_at=now,
        )
        return proposal, revision

    def _response(
        self,
        *,
        proposal_id: str,
        incident_id: str,
        action_class: ActionClass,
        status: OperatorActionStatusV1,
        outcome: PolicyOutcomeV1,
        reason_codes: list[str],
        executed: bool = False,
        executed_action_id: str | None = None,
        approval_id: str | None = None,
    ) -> OperatorActionResponseV1:
        return OperatorActionResponseV1(
            schema_version=OPERATOR_ACTION_RESPONSE_SCHEMA_VERSION,
            proposal_id=proposal_id,
            incident_id=incident_id,
            action_class=action_class,
            status=status,
            policy_outcome=outcome,
            reason_codes=reason_codes,
            executed=executed,
            executed_action_id=executed_action_id,
            approval_id=approval_id,
        )


def _operator_incident_id(run_id: str) -> str:
    # Authored ids allow only lowercase [a-z0-9._-] after the namespace; run ids embed an
    # uppercase ULID, so lowercase the derived suffix. Deterministic per run.
    suffix = run_id.split(":")[-1].lower()
    return f"incident:inc_op_{suffix}"[:64]
