"""Scenario-level holdout evaluation for Phase 15 detectors."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from aegis_contracts.detection import (
    EvaluationRunV1,
    EvaluationSeedMetricsV1,
    MetricReportV1,
    RuleEvaluationStatus,
)
from aegis_contracts.versioning import EVALUATION_RUN_SCHEMA_VERSION, WORKSPACE_VERSION
from aegis_ml.baselines.splits import HOLDOUT_SEEDS, SILENT_RELAY_SCENARIO_ID, TRAINING_SEEDS
from aegis_ml.baselines.store import baseline_checksum, load_baseline

from aegis_incidents.pipeline import evaluate_features_offline
from aegis_incidents.rules.registry import DETECTION_RULE_REGISTRY_V1
from aegis_incidents.simulation_helpers import run_scenario_events

EVIDENCE_PATH = Path("scenarios/operation-silent-relay/expected-evidence.yaml")

SEED_ROOT_CAUSE: dict[int, str] = {
    1000: "hidden-cause-compromised-credentials",
    1006: "hidden-cause-undocumented-maintenance",
    1007: "hidden-cause-internal-misuse",
    1014: "hidden-cause-defective-deployment",
}

CAUSE_EXPECTED_RULES: dict[str, set[str]] = {
    "hidden-cause-compromised-credentials": {
        "rule-unusual-login",
        "rule-service-account-misuse",
    },
    "hidden-cause-undocumented-maintenance": {"rule-deploy-health-correlation"},
    "hidden-cause-defective-deployment": {
        "rule-deploy-health-correlation",
        "rule-unusual-paths",
    },
    "hidden-cause-internal-misuse": {"rule-data-volume", "rule-unusual-paths"},
}


@dataclass(frozen=True)
class SeedEvaluation:
    seed: int
    run_id: str
    fired_rules: set[str]
    expected_rules: set[str]


def load_expected_evidence() -> dict[str, object]:
    return yaml.safe_load(EVIDENCE_PATH.read_text(encoding="utf-8"))


def evaluate_seed(seed: int, *, steps: int = 300) -> SeedEvaluation:
    run_id, events = run_scenario_events(seed=seed, steps=steps)
    baselines = load_baseline() if Path("models/baselines/v1/baseline.json").exists() else None
    pipeline = evaluate_features_offline(
        run_id=run_id,
        events=events,
        baselines=baselines,
    )
    fired = {
        evaluation.rule_id
        for evaluation in pipeline.evaluations
        if evaluation.status == RuleEvaluationStatus.FIRED
    }
    root_cause = SEED_ROOT_CAUSE[seed]
    return SeedEvaluation(
        seed=seed,
        run_id=run_id,
        fired_rules=fired,
        expected_rules=CAUSE_EXPECTED_RULES[root_cause],
    )


def seed_metrics(result: SeedEvaluation) -> EvaluationSeedMetricsV1:
    true_positives = len(result.fired_rules & result.expected_rules)
    false_positives = len(result.fired_rules - result.expected_rules)
    false_negatives = len(result.expected_rules - result.fired_rules)
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) else 1.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) else 1.0
    false_positive_rate = false_positives / max(false_positives + (true_positives or 1), 1)
    cause_coverage = true_positives / len(result.expected_rules) if result.expected_rules else 1.0
    return EvaluationSeedMetricsV1(
        seed=result.seed,
        run_id=result.run_id,
        precision=precision,
        recall=recall,
        false_positive_rate=false_positive_rate,
        detection_delay_sim_seconds=None,
        cause_coverage=cause_coverage,
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
    )


def run_holdout_evaluation(*, steps: int = 300) -> EvaluationRunV1:
    from datetime import UTC, datetime

    _ = load_expected_evidence()
    per_seed = [seed_metrics(evaluate_seed(seed, steps=steps)) for seed in HOLDOUT_SEEDS]
    precision = sum(item.precision for item in per_seed) / len(per_seed)
    recall = sum(item.recall for item in per_seed) / len(per_seed)
    false_positive_rate = sum(item.false_positive_rate for item in per_seed) / len(per_seed)
    cause_coverage = sum(item.cause_coverage for item in per_seed) / len(per_seed)
    baseline = load_baseline()
    return EvaluationRunV1(
        schema_version=EVALUATION_RUN_SCHEMA_VERSION,
        evaluation_id="eval-rules-holdout-v1",
        scenario_id=SILENT_RELAY_SCENARIO_ID,
        training_seeds=list(TRAINING_SEEDS),
        holdout_seeds=list(HOLDOUT_SEEDS),
        rule_registry_version=DETECTION_RULE_REGISTRY_V1.registry_version,
        threshold_config_version=DETECTION_RULE_REGISTRY_V1.threshold_config_version,
        baseline_checksum=baseline_checksum(baseline),
        feature_schema_version=baseline.feature_schema_version,
        workspace_version=WORKSPACE_VERSION,
        created_at=datetime.now(tz=UTC),
        metrics=MetricReportV1(
            schema_version=1,
            precision=precision,
            recall=recall,
            false_positive_rate=false_positive_rate,
            mean_detection_delay_sim_seconds=None,
            cause_coverage=cause_coverage,
            per_seed=per_seed,
        ),
    )
