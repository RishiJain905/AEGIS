"""Cursor-based event recovery from PostgreSQL."""

from __future__ import annotations

from dataclasses import dataclass

from aegis_contracts import (
    DomainEventEnvelopeV1,
    RealtimeMessageEnvelopeV1,
    WebSocketDeliveryMode,
    WebSocketErrorCode,
)
from aegis_event_streaming.envelope import build_realtime_envelope
from aegis_persistence.repositories.streaming import PostgresEventQueryRepository
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.websocket.config import GatewayConfig
from aegis_api.websocket.errors import GatewayError


@dataclass(frozen=True)
class RecoveryPlan:
    delivery_mode: WebSocketDeliveryMode
    events: list[DomainEventEnvelopeV1]


class SubscriptionRecoveryService:
    def __init__(self, config: GatewayConfig) -> None:
        self._config = config

    async def plan_recovery(
        self,
        session: AsyncSession,
        *,
        run_id: str,
        last_applied_sequence: int,
    ) -> RecoveryPlan:
        repo = PostgresEventQueryRepository(session)
        events = await repo.list_by_run(run_id, from_sequence=last_applied_sequence + 1)
        if not events:
            return RecoveryPlan(
                delivery_mode=WebSocketDeliveryMode.STREAM,
                events=[],
            )

        expected = last_applied_sequence + 1
        gap_detected = False
        largest_gap = 0
        deliverable: list[DomainEventEnvelopeV1] = []

        for event in events:
            if event.sequence < expected:
                continue
            if event.sequence > expected:
                gap_detected = True
                largest_gap = max(largest_gap, event.sequence - expected)
            deliverable.append(event)
            expected = event.sequence + 1

        if gap_detected and largest_gap > self._config.snapshot_gap_threshold:
            raise GatewayError(
                code=WebSocketErrorCode.WS_SEQUENCE_GAP,
                message=(
                    f"Sequence gap exceeds snapshot threshold for run {run_id}: "
                    f"expected {last_applied_sequence + 1}, gap size {largest_gap}"
                ),
                details={
                    "runId": run_id,
                    "fromSequence": last_applied_sequence + 1,
                    "gapSize": largest_gap,
                },
            )

        mode = (
            WebSocketDeliveryMode.BACKFILL
            if last_applied_sequence > 0 or gap_detected
            else WebSocketDeliveryMode.STREAM
        )
        return RecoveryPlan(delivery_mode=mode, events=deliverable)

    async def fill_sequence_gap(
        self,
        session: AsyncSession,
        *,
        run_id: str,
        from_sequence: int,
        to_sequence: int,
    ) -> list[DomainEventEnvelopeV1]:
        if to_sequence < from_sequence:
            return []
        repo = PostgresEventQueryRepository(session)
        events = await repo.list_by_run(
            run_id,
            from_sequence=from_sequence,
            to_sequence=to_sequence,
        )
        expected = from_sequence
        for event in events:
            if event.sequence != expected:
                raise GatewayError(
                    code=WebSocketErrorCode.WS_SEQUENCE_GAP,
                    message=(
                        f"Authoritative gap while backfilling run {run_id}: "
                        f"expected {expected}, received {event.sequence}"
                    ),
                    details={"runId": run_id, "expectedSequence": expected},
                )
            expected += 1
        return events


def envelope_from_domain_event(
    event: DomainEventEnvelopeV1,
    *,
    channel: str = "events",
) -> RealtimeMessageEnvelopeV1:
    return build_realtime_envelope(event, channel=channel)
