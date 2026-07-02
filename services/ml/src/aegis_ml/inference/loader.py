"""Verified model artifact loader with caching."""

from __future__ import annotations

from aegis_ml.models.artifact_store import (
    DEFAULT_MODEL_DIR,
    LoadedModelArtifact,
    load_verified_artifact,
)

_cached: LoadedModelArtifact | None = None


def get_loaded_model(*, force_reload: bool = False) -> LoadedModelArtifact:
    global _cached
    if _cached is None or force_reload:
        _cached = load_verified_artifact(model_dir=DEFAULT_MODEL_DIR)
    return _cached


def clear_model_cache() -> None:
    global _cached
    _cached = None
