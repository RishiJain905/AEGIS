"""Window semantics tests."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_ml.features.schema_registry import DEFAULT_WINDOW_DURATION_SIM_SECONDS
from aegis_ml.features.windows import window_bounds, window_start_epoch


def test_window_uses_simulation_time_not_wall_clock() -> None:
    sim_time = datetime(2026, 6, 15, 10, 7, 30, tzinfo=UTC)
    start = window_start_epoch(sim_time, DEFAULT_WINDOW_DURATION_SIM_SECONDS)
    duration = DEFAULT_WINDOW_DURATION_SIM_SECONDS
    expected = int(sim_time.timestamp() // duration) * duration
    assert start == expected
    window_start, window_end = window_bounds(start, DEFAULT_WINDOW_DURATION_SIM_SECONDS)
    assert window_start <= sim_time < window_end
