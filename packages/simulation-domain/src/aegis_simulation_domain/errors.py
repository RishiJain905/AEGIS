"""Simulation domain error types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class SimulationErrorCode(StrEnum):
    VALIDATION_FAILED = "SIMULATION_VALIDATION_FAILED"
    UNAUTHORIZED = "SIMULATION_UNAUTHORIZED"
    INVALID_STATE = "SIMULATION_INVALID_STATE"
    CHECKPOINT_INCOMPATIBLE = "SIMULATION_CHECKPOINT_INCOMPATIBLE"
    CHECKPOINT_CHECKSUM_INVALID = "SIMULATION_CHECKPOINT_CHECKSUM_INVALID"
    DUPLICATE_COMMAND = "SIMULATION_DUPLICATE_COMMAND"
    STALE_REVISION = "SIMULATION_STALE_REVISION"
    PLATFORM_INCOMPATIBLE = "SIMULATION_PLATFORM_INCOMPATIBLE"


@dataclass(slots=True)
class SimulationError(Exception):
    code: SimulationErrorCode
    message: str
    details: dict[str, Any] | None = None
    trace_id: str | None = None

    def __str__(self) -> str:
        return self.message
