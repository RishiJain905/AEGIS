"""Budget and timeout enforcement tests."""

from __future__ import annotations

import pytest
from aegis_agents.runtime.budget import apply_usage, check_budget
from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_contracts.agent_runtime import AgentBudgetV1
from aegis_contracts.versioning import AGENT_BUDGET_SCHEMA_VERSION


def _budget(**overrides: object) -> AgentBudgetV1:
    base = AgentBudgetV1(
        schema_version=AGENT_BUDGET_SCHEMA_VERSION,
        max_tokens=100,
        max_latency_ms=1000,
        max_cost_usd=0.5,
    )
    return base.model_copy(update=overrides)


def test_token_budget_exceeded() -> None:
    budget = _budget(consumed_tokens=95)
    with pytest.raises(AgentRuntimeError) as exc:
        check_budget(budget, additional_tokens=10)
    assert exc.value.code == AgentRuntimeErrorCode.BUDGET_EXCEEDED


def test_latency_budget_exceeded() -> None:
    budget = _budget(consumed_latency_ms=900)
    with pytest.raises(AgentRuntimeError) as exc:
        check_budget(budget, additional_latency_ms=200)
    assert exc.value.code == AgentRuntimeErrorCode.BUDGET_EXCEEDED


def test_apply_usage_accumulates_counters() -> None:
    budget = _budget()
    updated = apply_usage(budget, tokens=12, latency_ms=34, cost_usd=0.01)
    assert updated.consumed_tokens == 12
    assert updated.consumed_latency_ms == 34
    assert updated.consumed_cost_usd == 0.01


def test_timeout_error_code_is_stable() -> None:
    assert AgentRuntimeErrorCode.TASK_TIMEOUT.value == "TASK_TIMEOUT"
