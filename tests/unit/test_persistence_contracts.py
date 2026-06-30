"""Unit tests for persistence contract fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from aegis_contracts import IdempotencyRecordV1, ObjectMetadataReferenceV1, parse_contract


def test_idempotency_record_fixture_round_trip() -> None:
    fixture_path = Path("tests/contract/fixtures/valid/idempotency_record_v1.json")
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    record = parse_contract(IdempotencyRecordV1, payload)
    assert record.scope == "api:runs:create"
    assert record.replayed is False


def test_object_metadata_reference_fixture_round_trip() -> None:
    fixture_path = Path("tests/contract/fixtures/valid/object_metadata_reference_v1.json")
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    reference = parse_contract(ObjectMetadataReferenceV1, payload)
    assert reference.size_bytes == 4096
