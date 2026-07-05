"""Phase 20 role handler registry."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from aegis_contracts.entities import AgentRole
from aegis_persistence.unit_of_work import PostgresUnitOfWork

from aegis_agents.roles.common.schemas import (
    TRACE_STEP_OUTPUT_SCHEMA,
    WATCHTOWER_TRIAGE_OUTPUT_SCHEMA,
)
from aegis_agents.roles.oracle.schemas import ORACLE_HYPOTHESIS_OUTPUT_SCHEMA

PostProcessHook = Callable[["PostProcessContext", dict[str, Any]], Awaitable[None]]


@dataclass
class PostProcessContext:
    uow: PostgresUnitOfWork
    session_id: str
    task_id: str
    incident_id: str
    run_id: str
    trace_id: str
    idempotency_key: str
    visible_evidence_ids: set[str] = field(default_factory=set)


class RoleHandlerProtocol(Protocol):
    role: AgentRole
    prompt_version: str

    def output_schema(self) -> dict[str, Any]: ...

    def system_prompt(self) -> str: ...

    async def post_process(
        self,
        *,
        ctx: PostProcessContext,
        structured: dict[str, Any],
    ) -> None: ...


@dataclass(frozen=True)
class RoleHandler:
    role: AgentRole
    prompt_version: str
    system_prompt: str
    output_schema: dict[str, Any]
    default_tool_requests: list[dict[str, Any]] = field(default_factory=list)
    post_process: PostProcessHook | None = None


WATCHTOWER_HANDLER = RoleHandler(
    role=AgentRole.WATCHTOWER,
    prompt_version="phase20-watchtower-v1",
    system_prompt=(
        "You are WATCHTOWER, the AEGIS alert triage agent. "
        "Correlate alerts using only visible evidence, recommend escalation, "
        "and return concise grounded rationale without hidden chain-of-thought."
    ),
    output_schema=WATCHTOWER_TRIAGE_OUTPUT_SCHEMA,
    default_tool_requests=[
        {"name": "list_alerts", "arguments": {}, "purpose": "Enumerate run alerts for triage"},
        {"name": "list_existing_evidence", "arguments": {}, "purpose": "Load visible evidence"},
    ],
)

TRACE_HANDLER = RoleHandler(
    role=AgentRole.TRACE,
    prompt_version="phase20-trace-v1",
    system_prompt=(
        "You are TRACE, the AEGIS bounded investigation agent. "
        "Plan graph and event searches within hop and tool budgets, "
        "attach grounded evidence, and identify candidate affected assets."
    ),
    output_schema=TRACE_STEP_OUTPUT_SCHEMA,
    default_tool_requests=[
        {"name": "search_events", "arguments": {"limit": 200}, "purpose": "Survey recent events"},
        {"name": "list_existing_evidence", "arguments": {}, "purpose": "Load visible evidence"},
        {"name": "get_risk_scores", "arguments": {}, "purpose": "Review propagated risk"},
    ],
)

ORACLE_HANDLER = RoleHandler(
    role=AgentRole.ORACLE,
    prompt_version="phase21-oracle-v1",
    system_prompt=(
        "You are ORACLE, the AEGIS hypothesis generation agent. "
        "Produce multiple competing evidence-grounded hypotheses with explicit "
        "confidence, contradictions, unknowns, and verification requests."
    ),
    output_schema=ORACLE_HYPOTHESIS_OUTPUT_SCHEMA,
    default_tool_requests=[
        {"name": "list_existing_evidence", "arguments": {}, "purpose": "Load visible evidence"},
        {"name": "list_hypotheses", "arguments": {}, "purpose": "Review current hypotheses"},
    ],
)

ROLE_HANDLER_METADATA: dict[AgentRole, RoleHandler] = {
    AgentRole.WATCHTOWER: WATCHTOWER_HANDLER,
    AgentRole.TRACE: TRACE_HANDLER,
    AgentRole.ORACLE: ORACLE_HANDLER,
}


def _load_handlers() -> dict[AgentRole, RoleHandlerProtocol]:
    from aegis_agents.roles.oracle.handler import OracleRoleHandler
    from aegis_agents.roles.trace.handler import TraceRoleHandler
    from aegis_agents.roles.watchtower.handler import WatchtowerRoleHandler

    handlers: list[RoleHandlerProtocol] = [
        WatchtowerRoleHandler(),
        TraceRoleHandler(),
        OracleRoleHandler(),
    ]
    return {handler.role: handler for handler in handlers}


ROLE_HANDLER_REGISTRY: dict[AgentRole, RoleHandlerProtocol] = _load_handlers()


def get_role_handler(role: AgentRole) -> RoleHandlerProtocol | None:
    return ROLE_HANDLER_REGISTRY.get(role)
