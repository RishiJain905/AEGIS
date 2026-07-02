"""Feature pipeline domain errors."""

from __future__ import annotations

from dataclasses import dataclass

from aegis_contracts.features import FeatureErrorCode


@dataclass(frozen=True, slots=True)
class FeaturePipelineError(Exception):
    code: FeatureErrorCode
    message: str
    event_id: str | None = None
    sequence: int | None = None

    def __str__(self) -> str:
        return self.message
