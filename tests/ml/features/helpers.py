"""Shared helpers for feature pipeline tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aegis_contracts import ActorRef, ActorType, DomainEventEnvelopeV1, EventTypeRegistry
from aegis_contracts.versioning import DOMAIN_EVENT_SCHEMA_VERSION

RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
ENTITY_ID = "asset:svc-api-gateway"
BASE_SIM_TIME = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

_EVENT_IDS = (
    "evt_01ARZ3NDEKTSV4RRFFQ69G5FB0",
    "evt_01ARZ3NDEKTSV4RRFFQ69G5FB1",
    "evt_01ARZ3NDEKTSV4RRFFQ69G5FB2",
    "evt_01ARZ3NDEKTSV4RRFFQ69G5FB3",
    "evt_01ARZ3NDEKTSV4RRFFQ69G5FB4",
    "evt_01ARZ3NDEKTSV4RRFFQ69G5FB5",
    "evt_01ARZ3NDEKTSV4RRFFQ69G5FB6",
    "evt_01ARZ3NDEKTSV4RRFFQ69G5FB7",
    "evt_01ARZ3NDEKTSV4RRFFQ69G5FB8",
    "evt_01ARZ3NDEKTSV4RRFFQ69G5FB9",
)


def unique_event_id(index: int) -> str:
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    chars = [alphabet[(index >> (5 * position)) & 31] for position in range(26)]
    return f"evt_{''.join(chars)}"


def make_telemetry_event(
    *,
    sequence: int,
    event_type: str,
    payload: dict[str, object],
    sim_offset_seconds: int = 0,
    event_id_override: str | None = None,
) -> DomainEventEnvelopeV1:
    sim_time = BASE_SIM_TIME + timedelta(seconds=sim_offset_seconds)
    recorded_at = BASE_SIM_TIME + timedelta(milliseconds=sequence)
    merged_payload = {"schemaVersion": 1, "assetId": ENTITY_ID, **payload}
    return DomainEventEnvelopeV1(
        event_id=unique_event_id(sequence) if event_id_override is None else event_id_override,
        run_id=RUN_ID,
        sequence=sequence,
        type=event_type,
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=sim_time,
        recorded_at=recorded_at,
        actor=ActorRef(type=ActorType.SYSTEM, id="asset:simulation-engine"),
        subject=ActorRef(type=ActorType.ASSET, id=ENTITY_ID),
        payload=merged_payload,
        trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAX",
    )


def sample_auth_failed(sequence: int = 1, sim_offset_seconds: int = 10) -> DomainEventEnvelopeV1:
    return make_telemetry_event(
        sequence=sequence,
        event_type="telemetry.authentication.failed",
        payload={"outcome": "failed"},
        sim_offset_seconds=sim_offset_seconds,
    )


def sample_auth_succeeded(sequence: int = 2, sim_offset_seconds: int = 20) -> DomainEventEnvelopeV1:
    return make_telemetry_event(
        sequence=sequence,
        event_type="telemetry.authentication.succeeded",
        payload={"outcome": "succeeded"},
        sim_offset_seconds=sim_offset_seconds,
    )


def sample_hidden_condition(sequence: int = 99) -> DomainEventEnvelopeV1:
    return DomainEventEnvelopeV1(
        event_id=unique_event_id(sequence),
        run_id=RUN_ID,
        sequence=sequence,
        type="sim.hidden_condition.triggered",
        schema_version=DOMAIN_EVENT_SCHEMA_VERSION,
        sim_time=BASE_SIM_TIME,
        recorded_at=BASE_SIM_TIME,
        actor=ActorRef(type=ActorType.SYSTEM, id="asset:simulation-engine"),
        subject=ActorRef(type=ActorType.SYSTEM, id="asset:simulation-engine"),
        payload={
            "schemaVersion": EventTypeRegistry.payload_schema_version(
                "sim.hidden_condition.triggered"
            ),
            "conditionId": "hidden-cause-compromised-credentials",
        },
        trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAX",
    )
