"""Contract fixture round-trip tests."""

from __future__ import annotations

from aegis_contracts.features import (
    DatasetManifestV1,
    FeatureComputeRequestV1,
    FeatureComputeResponseV1,
    FeatureParityCheckResponseV1,
    FeatureSchemaManifestV1,
    FeatureVectorV1,
    FeatureWindowV1,
    OnlineFeatureUpdateV1,
)
from aegis_ml.features import (
    FEATURE_SCHEMA_MANIFEST_V1,
    build_compute_response,
    compute_features_from_events,
)

from tests.ml.features.helpers import RUN_ID, sample_auth_failed, sample_auth_succeeded


def test_feature_schema_manifest_round_trip() -> None:
    payload = FEATURE_SCHEMA_MANIFEST_V1.model_dump(mode="json", by_alias=True)
    parsed = FeatureSchemaManifestV1.model_validate(payload)
    assert parsed.feature_schema_version == 1


def test_compute_response_contract() -> None:
    result = compute_features_from_events(
        run_id=RUN_ID,
        events=[sample_auth_failed(), sample_auth_succeeded()],
    )
    response = build_compute_response(result)
    payload = response.model_dump(mode="json", by_alias=True)
    parsed = FeatureComputeResponseV1.model_validate(payload)
    assert parsed.output_checksum.startswith("sha256:")


def test_placeholder_contract_types_validate() -> None:
    _ = FeatureVectorV1
    _ = FeatureWindowV1
    _ = DatasetManifestV1
    _ = OnlineFeatureUpdateV1
    _ = FeatureComputeRequestV1
    _ = FeatureParityCheckResponseV1
