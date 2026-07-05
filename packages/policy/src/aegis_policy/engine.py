"""Deterministic policy evaluation engine for Phase 22 WARDEN."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_contracts.entities import ActionClass, IncidentState
from aegis_contracts.proposals import (
    ApprovalRequirementV1,
    PolicyDecisionV1,
    PolicyInputV1,
    PolicyOutcomeV1,
    PolicyReasonCodeV1,
)
from aegis_contracts.versioning import (
    APPROVAL_REQUIREMENT_SCHEMA_VERSION,
    POLICY_DECISION_SCHEMA_VERSION,
)

from aegis_policy.commands import (
    CRITICALITY_BLOCK_THRESHOLD,
    SCENARIO_RESTRICTED_COMMANDS,
    expected_action_class,
    parse_command,
)


class PolicyEngine:
    """Pure deterministic policy evaluator."""

    def evaluate(
        self,
        policy_input: PolicyInputV1,
        *,
        decision_id: str,
        incident_id: str,
        session_id: str,
        task_id: str,
        explanation_prose: str = "",
    ) -> PolicyDecisionV1:
        now = datetime.now(UTC)

        if policy_input.proposal_revision_id != policy_input.current_revision_id:
            return self._decision(
                decision_id=decision_id,
                incident_id=incident_id,
                session_id=session_id,
                task_id=task_id,
                policy_input=policy_input,
                outcome=PolicyOutcomeV1.BLOCK,
                reason_codes=[PolicyReasonCodeV1.BLOCKED_STALE_REVISION],
                explanation_prose=explanation_prose,
                evaluated_at=now,
            )

        if policy_input.incident_state in {IncidentState.RESOLVED, IncidentState.CLOSED}:
            return self._decision(
                decision_id=decision_id,
                incident_id=incident_id,
                session_id=session_id,
                task_id=task_id,
                policy_input=policy_input,
                outcome=PolicyOutcomeV1.BLOCK,
                reason_codes=[PolicyReasonCodeV1.BLOCKED_INCIDENT_STATE],
                explanation_prose=explanation_prose,
                evaluated_at=now,
            )

        parsed = parse_command(policy_input.scenario_command.value)
        if parsed is None:
            return self._decision(
                decision_id=decision_id,
                incident_id=incident_id,
                session_id=session_id,
                task_id=task_id,
                policy_input=policy_input,
                outcome=PolicyOutcomeV1.BLOCK,
                reason_codes=[PolicyReasonCodeV1.BLOCKED_MALFORMED_COMMAND],
                explanation_prose=explanation_prose,
                evaluated_at=now,
            )

        expected_class = expected_action_class(parsed)
        if policy_input.action_class != expected_class:
            return self._decision(
                decision_id=decision_id,
                incident_id=incident_id,
                session_id=session_id,
                task_id=task_id,
                policy_input=policy_input,
                outcome=PolicyOutcomeV1.BLOCK,
                reason_codes=[PolicyReasonCodeV1.BLOCKED_INVALID_ACTION_CLASS],
                explanation_prose=explanation_prose,
                evaluated_at=now,
            )

        if policy_input.scenario_restricted and parsed in SCENARIO_RESTRICTED_COMMANDS:
            return self._decision(
                decision_id=decision_id,
                incident_id=incident_id,
                session_id=session_id,
                task_id=task_id,
                policy_input=policy_input,
                outcome=PolicyOutcomeV1.BLOCK,
                reason_codes=[PolicyReasonCodeV1.BLOCKED_SCENARIO_RESTRICTION],
                explanation_prose=explanation_prose,
                evaluated_at=now,
            )

        if (
            policy_input.action_class == ActionClass.CRITICAL
            and policy_input.asset_criticality >= CRITICALITY_BLOCK_THRESHOLD
            and parsed in SCENARIO_RESTRICTED_COMMANDS
        ):
            return self._decision(
                decision_id=decision_id,
                incident_id=incident_id,
                session_id=session_id,
                task_id=task_id,
                policy_input=policy_input,
                outcome=PolicyOutcomeV1.BLOCK,
                reason_codes=[PolicyReasonCodeV1.BLOCKED_CRITICALITY_THRESHOLD],
                explanation_prose=explanation_prose,
                evaluated_at=now,
            )

        if policy_input.action_class in {ActionClass.OPERATIONAL, ActionClass.CRITICAL}:
            reason = (
                PolicyReasonCodeV1.APPROVAL_REQUIRED_CRITICAL
                if policy_input.action_class == ActionClass.CRITICAL
                else PolicyReasonCodeV1.APPROVAL_REQUIRED_OPERATIONAL
            )
            return self._decision(
                decision_id=decision_id,
                incident_id=incident_id,
                session_id=session_id,
                task_id=task_id,
                policy_input=policy_input,
                outcome=PolicyOutcomeV1.APPROVAL_REQUIRED,
                reason_codes=[reason],
                approval_requirement=ApprovalRequirementV1(
                    schema_version=APPROVAL_REQUIREMENT_SCHEMA_VERSION,
                    required=True,
                    approver_roles=["incident_commander", "security_lead"],
                    rationale=(
                        "Class 2/3 simulated actions require explicit human approval "
                        "before execution (Phase 24 workflow)."
                    ),
                ),
                explanation_prose=explanation_prose,
                evaluated_at=now,
            )

        reason_codes = [
            PolicyReasonCodeV1.ALLOWED_READ_ONLY
            if policy_input.action_class == ActionClass.READ_ONLY
            else PolicyReasonCodeV1.ALLOWED_LOW_IMPACT
        ]
        return self._decision(
            decision_id=decision_id,
            incident_id=incident_id,
            session_id=session_id,
            task_id=task_id,
            policy_input=policy_input,
            outcome=PolicyOutcomeV1.ALLOW,
            reason_codes=reason_codes,
            explanation_prose=explanation_prose,
            evaluated_at=now,
        )

    def _decision(
        self,
        *,
        decision_id: str,
        incident_id: str,
        session_id: str,
        task_id: str,
        policy_input: PolicyInputV1,
        outcome: PolicyOutcomeV1,
        reason_codes: list[PolicyReasonCodeV1],
        approval_requirement: ApprovalRequirementV1 | None = None,
        explanation_prose: str,
        evaluated_at: datetime,
    ) -> PolicyDecisionV1:
        return PolicyDecisionV1(
            schema_version=POLICY_DECISION_SCHEMA_VERSION,
            id=decision_id,
            proposal_id=policy_input.proposal_id,
            proposal_revision_id=policy_input.proposal_revision_id,
            incident_id=incident_id,
            session_id=session_id,
            task_id=task_id,
            outcome=outcome,
            reason_codes=reason_codes,
            approval_requirement=approval_requirement,
            policy_input=policy_input,
            explanation_prose=explanation_prose,
            evaluated_at=evaluated_at,
        )
