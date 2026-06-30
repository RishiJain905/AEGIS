"""Primitive validator unit tests."""

from __future__ import annotations

import pytest
from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.graph import GraphNodeV1
from aegis_contracts.parsing import parse_contract
from aegis_contracts.primitives import validate_authored_id, validate_runtime_id


def test_validate_authored_id_accepts_namespaced_id() -> None:
    assert validate_authored_id("asset:svc-api-gateway") == "asset:svc-api-gateway"


def test_validate_authored_id_rejects_invalid() -> None:
    with pytest.raises(ContractValidationError) as exc_info:
        validate_authored_id("invalid")
    assert exc_info.value.code == ContractErrorCode.INVALID_IDENTIFIER


def test_validate_runtime_id_accepts_prefixed_ulid() -> None:
    value = "evt_01ARZ3NDEKTSV4RRFFQ69G5FAW"
    assert validate_runtime_id("evt", value) == value


def test_validate_runtime_id_rejects_wrong_prefix() -> None:
    with pytest.raises(ContractValidationError) as exc_info:
        validate_runtime_id("evt", "run_01ARZ3NDEKTSV4RRFFQ69G5FAV")
    assert exc_info.value.code == ContractErrorCode.INVALID_IDENTIFIER


def test_graph_node_parses_minimal_payload() -> None:
    payload = {
        "schemaVersion": 1,
        "id": "asset:svc-api-gateway",
        "entityType": "asset",
        "assetType": "service",
        "label": "API Gateway",
        "riskScore": 0.5,
        "criticality": 0.5,
        "status": "normal",
        "revision": 1,
    }
    parsed = parse_contract(GraphNodeV1, payload)
    assert parsed.id == "asset:svc-api-gateway"
