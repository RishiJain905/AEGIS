"""Ordering and duplicate handling tests."""

from __future__ import annotations

from aegis_contracts.features import FeatureErrorCode
from aegis_ml.features.engine import compute_features_from_events

from tests.ml.features.helpers import RUN_ID, sample_auth_failed, sample_auth_succeeded


def test_duplicate_event_is_rejected() -> None:
    event = sample_auth_failed()
    result = compute_features_from_events(
        run_id=RUN_ID,
        events=[event, event.model_copy(update={"sequence": 2})],
    )
    assert any(
        rejection.code == FeatureErrorCode.DUPLICATE_EVENT for rejection in result.rejections
    )


def test_out_of_order_detection() -> None:
    from aegis_ml.features.ordering import detect_out_of_order

    first = sample_auth_failed(sequence=2)
    second = sample_auth_succeeded(sequence=1)
    rejections = detect_out_of_order([first, second])
    assert any(rejection.code == FeatureErrorCode.OUT_OF_ORDER for rejection in rejections)
