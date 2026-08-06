"""The agents' search_events tool must answer the Evidence tab's queries.

The QA P1: the copilot reported an empty evidence catalogue while the Evidence
tab showed the run's events. Half the fix is the catalogue being the event
pool; the other half is the tool being able to FIND events the way the
operator's search does — by asset, type, text, and time window. These tests
pin the handler's filters against the shared matcher.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from aegis_agents.tools import investigation as investigation_tools
from aegis_agents.tools.investigation.handlers import handle_search_events
from aegis_contracts.events import ActorRef, ActorType, DomainEventEnvelopeV1
from aegis_contracts.versioning import DOMAIN_EVENT_SCHEMA_VERSION

_RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
_TRACE_ID = "trc_01ARZ3NDEKTSV4RRFFQ69G5FAV"
_NOW = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)


def _event(
    *,
    index: int,
    event_type: str = "telemetry.authentication.failed",
    asset_id: str = "asset:svc-sso-broker",
    sim_time: datetime = _NOW,
    payload: dict[str, object] | None = None,
) -> DomainEventEnvelopeV1:
    return DomainEventEnvelopeV1(
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        event_id=f"evt_{index:026d}",
        run_id=_RUN_ID,
        sequence=index,
        type=event_type,
        sim_time=sim_time,
        recorded_at=_NOW,
        actor=ActorRef(type=ActorType.SYSTEM, id="asset:detection-engine"),
        subject=ActorRef(type=ActorType.ASSET, id=asset_id),
        payload=payload if payload is not None else {"assetId": asset_id},
        trace_id=_TRACE_ID,
    )


class _FakeQueryRepo:
    """Stands in for PostgresEventQueryRepository inside the handler module."""

    def __init__(self, session: Any) -> None:
        self._session = session

    async def list_by_run(
        self,
        run_id: str,
        *,
        from_sequence: int | None = None,
        to_sequence: int | None = None,
        limit: int = 2000,
    ) -> list[DomainEventEnvelopeV1]:
        events = [
            event
            for event in _EVENTS
            if (from_sequence is None or event.sequence >= from_sequence)
            and (to_sequence is None or event.sequence <= to_sequence)
        ]
        return events[:limit]


_EVENTS = [
    _event(
        index=1,
        event_type="telemetry.authentication.succeeded",
        asset_id="asset:svc-sso-broker",
    ),
    _event(
        index=2,
        event_type="telemetry.authentication.failed",
        asset_id="asset:svc-sso-broker",
        sim_time=datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
        payload={"assetId": "asset:svc-sso-broker", "username": "r.jain"},
    ),
    _event(index=3, event_type="alert.created", asset_id="asset:svc-sso-broker"),
    _event(index=4, event_type="telemetry.authentication.failed", asset_id="asset:db-primary"),
]


class _FakeCtx:
    run_id = _RUN_ID
    trace_id = _TRACE_ID

    class _Uow:
        class _Session:
            pass

        session = _Session()

    uow = _Uow()


@pytest.fixture(autouse=True)
def _patch_query_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        investigation_tools.handlers,
        "PostgresEventQueryRepository",
        _FakeQueryRepo,
    )


async def _search(payload: dict[str, Any]) -> dict[str, Any]:
    return await handle_search_events(_FakeCtx(), payload)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_search_events_returns_everything_without_filters() -> None:
    result = await _search({"limit": 200})
    assert result["count"] == 4
    assert [item["eventId"] for item in result["events"]] == [
        event.event_id for event in _EVENTS
    ]


@pytest.mark.asyncio
async def test_search_events_filters_by_asset() -> None:
    result = await _search({"assetId": "asset:svc-sso-broker"})
    assert result["count"] == 3
    assert all(item["eventId"] != _EVENTS[3].event_id for item in result["events"])


@pytest.mark.asyncio
async def test_search_events_filters_by_type_prefix() -> None:
    result = await _search({"eventTypePrefix": "telemetry.authentication"})
    assert result["count"] == 3
    assert {item["type"] for item in result["events"]} == {
        "telemetry.authentication.succeeded",
        "telemetry.authentication.failed",
    }


@pytest.mark.asyncio
async def test_search_events_filters_by_text_in_payload() -> None:
    result = await _search({"text": "r.jain"})
    assert result["count"] == 1
    assert result["events"][0]["eventId"] == _EVENTS[1].event_id


@pytest.mark.asyncio
async def test_search_events_filters_by_sim_time_window() -> None:
    result = await _search(
        {
            "fromSimTime": "2026-01-01T00:04:00Z",
            "toSimTime": "2026-01-01T00:06:00Z",
        }
    )
    assert result["count"] == 1
    assert result["events"][0]["eventId"] == _EVENTS[1].event_id


@pytest.mark.asyncio
async def test_search_events_matches_a_cited_event_id() -> None:
    """The trust loop: the model cites an id from the catalogue, then searches
    for it the way the operator would in the Evidence tab."""
    result = await _search({"text": _EVENTS[2].event_id})
    assert result["count"] == 1
    assert result["events"][0]["eventId"] == _EVENTS[2].event_id


@pytest.mark.asyncio
async def test_search_events_respects_the_sequence_window() -> None:
    result = await _search({"fromSequence": 2, "toSequence": 3})
    assert result["count"] == 2
    assert [item["sequence"] for item in result["events"]] == [2, 3]


@pytest.mark.asyncio
async def test_search_events_bounds_the_result_limit() -> None:
    result = await _search({"limit": 2})
    assert result["count"] == 2
    assert len(result["events"]) == 2
