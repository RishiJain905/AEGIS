"""TRACE evidence collector — execute plan steps with deduplication."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from aegis_contracts.agent_runtime import ToolInvocationStatus, ToolInvocationV1
from aegis_contracts.entities import AgentRole
from aegis_contracts.investigation import (
    EvidenceAttachmentV1,
    TraceInvestigationPlanV1,
    TraceSearchStepV1,
)
from aegis_contracts.versioning import (
    TOOL_INVOCATION_SCHEMA_VERSION,
    TRACE_INVESTIGATION_PLAN_SCHEMA_VERSION,
)
from aegis_persistence.unit_of_work import PostgresUnitOfWork

from aegis_agents.roles.common.budgets import InvestigationBudgetTracker
from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_agents.runtime.ids import new_runtime_id
from aegis_agents.tools.handlers import ToolExecutionContext
from aegis_agents.tools.investigation.definitions import INVESTIGATION_TOOL_DEFINITIONS
from aegis_agents.tools.investigation.handlers import INVESTIGATION_TOOL_HANDLERS
from aegis_agents.tools.permissions import authorize_tool_call
from aegis_agents.tools.registry import ToolRegistry
from aegis_agents.tools.validator import validate_payload


@dataclass
class TraceCollectionResult:
    plan: TraceInvestigationPlanV1
    invocations: list[ToolInvocationV1] = field(default_factory=list)
    attachment_ids: list[str] = field(default_factory=list)
    deduplicated_source_keys: list[str] = field(default_factory=list)


class TraceCollector:
    def __init__(
        self,
        *,
        registry: Any | None = None,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        if registry is None:
            from aegis_agents.runtime.registry import DEFAULT_AGENT_REGISTRY

            registry = DEFAULT_AGENT_REGISTRY
        self._registry = registry
        self._tool_registry = tool_registry or ToolRegistry(INVESTIGATION_TOOL_DEFINITIONS)

    async def execute_plan(
        self,
        uow: PostgresUnitOfWork,
        *,
        ctx: ToolExecutionContext,
        plan_output: dict[str, Any],
    ) -> TraceCollectionResult:
        now = datetime.now(UTC)
        search_steps = [
            TraceSearchStepV1(
                tool_name=step["toolName"],
                arguments=step.get("arguments", {}),
                purpose=step["purpose"],
            )
            for step in plan_output.get("searchSteps", [])
            if isinstance(step, dict) and "toolName" in step and "purpose" in step
        ]
        plan = TraceInvestigationPlanV1(
            schema_version=TRACE_INVESTIGATION_PLAN_SCHEMA_VERSION,
            id=new_runtime_id("tplan"),
            incident_id=ctx.incident_id,
            run_id=ctx.run_id,
            session_id=ctx.session_id,
            task_id=ctx.task_id,
            seed_asset_ids=plan_output.get("seedAssetIds", []),
            time_window_start_sequence=plan_output.get("timeWindowStartSequence"),
            time_window_end_sequence=plan_output.get("timeWindowEndSequence"),
            max_hops=int(plan_output.get("maxHops", 4)),
            max_tool_calls=int(plan_output.get("maxToolCalls", 20)),
            max_tokens=int(plan_output.get("maxTokens", 8000)),
            search_steps=search_steps,
            rationale=plan_output.get("rationale", "Bounded TRACE investigation plan"),
            created_at=now,
        )
        await uow.investigation.add_plan(plan)

        budget = InvestigationBudgetTracker(
            max_tool_calls=plan.max_tool_calls,
            max_hops=plan.max_hops,
            trace_id=ctx.trace_id,
        )
        role = await self._session_role(uow, ctx.session_id)
        definition = self._registry.get(role)
        invocations: list[ToolInvocationV1] = []
        seen_sources: set[str] = set()
        attachment_ids: list[str] = []
        deduplicated_source_keys: list[str] = []

        for step in plan.search_steps:
            budget.record_tool_call(hops=self._estimate_hops(step))
            invocation = await self._invoke_step(
                uow=uow,
                definition=definition,
                ctx=ctx,
                step=step,
            )
            invocations.append(invocation)
            if step.tool_name == "attach_evidence":
                source_key = self._attachment_source_key(step.arguments)
                if source_key in seen_sources:
                    deduplicated_source_keys.append(source_key)
                    continue
                seen_sources.add(source_key)
                attachment_id = (
                    invocation.output_payload.get("attachmentId")
                    if invocation.output_payload
                    else None
                )
                if attachment_id:
                    attachment_ids.append(attachment_id)

        return TraceCollectionResult(
            plan=plan,
            invocations=invocations,
            attachment_ids=attachment_ids,
            deduplicated_source_keys=deduplicated_source_keys,
        )

    async def dedupe_attachments(
        self,
        attachments: list[EvidenceAttachmentV1],
    ) -> list[EvidenceAttachmentV1]:
        seen: set[str] = set()
        unique: list[EvidenceAttachmentV1] = []
        for attachment in attachments:
            key = self._provenance_key(attachment)
            if key in seen:
                continue
            seen.add(key)
            unique.append(attachment)
        return unique

    async def _invoke_step(
        self,
        *,
        uow: PostgresUnitOfWork,
        definition: Any,
        ctx: ToolExecutionContext,
        step: TraceSearchStepV1,
    ) -> ToolInvocationV1:
        started = time.perf_counter()
        now = datetime.now(UTC)
        invocation_id = new_runtime_id("tiv")
        tool = self._tool_registry.get(step.tool_name)
        if tool is None:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.TOOL_UNAUTHORIZED,
                message=f"Unknown investigation tool: {step.tool_name}",
                details={"toolName": step.tool_name},
                trace_id=ctx.trace_id,
            )

        try:
            authorize_tool_call(
                registry=self._tool_registry,
                definition=definition,
                tool_name=step.tool_name,
                trace_id=ctx.trace_id,
            )
            validate_payload(
                step.arguments,
                tool.input_schema,
                label="tool input",
                trace_id=ctx.trace_id,
            )
            handler = INVESTIGATION_TOOL_HANDLERS.get(step.tool_name)
            if handler is None:
                raise AgentRuntimeError(
                    code=AgentRuntimeErrorCode.TOOL_UNAUTHORIZED,
                    message=f"No handler registered for tool: {step.tool_name}",
                    details={"toolName": step.tool_name},
                    trace_id=ctx.trace_id,
                )
            output = await handler(ctx, step.arguments)
            validate_payload(
                output,
                tool.output_schema,
                label="tool output",
                trace_id=ctx.trace_id,
            )
            duration_ms = int((time.perf_counter() - started) * 1000)
            invocation = ToolInvocationV1(
                schema_version=TOOL_INVOCATION_SCHEMA_VERSION,
                id=invocation_id,
                task_id=ctx.task_id,
                session_id=ctx.session_id,
                tool_name=step.tool_name,
                tool_class=tool.tool_class,
                status=ToolInvocationStatus.SUCCESS,
                duration_ms=duration_ms,
                input_payload=step.arguments,
                output_payload=output,
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
                tool_name=step.tool_name,
                tool_class=tool.tool_class,
                status=status,
                duration_ms=duration_ms,
                input_payload=step.arguments,
                output_payload=None,
                error_code=exc.code.value,
                error_message=exc.message,
                created_at=now,
            )
            await uow.tool_invocations.add(invocation)
            raise

        await uow.tool_invocations.add(invocation)
        return invocation

    async def _session_role(self, uow: PostgresUnitOfWork, session_id: str) -> AgentRole:
        session = await uow.agent_sessions.get_by_id(session_id)
        if session is None:
            return AgentRole.TRACE
        return session.role

    def _estimate_hops(self, step: TraceSearchStepV1) -> int:
        if step.tool_name in {"get_relationships", "list_relationships"}:
            return int(step.arguments.get("maxDegree", 1))
        if step.tool_name in {"get_paths", "get_graph_paths"}:
            return int(step.arguments.get("maxHops", 1))
        return 0

    def _attachment_source_key(self, arguments: dict[str, Any]) -> str:
        provenance = arguments.get("provenance", {})
        if not isinstance(provenance, dict):
            return ""
        source_type = provenance.get("sourceType", "")
        source_id = provenance.get("sourceId", "")
        return f"{source_type}:{source_id}"

    def _provenance_key(self, attachment: EvidenceAttachmentV1) -> str:
        return f"{attachment.provenance.source_type.value}:{attachment.provenance.source_id}"
