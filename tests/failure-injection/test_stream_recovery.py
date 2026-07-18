"""Redis, relay-worker, and WebSocket recovery through real PostgreSQL/Redis."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from aegis_api.websocket.config import GatewayConfig
from aegis_api.websocket.errors import GatewayError
from aegis_api.websocket.recovery import SubscriptionRecoveryService
from aegis_contracts import WebSocketErrorCode
from aegis_event_streaming.relay import PostgresOutboxRelay
from aegis_event_streaming.stream_names import DOMAIN_EVENTS_STREAM
from aegis_persistence.orm.tables import OutboxRow
from aegis_persistence.repositories.postgres import PostgresGraphSnapshotRepository
from aegis_persistence.repositories.streaming import PostgresOutboxRepository
from aegis_simulation.graph_projection import build_graph_snapshot_from_runtime
from aegis_simulation.run_command_service import RunCommandService
from aegis_simulation_domain import SimulationEngine
from sqlalchemy import select, update
from tests.integration.streaming.helpers import make_test_event, sample_event_id, seed_run

pytestmark = [pytest.mark.failure_injection, pytest.mark.asyncio]


async def _wait_for_redis(redis_client) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            if await redis_client.ping():
                return
        except Exception:
            pass
        await asyncio.sleep(0.2)
    pytest.fail("Timed out waiting for Redis PING after restart")


async def test_redis_loss_preserves_authority_and_relay_recovers(
    unit_of_work,
    session_maker,
    redis_client,
    compose_controller,
    settings,
) -> None:
    run_id = "run_01ARZ3NDEKTSV4RRFFQ69G5FA1"
    await seed_run(unit_of_work, run_id=run_id)
    event = make_test_event(event_id=sample_event_id(1), run_id=run_id, sequence=1)
    await unit_of_work.append_event(event)
    await unit_of_work.commit()

    compose_controller.stop("redis")
    relay = PostgresOutboxRelay(session_maker, redis_client)
    assert await relay.publish_batch() == 0
    assert await unit_of_work.events.get_by_id(event.event_id) == event
    async with session_maker() as session:
        row = (await session.execute(select(OutboxRow))).scalar_one()
        assert row.published_at is None

    compose_controller.start("redis")
    await _wait_for_redis(redis_client)
    deadline = time.monotonic() + 10
    published = 0
    while time.monotonic() < deadline and published == 0:
        published = await relay.publish_until_empty()
        if published == 0:
            await asyncio.sleep(0.2)
    assert published == 1
    async with session_maker() as session:
        plan = await SubscriptionRecoveryService(
            GatewayConfig.from_settings(settings)
        ).plan_recovery(
            session,
            run_id=run_id,
            last_applied_sequence=0,
        )
    assert [item.sequence for item in plan.events] == [1]


async def test_worker_restart_mid_claim_has_no_lost_or_duplicate_event(
    unit_of_work,
    session_maker,
    redis_client,
    compose_controller,
) -> None:
    compose_controller.stop("worker")
    run_id = "run_01ARZ3NDEKTSV4RRFFQ69G5FA2"
    await seed_run(unit_of_work, run_id=run_id)
    event = make_test_event(event_id=sample_event_id(2), run_id=run_id, sequence=1)
    await unit_of_work.append_event(event)
    await unit_of_work.commit()
    async with session_maker() as session:
        claims = await PostgresOutboxRepository(session).claim_batch(
            claim_owner="worker-before-restart",
            batch_size=1,
            claim_ttl_seconds=3600,
        )
        await session.commit()
    assert len(claims) == 1

    compose_controller.start("worker")
    compose_controller.restart("worker")
    async with session_maker() as session:
        await session.execute(
            update(OutboxRow).values(claimed_at=datetime.now(UTC) - timedelta(hours=2))
        )
        await session.commit()
    relay = PostgresOutboxRelay(session_maker, redis_client)
    assert await relay.publish_until_empty() == 1
    assert await relay.publish_until_empty() == 0
    entries = await redis_client.xrange(DOMAIN_EVENTS_STREAM, "-", "+")
    ids = [fields["eventId"] for _, fields in entries]
    assert ids.count(event.event_id) == 1


async def test_websocket_gap_requires_snapshot_then_cursor_catchup(
    unit_of_work,
    session_maker,
    settings,
) -> None:
    run_id = "run_01ARZ3NDEKTSV4RRFFQ69G5FA3"
    await seed_run(unit_of_work, run_id=run_id)
    for sequence in (1, 2, 3):
        await unit_of_work.append_event(
            make_test_event(
                event_id=sample_event_id(sequence + 3),
                run_id=run_id,
                sequence=sequence,
            )
        )
    await unit_of_work.commit()
    gateway_config = GatewayConfig.from_settings(settings)
    recovery = SubscriptionRecoveryService(
        GatewayConfig(**{**gateway_config.__dict__, "snapshot_gap_threshold": 1})
    )
    async with session_maker() as session:
        catchup = await recovery.plan_recovery(session, run_id=run_id, last_applied_sequence=1)
    assert [event.sequence for event in catchup.events] == [2, 3]

    manifest = SimulationEngine.load_manifest(Path("scenarios/_fixtures/valid-minimal"))
    runtime = SimulationEngine.create_runtime(
        manifest=manifest,
        seed=42,
        scenario_version_id="scenario-version:streaming-test-v1",
        run_id=run_id,
    )
    runtime.start()
    snapshot = build_graph_snapshot_from_runtime(runtime, sequence=3)
    await PostgresGraphSnapshotRepository(unit_of_work.session).add(snapshot)
    await unit_of_work.commit()

    await unit_of_work.append_event(
        make_test_event(event_id=sample_event_id(8), run_id=run_id, sequence=9)
    )
    await unit_of_work.commit()
    with pytest.raises(GatewayError) as exc_info:
        async with session_maker() as session:
            await recovery.plan_recovery(session, run_id=run_id, last_applied_sequence=3)
    assert exc_info.value.code == WebSocketErrorCode.WS_SEQUENCE_GAP
    assert exc_info.value.details == {"runId": run_id, "fromSequence": 4, "gapSize": 5}
    bootstrap = await RunCommandService(workspace_root=Path.cwd()).get_bootstrap_payload(
        unit_of_work, run_id
    )
    assert bootstrap.graph_snapshot.sequence == 3
    assert bootstrap.last_applied_sequence == 9
