"""Unit tests for persistence error mapping."""

from __future__ import annotations

from aegis_contracts.errors import ContractErrorCode
from aegis_persistence.errors import (
    DuplicateEventError,
    DuplicateIdempotencyKeyError,
    StaleRevisionError,
)


def test_stale_revision_maps_to_contract_code() -> None:
    error = StaleRevisionError(
        entity_type="run",
        entity_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAX",
        expected_revision=1,
    )
    assert error.code == ContractErrorCode.STALE_REVISION


def test_duplicate_event_maps_to_contract_code() -> None:
    error = DuplicateEventError(
        run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAX",
        sequence=1,
        event_id="evt_01ARZ3NDEKTSV4RRFFQ69G5FAW",
    )
    assert error.code == ContractErrorCode.DUPLICATE_EVENT


def test_duplicate_idempotency_key_error_details() -> None:
    error = DuplicateIdempotencyKeyError(scope="api:test", idempotency_key="key-1")
    assert error.code == ContractErrorCode.VALIDATION_FAILED
    assert error.details["scope"] == "api:test"
