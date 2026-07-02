"""Input guard tests."""

from __future__ import annotations

from aegis_contracts.features import FeatureErrorCode
from aegis_ml.features.input_guard import classify_event

from tests.ml.features.helpers import sample_auth_failed, sample_hidden_condition


def test_hidden_truth_is_blocked() -> None:
    rejection = classify_event(sample_hidden_condition())
    assert rejection is not None
    assert rejection.code == FeatureErrorCode.HIDDEN_TRUTH_BLOCKED


def test_unsupported_sim_event_is_rejected() -> None:
    event = sample_auth_failed()
    unsupported = event.model_copy(update={"type": "sim.run.started"})
    rejection = classify_event(unsupported)
    assert rejection is not None
    assert rejection.code == FeatureErrorCode.UNSUPPORTED_EVENT


def test_malformed_payload_missing_asset_id() -> None:
    event = sample_auth_failed()
    malformed = event.model_copy(update={"payload": {"schemaVersion": 1}})
    rejection = classify_event(malformed)
    assert rejection is not None
    assert rejection.code == FeatureErrorCode.MALFORMED_PAYLOAD


def test_valid_telemetry_is_accepted() -> None:
    assert classify_event(sample_auth_failed()) is None
