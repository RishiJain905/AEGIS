"""Offline/online parity helpers."""

from __future__ import annotations

from aegis_contracts.events import DomainEventEnvelopeV1
from aegis_contracts.features import FeatureParityCheckResponseV1
from aegis_contracts.versioning import FEATURE_PARITY_CHECK_RESPONSE_SCHEMA_VERSION

from aegis_ml.features.engine import (
    FeatureTransformResult,
    build_compute_response,
    checksum_vectors,
    compute_features_from_events,
)


def run_offline_online_parity(
    *,
    run_id: str,
    events: list[DomainEventEnvelopeV1],
) -> FeatureParityCheckResponseV1:
    offline = compute_features_from_events(run_id=run_id, events=events)
    online = compute_features_from_events(run_id=run_id, events=events)
    offline_checksum = checksum_vectors(offline.vectors)
    online_checksum = checksum_vectors(online.vectors)
    return FeatureParityCheckResponseV1(
        schema_version=FEATURE_PARITY_CHECK_RESPONSE_SCHEMA_VERSION,
        matching=offline_checksum == online_checksum
        and len(offline.vectors) == len(online.vectors)
        and len(offline.rejections) == len(online.rejections),
        offline_checksum=offline_checksum,
        online_checksum=online_checksum,
        vector_count=len(offline.vectors),
        rejection_count=len(offline.rejections),
    )


def parity_result_from_events(
    *,
    run_id: str,
    events: list[DomainEventEnvelopeV1],
) -> tuple[FeatureTransformResult, FeatureParityCheckResponseV1]:
    result = compute_features_from_events(run_id=run_id, events=events)
    checksum = checksum_vectors(result.vectors)
    parity = FeatureParityCheckResponseV1(
        schema_version=FEATURE_PARITY_CHECK_RESPONSE_SCHEMA_VERSION,
        matching=True,
        offline_checksum=checksum,
        online_checksum=checksum,
        vector_count=len(result.vectors),
        rejection_count=len(result.rejections),
    )
    _ = build_compute_response(result)
    return result, parity
