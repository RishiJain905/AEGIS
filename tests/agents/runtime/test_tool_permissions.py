"""Tool permission and validation tests."""

from __future__ import annotations

import pytest
from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_agents.runtime.registry import build_definition
from aegis_agents.tools.permissions import authorize_tool_call
from aegis_agents.tools.registry import ToolRegistry
from aegis_agents.tools.validator import validate_payload
from aegis_contracts.agent_runtime import AgentToolClass
from aegis_contracts.entities import AgentRole
from aegis_contracts.versioning import TOOL_DEFINITION_SCHEMA_VERSION


def test_execution_tool_rejected_for_model_visibility() -> None:
    from aegis_contracts.agent_runtime import ToolDefinitionV1

    tool = ToolDefinitionV1(
        schema_version=TOOL_DEFINITION_SCHEMA_VERSION,
        name="execute_simulation_command",
        description="hidden",
        tool_class=AgentToolClass.EXECUTION,
        model_visible=False,
        allowed_roles=[],
    )
    registry = ToolRegistry([tool])
    visible = registry.model_visible_tools(AgentRole.TRACE)
    assert visible == []


def test_unauthorized_tool_rejected() -> None:
    definition = build_definition(AgentRole.SCRIBE)
    with pytest.raises(AgentRuntimeError) as exc:
        authorize_tool_call(
            registry=ToolRegistry(),
            definition=definition,
            tool_name="create_action_proposal",
        )
    assert exc.value.code == AgentRuntimeErrorCode.TOOL_UNAUTHORIZED


def test_malformed_tool_input_rejected() -> None:
    from aegis_agents.tools.definitions import CANONICAL_TOOL_DEFINITIONS

    tool = next(item for item in CANONICAL_TOOL_DEFINITIONS if item.name == "create_hypothesis")
    with pytest.raises(AgentRuntimeError) as exc:
        validate_payload({}, tool.input_schema, label="tool input")
    assert exc.value.code == AgentRuntimeErrorCode.TOOL_VALIDATION_FAILED
