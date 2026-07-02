"""Rule failure isolation tests."""

from unittest.mock import patch

from aegis_contracts.detection import RuleEvaluationStatus
from aegis_incidents.rules.evaluator import evaluate_vectors
from aegis_incidents.rules.registry import DETECTION_RULE_REGISTRY_V1

from tests.ml.rules.helpers import make_feature_vector


def test_broken_rule_does_not_stop_pipeline() -> None:
    vector = make_feature_vector(values={"auth_failure_rate": 0.1, "auth_failed_count": 1.0})
    with patch(
        "aegis_incidents.rules.evaluator._evaluate_unusual_login",
        side_effect=RuntimeError("boom"),
    ):
        evaluations = evaluate_vectors(
            [vector],
            run_id=vector.provenance.run_id,
            rules=DETECTION_RULE_REGISTRY_V1.rules,
            baselines=None,
        )
    statuses = {item.rule_id: item.status for item in evaluations}
    assert statuses["rule-unusual-login"] == RuleEvaluationStatus.ERROR
    assert any(status == RuleEvaluationStatus.SKIPPED for status in statuses.values())
