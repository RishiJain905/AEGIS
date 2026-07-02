"""Deterministic rule firing tests."""

from aegis_contracts.detection import RuleEvaluationStatus
from aegis_incidents.rules.evaluator import evaluate_rule_for_vector
from aegis_incidents.rules.registry import DETECTION_RULE_REGISTRY_V1
from aegis_incidents.rules.state import DetectionRunState

from tests.ml.rules.helpers import make_feature_vector


def _rule(rule_id: str):
    return next(rule for rule in DETECTION_RULE_REGISTRY_V1.rules if rule.rule_id == rule_id)


def test_unusual_login_fires_on_threshold() -> None:
    vector = make_feature_vector(
        values={"auth_failure_rate": 0.5, "auth_failed_count": 8},
    )
    result = evaluate_rule_for_vector(
        _rule("rule-unusual-login"),
        vector,
        run_id=vector.provenance.run_id,
        state=DetectionRunState(),
        baselines=None,
    )
    assert result.status == RuleEvaluationStatus.FIRED
    assert result.candidate is not None


def test_unusual_login_skips_normal_activity() -> None:
    vector = make_feature_vector(
        values={"auth_failure_rate": 0.05, "auth_failed_count": 1},
    )
    result = evaluate_rule_for_vector(
        _rule("rule-unusual-login"),
        vector,
        run_id=vector.provenance.run_id,
        state=DetectionRunState(),
        baselines=None,
    )
    assert result.status == RuleEvaluationStatus.SKIPPED


def test_deploy_health_correlation_requires_both_signals() -> None:
    vector = make_feature_vector(
        values={"deploy_failure_rate": 0.4, "health_unhealthy_rate": 0.35},
    )
    result = evaluate_rule_for_vector(
        _rule("rule-deploy-health-correlation"),
        vector,
        run_id=vector.provenance.run_id,
        state=DetectionRunState(),
        baselines=None,
    )
    assert result.status == RuleEvaluationStatus.FIRED
