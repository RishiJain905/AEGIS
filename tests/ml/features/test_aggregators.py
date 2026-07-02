"""Aggregator tests."""

from __future__ import annotations

from aegis_ml.features.aggregators import WindowAccumulator, accumulator_to_values
from aegis_ml.features.schema_registry import MISSING_SENTINEL

from tests.ml.features.helpers import (
    make_telemetry_event,
    sample_auth_failed,
    sample_auth_succeeded,
)


def test_auth_aggregator_counts_and_rate() -> None:
    accumulator = WindowAccumulator(
        entity_id="asset:svc-api-gateway",
        window_start_epoch=0,
        window_start=sample_auth_failed().sim_time,
        window_end=sample_auth_failed().sim_time,
    )
    accumulator.ingest(sample_auth_failed())
    accumulator.ingest(sample_auth_succeeded())
    values = accumulator_to_values(accumulator)
    assert values[0] == 2.0
    assert values[1] == 1.0
    assert values[2] == 0.5


def test_network_protocol_one_hot_is_deterministic() -> None:
    accumulator = WindowAccumulator(
        entity_id="asset:svc-api-gateway",
        window_start_epoch=0,
        window_start=sample_auth_failed().sim_time,
        window_end=sample_auth_failed().sim_time,
    )
    accumulator.ingest(
        make_telemetry_event(
            sequence=3,
            event_type="telemetry.network.connection",
            payload={"protocol": "udp", "bytes": 2048},
            sim_offset_seconds=5,
        )
    )
    accumulator.ingest(
        make_telemetry_event(
            sequence=4,
            event_type="telemetry.network.connection",
            payload={"protocol": "tcp", "bytes": 1024},
            sim_offset_seconds=6,
        )
    )
    values = accumulator_to_values(accumulator)
    assert values[9] == 2.0
    assert values[10] == 3072.0
    assert values[11] == 1536.0
    assert values[12] == 0.0
    assert values[13] == 1.0
    assert values[14] == 0.0


def test_zero_denominator_rate_uses_missing_sentinel() -> None:
    accumulator = WindowAccumulator(
        entity_id="asset:svc-api-gateway",
        window_start_epoch=0,
        window_start=sample_auth_failed().sim_time,
        window_end=sample_auth_failed().sim_time,
    )
    values = accumulator_to_values(accumulator)
    assert values[2] == MISSING_SENTINEL
