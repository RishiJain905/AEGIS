"""Baseline calibration and scoring tests."""

from aegis_incidents.rules.evaluator import evaluate_rule_for_vector
from aegis_incidents.rules.registry import DETECTION_RULE_REGISTRY_V1
from aegis_incidents.rules.state import DetectionRunState
from aegis_ml.baselines.calibration import calibrate_baselines_from_vectors
from aegis_ml.baselines.scorer import score_feature_against_baseline
from aegis_ml.baselines.store import baseline_checksum

from tests.ml.rules.helpers import make_feature_vector


def test_calibration_is_deterministic() -> None:
    vectors = [
        make_feature_vector(values={"net_bytes_total": 100.0, "db_query_count": 5.0}),
        make_feature_vector(values={"net_bytes_total": 120.0, "db_query_count": 6.0}),
    ]
    first = calibrate_baselines_from_vectors(vectors, training_seeds=[1, 11])
    second = calibrate_baselines_from_vectors(vectors, training_seeds=[1, 11])
    assert baseline_checksum(first) == baseline_checksum(second)


def test_z_score_detects_volume_deviation() -> None:
    vectors = [
        make_feature_vector(values={"net_bytes_total": 100.0, "db_query_count": 5.0}),
        make_feature_vector(values={"net_bytes_total": 110.0, "db_query_count": 5.0}),
        make_feature_vector(values={"net_bytes_total": 105.0, "db_query_count": 5.0}),
    ]
    baseline = calibrate_baselines_from_vectors(vectors, training_seeds=[1])
    scored = score_feature_against_baseline(
        baseline,
        feature_name="net_bytes_total",
        entity_id="asset:svc-identity-broker",
        observed=5000.0,
        z_threshold=2.0,
    )
    assert scored is not None
    rule = next(r for r in DETECTION_RULE_REGISTRY_V1.rules if r.rule_id == "rule-data-volume")
    vector = make_feature_vector(values={"net_bytes_total": 5000.0, "db_query_count": 5.0})
    result = evaluate_rule_for_vector(
        rule,
        vector,
        run_id=vector.provenance.run_id,
        state=DetectionRunState(),
        baselines=baseline,
    )
    assert result.candidate is not None
