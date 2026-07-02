"""Holdout evaluation for Isolation Forest model."""

from __future__ import annotations

import json
import resource
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from aegis_contracts.detection import EvaluationRunV1, EvaluationSeedMetricsV1, MetricReportV1
from aegis_contracts.versioning import EVALUATION_RUN_SCHEMA_VERSION, WORKSPACE_VERSION
from aegis_ml.baselines.splits import HOLDOUT_SEEDS, SILENT_RELAY_SCENARIO_ID, TRAINING_SEEDS
from aegis_ml.inference.service import run_inference_for_events
from aegis_ml.models.artifact_store import DEFAULT_MODEL_DIR, load_manifest, verify_artifact
from aegis_ml.training.simulation_helpers import run_scenario_events

EVIDENCE_PATH = Path("scenarios/operation-silent-relay/expected-evidence.yaml")

SEED_ROOT_CAUSE: dict[int, str] = {
    1000: "hidden-cause-compromised-credentials",
    1006: "hidden-cause-undocumented-maintenance",
    1007: "hidden-cause-internal-misuse",
    1014: "hidden-cause-defective-deployment",
}

CAUSE_ANOMALY_ENTITIES: dict[str, set[str]] = {
    "hidden-cause-compromised-credentials": {
        "asset:svc-api-gateway",
        "asset:identity:contractor-lena",
    },
    "hidden-cause-undocumented-maintenance": {"asset:svc-logistics-api"},
    "hidden-cause-defective-deployment": {"asset:svc-logistics-api", "asset:svc-api-gateway"},
    "hidden-cause-internal-misuse": {"asset:svc-data-warehouse", "asset:identity:analyst-marcus"},
}


@dataclass(frozen=True)
class ModelSeedEvaluation:
    seed: int
    run_id: str
    flagged_entities: set[str]
    expected_entities: set[str]
    mean_latency_ms: float
    score_distribution: dict[str, float]


def load_expected_evidence() -> dict[str, Any]:
    raw = yaml.safe_load(EVIDENCE_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = "Invalid expected evidence configuration"
        raise ValueError(msg)
    return raw


def evaluate_seed(seed: int, *, steps: int = 300) -> ModelSeedEvaluation:
    run_id, events = run_scenario_events(seed=seed, steps=steps)
    latencies: list[float] = []
    start = time.perf_counter()
    pipeline = run_inference_for_events(run_id=run_id, events=events)
    latencies.append((time.perf_counter() - start) * 1000.0 / max(len(pipeline.results), 1))

    flagged = {item.entity_id for item in pipeline.results if item.is_anomaly}
    root_cause = SEED_ROOT_CAUSE[seed]
    expected = CAUSE_ANOMALY_ENTITIES[root_cause]
    scores = [item.score for item in pipeline.results]
    distribution = {
        "min": float(min(scores)) if scores else 0.0,
        "max": float(max(scores)) if scores else 0.0,
        "mean": float(np.mean(scores)) if scores else 0.0,
        "p95": float(np.quantile(scores, 0.95)) if scores else 0.0,
    }
    return ModelSeedEvaluation(
        seed=seed,
        run_id=run_id,
        flagged_entities=flagged,
        expected_entities=expected,
        mean_latency_ms=float(np.mean(latencies)) if latencies else 0.0,
        score_distribution=distribution,
    )


def seed_metrics(result: ModelSeedEvaluation) -> EvaluationSeedMetricsV1:
    true_positives = len(result.flagged_entities & result.expected_entities)
    false_positives = len(result.flagged_entities - result.expected_entities)
    false_negatives = len(result.expected_entities - result.flagged_entities)
    positive_denominator = true_positives + false_positives
    precision = true_positives / positive_denominator if positive_denominator else 1.0
    negative_denominator = true_positives + false_negatives
    recall = true_positives / negative_denominator if negative_denominator else 1.0
    false_positive_rate = false_positives / max(false_positives + (true_positives or 1), 1)
    cause_coverage = (
        true_positives / len(result.expected_entities) if result.expected_entities else 1.0
    )
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


def load_rules_evaluation() -> dict[str, Any] | None:
    path = Path("models/evaluation/rules/holdout-v1/evaluation_run.json")
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return None
    return raw


def run_model_holdout_evaluation(*, steps: int = 300) -> dict[str, Any]:
    _ = load_expected_evidence()
    verification = verify_artifact(model_dir=DEFAULT_MODEL_DIR)
    manifest = load_manifest(model_dir=DEFAULT_MODEL_DIR)
    per_seed_results = [evaluate_seed(seed, steps=steps) for seed in HOLDOUT_SEEDS]
    per_seed_metrics = [seed_metrics(item) for item in per_seed_results]
    precision = sum(item.precision for item in per_seed_metrics) / len(per_seed_metrics)
    recall = sum(item.recall for item in per_seed_metrics) / len(per_seed_metrics)
    false_positive_rate = sum(item.false_positive_rate for item in per_seed_metrics) / len(
        per_seed_metrics
    )
    cause_coverage = sum(item.cause_coverage for item in per_seed_metrics) / len(per_seed_metrics)
    mean_latency = sum(item.mean_latency_ms for item in per_seed_results) / len(per_seed_results)
    peak_memory_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    rules_eval = load_rules_evaluation()
    evaluation = EvaluationRunV1(
        schema_version=EVALUATION_RUN_SCHEMA_VERSION,
        evaluation_id="eval-isolation-forest-holdout-v1",
        scenario_id=SILENT_RELAY_SCENARIO_ID,
        training_seeds=list(TRAINING_SEEDS),
        holdout_seeds=list(HOLDOUT_SEEDS),
        rule_registry_version=manifest.semantic_version,
        threshold_config_version=str(manifest.threshold),
        baseline_checksum=manifest.artifact_checksum,
        feature_schema_version=manifest.feature_schema_version,
        workspace_version=WORKSPACE_VERSION,
        created_at=datetime.now(tz=UTC),
        metrics=MetricReportV1(
            schema_version=1,
            precision=precision,
            recall=recall,
            false_positive_rate=false_positive_rate,
            mean_detection_delay_sim_seconds=None,
            cause_coverage=cause_coverage,
            per_seed=per_seed_metrics,
        ),
    )
    payload: dict[str, Any] = {
        "evaluationRun": evaluation.model_dump(mode="json", by_alias=True),
        "artifactVerification": verification.model_dump(mode="json", by_alias=True),
        "scoreDistributions": {
            str(item.seed): item.score_distribution for item in per_seed_results
        },
        "inferenceLatencyMs": {"mean": mean_latency},
        "peakMemoryKb": peak_memory_kb,
        "rulesComparison": rules_eval,
        "modelManifestId": manifest.id,
    }
    return payload
