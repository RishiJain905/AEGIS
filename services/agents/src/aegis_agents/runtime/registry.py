"""Agent definition registry for generic Phase 19 runtime and Phase 20 investigation roles."""

from __future__ import annotations

from aegis_agents.roles.registry import get_role_handler
from aegis_contracts.agent_runtime import AgentBudgetV1, AgentDefinitionV1
from aegis_contracts.entities import AgentRole
from aegis_contracts.versioning import (
    AGENT_BUDGET_SCHEMA_VERSION,
    AGENT_DEFINITION_SCHEMA_VERSION,
)

_DEFAULT_BUDGET = AgentBudgetV1(
    schema_version=AGENT_BUDGET_SCHEMA_VERSION,
    max_tokens=8000,
    max_latency_ms=60_000,
    max_cost_usd=1.0,
)

_BASE_TOOLS = [
    "list_evidence",
    "get_incident",
    "create_hypothesis",
]

_WATCHTOWER_TOOLS = [
    "get_incident",
    "list_alerts",
    "get_alert",
    "get_risk_scores",
    "list_existing_evidence",
]

_TRACE_TOOLS = [
    "get_incident",
    "list_alerts",
    "get_alert",
    "get_risk_scores",
    "list_existing_evidence",
    "search_events",
    "get_asset",
    "list_relationships",
    "get_graph_paths",
    "get_incident_timeline",
    "attach_evidence",
    "create_investigation_note",
]

_ORACLE_TOOLS = [
    "get_incident",
    "list_existing_evidence",
    "list_hypotheses",
    "create_hypothesis_revision",
    "request_trace_verification",
    "retire_hypothesis",
]

_BASTION_TOOLS = [
    "get_incident",
    "list_existing_evidence",
    "list_hypotheses",
    "get_risk_scores",
    "list_alerts",
    "create_response_proposal",
]

_WARDEN_TOOLS = [
    "get_incident",
    "list_proposals",
    "get_risk_scores",
]

_SCRIBE_TOOLS = [
    "get_incident",
    "list_existing_evidence",
    "list_hypotheses",
    "list_proposals",
    "search_events",
    "list_alerts",
]

_ROLE_TOOLS: dict[AgentRole, list[str]] = {
    AgentRole.WATCHTOWER: _WATCHTOWER_TOOLS,
    AgentRole.TRACE: _TRACE_TOOLS,
    AgentRole.ORACLE: _ORACLE_TOOLS,
    AgentRole.BASTION: _BASTION_TOOLS,
    AgentRole.WARDEN: _WARDEN_TOOLS,
    AgentRole.SCRIBE: _SCRIBE_TOOLS,
}


def build_definition(role: AgentRole, *, provider_id: str = "mock") -> AgentDefinitionV1:
    handler = get_role_handler(role)
    prompt_version = handler.prompt_version if handler is not None else "phase19-v1"
    return AgentDefinitionV1(
        schema_version=AGENT_DEFINITION_SCHEMA_VERSION,
        role=role,
        definition_id=f"runtime-{role.value.lower()}-v1",
        prompt_version=prompt_version,
        provider_id=provider_id,
        model_id=f"{provider_id}-v1",
        allowed_tools=_ROLE_TOOLS[role],
        default_budget=_DEFAULT_BUDGET,
    )


class AgentDefinitionRegistry:
    def __init__(self) -> None:
        self._definitions = {role: build_definition(role) for role in AgentRole}

    def get(self, role: AgentRole) -> AgentDefinitionV1:
        return self._definitions[role]

    def list_definitions(self) -> list[AgentDefinitionV1]:
        return list(self._definitions.values())


DEFAULT_AGENT_REGISTRY = AgentDefinitionRegistry()
