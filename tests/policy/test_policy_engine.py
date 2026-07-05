"""Deterministic policy engine tests."""

from __future__ import annotations

from aegis_contracts.entities import ActionClass, AgentRole, IncidentState
from aegis_contracts.proposals import (
    PolicyInputV1,
    PolicyOutcomeV1,
    PolicyReasonCodeV1,
    ScenarioCommandTemplateV1,
)
from aegis_contracts.versioning import POLICY_INPUT_SCHEMA_VERSION
from aegis_policy import PolicyEngine

_PROPOSAL_ID = "prp_01ARZ3NDEKTSV4RRFFQ69G5FAV"
_REVISION_ID = "prv_01ARZ3NDEKTSV4RRFFQ69G5FB0"
_REVISION_NEW = "prv_01ARZ3NDEKTSV4RRFFQ69G5FB1"
_ASSET_ID = "asset:svc-api-gateway"
_INCIDENT_ID = "incident:inc_synthetic_001"
_SESSION_ID = "agent-session:ags_warden_001"
_TASK_ID = "atk_01ARZ3NDEKTSV4RRFFQ69G5FB2"


def _input(**overrides: object) -> PolicyInputV1:
    base = {
        "schema_version": POLICY_INPUT_SCHEMA_VERSION,
        "proposal_id": _PROPOSAL_ID,
        "proposal_revision_id": _REVISION_ID,
        "proposal_revision_number": 1,
        "current_revision_id": _REVISION_ID,
        "action_class": ActionClass.READ_ONLY,
        "scenario_command": ScenarioCommandTemplateV1.OBSERVE,
        "agent_role": AgentRole.BASTION,
        "target_asset_id": _ASSET_ID,
        "asset_criticality": 0.5,
        "reversibility": "Fully reversible",
        "incident_state": IncidentState.INVESTIGATING,
        "scenario_restricted": False,
    }
    base.update(overrides)
    return PolicyInputV1(**base)  # type: ignore[arg-type]


def test_class_0_observe_allowed() -> None:
    engine = PolicyEngine()
    decision = engine.evaluate(
        _input(),
        decision_id="pdc_01ARZ3NDEKTSV4RRFFQ69G5FB3",
        incident_id=_INCIDENT_ID,
        session_id=_SESSION_ID,
        task_id=_TASK_ID,
    )
    assert decision.outcome == PolicyOutcomeV1.ALLOW
    assert PolicyReasonCodeV1.ALLOWED_READ_ONLY in decision.reason_codes


def test_class_2_requires_approval() -> None:
    engine = PolicyEngine()
    decision = engine.evaluate(
        _input(
            action_class=ActionClass.OPERATIONAL,
            scenario_command=ScenarioCommandTemplateV1.ISOLATE,
        ),
        decision_id="pdc_01ARZ3NDEKTSV4RRFFQ69G5FB4",
        incident_id=_INCIDENT_ID,
        session_id=_SESSION_ID,
        task_id=_TASK_ID,
    )
    assert decision.outcome == PolicyOutcomeV1.APPROVAL_REQUIRED
    assert decision.approval_requirement is not None
    assert decision.approval_requirement.required is True


def test_class_3_critical_requires_approval() -> None:
    engine = PolicyEngine()
    decision = engine.evaluate(
        _input(
            action_class=ActionClass.CRITICAL,
            scenario_command=ScenarioCommandTemplateV1.ROLLBACK_DEPLOYMENT,
        ),
        decision_id="pdc_01ARZ3NDEKTSV4RRFFQ69G5FB5",
        incident_id=_INCIDENT_ID,
        session_id=_SESSION_ID,
        task_id=_TASK_ID,
    )
    assert decision.outcome == PolicyOutcomeV1.APPROVAL_REQUIRED
    assert PolicyReasonCodeV1.APPROVAL_REQUIRED_CRITICAL in decision.reason_codes


def test_stale_revision_blocked() -> None:
    engine = PolicyEngine()
    decision = engine.evaluate(
        _input(
            proposal_revision_id=_REVISION_ID,
            current_revision_id=_REVISION_NEW,
        ),
        decision_id="pdc_01ARZ3NDEKTSV4RRFFQ69G5FB6",
        incident_id=_INCIDENT_ID,
        session_id=_SESSION_ID,
        task_id=_TASK_ID,
    )
    assert decision.outcome == PolicyOutcomeV1.BLOCK
    assert PolicyReasonCodeV1.BLOCKED_STALE_REVISION in decision.reason_codes


def test_invalid_action_class_blocked() -> None:
    engine = PolicyEngine()
    decision = engine.evaluate(
        _input(
            action_class=ActionClass.CRITICAL,
            scenario_command=ScenarioCommandTemplateV1.OBSERVE,
        ),
        decision_id="pdc_01ARZ3NDEKTSV4RRFFQ69G5FB7",
        incident_id=_INCIDENT_ID,
        session_id=_SESSION_ID,
        task_id=_TASK_ID,
    )
    assert decision.outcome == PolicyOutcomeV1.BLOCK
    assert PolicyReasonCodeV1.BLOCKED_INVALID_ACTION_CLASS in decision.reason_codes


def test_scenario_restriction_blocks_critical_on_high_criticality() -> None:
    engine = PolicyEngine()
    decision = engine.evaluate(
        _input(
            action_class=ActionClass.CRITICAL,
            scenario_command=ScenarioCommandTemplateV1.RESTART_SERVICE,
            asset_criticality=0.95,
            scenario_restricted=True,
        ),
        decision_id="pdc_01ARZ3NDEKTSV4RRFFQ69G5FB8",
        incident_id=_INCIDENT_ID,
        session_id=_SESSION_ID,
        task_id=_TASK_ID,
    )
    assert decision.outcome == PolicyOutcomeV1.BLOCK
    assert (
        PolicyReasonCodeV1.BLOCKED_SCENARIO_RESTRICTION in decision.reason_codes
        or PolicyReasonCodeV1.BLOCKED_CRITICALITY_THRESHOLD in decision.reason_codes
    )
