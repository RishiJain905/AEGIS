"""ORACLE tool permission tests."""

from __future__ import annotations

import pytest
from aegis_agents.runtime.errors import AgentRuntimeError
from aegis_agents.runtime.registry import DEFAULT_AGENT_REGISTRY
from aegis_agents.tools.definitions import CANONICAL_TOOL_DEFINITIONS
from aegis_agents.tools.permissions import authorize_tool_call
from aegis_agents.tools.registry import ToolRegistry
from aegis_contracts.entities import AgentRole


def test_oracle_cannot_execute_simulation_command() -> None:
    registry = ToolRegistry(CANONICAL_TOOL_DEFINITIONS)
    definition = DEFAULT_AGENT_REGISTRY.get(AgentRole.ORACLE)
    with pytest.raises(AgentRuntimeError):
        authorize_tool_call(
            registry=registry,
            definition=definition,
            tool_name="execute_simulation_command",
        )


def test_oracle_cannot_create_action_proposal() -> None:
    registry = ToolRegistry(CANONICAL_TOOL_DEFINITIONS)
    definition = DEFAULT_AGENT_REGISTRY.get(AgentRole.ORACLE)
    with pytest.raises(AgentRuntimeError):
        authorize_tool_call(
            registry=registry,
            definition=definition,
            tool_name="create_action_proposal",
        )


def test_oracle_can_use_hypothesis_revision_tool() -> None:
    registry = ToolRegistry(CANONICAL_TOOL_DEFINITIONS)
    definition = DEFAULT_AGENT_REGISTRY.get(AgentRole.ORACLE)
    authorize_tool_call(
        registry=registry,
        definition=definition,
        tool_name="create_hypothesis_revision",
    )
