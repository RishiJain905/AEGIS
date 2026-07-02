"""Feature-vector rule evaluation engine."""

from __future__ import annotations

from aegis_contracts.detection import (
    AlertCandidateV1,
    AlertEvidenceV1,
    DetectionRuleV1,
    RuleEvaluationStatus,
    RuleEvaluationV1,
    RuleExplanationV1,
    StatisticalBaselineV1,
    ThresholdOperator,
)
from aegis_contracts.features import FeatureVectorV1
from aegis_contracts.versioning import (
    ALERT_CANDIDATE_SCHEMA_VERSION,
    FEATURE_SCHEMA_VERSION,
    RULE_EXPLANATION_SCHEMA_VERSION,
)
from aegis_ml.baselines.scorer import score_feature_against_baseline
from aegis_ml.features.schema_registry import FEATURE_NAMES

from aegis_incidents.promotion import deterministic_event_id
from aegis_incidents.rules.dedup import build_deduplication_key
from aegis_incidents.rules.registry import load_threshold_config
from aegis_incidents.rules.state import DetectionRunState

MISSING_SENTINEL = -1.0


def _feature_map(vector: FeatureVectorV1) -> dict[str, float]:
    return {name: value for name, value in zip(FEATURE_NAMES, vector.values, strict=True)}


def _compare(operator: ThresholdOperator, observed: float, threshold: float) -> bool:
    if observed == MISSING_SENTINEL:
        return False
    if operator == ThresholdOperator.GTE:
        return observed >= threshold
    if operator == ThresholdOperator.GT:
        return observed > threshold
    if operator == ThresholdOperator.LTE:
        return observed <= threshold
    if operator == ThresholdOperator.LT:
        return observed < threshold
    if operator == ThresholdOperator.EQ:
        return observed == threshold
    msg = f"Unsupported operator: {operator}"
    raise ValueError(msg)


def _window_start_epoch(window_key: str) -> int:
    return int(window_key.split(":")[-1])


def _build_candidate(
    *,
    vector: FeatureVectorV1,
    rule: DetectionRuleV1,
    run_id: str,
    title: str,
    feature_name: str,
    observed: float,
    baseline: float | None,
    threshold: float,
    comparison: str,
    condition: str,
    summary: str,
    features: dict[str, float],
) -> AlertCandidateV1:
    window_start = _window_start_epoch(vector.window_key)
    dedup_key = build_deduplication_key(
        run_id=run_id,
        rule_id=rule.rule_id,
        entity_id=vector.entity_id,
        window_start_epoch=window_start,
    )
    explanation = RuleExplanationV1(
        schema_version=RULE_EXPLANATION_SCHEMA_VERSION,
        summary=summary,
        condition=condition,
        feature_name=feature_name,
        observed=observed,
        baseline=baseline,
        threshold=threshold,
        comparison=comparison,
        window_key=vector.window_key,
        detector_type=rule.detector_type,
    )
    source_event_id = (
        vector.provenance.source_event_ids[-1]
        if vector.provenance.source_event_ids
        else deterministic_event_id(dedup_key)
    )
    return AlertCandidateV1(
        schema_version=ALERT_CANDIDATE_SCHEMA_VERSION,
        run_id=run_id,
        rule_id=rule.rule_id,
        rule_version=rule.rule_version,
        detector_id=rule.rule_id,
        detector_version=rule.rule_version,
        detector_type=rule.detector_type,
        entity_id=vector.entity_id,
        title=title,
        severity=rule.severity,
        confidence=rule.confidence_base,
        observed_value=observed,
        baseline_value=baseline,
        threshold=threshold,
        source_window_key=vector.window_key,
        deduplication_key=dedup_key,
        explanation=explanation,
        evidence=AlertEvidenceV1(
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            feature_values={name: features[name] for name in rule.input_features if name in features},
            source_event_ids=list(vector.provenance.source_event_ids),
            window_key=vector.window_key,
            sequence_start=vector.provenance.sequence_start,
            sequence_end=vector.provenance.sequence_end,
            sim_time_start=vector.provenance.sim_time_start,
            sim_time_end=vector.provenance.sim_time_end,
        ),
        source_event_id=source_event_id,
    )


def _evaluate_unusual_login(
    vector: FeatureVectorV1,
    rule: DetectionRuleV1,
    features: dict[str, float],
    run_id: str,
) -> AlertCandidateV1 | None:
    rate = features["auth_failure_rate"]
    failed = features["auth_failed_count"]
    rate_threshold = rule.thresholds[0].value
    count_threshold = rule.thresholds[1].value
    if not (_compare(ThresholdOperator.GTE, rate, rate_threshold) and failed >= count_threshold):
        return None
    return _build_candidate(
        vector=vector,
        rule=rule,
        run_id=run_id,
        title="Elevated authentication failures",
        feature_name="auth_failure_rate",
        observed=rate,
        baseline=None,
        threshold=rate_threshold,
        comparison=f"auth_failure_rate {rate:.3f} >= {rate_threshold} AND auth_failed_count {failed:.0f} >= {count_threshold}",
        condition="auth_failure_rate >= threshold AND auth_failed_count >= min_count",
        summary=f"Authentication failure rate {rate:.1%} with {failed:.0f} failed attempts",
        features=features,
    )


def _evaluate_unseen_source(
    vector: FeatureVectorV1,
    rule: DetectionRuleV1,
    features: dict[str, float],
    run_id: str,
    state: DetectionRunState,
) -> AlertCandidateV1 | None:
    entity = vector.entity_id
    if entity in state.seen_entities:
        return None
    auth_count = features["auth_event_count"]
    net_count = features["net_connection_count"]
    min_activity = rule.thresholds[0].value
    activity = auth_count + net_count
    state.seen_entities.add(entity)
    if activity < min_activity:
        return None
    return _build_candidate(
        vector=vector,
        rule=rule,
        run_id=run_id,
        title="Unseen source activity detected",
        feature_name="auth_event_count",
        observed=activity,
        baseline=None,
        threshold=min_activity,
        comparison=f"first_seen activity {activity:.0f} >= {min_activity}",
        condition="entity first seen with activity >= min_activity_count",
        summary=f"First-seen entity {entity} produced {activity:.0f} auth/network events",
        features=features,
    )


def _evaluate_service_account_misuse(
    vector: FeatureVectorV1,
    rule: DetectionRuleV1,
    features: dict[str, float],
    run_id: str,
    state: DetectionRunState,
) -> AlertCandidateV1 | None:
    if ":svc-" not in vector.entity_id and not vector.entity_id.endswith("-api"):
        return None
    rate = features["auth_failure_rate"]
    api_count = features["api_request_count"]
    rate_threshold = rule.thresholds[0].value
    api_threshold = rule.thresholds[1].value
    had_burst = state.prior_auth_failure_burst.get(vector.entity_id, False)
    if rate >= rate_threshold:
        state.prior_auth_failure_burst[vector.entity_id] = True
    if not (had_burst or rate >= rate_threshold) or api_count < api_threshold:
        return None
    return _build_candidate(
        vector=vector,
        rule=rule,
        run_id=run_id,
        title="Service account misuse pattern",
        feature_name="api_request_count",
        observed=api_count,
        baseline=None,
        threshold=api_threshold,
        comparison=f"auth_failure_rate {rate:.3f} with api_request_count {api_count:.0f} >= {api_threshold}",
        condition="service asset auth stress with sustained API requests",
        summary=f"Service asset {vector.entity_id} shows misuse-like auth/API pattern",
        features=features,
    )


def _evaluate_unusual_paths(
    vector: FeatureVectorV1,
    rule: DetectionRuleV1,
    features: dict[str, float],
    run_id: str,
) -> AlertCandidateV1 | None:
    rate = features["proc_suspicious_rate"]
    count = features["proc_event_count"]
    rate_threshold = rule.thresholds[0].value
    count_threshold = rule.thresholds[1].value
    if not (rate >= rate_threshold and count >= count_threshold):
        return None
    return _build_candidate(
        vector=vector,
        rule=rule,
        run_id=run_id,
        title="Unusual process or API path activity",
        feature_name="proc_suspicious_rate",
        observed=rate,
        baseline=None,
        threshold=rate_threshold,
        comparison=f"proc_suspicious_rate {rate:.3f} >= {rate_threshold} AND proc_event_count {count:.0f} >= {count_threshold}",
        condition="proc_suspicious_rate >= threshold with minimum process events",
        summary=f"Suspicious process rate {rate:.1%} across {count:.0f} events",
        features=features,
    )


def _evaluate_deploy_health(
    vector: FeatureVectorV1,
    rule: DetectionRuleV1,
    features: dict[str, float],
    run_id: str,
) -> AlertCandidateV1 | None:
    deploy_rate = features["deploy_failure_rate"]
    health_rate = features["health_unhealthy_rate"]
    deploy_threshold = rule.thresholds[0].value
    health_threshold = rule.thresholds[1].value
    if not (deploy_rate >= deploy_threshold and health_rate >= health_threshold):
        return None
    observed = max(deploy_rate, health_rate)
    return _build_candidate(
        vector=vector,
        rule=rule,
        run_id=run_id,
        title="Deployment failure correlated with unhealthy checks",
        feature_name="deploy_failure_rate",
        observed=observed,
        baseline=None,
        threshold=deploy_threshold,
        comparison=(
            f"deploy_failure_rate {deploy_rate:.3f} >= {deploy_threshold} AND "
            f"health_unhealthy_rate {health_rate:.3f} >= {health_threshold}"
        ),
        condition="deploy_failure_rate and health_unhealthy_rate exceed paired thresholds",
        summary="Deployment failures coincide with unhealthy service checks",
        features=features,
    )


def _evaluate_data_volume(
    vector: FeatureVectorV1,
    rule: DetectionRuleV1,
    features: dict[str, float],
    run_id: str,
    baselines: StatisticalBaselineV1 | None,
) -> AlertCandidateV1 | None:
    if baselines is None:
        return None
    config = load_threshold_config()["rules"]["rule-data-volume"]
    z_threshold = float(config["z_score_threshold"])
    best: tuple[str, float, float, float] | None = None
    for feature_name in ("net_bytes_total", "db_query_count"):
        observed = features[feature_name]
        scored = score_feature_against_baseline(
            baselines,
            feature_name=feature_name,
            entity_id=vector.entity_id,
            observed=observed,
            z_threshold=z_threshold,
        )
        if scored is None:
            continue
        z_score, mean, std = scored
        if best is None or z_score > best[1]:
            best = (feature_name, z_score, mean, std)
    if best is None:
        return None
    feature_name, z_score, mean, _std = best
    observed = features[feature_name]
    return _build_candidate(
        vector=vector,
        rule=rule,
        run_id=run_id,
        title="Anomalous data volume detected",
        feature_name=feature_name,
        observed=observed,
        baseline=mean,
        threshold=z_threshold,
        comparison=f"z_score {z_score:.2f} >= {z_threshold} for {feature_name}",
        condition="observed value exceeds calibrated statistical baseline",
        summary=f"{feature_name} deviates from baseline (z={z_score:.2f})",
        features=features,
    )


def _evaluate_alert_flood(
    vector: FeatureVectorV1,
    rule: DetectionRuleV1,
    run_id: str,
    state: DetectionRunState,
) -> AlertCandidateV1 | None:
    config = load_threshold_config()["rules"]["rule-alert-flood-drift"]
    max_alerts = float(config["max_alerts_per_window"])
    window_seconds = int(config["window_sim_seconds"])
    sim_time = vector.provenance.sim_time_end
    recent = [
        entry
        for entry in state.alert_timestamps
        if (sim_time - entry[0]).total_seconds() <= window_seconds
    ]
    if len(recent) < max_alerts:
        return None
    features = _feature_map(vector)
    return _build_candidate(
        vector=vector,
        rule=rule,
        run_id=run_id,
        title="Alert flooding or detector drift",
        feature_name="alert_count",
        observed=float(len(recent)),
        baseline=None,
        threshold=max_alerts,
        comparison=f"alert_count {len(recent)} >= {max_alerts} within {window_seconds}s",
        condition="rolling alert count exceeds configured cap",
        summary=f"{len(recent)} alerts emitted within {window_seconds} simulation seconds",
        features=features,
    )


def evaluate_rule_for_vector(
    rule: DetectionRuleV1,
    vector: FeatureVectorV1,
    *,
    run_id: str,
    state: DetectionRunState,
    baselines: StatisticalBaselineV1 | None,
) -> RuleEvaluationV1:
    if not rule.enabled:
        return RuleEvaluationV1(
            schema_version=1,
            rule_id=rule.rule_id,
            status=RuleEvaluationStatus.SKIPPED,
        )
    try:
        features = _feature_map(vector)
        candidate: AlertCandidateV1 | None = None
        if rule.rule_id == "rule-unusual-login":
            candidate = _evaluate_unusual_login(vector, rule, features, run_id)
        elif rule.rule_id == "rule-unseen-source":
            candidate = _evaluate_unseen_source(vector, rule, features, run_id, state)
        elif rule.rule_id == "rule-service-account-misuse":
            candidate = _evaluate_service_account_misuse(vector, rule, features, run_id, state)
        elif rule.rule_id == "rule-data-volume":
            candidate = _evaluate_data_volume(vector, rule, features, run_id, baselines)
        elif rule.rule_id == "rule-unusual-paths":
            candidate = _evaluate_unusual_paths(vector, rule, features, run_id)
        elif rule.rule_id == "rule-deploy-health-correlation":
            candidate = _evaluate_deploy_health(vector, rule, features, run_id)
        elif rule.rule_id == "rule-alert-flood-drift":
            candidate = _evaluate_alert_flood(vector, rule, run_id, state)
        else:
            return RuleEvaluationV1(
                schema_version=1,
                rule_id=rule.rule_id,
                status=RuleEvaluationStatus.ERROR,
                error_code="UNKNOWN_RULE",
                error_message=f"Unknown rule id: {rule.rule_id}",
            )
        if candidate is None:
            return RuleEvaluationV1(
                schema_version=1,
                rule_id=rule.rule_id,
                status=RuleEvaluationStatus.SKIPPED,
            )
        return RuleEvaluationV1(
            schema_version=1,
            rule_id=rule.rule_id,
            status=RuleEvaluationStatus.FIRED,
            candidate=candidate,
        )
    except Exception as exc:  # noqa: BLE001 - rule isolation boundary
        return RuleEvaluationV1(
            schema_version=1,
            rule_id=rule.rule_id,
            status=RuleEvaluationStatus.ERROR,
            error_code="RULE_EVALUATION_FAILED",
            error_message=str(exc),
        )


def evaluate_vectors(
    vectors: list[FeatureVectorV1],
    *,
    run_id: str,
    rules: list[DetectionRuleV1],
    baselines: StatisticalBaselineV1 | None,
    state: DetectionRunState | None = None,
) -> list[RuleEvaluationV1]:
    run_state = state or DetectionRunState()
    evaluations: list[RuleEvaluationV1] = []
    for vector in vectors:
        for rule in rules:
            evaluations.append(
                evaluate_rule_for_vector(
                    rule,
                    vector,
                    run_id=run_id,
                    state=run_state,
                    baselines=baselines,
                )
            )
    return evaluations
