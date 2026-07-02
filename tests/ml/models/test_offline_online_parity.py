"""Offline/online scoring parity."""

from __future__ import annotations

from aegis_incidents.simulation_helpers import run_scenario_events
from aegis_ml.inference.batch import score_vectors
from aegis_ml.inference.scorer import score_vector
from aegis_ml.models.artifact_store import DEFAULT_MODEL_DIR, load_verified_artifact
from aegis_ml.models.isolation_forest.train import train_isolation_forest


def test_batch_and_single_scorer_match() -> None:
    if not (DEFAULT_MODEL_DIR / "manifest.json").exists():
        train_isolation_forest(output_dir=DEFAULT_MODEL_DIR, steps=120)
    run_id, events = run_scenario_events(seed=1000, steps=120)
    from aegis_ml.features import compute_features_from_events

    vectors = compute_features_from_events(run_id=run_id, events=events).vectors[:5]
    artifact = load_verified_artifact(model_dir=DEFAULT_MODEL_DIR)
    batch = score_vectors(vectors, artifact)
    singles = [score_vector(vector, artifact) for vector in vectors]
    for batch_item, single in zip(batch, singles, strict=True):
        assert batch_item.score == single.score
        assert batch_item.deduplication_key == single.deduplication_key
