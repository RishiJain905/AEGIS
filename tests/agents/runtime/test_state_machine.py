"""State machine transition tests."""

from __future__ import annotations

import pytest
from aegis_agents.runtime.errors import AgentRuntimeError
from aegis_agents.runtime.state_machine import assert_transition, can_transition, is_terminal
from aegis_contracts.entities import AgentSessionState


def test_valid_gathering_to_hypothesizing() -> None:
    assert can_transition(AgentSessionState.GATHERING, AgentSessionState.HYPOTHESIZING)


def test_invalid_completed_to_gathering() -> None:
    assert not can_transition(AgentSessionState.COMPLETED, AgentSessionState.GATHERING)


def test_assert_transition_raises() -> None:
    with pytest.raises(AgentRuntimeError):
        assert_transition(AgentSessionState.COMPLETED, AgentSessionState.GATHERING)


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (AgentSessionState.COMPLETED, True),
        (AgentSessionState.GATHERING, False),
    ],
)
def test_is_terminal(state: AgentSessionState, expected: bool) -> None:
    assert is_terminal(state) is expected
