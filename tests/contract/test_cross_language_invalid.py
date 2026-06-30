"""Invalid fixture failure-path tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.graph import GraphNodeV1
from aegis_contracts.parsing import parse_contract
from aegis_contracts.versioning import assert_supported_schema_version
from pydantic import ValidationError

INVALID_DIR = Path(__file__).resolve().parent / "fixtures" / "invalid"


def test_unknown_schema_version_raises_structured_error() -> None:
    payload = json.loads((INVALID_DIR / "unknown_schema_version.json").read_text(encoding="utf-8"))
    with pytest.raises((ContractValidationError, ValidationError)) as exc_info:
        parse_contract(GraphNodeV1, payload)
    error = exc_info.value
    if isinstance(error, ContractValidationError):
        assert error.code == ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED


def test_invalid_asset_id_raises_structured_error() -> None:
    payload = json.loads((INVALID_DIR / "invalid_asset_id.json").read_text(encoding="utf-8"))
    with pytest.raises((ContractValidationError, ValidationError)):
        parse_contract(GraphNodeV1, payload)


def test_missing_required_field_raises_validation_error() -> None:
    payload = json.loads((INVALID_DIR / "missing_required_field.json").read_text(encoding="utf-8"))
    with pytest.raises((ContractValidationError, ValidationError)):
        parse_contract(GraphNodeV1, payload)


def test_invalid_timestamp_raises_validation_error() -> None:
    from aegis_contracts.entities import RunV1

    payload = json.loads((INVALID_DIR / "invalid_timestamp.json").read_text(encoding="utf-8"))
    with pytest.raises((ContractValidationError, ValidationError)):
        parse_contract(RunV1, payload)


def test_assert_supported_schema_version_unknown_contract() -> None:
    with pytest.raises(ContractValidationError) as exc_info:
        assert_supported_schema_version("nonexistent_contract", 1)
    assert exc_info.value.code == ContractErrorCode.VALIDATION_FAILED


def test_assert_supported_schema_version_unsupported_version() -> None:
    with pytest.raises(ContractValidationError) as exc_info:
        assert_supported_schema_version("graph_node", 99)
    assert exc_info.value.code == ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED
