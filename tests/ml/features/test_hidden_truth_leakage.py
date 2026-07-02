"""Hidden truth leakage tests."""

from __future__ import annotations

from aegis_ml.features.engine import compute_features_from_events

from tests.ml.features.helpers import RUN_ID, sample_auth_failed, sample_hidden_condition


def test_hidden_truth_never_appears_in_feature_values() -> None:
    result = compute_features_from_events(
        run_id=RUN_ID,
        events=[sample_auth_failed(), sample_hidden_condition(sequence=2)],
    )
    assert len(result.vectors) == 1
    hidden_markers = {
        "hidden-cause",
        "compromised",
        "conditionId",
        "sim.hidden_condition",
    }
    for vector in result.vectors:
        for value in vector.values:
            assert str(value) not in hidden_markers
        for source_id in vector.provenance.source_event_ids:
            assert source_id == sample_auth_failed().event_id
