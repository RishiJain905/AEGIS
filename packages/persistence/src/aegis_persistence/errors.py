"""Persistence-layer errors mapped to contract error codes."""

from __future__ import annotations

from aegis_contracts.errors import ContractErrorCode, ContractValidationError


class StaleRevisionError(ContractValidationError):
    def __init__(
        self,
        *,
        entity_type: str,
        entity_id: str,
        expected_revision: int,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(
            code=ContractErrorCode.STALE_REVISION,
            message=f"Stale revision for {entity_type} {entity_id}",
            details={
                "entityType": entity_type,
                "entityId": entity_id,
                "expectedRevision": expected_revision,
            },
            trace_id=trace_id,
        )


class DuplicateEventError(ContractValidationError):
    def __init__(
        self,
        *,
        run_id: str,
        sequence: int | None = None,
        event_id: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        details: dict[str, object] = {"runId": run_id}
        if sequence is not None:
            details["sequence"] = sequence
        if event_id is not None:
            details["eventId"] = event_id
        super().__init__(
            code=ContractErrorCode.DUPLICATE_EVENT,
            message="Duplicate domain event",
            details=details,
            trace_id=trace_id,
        )


class DuplicateIdempotencyKeyError(ContractValidationError):
    def __init__(
        self,
        *,
        scope: str,
        idempotency_key: str,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(
            code=ContractErrorCode.VALIDATION_FAILED,
            message="Duplicate idempotency key",
            details={"scope": scope, "idempotencyKey": idempotency_key},
            trace_id=trace_id,
        )
