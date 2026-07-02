"""Model fallback when artifact unavailable."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from aegis_incidents.simulation_helpers import run_scenario_events
from aegis_ml.inference.service import run_inference_for_events


def test_fallback_when_model_missing(tmp_path: Path) -> None:
    run_id, events = run_scenario_events(seed=1000, steps=120)
    with patch("aegis_ml.inference.loader.DEFAULT_MODEL_DIR", tmp_path / "missing"):
        result = run_inference_for_events(run_id=run_id, events=events)
    assert result.fallback.active is True
    assert result.results == []
