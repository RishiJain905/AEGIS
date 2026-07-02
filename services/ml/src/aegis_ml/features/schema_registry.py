"""Versioned feature schema registry for Phase 14."""

from __future__ import annotations

from aegis_contracts.features import (
    DEFAULT_WINDOW_DURATION_SIM_SECONDS,
    TRANSFORM_VERSION,
    FeatureDataType,
    FeatureDefinitionV1,
    FeatureSchemaManifestV1,
)
from aegis_contracts.versioning import (
    FEATURE_SCHEMA_MANIFEST_SCHEMA_VERSION,
    FEATURE_SCHEMA_VERSION,
)

MISSING_SENTINEL = -1.0
NET_PROTOCOL_MAPPING_VERSION = 1
NET_PROTOCOL_VALUES = ("tcp", "udp", "__MISSING__")


def _count_feature(name: str, order_index: int) -> FeatureDefinitionV1:
    return FeatureDefinitionV1(
        name=name,
        order_index=order_index,
        dtype=FeatureDataType.FLOAT,
        unit="count",
        min_value=0.0,
        missing_sentinel=MISSING_SENTINEL,
    )


def _rate_feature(name: str, order_index: int) -> FeatureDefinitionV1:
    return FeatureDefinitionV1(
        name=name,
        order_index=order_index,
        dtype=FeatureDataType.FLOAT,
        unit="ratio",
        min_value=0.0,
        max_value=1.0,
        missing_sentinel=MISSING_SENTINEL,
    )


def _categorical_feature(name: str, order_index: int) -> FeatureDefinitionV1:
    return FeatureDefinitionV1(
        name=name,
        order_index=order_index,
        dtype=FeatureDataType.CATEGORICAL,
        unit="one_hot",
        min_value=0.0,
        max_value=1.0,
        missing_sentinel=MISSING_SENTINEL,
        categorical_mapping_version=NET_PROTOCOL_MAPPING_VERSION,
        categorical_values=list(NET_PROTOCOL_VALUES),
    )


FEATURE_DEFINITIONS: tuple[FeatureDefinitionV1, ...] = (
    _count_feature("auth_event_count", 0),
    _count_feature("auth_failed_count", 1),
    _rate_feature("auth_failure_rate", 2),
    _count_feature("api_request_count", 3),
    _count_feature("api_error_count", 4),
    _rate_feature("api_error_rate", 5),
    _count_feature("db_query_count", 6),
    _count_feature("db_anomalous_count", 7),
    _rate_feature("db_anomalous_rate", 8),
    _count_feature("net_connection_count", 9),
    _count_feature("net_bytes_total", 10),
    _count_feature("net_bytes_mean", 11),
    _categorical_feature("net_protocol_tcp", 12),
    _categorical_feature("net_protocol_udp", 13),
    _categorical_feature("net_protocol_missing", 14),
    _count_feature("proc_event_count", 15),
    _count_feature("proc_suspicious_count", 16),
    _rate_feature("proc_suspicious_rate", 17),
    _count_feature("deploy_count", 18),
    _count_feature("deploy_failed_count", 19),
    _rate_feature("deploy_failure_rate", 20),
    _count_feature("health_check_count", 21),
    _count_feature("health_unhealthy_count", 22),
    _rate_feature("health_unhealthy_rate", 23),
    _count_feature("ai_inference_count", 24),
    _count_feature("ai_anomalous_count", 25),
    _rate_feature("ai_anomalous_rate", 26),
)

FEATURE_SCHEMA_MANIFEST_V1 = FeatureSchemaManifestV1(
    schema_version=FEATURE_SCHEMA_MANIFEST_SCHEMA_VERSION,
    feature_schema_version=FEATURE_SCHEMA_VERSION,
    transform_version=TRANSFORM_VERSION,
    window_duration_sim_seconds=DEFAULT_WINDOW_DURATION_SIM_SECONDS,
    features=list(FEATURE_DEFINITIONS),
)

FEATURE_COUNT = len(FEATURE_DEFINITIONS)
FEATURE_NAMES: tuple[str, ...] = tuple(feature.name for feature in FEATURE_DEFINITIONS)

TELEMETRY_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "telemetry.authentication.failed",
        "telemetry.authentication.succeeded",
        "telemetry.api.request",
        "telemetry.database.query",
        "telemetry.network.connection",
        "telemetry.process.activity",
        "telemetry.deployment.event",
        "telemetry.health.check",
        "telemetry.ai.inference",
    }
)

HIDDEN_TRUTH_PREFIXES: tuple[str, ...] = ("sim.hidden_condition.",)
