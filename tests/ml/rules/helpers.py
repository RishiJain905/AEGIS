"""Shared helpers for detection rule tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aegis_contracts.features import FeatureProvenanceV1, FeatureVectorV1
from aegis_contracts.versioning import FEATURE_SCHEMA_VERSION, FEATURE_VECTOR_SCHEMA_VERSION
from aegis_ml.features.schema_registry import FEATURE_NAMES, TRANSFORM_VERSION

RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
ENTITY_ID = "asset:svc-identity-broker"
BASE_SIM = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def make_feature_vector(
    *,
    values: dict[str, float],
    entity_id: str = ENTITY_ID,
    window_start_epoch: int = 0,
    sequence_start: int = 1,
    sequence_end: int = 10,
) -> FeatureVectorV1:
    ordered = [values.get(name, 0.0) for name in FEATURE_NAMES]
    window_key = f"{RUN_ID}:{entity_id}:{window_start_epoch}"
    provenance = FeatureProvenanceV1(
        run_id=RUN_ID,
        entity_id=entity_id,
        sequence_start=sequence_start,
        sequence_end=sequence_end,
        sim_time_start=BASE_SIM,
        sim_time_end=BASE_SIM + timedelta(seconds=299),
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        transform_version=TRANSFORM_VERSION,
        source_event_ids=["evt_01ARZ3NDEKTSV4RRFFQ69G5FB0"],
    )
    return FeatureVectorV1(
        schema_version=FEATURE_VECTOR_SCHEMA_VERSION,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        window_key=window_key,
        entity_id=entity_id,
        values=ordered,
        provenance=provenance,
    )
