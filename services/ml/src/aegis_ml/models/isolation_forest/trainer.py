"""Feature vector to training matrix conversion."""

from __future__ import annotations

import numpy as np
from aegis_contracts.features import FeatureVectorV1
from aegis_ml.features.schema_registry import FEATURE_NAMES, MISSING_SENTINEL


def vectors_to_matrix(vectors: list[FeatureVectorV1]) -> np.ndarray:
    if not vectors:
        return np.empty((0, len(FEATURE_NAMES)))
    rows: list[list[float]] = []
    for vector in vectors:
        row = []
        for value in vector.values:
            if value < 0 or value == MISSING_SENTINEL:
                row.append(0.0)
            else:
                row.append(float(value))
        rows.append(row)
    return np.array(rows, dtype=np.float64)


def compute_feature_statistics(vectors: list[FeatureVectorV1]) -> dict[str, tuple[float, float]]:
    matrix = vectors_to_matrix(vectors)
    stats: dict[str, tuple[float, float]] = {}
    for index, name in enumerate(FEATURE_NAMES):
        column = matrix[:, index]
        mean = float(np.mean(column))
        std = float(np.std(column))
        stats[name] = (mean, std if std > 1e-9 else 1.0)
    return stats
