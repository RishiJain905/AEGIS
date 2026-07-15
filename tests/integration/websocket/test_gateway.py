"""Integration tests for WebSocket gateway."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from aegis_api.main import create_app
from aegis_contracts import AegisSettings, load_settings
from aegis_contracts.versioning import PROTOCOL_VERSION_V1
from aegis_event_streaming.envelope import build_realtime_envelope, envelope_to_redis_fields
from aegis_event_streaming.relay import PostgresOutboxRelay
from aegis_event_streaming.stream_names import DOMAIN_EVENTS_STREAM
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from fastapi.testclient import TestClient
from tests.integration.auth_helpers import issue_ws_ticket, login_as
from tests.integration.streaming.helpers import make_test_event, sample_event_id, seed_run


def _trace_id() -> str:
    return "trc_01ARZ3NDEKTSV4RRFFQ69G5FAX"


def _frame(message_type: str, payload: dict) -> str:
    return json.dumps(
        {
            "schemaVersion": 1,
            "protocolVersion": PROTOCOL_VERSION_V1,
            "messageType": message_type,
            "traceId": _trace_id(),
            "sentAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "payload": payload,
        }
    )


def _hello(token: str) -> str:
    return _frame("hello", {"protocolVersion": PROTOCOL_VERSION_V1, "authToken": token})


def _subscribe(run_id: str, *, last_applied_sequence: int = 0) -> str:
    return _frame(
        "subscribe",
        {"runId": run_id, "channel": "events", "lastAppliedSequence": last_applied_sequence},
    )


@pytest.fixture
def ws_settings() -> AegisSettings:
    settings = load_settings()
    return settings.model_copy(
        update={
            "AEGIS_WS_MAX_QUEUE_DEPTH": 8,
            "AEGIS_WS_HEARTBEAT_INTERVAL_SECONDS": 60,
            "AEGIS_WS_IDLE_TIMEOUT_SECONDS": 120,
        }
    )


@pytest.fixture
def api_client(ws_settings: AegisSettings, redis_available: None) -> TestClient:
    app = create_app(ws_settings)
    with TestClient(app) as client:
        # Lifespan seeds development identities when AEGIS_DEV_AUTH_ENABLED.
        yield client


@pytest.fixture
def ws_auth_token(api_client: TestClient) -> str:
    csrf = login_as(api_client)
    return issue_ws_ticket(api_client, csrf=csrf)


@pytest.mark.asyncio
async def test_connect_and_subscribe_delivers_events(
    unit_of_work: PostgresUnitOfWork,
    session_maker,
    redis_client,
    api_client: TestClient,
    ws_auth_token: str,
) -> None:
    run_id = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
    await seed_run(unit_of_work, run_id=run_id)
    for seq in range(1, 4):
        await unit_of_work.append_event(
            make_test_event(
                event_id=sample_event_id(seq),
                run_id=run_id,
                sequence=seq,
            )
        )
    await unit_of_work.commit()

    relay = PostgresOutboxRelay(session_maker, redis_client)
    assert await relay.publish_until_empty() == 3

    with api_client.websocket_connect("/ws/v1/realtime") as ws:
        ws.send_text(_hello(ws_auth_token))
        ack = json.loads(ws.receive_text())
        assert ack["messageType"] == "hello_ack"

        ws.send_text(_subscribe(run_id))
        subscribed = json.loads(ws.receive_text())
        assert subscribed["messageType"] == "subscribed"

        sequences: list[int] = []
        for _ in range(5):
            msg = json.loads(ws.receive_text())
            if msg["messageType"] == "event":
                sequences.append(msg["payload"]["envelope"]["event"]["sequence"])
            elif msg["messageType"] == "resync_complete":
                break

        assert sequences == [1, 2, 3]


@pytest.mark.asyncio
async def test_unauthorized_subscription_rejected(api_client: TestClient) -> None:
    with api_client.websocket_connect("/ws/v1/realtime") as ws:
        ws.send_text(_hello("not-a-valid-token"))
        msg = json.loads(ws.receive_text())
        assert msg["messageType"] == "error"
        assert msg["payload"]["error"]["code"] == "WS_UNAUTHORIZED"


@pytest.mark.asyncio
async def test_unknown_run_rejected(
    unit_of_work: PostgresUnitOfWork,
    api_client: TestClient,
    ws_auth_token: str,
) -> None:
    _ = unit_of_work
    with api_client.websocket_connect("/ws/v1/realtime") as ws:
        ws.send_text(_hello(ws_auth_token))
        ws.receive_text()
        ws.send_text(_subscribe("run_01ARZ3NDEKTSV4RRFFQ69G5FAX"))
        msg = json.loads(ws.receive_text())
        assert msg["messageType"] == "error"
        assert msg["payload"]["error"]["code"] == "WS_UNKNOWN_RUN"


@pytest.mark.asyncio
async def test_reconnect_with_cursor(
    unit_of_work: PostgresUnitOfWork,
    session_maker,
    redis_client,
    api_client: TestClient,
    ws_auth_token: str,
) -> None:
    run_id = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
    await seed_run(unit_of_work, run_id=run_id)
    for seq in range(1, 6):
        await unit_of_work.append_event(
            make_test_event(
                event_id=sample_event_id(seq),
                run_id=run_id,
                sequence=seq,
            )
        )
    await unit_of_work.commit()
    relay = PostgresOutboxRelay(session_maker, redis_client)
    await relay.publish_until_empty()

    with api_client.websocket_connect("/ws/v1/realtime") as ws:
        ws.send_text(_hello(ws_auth_token))
        ws.receive_text()
        ws.send_text(_subscribe(run_id))
        ws.receive_text()
        seen = 0
        while seen < 2:
            msg = json.loads(ws.receive_text())
            if msg["messageType"] == "event":
                seen += 1

    with api_client.websocket_connect("/ws/v1/realtime") as ws:
        ws.send_text(_hello(ws_auth_token))
        ws.receive_text()
        ws.send_text(_subscribe(run_id, last_applied_sequence=2))
        msg = json.loads(ws.receive_text())
        assert msg["messageType"] == "subscribed"
        assert msg["payload"]["deliveryMode"] in {"backfill", "stream"}
        sequences = []
        for _ in range(6):
            incoming = json.loads(ws.receive_text())
            if incoming["messageType"] == "event":
                sequences.append(incoming["payload"]["envelope"]["event"]["sequence"])
            if incoming["messageType"] == "resync_complete":
                break
        assert sequences == [3, 4, 5]


@pytest.mark.asyncio
async def test_duplicate_events_suppressed(
    unit_of_work: PostgresUnitOfWork,
    session_maker,
    redis_client,
    api_client: TestClient,
    ws_auth_token: str,
) -> None:
    run_id = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
    await seed_run(unit_of_work, run_id=run_id)
    event = make_test_event(
        event_id=sample_event_id(0),
        run_id=run_id,
        sequence=1,
    )
    await unit_of_work.append_event(event)
    await unit_of_work.commit()
    relay = PostgresOutboxRelay(session_maker, redis_client)
    await relay.publish_until_empty()

    envelope = build_realtime_envelope(event)
    fields = envelope_to_redis_fields(envelope)
    await redis_client.xadd(DOMAIN_EVENTS_STREAM, fields)
    await redis_client.xadd(DOMAIN_EVENTS_STREAM, fields)

    with api_client.websocket_connect("/ws/v1/realtime") as ws:
        ws.send_text(_hello(ws_auth_token))
        ws.receive_text()
        ws.send_text(_subscribe(run_id))
        ws.receive_text()
        event_count = 0
        warning_seen = False
        for _ in range(8):
            try:
                msg = json.loads(ws.receive_text())
            except Exception:
                break
            if msg["messageType"] == "event":
                event_count += 1
            if msg["messageType"] == "warning":
                warning_seen = True
            if msg["messageType"] == "resync_complete":
                break
        assert event_count >= 1
        assert warning_seen or event_count == 1


@pytest.mark.asyncio
async def test_invalid_message_rejected(api_client: TestClient) -> None:
    with api_client.websocket_connect("/ws/v1/realtime") as ws:
        ws.send_text("{not-json")
        msg = json.loads(ws.receive_text())
        assert msg["messageType"] == "error"
        assert msg["payload"]["error"]["code"] == "WS_INVALID_MESSAGE"


@pytest.mark.asyncio
async def test_pg_backfill_on_subscribe(
    unit_of_work: PostgresUnitOfWork,
    session_maker,
    redis_client,
    api_client: TestClient,
    ws_auth_token: str,
) -> None:
    run_id = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
    await seed_run(unit_of_work, run_id=run_id)
    for seq in range(1, 4):
        await unit_of_work.append_event(
            make_test_event(
                event_id=sample_event_id(seq),
                run_id=run_id,
                sequence=seq,
            )
        )
    await unit_of_work.commit()

    with api_client.websocket_connect("/ws/v1/realtime") as ws:
        ws.send_text(_hello(ws_auth_token))
        ws.receive_text()
        ws.send_text(_subscribe(run_id, last_applied_sequence=1))
        subscribed = json.loads(ws.receive_text())
        assert subscribed["payload"]["deliveryMode"] == "backfill"
        sequences = []
        for _ in range(5):
            msg = json.loads(ws.receive_text())
            if msg["messageType"] == "event":
                sequences.append(msg["payload"]["envelope"]["event"]["sequence"])
            if msg["messageType"] == "resync_complete":
                break
        assert sequences == [2, 3]


@pytest.mark.asyncio
async def test_slow_client_queue_overflow_triggers_snapshot_required(
    unit_of_work: PostgresUnitOfWork,
    session_maker,
    redis_client,
    ws_settings: AegisSettings,
) -> None:
    tight_settings = ws_settings.model_copy(update={"AEGIS_WS_MAX_QUEUE_DEPTH": 1})
    app = create_app(tight_settings)
    run_id = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
    await seed_run(unit_of_work, run_id=run_id)
    for seq in range(1, 6):
        await unit_of_work.append_event(
            make_test_event(
                event_id=sample_event_id(seq),
                run_id=run_id,
                sequence=seq,
            )
        )
    await unit_of_work.commit()
    relay = PostgresOutboxRelay(session_maker, redis_client)
    await relay.publish_until_empty()

    with TestClient(app) as client:
        csrf = login_as(client)
        token = issue_ws_ticket(client, csrf=csrf)
        with client.websocket_connect("/ws/v1/realtime") as ws:
            ws.send_text(_hello(token))
            ws.receive_text()
            ws.send_text(_subscribe(run_id))
            ws.receive_text()
            saw_snapshot = False
            for _ in range(12):
                msg = json.loads(ws.receive_text())
                if msg["messageType"] == "snapshot_required":
                    saw_snapshot = True
                    assert msg["payload"]["reason"] == "WS_QUEUE_OVERFLOW"
                    break
            assert saw_snapshot
