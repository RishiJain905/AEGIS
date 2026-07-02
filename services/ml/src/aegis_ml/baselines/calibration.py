"""Baseline calibration from training-seed feature vectors."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import UTC, datetime

from aegis_contracts.detection import (
    BASELINE_VERSION,
    BaselineMethod,
    StatisticalBaselineEntryV1,
    StatisticalBaselineV1,
)
from aegis_contracts.features import FeatureVectorV1
from aegis_contracts.versioning import FEATURE_SCHEMA_VERSION, STATISTICAL_BASELINE_SCHEMA_VERSION

from aegis_ml.baselines.splits import TRAINING_SEEDS
from aegis_ml.features.schema_registry import FEATURE_NAMES

VOLUME_FEATURES = ("net_bytes_total", "db_query_count")
DEFAULT_Z_THRESHOLD = 3.0


def _aggregate(values: list[float]) -> tuple[float, float, int]:
    if not values:
        return 0.0, 0.0, 0
    mean = sum(values) / len(values)
    if len(values) == 1:
        return mean, 0.0, 1
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return mean, math.sqrt(variance), len(values)


def calibrate_baselines_from_vectors(
    vectors: list[FeatureVectorV1],
    *,
    training_seeds: list[int] | None = None,
    z_score_threshold: float = DEFAULT_Z_THRESHOLD,
) -> StatisticalBaselineV1:
    grouped: dict[tuple[str, str | None], list[float]] = defaultdict(list)
    for vector in vectors:
        feature_map = {
            name: value for name, value in zip(FEATURE_NAMES, vector.values, strict=True)
        }
        for feature_name in VOLUME_FEATURES:
            value = feature_map[feature_name]
            if value < 0:
                continue
            grouped[(feature_name, vector.entity_id)].append(value)
            grouped[(feature_name, None)].append(value)

    entries: list[StatisticalBaselineEntryV1] = []
    for (feature_name, entity_id), values in sorted(
        grouped.items(),
        key=lambda item: (item[0][0], item[0][1] or ""),
    ):
        mean, std, count = _aggregate(values)
        if count == 0:
            continue
        entries.append(
            StatisticalBaselineEntryV1(
                feature_name=feature_name,
                entity_id=entity_id,
                mean=mean,
                std=std,
                sample_count=count,
                z_score_threshold=z_score_threshold,
            )
        )

    created_at = datetime.fromtimestamp(
        sum(training_seeds or TRAINING_SEEDS) % 1_000_000,
        tz=UTC,
    )
    return StatisticalBaselineV1(
        schema_version=STATISTICAL_BASELINE_SCHEMA_VERSION,
        baseline_version=BASELINE_VERSION,
        method=BaselineMethod.ROLLING_MEAN_STD,
        training_seeds=list(training_seeds or TRAINING_SEEDS),
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        entries=entries,
        created_at=created_at,
    )
