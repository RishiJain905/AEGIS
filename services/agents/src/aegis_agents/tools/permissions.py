"""Server-side tool permission checks."""

from __future__ import annotations

from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_agents.tools.registry import ToolRegistry
from aegis_contracts.agent_runtime import AgentDefinitionV1, AgentToolClass
from aegis_contracts.entities import AgentRole


def authorize_tool_call(
    *,
    registry: ToolRegistry,
    definition: AgentDefinitionV1,
    tool_name: str,
    trace_id: str | None = None,
) -> None:
    tool = registry.get(tool_name)
    if tool is None:
        raise AgentRuntimeError(
            code=AgentRuntimeErrorCode.TOOL_UNAUTHORIZED,
            message=f"Unknown tool: {tool_name}",
            details={"toolName": tool_name},
            trace_id=trace_id,
        )
    if tool.tool_class == AgentToolClass.EXECUTION:
        raise AgentRuntimeError(
            code=AgentRuntimeErrorCode.TOOL_UNAUTHORIZED,
            message="Execution-class tools are not invokable by the agent runtime",
            details={"toolName": tool_name},
            trace_id=trace_id,
        )
    if definition.role not in tool.allowed_roles:
        raise AgentRuntimeError(
            code=AgentRuntimeErrorCode.TOOL_UNAUTHORIZED,
            message=f"Role {definition.role.value} is not permitted to call {tool_name}",
            details={"toolName": tool_name, "role": definition.role.value},
            trace_id=trace_id,
        )
    if tool_name not in definition.allowed_tools:
        raise AgentRuntimeError(
            code=AgentRuntimeErrorCode.TOOL_UNAUTHORIZED,
            message=f"Tool {tool_name} is not in the agent definition allowlist",
            details={"toolName": tool_name, "definitionId": definition.definition_id},
            trace_id=trace_id,
        )


def role_from_definition(definition: AgentDefinitionV1) -> AgentRole:
    return definition.role
