"""Simulation-time tumbling window helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aegis_contracts.primitives import SimTimestamp


def sim_time_to_epoch_seconds(sim_time: SimTimestamp) -> float:
    return sim_time.timestamp()


def epoch_seconds_to_sim_time(epoch_seconds: float) -> datetime:
    whole_seconds = int(epoch_seconds)
    fractional = epoch_seconds - whole_seconds
    base = datetime.fromtimestamp(whole_seconds, tz=UTC) + timedelta(seconds=fractional)
    return base


def window_start_epoch(sim_time: SimTimestamp, window_duration_seconds: int) -> int:
    epoch = sim_time_to_epoch_seconds(sim_time)
    return int(epoch // window_duration_seconds) * window_duration_seconds


def window_bounds(
    window_start_epoch_value: int,
    window_duration_seconds: int,
) -> tuple[datetime, datetime]:
    start = epoch_seconds_to_sim_time(float(window_start_epoch_value))
    end = epoch_seconds_to_sim_time(float(window_start_epoch_value + window_duration_seconds))
    return start, end


def build_window_key(run_id: str, entity_id: str, window_start_epoch_value: int) -> str:
    return f"{run_id}:{entity_id}:{window_start_epoch_value}"
