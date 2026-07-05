"""Failure isolation guarantees for agent runtime."""

from __future__ import annotations

import pytest
from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_agents.runtime.state_machine import assert_transition
from aegis_contracts.entities import AgentSessionState


def test_terminal_states_reject_further_transitions() -> None:
    with pytest.raises(AgentRuntimeError) as exc:
        assert_transition(AgentSessionState.FAILED, AgentSessionState.GATHERING)
    assert exc.value.code == AgentRuntimeErrorCode.INVALID_TRANSITION


def test_execution_tool_error_code_is_stable() -> None:
    assert AgentRuntimeErrorCode.TOOL_UNAUTHORIZED.value == "TOOL_UNAUTHORIZED"
