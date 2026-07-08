"""SCRIBE agent role tests."""

from __future__ import annotations

from aegis_agents.runtime.errors import AgentRuntimeError
from aegis_agents.runtime.registry import build_definition
from aegis_agents.tools.definitions import CANONICAL_TOOL_DEFINITIONS
from aegis_agents.tools.permissions import authorize_tool_call
from aegis_agents.tools.registry import ToolRegistry
from aegis_contracts.entities import AgentRole


def test_scribe_definition_uses_read_only_tools() -> None:
    definition = build_definition(AgentRole.SCRIBE)
    assert "create_hypothesis" not in definition.allowed_tools
    assert "create_response_proposal" not in definition.allowed_tools
    assert "list_proposals" in definition.allowed_tools


def test_scribe_cannot_use_execution_tools() -> None:
    registry = ToolRegistry(CANONICAL_TOOL_DEFINITIONS)
    definition = build_definition(AgentRole.SCRIBE)
    try:
        authorize_tool_call(
            registry=registry,
            definition=definition,
            tool_name="execute_simulation_command",
        )
        rejected = False
    except AgentRuntimeError:
        rejected = True
    assert rejected is True
