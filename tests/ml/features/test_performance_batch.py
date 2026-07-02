"""Performance and memory bounds for large batches."""

from __future__ import annotations

import time

from aegis_ml.features.engine import compute_features_from_events

from tests.ml.features.helpers import RUN_ID, make_telemetry_event, unique_event_id


def test_large_batch_stays_within_bounds() -> None:
    events = [
        make_telemetry_event(
            sequence=index + 1,
            event_type="telemetry.api.request",
            payload={"statusCode": 500 if index % 17 == 0 else 200},
            sim_offset_seconds=index % 300,
            event_id_override=unique_event_id(index),
        )
        for index in range(5000)
    ]
    started = time.perf_counter()
    result = compute_features_from_events(run_id=RUN_ID, events=events)
    elapsed = time.perf_counter() - started
    assert result.vectors
    assert elapsed < 30.0
