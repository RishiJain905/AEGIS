"""Contract tests for WebSocket protocol v1."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aegis_contracts import WebSocketFrameV1, parse_contract

FIXTURES = Path("tests/contract/fixtures/valid")


def test_websocket_frame_fixture_roundtrip() -> None:
    raw = json.loads((FIXTURES / "websocket_frame_v1.json").read_text())
    frame = parse_contract(WebSocketFrameV1, raw)
    assert frame.message_type.value == "subscribed"
    assert frame.payload["deliveryMode"] == "stream"


@pytest.mark.parametrize(
    "message_type,payload",
    [
        (
            "hello",
            {"protocolVersion": 1, "authToken": "aegis-dev-token"},
        ),
        (
            "subscribe",
            {
                "runId": "run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
                "channel": "events",
                "lastAppliedSequence": 0,
            },
        ),
        (
            "snapshot_required",
            {
                "runId": "run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
                "reason": "WS_QUEUE_OVERFLOW",
                "fromSequence": 10,
            },
        ),
    ],
)
def test_websocket_frame_payload_validation(message_type: str, payload: dict) -> None:
    frame = {
        "schemaVersion": 1,
        "protocolVersion": 1,
        "messageType": message_type,
        "traceId": "trc_01ARZ3NDEKTSV4RRFFQ69G5FAX",
        "sentAt": "2026-06-30T12:00:00.000Z",
        "payload": payload,
    }
    parsed = parse_contract(WebSocketFrameV1, frame)
    assert parsed.message_type.value == message_type
