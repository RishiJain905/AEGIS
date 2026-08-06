"""The shared event matcher: one search for the Evidence tab and the copilot.

The operator's Evidence tab and the agents' ``search_events`` tool must answer
the same queries the same way — a filter the Evidence tab supports but the
copilot cannot run is exactly how the copilot ended up reporting an empty
evidence catalogue beside a full Evidence tab. These tests pin the shared
matcher both surfaces delegate to.
"""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_contracts.event_query import (
    event_asset_id,
    event_evidence_summary,
    event_matches_filters,
)
from aegis_contracts.events import ActorRef, ActorType, DomainEventEnvelopeV1
from aegis_contracts.versioning import DOMAIN_EVENT_SCHEMA_VERSION

_RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
_TRACE_ID = "trc_01ARZ3NDEKTSV4RRFFQ69G5FAV"
_NOW = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)


def _event(
    *,
    event_id: str = "evt_01ARZ3NDEKTSV4RRFFQ69G5FAV",
    sequence: int = 1,
    event_type: str = "telemetry.authentication.failed",
    asset_id: str = "asset:svc-sso-broker",
    sim_time: datetime = _NOW,
    payload: dict[str, object] | None = None,
) -> DomainEventEnvelopeV1:
    return DomainEventEnvelopeV1(
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        event_id=event_id,
        run_id=_RUN_ID,
        sequence=sequence,
        type=event_type,
        sim_time=sim_time,
        recorded_at=_NOW,
        actor=ActorRef(type=ActorType.SYSTEM, id="asset:detection-engine"),
        subject=ActorRef(type=ActorType.ASSET, id=asset_id),
        payload=payload if payload is not None else {"assetId": asset_id},
        trace_id=_TRACE_ID,
    )


def test_asset_id_comes_from_the_payload_keys_first() -> None:
    event = _event(payload={"targetAssetId": "asset:db-primary"})
    assert event_asset_id(event) == "asset:db-primary"


def test_asset_id_falls_back_to_the_subject() -> None:
    event = _event(payload={})
    assert event_asset_id(event) == "asset:svc-sso-broker"


def test_asset_id_is_none_when_no_asset_is_named() -> None:
    event = _event(
        payload={},
        asset_id="asset:svc-sso-broker",
    ).model_copy(update={"subject": ActorRef(type=ActorType.SYSTEM, id="service:detection-engine")})
    assert event_asset_id(event) is None


def test_evidence_summary_names_type_time_and_asset() -> None:
    summary = event_evidence_summary(_event())
    assert summary == (
        "telemetry.authentication.failed @ 2026-01-01T00:00:00+00:00 [asset:svc-sso-broker]"
    )


def test_evidence_summary_omits_the_asset_when_none_is_named() -> None:
    event = _event(payload={}).model_copy(
        update={"subject": ActorRef(type=ActorType.SYSTEM, id="service:detection-engine")}
    )
    assert event_evidence_summary(event) == (
        "telemetry.authentication.failed @ 2026-01-01T00:00:00+00:00"
    )


def test_no_filters_matches_everything() -> None:
    assert event_matches_filters(_event()) is True


def test_asset_filter_matches_only_that_asset() -> None:
    event = _event()
    assert event_matches_filters(event, asset_id="asset:svc-sso-broker") is True
    assert event_matches_filters(event, asset_id="asset:db-primary") is False


def test_type_prefix_filter() -> None:
    event = _event()
    assert event_matches_filters(event, event_type_prefix="telemetry.authentication") is True
    assert event_matches_filters(event, event_type_prefix="detection") is False


def test_text_matches_type_and_payload_case_insensitively() -> None:
    event = _event(payload={"username": "r.jain", "sourceIp": "10.0.0.7"})
    assert event_matches_filters(event, text="r.jain") is True
    assert event_matches_filters(event, text="AUTHENTICATION") is True
    assert event_matches_filters(event, text="no-such-string") is False


def test_text_matches_the_event_id_so_cited_ids_are_searchable() -> None:
    """The trust loop: the copilot cites an evt_... id, the operator pastes it
    into Evidence and finds the event."""
    event = _event()
    assert event_matches_filters(event, text=event.event_id) is True


def test_sim_time_window_filters() -> None:
    event = _event(sim_time=datetime(2026, 1, 1, 0, 5, tzinfo=UTC))
    assert (
        event_matches_filters(
            event,
            from_sim_time=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
            to_sim_time=datetime(2026, 1, 1, 0, 10, tzinfo=UTC),
        )
        is True
    )
    assert (
        event_matches_filters(
            event,
            from_sim_time=datetime(2026, 1, 1, 0, 6, tzinfo=UTC),
        )
        is False
    )
    assert (
        event_matches_filters(
            event,
            to_sim_time=datetime(2026, 1, 1, 0, 4, tzinfo=UTC),
        )
        is False
    )


def test_filters_combine_with_and() -> None:
    event = _event()
    assert (
        event_matches_filters(
            event,
            asset_id="asset:svc-sso-broker",
            event_type_prefix="telemetry.authentication",
            text="failed",
        )
        is True
    )
    assert (
        event_matches_filters(
            event,
            asset_id="asset:svc-sso-broker",
            event_type_prefix="detection",
        )
        is False
    )
