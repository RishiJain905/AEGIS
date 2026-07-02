"""Determinism tests."""

from __future__ import annotations

from aegis_ml.features.engine import checksum_vectors, compute_features_from_events

from tests.ml.features.helpers import RUN_ID, sample_auth_failed, sample_auth_succeeded


def test_identical_inputs_produce_identical_checksum() -> None:
    events = [sample_auth_failed(), sample_auth_succeeded()]
    first = compute_features_from_events(run_id=RUN_ID, events=events)
    second = compute_features_from_events(run_id=RUN_ID, events=events)
    assert checksum_vectors(first.vectors) == checksum_vectors(second.vectors)
    assert first.vectors[0].values == second.vectors[0].values
