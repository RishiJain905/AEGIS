"""Phase 22 WARDEN policy evaluation tests."""

from __future__ import annotations

from aegis_agents.roles.registry import get_role_handler
from aegis_agents.roles.warden.handler import WardenRoleHandler
from aegis_agents.runtime.errors import AgentRuntimeError
from aegis_agents.runtime.registry import DEFAULT_AGENT_REGISTRY
from aegis_agents.tools.definitions import CANONICAL_TOOL_DEFINITIONS
from aegis_agents.tools.permissions import authorize_tool_call
from aegis_agents.tools.registry import ToolRegistry
from aegis_contracts.entities import ActionClass, AgentRole, IncidentState
from aegis_contracts.proposals import PolicyOutcomeV1, ScenarioCommandTemplateV1
from aegis_contracts.versioning import POLICY_INPUT_SCHEMA_VERSION
from aegis_policy import PolicyEngine


def test_warden_handler_registered_with_phase22_prompt() -> None:
    handler = get_role_handler(AgentRole.WARDEN)
    assert handler is not None
    assert handler.prompt_version == "phase22-warden-v1"


def test_warden_cannot_create_proposals() -> None:
    registry = ToolRegistry(CANONICAL_TOOL_DEFINITIONS)
    definition = DEFAULT_AGENT_REGISTRY.get(AgentRole.WARDEN)
    try:
        authorize_tool_call(
            registry=registry,
            definition=definition,
            tool_name="create_response_proposal",
        )
        raised = False
    except AgentRuntimeError:
        raised = True
    assert raised


def test_policy_decision_independent_of_model_prose() -> None:
    engine = PolicyEngine()
    from aegis_contracts.proposals import PolicyInputV1

    policy_input = PolicyInputV1(
        schema_version=POLICY_INPUT_SCHEMA_VERSION,
        proposal_id="prp_01ARZ3NDEKTSV4RRFFQ69G5FBA",
        proposal_revision_id="prv_01ARZ3NDEKTSV4RRFFQ69G5FBB",
        proposal_revision_number=1,
        current_revision_id="prv_01ARZ3NDEKTSV4RRFFQ69G5FBB",
        action_class=ActionClass.OPERATIONAL,
        scenario_command=ScenarioCommandTemplateV1.ISOLATE,
        agent_role=AgentRole.BASTION,
        target_asset_id="asset:svc-api-gateway",
        asset_criticality=0.5,
        reversibility="Reversible",
        incident_state=IncidentState.CONTAINMENT_PROPOSED,
        scenario_restricted=False,
    )
    decision = engine.evaluate(
        policy_input,
        decision_id="pdc_01ARZ3NDEKTSV4RRFFQ69G5FBC",
        incident_id="incident:inc_synthetic_001",
        session_id="agent-session:ags_warden_001",
        task_id="atk_01ARZ3NDEKTSV4RRFFQ69G5FBD",
        explanation_prose="Model claims allow but policy is authoritative.",
    )
    assert decision.outcome == PolicyOutcomeV1.APPROVAL_REQUIRED
    assert decision.explanation_prose.startswith("Model claims")


def test_warden_handler_uses_policy_engine() -> None:
    handler = WardenRoleHandler()
    assert handler._policy is not None
