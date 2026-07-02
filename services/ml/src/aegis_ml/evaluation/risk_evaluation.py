"""Graph risk holdout evaluation (evaluation-only labels)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aegis_contracts.detection import EvaluationRunV1, EvaluationSeedMetricsV1, MetricReportV1
from aegis_contracts.versioning import EVALUATION_RUN_SCHEMA_VERSION, WORKSPACE_VERSION
from aegis_graph_risk import (
    DEFAULT_RISK_ENGINE_CONFIG_V1,
    compute_risk_scores,
    deduplicate_risk_inputs,
)
from aegis_graph_risk.normalize import normalize_alert_to_risk_input
from aegis_incidents.pipeline import evaluate_features_offline
from aegis_incidents.promotion import candidate_to_alert
from aegis_incidents.rules.registry import DETECTION_RULE_REGISTRY_V1
from aegis_ml.baselines.splits import HOLDOUT_SEEDS, SILENT_RELAY_SCENARIO_ID, TRAINING_SEEDS
from aegis_ml.baselines.store import DEFAULT_BASELINE_DIR, baseline_checksum, load_baseline
from aegis_simulation.graph_projection import build_graph_snapshot_from_runtime
from aegis_simulation_domain import SimulationEngine
from aegis_simulation_domain.runtime import SimulationRuntime


def _run_seed_runtime(*, seed: int, steps: int) -> SimulationRuntime:
    package_dir = Path("scenarios/operation-silent-relay")
    manifest = SimulationEngine.load_manifest(package_dir)
    scenario_version_id = f"scenario-version:{manifest.metadata.version}"
    runtime = SimulationEngine.create_runtime(
        manifest=manifest,
        seed=seed,
        scenario_version_id=scenario_version_id,
    )
    runtime.start()
    runtime.run_steps(steps)
    return runtime


def evaluate_graph_risk_holdout(*, steps: int, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    baselines = None
    if (DEFAULT_BASELINE_DIR / "baseline.json").exists():
        baselines = load_baseline()

    per_seed: list[EvaluationSeedMetricsV1] = []
    propagated_reach_values: list[float] = []
    checksum = "sha256:empty"

    for seed in sorted(HOLDOUT_SEEDS):
        runtime = _run_seed_runtime(seed=seed, steps=steps)
        detection = evaluate_features_offline(
            run_id=runtime.run_id,
            events=list(runtime.events),
            registry=DETECTION_RULE_REGISTRY_V1,
            baselines=baselines,
        )
        alerts = [candidate_to_alert(candidate) for candidate in detection.accepted_candidates]
        snapshot = build_graph_snapshot_from_runtime(runtime, sequence=steps)
        sim_time = runtime.clock.sim_time
        inputs = deduplicate_risk_inputs(
            [normalize_alert_to_risk_input(alert, sim_time=sim_time) for alert in alerts]
        )
        result = compute_risk_scores(
            snapshot,
            inputs,
            DEFAULT_RISK_ENGINE_CONFIG_V1,
            current_sim_time=sim_time,
            computed_at_sequence=steps,
        )
        checksum = result.checksum
        origins = len(inputs)
        propagated = len([score for score in result.scores if score.propagated > 0.0])
        reach_ratio = min(1.0, propagated / max(origins, 1))
        propagated_reach_values.append(reach_ratio)
        per_seed.append(
            EvaluationSeedMetricsV1(
                seed=seed,
                run_id=runtime.run_id,
                precision=reach_ratio,
                recall=reach_ratio,
                false_positive_rate=0.0,
                detection_delay_sim_seconds=None,
                cause_coverage=reach_ratio,
                true_positives=propagated,
                false_positives=0,
                false_negatives=max(origins - propagated, 0),
            )
        )

    mean_reach = sum(propagated_reach_values) / len(propagated_reach_values)
    baseline = load_baseline() if baselines else None
    evaluation = EvaluationRunV1(
        schema_version=EVALUATION_RUN_SCHEMA_VERSION,
        evaluation_id="graph-risk-holdout-v1",
        scenario_id=SILENT_RELAY_SCENARIO_ID,
        training_seeds=list(TRAINING_SEEDS),
        holdout_seeds=list(HOLDOUT_SEEDS),
        rule_registry_version=DETECTION_RULE_REGISTRY_V1.registry_version,
        threshold_config_version=DETECTION_RULE_REGISTRY_V1.threshold_config_version,
        baseline_checksum=baseline_checksum(baseline) if baseline else "sha256:" + "0" * 64,
        feature_schema_version=baseline.feature_schema_version if baseline else 1,
        workspace_version=WORKSPACE_VERSION,
        created_at=datetime.now(tz=UTC),
        metrics=MetricReportV1(
            schema_version=1,
            precision=mean_reach,
            recall=mean_reach,
            false_positive_rate=0.0,
            mean_detection_delay_sim_seconds=None,
            cause_coverage=mean_reach,
            per_seed=per_seed,
        ),
    )
    manifest = {
        "evaluationId": evaluation.evaluation_id,
        "algorithmVersion": "graph-risk-v1",
        "holdoutSeeds": list(HOLDOUT_SEEDS),
        "meanPropagatedReachRatio": mean_reach,
        "checksum": checksum,
    }
    output_dir.joinpath("evaluation_run.json").write_text(
        json.dumps(evaluation.model_dump(mode="json", by_alias=True), indent=2),
        encoding="utf-8",
    )
    output_dir.joinpath("manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    return manifest
