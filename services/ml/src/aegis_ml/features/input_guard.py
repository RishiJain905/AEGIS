"""Input validation and hidden-truth guards for feature extraction."""

from __future__ import annotations

from aegis_contracts.events import DomainEventEnvelopeV1
from aegis_contracts.features import FeatureErrorCode, FeatureRejectionV1

from aegis_ml.features.schema_registry import HIDDEN_TRUTH_PREFIXES, TELEMETRY_EVENT_TYPES


def classify_event(event: DomainEventEnvelopeV1) -> FeatureRejectionV1 | None:
    event_type = event.type
    if any(event_type.startswith(prefix) for prefix in HIDDEN_TRUTH_PREFIXES):
        return FeatureRejectionV1(
            event_id=event.event_id,
            sequence=event.sequence,
            code=FeatureErrorCode.HIDDEN_TRUTH_BLOCKED,
            message=f"Hidden scenario truth event blocked from features: {event_type}",
        )
    if not event_type.startswith("telemetry."):
        return FeatureRejectionV1(
            event_id=event.event_id,
            sequence=event.sequence,
            code=FeatureErrorCode.UNSUPPORTED_EVENT,
            message=f"Unsupported event type for feature extraction: {event_type}",
        )
    if event_type not in TELEMETRY_EVENT_TYPES:
        return FeatureRejectionV1(
            event_id=event.event_id,
            sequence=event.sequence,
            code=FeatureErrorCode.UNSUPPORTED_EVENT,
            message=f"Telemetry event type not registered for features: {event_type}",
        )
    asset_id = event.payload.get("assetId")
    if not isinstance(asset_id, str) or not asset_id:
        return FeatureRejectionV1(
            event_id=event.event_id,
            sequence=event.sequence,
            code=FeatureErrorCode.MALFORMED_PAYLOAD,
            message="Telemetry payload missing assetId",
        )
    return None


def extract_asset_id(event: DomainEventEnvelopeV1) -> str:
    asset_id = event.payload.get("assetId")
    if not isinstance(asset_id, str) or not asset_id:
        raise ValueError("assetId required")
    return asset_id
