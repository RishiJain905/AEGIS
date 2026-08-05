"""Phase 7 operator console search + ops-feed integration tests.

Both are thin projections over the events table: assert feed categorisation, exclusion of
low-level sim/telemetry noise, cursor pagination, and console filtering by type/asset/text.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest
from aegis_agents.runtime.events import build_task_completed_event
from aegis_agents.runtime.ids import new_runtime_id
from aegis_api.console.service import ConsoleService
from aegis_api.operator_actions.events import (
    build_operator_action_proposed_event,
    build_run_roe_changed_event,
)
from aegis_contracts import ActorRef, ActorType, DomainEventEnvelopeV1
from aegis_contracts.operator import ConsoleEventSearchRequestV1
from aegis_contracts.versioning import (
    CONSOLE_EVENT_SEARCH_REQUEST_SCHEMA_VERSION,
    DOMAIN_EVENT_SCHEMA_VERSION,
)
from aegis_persistence.engine import create_engine, get_session_maker
from aegis_persistence.sim_clock import run_sim_time
from aegis_persistence.unit_of_work import PostgresUnitOfWork

from tests.integration.agents.helpers import seed_investigation_run

pytestmark = pytest.mark.skipif(
    os.getenv("AEGIS_INTEGRATION_POSTGRES") != "1",
    reason="Requires PostgreSQL integration environment",
)


def _session_maker():
    from aegis_contracts import load_settings

    settings = load_settings()
    return get_session_maker(settings, engine=create_engine(settings))


async def _append(uow, event) -> None:
    await uow.append_event(event)


def _telemetry_event(run_id: str, sequence: int) -> DomainEventEnvelopeV1:
    now = datetime.now(UTC)
    return DomainEventEnvelopeV1(
        event_id=new_runtime_id("evt"),
        run_id=run_id,
        sequence=sequence,
        type="telemetry.api.request",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=now,
        recorded_at=now,
        actor=ActorRef(type=ActorType.ASSET, id="asset:device-workstation-01"),
        subject=ActorRef(type=ActorType.ASSET, id="asset:device-workstation-01"),
        payload={"schemaVersion": 1, "assetId": "asset:device-workstation-01"},
        trace_id=new_runtime_id("trc"),
    )


async def _seed_feed_events(uow, run_id: str) -> None:
    seq = await uow.events.next_sequence(run_id)
    await _append(
        uow,
        build_operator_action_proposed_event(
            event_id=new_runtime_id("evt"),
            run_id=run_id,
            sequence=seq,
            actor_id="user:op",
            trace_id=new_runtime_id("trc"),
            proposal_id=new_runtime_id("prp"),
            incident_id="incident:inc_op_feed",
            scenario_command="isolate",
            action_class="class_2",
            target_asset_id="asset:device-workstation-01",
            justification="Workstation is beaconing; cutting it off.",
            sim_time=await run_sim_time(uow, run_id),
        ),
    )
    seq = await uow.events.next_sequence(run_id)
    await _append(
        uow,
        build_run_roe_changed_event(
            event_id=new_runtime_id("evt"),
            run_id=run_id,
            sequence=seq,
            actor_id="user:op",
            trace_id=new_runtime_id("trc"),
            previous_roe="investigate",
            new_roe="forward_deployed",
            sim_time=await run_sim_time(uow, run_id),
        ),
    )
    seq = await uow.events.next_sequence(run_id)
    await _append(
        uow,
        build_task_completed_event(
            event_id=new_runtime_id("evt"),
            run_id=run_id,
            sequence=seq,
            session_id="agent-session:feed-test",
            task_id=new_runtime_id("atk"),
            trace_id=new_runtime_id("trc"),
            status="completed",
            sim_time=datetime.now(UTC),
        ),
    )
    # A low-level telemetry event that must NOT surface in the feed.
    seq = await uow.events.next_sequence(run_id)
    await _append(uow, _telemetry_event(run_id, seq))


@pytest.mark.asyncio
async def test_feed_excludes_telemetry_and_categorises() -> None:
    service = ConsoleService()
    async with PostgresUnitOfWork(_session_maker()) as uow:
        _incident, run_id, _alerts, _ev = await seed_investigation_run(uow)
        await _seed_feed_events(uow, run_id)
        page = await service.feed(uow, run_id=run_id, cursor=None, limit=100)
    categories = {entry.category for entry in page.entries}
    types = {entry.type for entry in page.entries}
    assert "telemetry.api.request" not in types
    assert {"operator_action", "roe", "agent"}.issubset(categories)
    roe_entry = next(e for e in page.entries if e.type == "run.roe_changed")
    assert roe_entry.payload["newRoe"] == "forward_deployed"


@pytest.mark.asyncio
async def test_feed_cursor_pagination() -> None:
    service = ConsoleService()
    async with PostgresUnitOfWork(_session_maker()) as uow:
        _incident, run_id, _alerts, _ev = await seed_investigation_run(uow)
        await _seed_feed_events(uow, run_id)
        first = await service.feed(uow, run_id=run_id, cursor=None, limit=2)
        assert len(first.entries) == 2
        assert first.next_cursor is not None
        second = await service.feed(uow, run_id=run_id, cursor=first.next_cursor, limit=2)
    # No overlap across pages.
    first_seqs = {e.sequence for e in first.entries}
    second_seqs = {e.sequence for e in second.entries}
    assert first_seqs.isdisjoint(second_seqs)


@pytest.mark.asyncio
async def test_console_search_filters_by_type_and_asset() -> None:
    service = ConsoleService()
    async with PostgresUnitOfWork(_session_maker()) as uow:
        _incident, run_id, _alerts, _ev = await seed_investigation_run(uow)
        await _seed_feed_events(uow, run_id)
        by_type = await service.search_events(
            uow,
            run_id=run_id,
            request=ConsoleEventSearchRequestV1(
                schema_version=CONSOLE_EVENT_SEARCH_REQUEST_SCHEMA_VERSION,
                event_type_prefix="operator.",
                limit=100,
            ),
        )
        assert by_type.count >= 1
        assert all(e.type.startswith("operator.") for e in by_type.events)

        by_asset = await service.search_events(
            uow,
            run_id=run_id,
            request=ConsoleEventSearchRequestV1(
                schema_version=CONSOLE_EVENT_SEARCH_REQUEST_SCHEMA_VERSION,
                asset_id="asset:device-workstation-01",
                limit=100,
            ),
        )
        assert by_asset.count >= 1
        assert all(e.asset_id == "asset:device-workstation-01" for e in by_asset.events)
