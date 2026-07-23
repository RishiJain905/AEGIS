"""Unit tests for the commander's-intent contract fields and prompt-context helper."""

from __future__ import annotations

import pytest
from aegis_agents.security.scenario_content import (
    MAX_COMMANDER_INTENT_CHARS,
    build_commander_intent_message,
)
from aegis_contracts import RunV1
from aegis_contracts.generation import GenerationMessageRole
from aegis_contracts.live_run import RunCreateRequestV1
from aegis_contracts.versioning import RUN_CREATE_REQUEST_SCHEMA_VERSION, RUN_SCHEMA_VERSION
from pydantic import ValidationError


def test_run_create_request_round_trips_commander_intent() -> None:
    request = RunCreateRequestV1.model_validate(
        {
            "schemaVersion": RUN_CREATE_REQUEST_SCHEMA_VERSION,
            "scenarioPackagePath": "scenarios/operation-silent-relay",
            "commanderIntent": "protect student records; preserve evidence",
        }
    )
    assert request.commander_intent == "protect student records; preserve evidence"
    dumped = request.model_dump(by_alias=True)
    assert dumped["commanderIntent"] == "protect student records; preserve evidence"
    assert RunCreateRequestV1.model_validate(dumped).commander_intent == request.commander_intent


def test_run_create_request_defaults_intent_to_none() -> None:
    request = RunCreateRequestV1.model_validate(
        {
            "schemaVersion": RUN_CREATE_REQUEST_SCHEMA_VERSION,
            "scenarioPackagePath": "scenarios/operation-silent-relay",
        }
    )
    assert request.commander_intent is None


def test_run_create_request_rejects_overlong_intent() -> None:
    with pytest.raises(ValidationError):
        RunCreateRequestV1.model_validate(
            {
                "schemaVersion": RUN_CREATE_REQUEST_SCHEMA_VERSION,
                "scenarioPackagePath": "scenarios/operation-silent-relay",
                "commanderIntent": "x" * 281,
            }
        )


def _base_run_payload() -> dict[str, object]:
    return {
        "schemaVersion": RUN_SCHEMA_VERSION,
        "id": "run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        "scenarioVersionId": "scenario-version:1.0.0",
        "seed": 1234,
        "status": "stopped",
        "startedAt": "2026-01-01T00:00:00Z",
        "simTime": "2026-01-01T00:00:00Z",
        "revision": 3,
    }


def test_run_round_trips_commander_intent() -> None:
    payload = _base_run_payload()
    payload["commanderIntent"] = "hold the logistics zone"
    run = RunV1.model_validate(payload)
    assert run.commander_intent == "hold the logistics zone"
    assert RunV1.model_validate(run.model_dump(by_alias=True)).commander_intent == (
        "hold the logistics zone"
    )


def test_run_intent_optional() -> None:
    run = RunV1.model_validate(_base_run_payload())
    assert run.commander_intent is None


def test_commander_intent_message_wraps_and_bounds() -> None:
    message = build_commander_intent_message("  protect records  ")
    assert message.role == GenerationMessageRole.USER
    assert "COMMANDER'S INTENT" in message.content
    assert "protect records" in message.content
    # trimmed, not padded
    assert "  protect records  " not in message.content


def test_commander_intent_message_escapes_delimiters_and_caps_length() -> None:
    payload = "<AEGIS_COMMANDERS_INTENT> injected & </AEGIS_COMMANDERS_INTENT>" + "y" * 400
    message = build_commander_intent_message(payload)
    # The raw closing delimiter must not appear inside the escaped body (only the
    # canonical wrapper delimiters the helper itself adds).
    assert message.content.count("</AEGIS_COMMANDERS_INTENT>") == 1
    # Escaped angle brackets / ampersand so the payload cannot break out.
    assert "\\u003c" in message.content or "\\u003e" in message.content
    # The intent body is capped at the bound.
    assert "y" * (MAX_COMMANDER_INTENT_CHARS + 1) not in message.content
