"""Versioned detection rule registry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from aegis_contracts.detection import (
    THRESHOLD_CONFIG_VERSION,
    DetectionRuleRegistryV1,
    DetectionRuleV1,
    DetectorType,
    RuleThresholdV1,
    ThresholdOperator,
)
from aegis_contracts.versioning import (
    DETECTION_RULE_REGISTRY_SCHEMA_VERSION,
    DETECTION_RULE_SCHEMA_VERSION,
    RULE_THRESHOLD_SCHEMA_VERSION,
)

from aegis_incidents.rules import RULE_REGISTRY_VERSION

THRESHOLDS_PATH = Path(__file__).resolve().parent / "config" / "thresholds_v1.yaml"


def _threshold(
    feature_name: str,
    operator: str,
    value: float,
    min_count: float | None = None,
) -> RuleThresholdV1:
    return RuleThresholdV1(
        schema_version=RULE_THRESHOLD_SCHEMA_VERSION,
        feature_name=feature_name,
        operator=ThresholdOperator(operator),
        value=value,
        min_count=min_count,
    )


def load_threshold_config() -> dict[str, Any]:
    raw = yaml.safe_load(THRESHOLDS_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = "Invalid threshold configuration"
        raise ValueError(msg)
    return raw


def build_detection_rule_registry() -> DetectionRuleRegistryV1:
    config = load_threshold_config()
    rules_config = config.get("rules", {})
    if not isinstance(rules_config, dict):
        msg = "Invalid rules section in threshold configuration"
        raise ValueError(msg)

    login = rules_config["rule-unusual-login"]
    unseen = rules_config["rule-unseen-source"]
    misuse = rules_config["rule-service-account-misuse"]
    volume = rules_config["rule-data-volume"]
    paths = rules_config["rule-unusual-paths"]
    deploy_health = rules_config["rule-deploy-health-correlation"]
    flood = rules_config["rule-alert-flood-drift"]

    rules = [
        DetectionRuleV1(
            schema_version=DETECTION_RULE_SCHEMA_VERSION,
            rule_id="rule-unusual-login",
            rule_version=RULE_REGISTRY_VERSION,
            detector_type=DetectorType.DETERMINISTIC,
            title="Unusual login pattern",
            description="Elevated authentication failure rate with sufficient failed attempts",
            input_features=["auth_failure_rate", "auth_failed_count"],
            thresholds=[
                _threshold("auth_failure_rate", "gte", float(login["auth_failure_rate"])),
                _threshold(
                    "auth_failed_count",
                    "gte",
                    float(login["auth_failed_count"]),
                ),
            ],
            severity=str(login["severity"]),
            confidence_base=float(login["confidence_base"]),
            cooldown_sim_seconds=int(login["cooldown_sim_seconds"]),
            suppression_group=str(login["suppression_group"]),
        ),
        DetectionRuleV1(
            schema_version=DETECTION_RULE_SCHEMA_VERSION,
            rule_id="rule-unseen-source",
            rule_version=RULE_REGISTRY_VERSION,
            detector_type=DetectorType.DETERMINISTIC,
            title="Unseen device or source activity",
            description="First-seen entity with meaningful authentication or network activity",
            input_features=["auth_event_count", "net_connection_count"],
            thresholds=[
                _threshold(
                    "auth_event_count",
                    "gte",
                    float(unseen["min_activity_count"]),
                ),
            ],
            severity=str(unseen["severity"]),
            confidence_base=float(unseen["confidence_base"]),
            cooldown_sim_seconds=int(unseen["cooldown_sim_seconds"]),
            suppression_group=str(unseen["suppression_group"]),
        ),
        DetectionRuleV1(
            schema_version=DETECTION_RULE_SCHEMA_VERSION,
            rule_id="rule-service-account-misuse",
            rule_version=RULE_REGISTRY_VERSION,
            detector_type=DetectorType.DETERMINISTIC,
            title="Service account misuse pattern",
            description=(
                "Authentication stress followed by sustained API activity on service assets"
            ),
            input_features=["auth_failure_rate", "auth_event_count", "api_request_count"],
            thresholds=[
                _threshold("auth_failure_rate", "gte", float(misuse["auth_failure_rate"])),
                _threshold("api_request_count", "gte", float(misuse["api_request_count"])),
            ],
            severity=str(misuse["severity"]),
            confidence_base=float(misuse["confidence_base"]),
            cooldown_sim_seconds=int(misuse["cooldown_sim_seconds"]),
            suppression_group=str(misuse["suppression_group"]),
        ),
        DetectionRuleV1(
            schema_version=DETECTION_RULE_SCHEMA_VERSION,
            rule_id="rule-data-volume",
            rule_version=RULE_REGISTRY_VERSION,
            detector_type=DetectorType.STATISTICAL_BASELINE,
            title="Anomalous data volume",
            description="Network or database volume exceeds calibrated statistical baseline",
            input_features=["net_bytes_total", "db_query_count"],
            thresholds=[
                _threshold("net_bytes_total", "gte", float(volume["z_score_threshold"])),
                _threshold("db_query_count", "gte", float(volume["z_score_threshold"])),
            ],
            severity=str(volume["severity"]),
            confidence_base=float(volume["confidence_base"]),
            cooldown_sim_seconds=int(volume["cooldown_sim_seconds"]),
            suppression_group=str(volume["suppression_group"]),
        ),
        DetectionRuleV1(
            schema_version=DETECTION_RULE_SCHEMA_VERSION,
            rule_id="rule-unusual-paths",
            rule_version=RULE_REGISTRY_VERSION,
            detector_type=DetectorType.DETERMINISTIC,
            title="Unusual process or API paths",
            description="Elevated suspicious process activity with supporting event volume",
            input_features=["proc_suspicious_rate", "proc_event_count", "api_error_rate"],
            thresholds=[
                _threshold("proc_suspicious_rate", "gte", float(paths["proc_suspicious_rate"])),
                _threshold("proc_event_count", "gte", float(paths["proc_event_count"])),
            ],
            severity=str(paths["severity"]),
            confidence_base=float(paths["confidence_base"]),
            cooldown_sim_seconds=int(paths["cooldown_sim_seconds"]),
            suppression_group=str(paths["suppression_group"]),
        ),
        DetectionRuleV1(
            schema_version=DETECTION_RULE_SCHEMA_VERSION,
            rule_id="rule-deploy-health-correlation",
            rule_version=RULE_REGISTRY_VERSION,
            detector_type=DetectorType.DETERMINISTIC,
            title="Deployment and health correlation",
            description="Concurrent deployment failures and unhealthy service checks",
            input_features=["deploy_failure_rate", "health_unhealthy_rate"],
            thresholds=[
                _threshold(
                    "deploy_failure_rate",
                    "gte",
                    float(deploy_health["deploy_failure_rate"]),
                ),
                _threshold(
                    "health_unhealthy_rate",
                    "gte",
                    float(deploy_health["health_unhealthy_rate"]),
                ),
            ],
            severity=str(deploy_health["severity"]),
            confidence_base=float(deploy_health["confidence_base"]),
            cooldown_sim_seconds=int(deploy_health["cooldown_sim_seconds"]),
            suppression_group=str(deploy_health["suppression_group"]),
        ),
        DetectionRuleV1(
            schema_version=DETECTION_RULE_SCHEMA_VERSION,
            rule_id="rule-alert-flood-drift",
            rule_version=RULE_REGISTRY_VERSION,
            detector_type=DetectorType.DETERMINISTIC,
            title="Alert flooding or detector drift",
            description="Excessive alert generation within a rolling simulation-time window",
            input_features=["alert_count"],
            thresholds=[
                _threshold(
                    "alert_count",
                    "gte",
                    float(flood["max_alerts_per_window"]),
                ),
            ],
            severity=str(flood["severity"]),
            confidence_base=float(flood["confidence_base"]),
            cooldown_sim_seconds=int(flood["cooldown_sim_seconds"]),
            suppression_group=str(flood["suppression_group"]),
        ),
    ]

    return DetectionRuleRegistryV1(
        schema_version=DETECTION_RULE_REGISTRY_SCHEMA_VERSION,
        registry_version=RULE_REGISTRY_VERSION,
        threshold_config_version=str(
            config.get("thresholdConfigVersion", THRESHOLD_CONFIG_VERSION)
        ),
        rules=rules,
    )


DETECTION_RULE_REGISTRY_V1 = build_detection_rule_registry()
