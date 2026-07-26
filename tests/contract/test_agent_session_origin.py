"""Contract tests for the agent-session ``origin`` discriminator.

``origin`` separates operator copilot threads from the background triage sessions the
autonomy worker opens on its own, so the copilot can render only the former. It is
server-determined at creation and must never be accepted from a client, and sessions
persisted before the field existed have to keep parsing.
"""

from __future__ import annotations

import pytest
from aegis_contracts.agent_runtime import CreateAgentSessionRequestV1
from aegis_contracts.entities import (
    AgentRole,
    AgentSessionState,
    AgentSessionV1,
    AutonomyInitiatorV1,
)
from aegis_contracts.versioning import (
    AGENT_SESSION_SCHEMA_VERSION,
    CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
)
from pydantic import ValidationError

_NOW = "2026-07-26T00:00:00Z"
_RUN = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
_TRACE = "trc_01ARZ3NDEKTSV4RRFFQ69G5FAV"


def _session(**overrides: object) -> AgentSessionV1:
    payload: dict[str, object] = {
        "schemaVersion": AGENT_SESSION_SCHEMA_VERSION,
        "id": "agent-session:ags_origin_001",
        "runId": _RUN,
        "incidentId": None,
        "role": AgentRole.WATCHTOWER,
        "state": AgentSessionState.QUEUED,
        "traceId": _TRACE,
        "createdAt": _NOW,
        "updatedAt": _NOW,
    }
    payload.update(overrides)
    return AgentSessionV1(**payload)  # type: ignore[arg-type]


def test_origin_defaults_to_operator() -> None:
    assert _session().origin is AutonomyInitiatorV1.OPERATOR


def test_origin_accepts_autonomy() -> None:
    session = _session(origin=AutonomyInitiatorV1.AUTONOMY)
    assert session.origin is AutonomyInitiatorV1.AUTONOMY


def test_legacy_payload_without_origin_reads_back_as_operator() -> None:
    """Rows persisted before the field existed must stay parseable.

    The session's identity lives in a JSONB payload, so every stored session predating
    this field arrives without the key. Defaulting to operator is the safe direction:
    a misclassified session stays visible rather than silently disappearing.
    """
    legacy = {
        "schemaVersion": AGENT_SESSION_SCHEMA_VERSION,
        "id": "agent-session:ags_origin_legacy",
        "runId": _RUN,
        "incidentId": None,
        "role": "WATCHTOWER",
        "state": "queued",
        "traceId": _TRACE,
        "createdAt": _NOW,
        "updatedAt": _NOW,
    }
    assert AgentSessionV1.model_validate(legacy).origin is AutonomyInitiatorV1.OPERATOR


def test_origin_round_trips_through_the_serialized_payload() -> None:
    stored = _session(origin=AutonomyInitiatorV1.AUTONOMY).model_dump(
        by_alias=True, mode="json"
    )
    assert stored["origin"] == "autonomy"
    assert AgentSessionV1.model_validate(stored).origin is AutonomyInitiatorV1.AUTONOMY


def test_origin_rejects_an_unknown_value() -> None:
    with pytest.raises(ValidationError):
        _session(origin="worker")


def test_create_session_request_cannot_declare_an_origin() -> None:
    """Origin is decided by the call site, not the caller.

    The create-session request forbids extras, so a client cannot open a session that
    claims to be autonomy triage (hiding it from the operator) or claims an autonomy
    thread is operator-owned.
    """
    with pytest.raises(ValidationError):
        CreateAgentSessionRequestV1(
            schemaVersion=CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
            role=AgentRole.WATCHTOWER,
            traceId=_TRACE,
            origin="autonomy",  # type: ignore[call-arg]
        )
