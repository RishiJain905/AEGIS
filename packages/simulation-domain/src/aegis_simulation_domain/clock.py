"""Serializable virtual simulation clock."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aegis_contracts.primitives import SimTimestamp


class VirtualClock:
    def __init__(self, initial: SimTimestamp) -> None:
        self._sim_time = initial

    @property
    def sim_time(self) -> datetime:
        return self._sim_time

    def advance_to(self, target: SimTimestamp) -> None:
        if target < self._sim_time:
            msg = f"Cannot move virtual clock backwards: {target} < {self._sim_time}"
            raise ValueError(msg)
        self._sim_time = target

    def advance_by_seconds(self, seconds: int) -> None:
        self._sim_time = self._sim_time + timedelta(seconds=seconds)

    def to_snapshot(self) -> datetime:
        return self._sim_time.astimezone(UTC)

    @classmethod
    def from_snapshot(cls, sim_time: datetime) -> VirtualClock:
        return cls(sim_time.astimezone(UTC))
