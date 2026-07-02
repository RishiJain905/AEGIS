"""Graceful fallback when model inference is unavailable."""

from __future__ import annotations

from dataclasses import dataclass

from aegis_ml.models.errors import ModelErrorCode


@dataclass(frozen=True)
class FallbackState:
    active: bool
    reason: str | None = None
    error_code: ModelErrorCode | None = None


def fallback_from_exception(exc: Exception) -> FallbackState:
    from aegis_ml.models.artifact_store import ModelArtifactError

    if isinstance(exc, ModelArtifactError):
        return FallbackState(active=True, reason=exc.message, error_code=exc.code)
    return FallbackState(active=True, reason=str(exc), error_code=ModelErrorCode.INFERENCE_FAILED)
