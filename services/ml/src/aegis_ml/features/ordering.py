"""Deterministic event ordering for feature extraction."""

from __future__ import annotations

from aegis_contracts.events import DomainEventEnvelopeV1
from aegis_contracts.features import FeatureErrorCode, FeatureRejectionV1


def sort_events_by_sequence(
    events: list[DomainEventEnvelopeV1],
) -> list[DomainEventEnvelopeV1]:
    return sorted(events, key=lambda event: (event.sequence, event.event_id))


def detect_out_of_order(
    events: list[DomainEventEnvelopeV1],
    *,
    expected_start_sequence: int = 0,
) -> list[FeatureRejectionV1]:
    rejections: list[FeatureRejectionV1] = []
    previous = expected_start_sequence - 1
    for event in events:
        if event.sequence <= previous:
            rejections.append(
                FeatureRejectionV1(
                    event_id=event.event_id,
                    sequence=event.sequence,
                    code=FeatureErrorCode.OUT_OF_ORDER,
                    message=(f"Event sequence {event.sequence} is not strictly after {previous}"),
                )
            )
        previous = max(previous, event.sequence)
    return rejections
