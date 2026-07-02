"""Graph risk domain errors."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class GraphRiskErrorCode(StrEnum):
    VALIDATION_FAILED = "validation_failed"
    MISSING_ENTITY = "missing_entity"
    INCOMPATIBLE_ALGORITHM = "incompatible_algorithm"
    INVALID_WEIGHT = "invalid_weight"
    MALFORMED_PATH = "malformed_path"
    STALE_STATE = "stale_state"


@dataclass(slots=True)
class GraphRiskError(Exception):
    code: GraphRiskErrorCode
    message: str
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return self.message
