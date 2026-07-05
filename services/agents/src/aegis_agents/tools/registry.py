"""Allowlisted tool registry."""

from __future__ import annotations

from aegis_agents.tools.definitions import CANONICAL_TOOL_DEFINITIONS
from aegis_contracts.agent_runtime import ToolDefinitionV1
from aegis_contracts.entities import AgentRole
from aegis_contracts.generation import ToolSchemaV1
from aegis_contracts.versioning import TOOL_SCHEMA_SCHEMA_VERSION


class ToolRegistry:
    def __init__(self, definitions: list[ToolDefinitionV1] | None = None) -> None:
        items = definitions or CANONICAL_TOOL_DEFINITIONS
        self._by_name = {item.name: item for item in items}

    def get(self, name: str) -> ToolDefinitionV1 | None:
        return self._by_name.get(name)

    def list_definitions(self) -> list[ToolDefinitionV1]:
        return list(self._by_name.values())

    def model_visible_tools(self, role: AgentRole) -> list[ToolDefinitionV1]:
        return [
            definition
            for definition in self._by_name.values()
            if definition.model_visible and role in definition.allowed_roles
        ]

    def model_visible_tool_schemas(self, role: AgentRole) -> list[ToolSchemaV1]:
        return [
            ToolSchemaV1(
                schema_version=TOOL_SCHEMA_SCHEMA_VERSION,
                name=definition.name,
                description=definition.description,
                parameters=definition.input_schema,
            )
            for definition in self.model_visible_tools(role)
        ]


DEFAULT_TOOL_REGISTRY = ToolRegistry()
