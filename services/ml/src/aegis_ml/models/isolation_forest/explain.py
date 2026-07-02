"""Structured anomaly explanations from feature deviations."""

from __future__ import annotations

from aegis_contracts.features import FeatureVectorV1
from aegis_contracts.models import (
    AnomalyExplanationV1,
    AnomalyRiskBand,
    BaselineComparisonV1,
    SourceWindowV1,
)
from aegis_contracts.versioning import ANOMALY_EXPLANATION_SCHEMA_VERSION
from aegis_ml.features.schema_registry import FEATURE_NAMES, MISSING_SENTINEL


def build_explanation(
    *,
    vector: FeatureVectorV1,
    normalized_score: float,
    threshold: float,
    model_version_id: str,
    model_semantic_version: str,
    feature_stats: dict[str, tuple[float, float]],
    baseline_version: str | None = None,
) -> AnomalyExplanationV1:
    contributions: dict[str, float] = {}
    for name, value in zip(FEATURE_NAMES, vector.values, strict=True):
        if value < 0 or value == MISSING_SENTINEL:
            continue
        mean, std = feature_stats.get(name, (0.0, 1.0))
        z = abs((float(value) - mean) / std) if std > 1e-9 else 0.0
        if z > 0.01:
            contributions[name] = round(z, 4)

    top_features = sorted(contributions, key=contributions.get, reverse=True)[:5]
    if not top_features:
        top_features = list(FEATURE_NAMES[:3])

    top_name = top_features[0]
    top_value = dict(zip(FEATURE_NAMES, vector.values, strict=True)).get(top_name, 0.0)
    mean, std = feature_stats.get(top_name, (0.0, 1.0))
    comparison = None
    if baseline_version and top_name in feature_stats:
        comparison = BaselineComparisonV1(
            baseline_version=baseline_version,
            feature_name=top_name,
            observed_value=float(top_value) if top_value >= 0 else 0.0,
            baseline_mean=mean,
            baseline_std=std,
            z_score=contributions.get(top_name, 0.0),
        )

    summary = (
        f"Isolation Forest score {normalized_score:.2f} exceeds threshold {threshold:.2f}; "
        f"top deviations: {', '.join(top_features[:3])}"
    )

    window_start = int(vector.window_key.rsplit(":", 1)[-1])
    window_end = window_start + 300

    return AnomalyExplanationV1(
        schema_version=ANOMALY_EXPLANATION_SCHEMA_VERSION,
        summary=summary,
        top_features=top_features,
        feature_contributions=contributions,
        threshold=threshold,
        observed_score=normalized_score,
        source_window=SourceWindowV1(
            window_start_epoch=window_start,
            window_end_epoch=window_end,
            sim_time_start=vector.provenance.sim_time_start,
            sim_time_end=vector.provenance.sim_time_end,
        ),
        model_version_id=model_version_id,  # type: ignore[arg-type]
        model_semantic_version=model_semantic_version,
        comparison_baseline=comparison,
    )


def risk_band_for_score(
    score: float,
    *,
    threshold: float,
    elevated_threshold: float,
) -> AnomalyRiskBand:
    if score >= threshold:
        return AnomalyRiskBand.HIGH
    if score >= elevated_threshold:
        return AnomalyRiskBand.ELEVATED
    return AnomalyRiskBand.NORMAL
