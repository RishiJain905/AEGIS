"""Detection determinism tests."""

from aegis_incidents.pipeline import evaluate_features_offline

from tests.ml.features.helpers import sample_auth_failed


def test_identical_inputs_produce_identical_checksum() -> None:
    events = [sample_auth_failed(sequence=1), sample_auth_failed(sequence=2, sim_offset_seconds=15)]
    first = evaluate_features_offline(run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV", events=events)
    second = evaluate_features_offline(run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV", events=events)
    assert first.deterministic_checksum == second.deterministic_checksum
