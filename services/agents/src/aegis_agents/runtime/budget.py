"""Token, latency, and cost budget enforcement."""

# ruff: noqa: E501

from __future__ import annotations

from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_contracts.agent_runtime import AgentBudgetV1


def check_budget(
    budget: AgentBudgetV1,
    *,
    additional_tokens: int = 0,
    additional_latency_ms: int = 0,
    additional_cost_usd: float = 0.0,
    trace_id: str | None = None,
) -> None:
    if budget.consumed_tokens + additional_tokens > budget.max_tokens:
        raise AgentRuntimeError(
            code=AgentRuntimeErrorCode.BUDGET_EXCEEDED,
            message="Token budget exceeded",
            details={"consumedTokens": budget.consumed_tokens, "maxTokens": budget.max_tokens},
            trace_id=trace_id,
        )
    if budget.consumed_latency_ms + additional_latency_ms > budget.max_latency_ms:
        raise AgentRuntimeError(
            code=AgentRuntimeErrorCode.BUDGET_EXCEEDED,
            message="Latency budget exceeded",
            details={
                "consumedLatencyMs": budget.consumed_latency_ms,
                "maxLatencyMs": budget.max_latency_ms,
            },
            trace_id=trace_id,
        )
    if budget.consumed_cost_usd + additional_cost_usd > budget.max_cost_usd:
        raise AgentRuntimeError(
            code=AgentRuntimeErrorCode.BUDGET_EXCEEDED,
            message="Cost budget exceeded",
            details={"consumedCostUsd": budget.consumed_cost_usd, "maxCostUsd": budget.max_cost_usd},
            trace_id=trace_id,
        )


def apply_usage(
    budget: AgentBudgetV1,
    *,
    tokens: int,
    latency_ms: int,
    cost_usd: float,
) -> AgentBudgetV1:
    return budget.model_copy(
        update={
            "consumed_tokens": budget.consumed_tokens + tokens,
            "consumed_latency_ms": budget.consumed_latency_ms + latency_ms,
            "consumed_cost_usd": budget.consumed_cost_usd + cost_usd,
        }
    )
