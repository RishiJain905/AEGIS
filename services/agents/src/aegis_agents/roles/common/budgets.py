"""Investigation-specific budget tracking for bounded TRACE searches."""

from __future__ import annotations

from dataclasses import dataclass, field

from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode


@dataclass
class InvestigationBudgetTracker:
    max_tool_calls: int
    max_hops: int
    consumed_tool_calls: int = field(default=0)
    consumed_hops: int = field(default=0)
    trace_id: str | None = None

    def record_tool_call(self, *, hops: int = 0) -> None:
        self.consumed_tool_calls += 1
        if hops > 0:
            self.consumed_hops = max(self.consumed_hops, hops)
        self.check()

    def check(self) -> None:
        if self.consumed_tool_calls > self.max_tool_calls:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.BUDGET_EXCEEDED,
                message="Investigation tool-call budget exceeded",
                details={
                    "consumedToolCalls": self.consumed_tool_calls,
                    "maxToolCalls": self.max_tool_calls,
                },
                trace_id=self.trace_id,
            )
        if self.consumed_hops > self.max_hops:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.BUDGET_EXCEEDED,
                message="Investigation hop budget exceeded",
                details={
                    "consumedHops": self.consumed_hops,
                    "maxHops": self.max_hops,
                },
                trace_id=self.trace_id,
            )
