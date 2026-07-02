"""Statistical baseline scoring."""

from __future__ import annotations

from aegis_contracts.detection import StatisticalBaselineV1

MIN_STD = 1e-6


def score_feature_against_baseline(
    baseline: StatisticalBaselineV1,
    *,
    feature_name: str,
    entity_id: str,
    observed: float,
    z_threshold: float,
) -> tuple[float, float, float] | None:
    if observed < 0:
        return None
    entry = None
    for candidate in baseline.entries:
        if candidate.feature_name != feature_name:
            continue
        if candidate.entity_id in (None, entity_id):
            entry = candidate
            break
    if entry is None or entry.sample_count < 1:
        return None
    std = max(entry.std, MIN_STD)
    z_score = abs(observed - entry.mean) / std
    if z_score < z_threshold:
        return None
    return z_score, entry.mean, std
