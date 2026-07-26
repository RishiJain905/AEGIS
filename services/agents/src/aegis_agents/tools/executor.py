"""Audited tool invocation executor."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_agents.runtime.ids import new_runtime_id
from aegis_agents.tools.handlers import TOOL_HANDLERS, ToolExecutionContext
from aegis_agents.tools.permissions import authorize_tool_call
from aegis_agents.tools.registry import DEFAULT_TOOL_REGISTRY, ToolRegistry
from aegis_agents.tools.validator import validate_payload
from aegis_contracts.agent_runtime import (
    AgentDefinitionV1,
    ToolInvocationStatus,
    ToolInvocationV1,
)
from aegis_contracts.versioning import TOOL_INVOCATION_SCHEMA_VERSION
from aegis_persistence.unit_of_work import PostgresUnitOfWork


class ToolExecutor:
    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self._registry = registry or DEFAULT_TOOL_REGISTRY

    async def invoke(
        self,
        *,
        uow: PostgresUnitOfWork,
        definition: AgentDefinitionV1,
        ctx: ToolExecutionContext,
        tool_name: str,
        payload: dict[str, Any],
        loop_iteration: int | None = None,
    ) -> ToolInvocationV1:
        """Run one allowlisted tool and persist an audit row for the attempt.

        ``loop_iteration`` records which round of the agent's multi-turn tool loop
        asked for this call (``None`` for a call that came from the model's final
        answer). It is audit metadata only — it never influences authorization.
        """
        started = time.perf_counter()
        now = datetime.now(UTC)
        invocation_id = new_runtime_id("tiv")
        tool = self._registry.get(tool_name)
        if tool is None:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.TOOL_UNAUTHORIZED,
                message=f"Unknown tool: {tool_name}",
                details={"toolName": tool_name},
                trace_id=ctx.trace_id,
            )

        try:
            authorize_tool_call(
                registry=self._registry,
                definition=definition,
                tool_name=tool_name,
                trace_id=ctx.trace_id,
            )
            validate_payload(payload, tool.input_schema, label="tool input", trace_id=ctx.trace_id)
            handler = TOOL_HANDLERS.get(tool_name)
            if handler is None:
                raise AgentRuntimeError(
                    code=AgentRuntimeErrorCode.TOOL_UNAUTHORIZED,
                    message=f"No handler registered for tool: {tool_name}",
                    details={"toolName": tool_name},
                    trace_id=ctx.trace_id,
                )
            output = await handler(ctx, payload)
            validate_payload(output, tool.output_schema, label="tool output", trace_id=ctx.trace_id)
            duration_ms = int((time.perf_counter() - started) * 1000)
            invocation = ToolInvocationV1(
                schema_version=TOOL_INVOCATION_SCHEMA_VERSION,
                id=invocation_id,
                task_id=ctx.task_id,
                session_id=ctx.session_id,
                tool_name=tool_name,
                tool_class=tool.tool_class,
                status=ToolInvocationStatus.SUCCESS,
                duration_ms=duration_ms,
                input_payload=payload,
                output_payload=output,
                loop_iteration=loop_iteration,
                created_at=now,
            )
        except AgentRuntimeError as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            status = (
                ToolInvocationStatus.REJECTED
                if exc.code == AgentRuntimeErrorCode.TOOL_UNAUTHORIZED
                else ToolInvocationStatus.FAILED
            )
            invocation = ToolInvocationV1(
                schema_version=TOOL_INVOCATION_SCHEMA_VERSION,
                id=invocation_id,
                task_id=ctx.task_id,
                session_id=ctx.session_id,
                tool_name=tool_name,
                tool_class=tool.tool_class,
                status=status,
                duration_ms=duration_ms,
                input_payload=payload,
                output_payload=None,
                error_code=exc.code.value,
                error_message=exc.message,
                loop_iteration=loop_iteration,
                created_at=now,
            )
            await uow.tool_invocations.add(invocation)
            raise

        await uow.tool_invocations.add(invocation)
        return invocation
