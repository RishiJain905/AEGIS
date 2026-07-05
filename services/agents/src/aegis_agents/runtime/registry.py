"""Agent definition registry for generic Phase 19 runtime."""

from __future__ import annotations

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

_ROLE_TOOLS: dict[AgentRole, list[str]] = {
    AgentRole.WATCHTOWER: _BASE_TOOLS,
    AgentRole.TRACE: _BASE_TOOLS + ["create_action_proposal"],
    AgentRole.ORACLE: _BASE_TOOLS,
    AgentRole.BASTION: _BASE_TOOLS + ["create_action_proposal"],
    AgentRole.WARDEN: _BASE_TOOLS + ["create_action_proposal"],
    AgentRole.SCRIBE: _BASE_TOOLS,
}


def build_definition(role: AgentRole, *, provider_id: str = "mock") -> AgentDefinitionV1:
    return AgentDefinitionV1(
        schema_version=AGENT_DEFINITION_SCHEMA_VERSION,
        role=role,
        definition_id=f"runtime-{role.value.lower()}-v1",
        prompt_version="phase19-v1",
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
