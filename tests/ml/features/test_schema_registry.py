"""Schema registry tests."""

from __future__ import annotations

from aegis_ml.features.schema_registry import (
    FEATURE_COUNT,
    FEATURE_NAMES,
    FEATURE_SCHEMA_MANIFEST_V1,
    MISSING_SENTINEL,
)


def test_feature_count_is_stable() -> None:
    assert FEATURE_COUNT == 27
    assert len(FEATURE_NAMES) == FEATURE_COUNT


def test_feature_ordering_is_deterministic() -> None:
    indices = [feature.order_index for feature in FEATURE_SCHEMA_MANIFEST_V1.features]
    assert indices == list(range(FEATURE_COUNT))
    names = [feature.name for feature in FEATURE_SCHEMA_MANIFEST_V1.features]
    assert names == list(FEATURE_NAMES)


def test_missing_sentinel_documented() -> None:
    rates = [
        feature
        for feature in FEATURE_SCHEMA_MANIFEST_V1.features
        if feature.unit == "ratio"
    ]
    assert rates
    assert all(feature.missing_sentinel == MISSING_SENTINEL for feature in rates)
