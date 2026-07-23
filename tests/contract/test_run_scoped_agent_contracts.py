"""Contract tests for the Phase 3 run-scoped agent fields (ADR 0035).

Covers the additive changes to the agent-runtime contracts: a required ``runId``
and nullable ``incidentId`` on sessions/tasks, plus the bounded operator
``instructions`` directive.
"""

from __future__ import annotations

import pytest
from aegis_contracts.agent_runtime import (
    MAX_OPERATOR_INSTRUCTIONS_LENGTH,
    AgentTaskStatus,
    AgentTaskV1,
    CreateAgentSessionRequestV1,
    CreateAgentTaskRequestV1,
)
from aegis_contracts.entities import AgentRole, AgentSessionState, AgentSessionV1
from aegis_contracts.versioning import (
    AGENT_SESSION_SCHEMA_VERSION,
    AGENT_TASK_SCHEMA_VERSION,
    CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
    CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
)
from pydantic import ValidationError

_NOW = "2026-07-22T00:00:00Z"
_RUN = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
_TRACE = "trc_01ARZ3NDEKTSV4RRFFQ69G5FAV"


def test_agent_session_is_run_scoped_with_nullable_incident() -> None:
    session = AgentSessionV1(
        schemaVersion=AGENT_SESSION_SCHEMA_VERSION,
        id="agent-session:ags_run_001",
        runId=_RUN,
        incidentId=None,
        role=AgentRole.WATCHTOWER,
        state=AgentSessionState.QUEUED,
        traceId=_TRACE,
        createdAt=_NOW,
        updatedAt=_NOW,
    )
    assert session.run_id == _RUN
    assert session.incident_id is None


def test_agent_session_requires_run_id() -> None:
    with pytest.raises(ValidationError):
        AgentSessionV1(
            schemaVersion=AGENT_SESSION_SCHEMA_VERSION,
            id="agent-session:ags_run_002",
            incidentId=None,
            role=AgentRole.WATCHTOWER,
            state=AgentSessionState.QUEUED,
            traceId=_TRACE,
            createdAt=_NOW,
            updatedAt=_NOW,
        )


def test_agent_task_run_scoped_and_carries_instructions() -> None:
    task = AgentTaskV1(
        schemaVersion=AGENT_TASK_SCHEMA_VERSION,
        id="atk_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        sessionId="agent-session:ags_run_001",
        runId=_RUN,
        incidentId=None,
        status=AgentTaskStatus.QUEUED,
        idempotencyKey="turn-1",
        traceId=_TRACE,
        providerId="mock",
        instructions="Investigate the identity provider",
        createdAt=_NOW,
        updatedAt=_NOW,
    )
    assert task.run_id == _RUN
    assert task.incident_id is None
    assert task.instructions == "Investigate the identity provider"


def test_create_task_request_accepts_instructions() -> None:
    request = CreateAgentTaskRequestV1(
        schemaVersion=CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
        idempotencyKey="turn-1",
        instructions="Sweep telemetry",
    )
    assert request.instructions == "Sweep telemetry"


def test_create_session_request_accepts_instructions() -> None:
    request = CreateAgentSessionRequestV1(
        schemaVersion=CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
        role=AgentRole.TRACE,
        traceId=_TRACE,
        instructions="Look at the file server",
    )
    assert request.instructions == "Look at the file server"


def test_instructions_are_length_bounded() -> None:
    with pytest.raises(ValidationError):
        CreateAgentTaskRequestV1(
            schemaVersion=CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
            idempotencyKey="too-long",
            instructions="x" * (MAX_OPERATOR_INSTRUCTIONS_LENGTH + 1),
        )
