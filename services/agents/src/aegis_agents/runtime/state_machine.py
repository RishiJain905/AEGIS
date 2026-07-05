"""Incident-scoped agent session state machine."""

from __future__ import annotations

from typing import Never

from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_contracts.entities import AgentSessionState

_TRANSITIONS: dict[AgentSessionState, frozenset[AgentSessionState]] = {
    AgentSessionState.QUEUED: frozenset({AgentSessionState.GATHERING, AgentSessionState.CANCELLED}),
    AgentSessionState.GATHERING: frozenset({
        AgentSessionState.HYPOTHESIZING,
        AgentSessionState.FAILED,
        AgentSessionState.CANCELLED,
    }),
    AgentSessionState.HYPOTHESIZING: frozenset({
        AgentSessionState.VERIFYING,
        AgentSessionState.FAILED,
        AgentSessionState.CANCELLED,
    }),
    AgentSessionState.VERIFYING: frozenset({
        AgentSessionState.GATHERING,
        AgentSessionState.PROPOSING,
        AgentSessionState.COMPLETED,
        AgentSessionState.FAILED,
        AgentSessionState.CANCELLED,
    }),
    AgentSessionState.PROPOSING: frozenset({
        AgentSessionState.APPROVAL_PENDING,
        AgentSessionState.COMPLETED,
        AgentSessionState.FAILED,
        AgentSessionState.CANCELLED,
    }),
    AgentSessionState.APPROVAL_PENDING: frozenset({
        AgentSessionState.PROPOSING,
        AgentSessionState.EXECUTING,
        AgentSessionState.CANCELLED,
    }),
    AgentSessionState.EXECUTING: frozenset({
        AgentSessionState.COMPLETED,
        AgentSessionState.FAILED,
        AgentSessionState.CANCELLED,
    }),
    AgentSessionState.COMPLETED: frozenset(),
    AgentSessionState.FAILED: frozenset({AgentSessionState.QUEUED}),
    AgentSessionState.CANCELLED: frozenset(),
}


def can_transition(from_state: AgentSessionState, to_state: AgentSessionState) -> bool:
    return to_state in _TRANSITIONS.get(from_state, frozenset())


def assert_transition(
    from_state: AgentSessionState,
    to_state: AgentSessionState,
    *,
    trace_id: str | None = None,
) -> None:
    if not can_transition(from_state, to_state):
        raise AgentRuntimeError(
            code=AgentRuntimeErrorCode.INVALID_TRANSITION,
            message=f"Invalid agent session transition: {from_state.value} -> {to_state.value}",
            details={"fromState": from_state.value, "toState": to_state.value},
            trace_id=trace_id,
        )


def is_terminal(state: AgentSessionState) -> bool:
    match state:
        case AgentSessionState.COMPLETED | AgentSessionState.FAILED | AgentSessionState.CANCELLED:
            return True
        case (
            AgentSessionState.QUEUED
            | AgentSessionState.GATHERING
            | AgentSessionState.HYPOTHESIZING
            | AgentSessionState.VERIFYING
            | AgentSessionState.PROPOSING
            | AgentSessionState.APPROVAL_PENDING
            | AgentSessionState.EXECUTING
        ):
            return False
        case _:
            exhaustive: Never = state
            raise AssertionError(f"Unhandled agent session state: {exhaustive!r}")
