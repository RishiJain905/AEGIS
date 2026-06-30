"""Schema version matrix tests."""

from __future__ import annotations

import pytest
from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.versioning import (
    GRAPH_NODE_SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    assert_supported_schema_version,
)


@pytest.mark.parametrize(
    ("contract_name", "supported_versions"),
    sorted(SUPPORTED_SCHEMA_VERSIONS.items()),
)
def test_supported_versions_accepted(
    contract_name: str,
    supported_versions: frozenset[int],
) -> None:
    for version in supported_versions:
        assert_supported_schema_version(contract_name, version)


def test_graph_node_v1_version_constant() -> None:
    assert GRAPH_NODE_SCHEMA_VERSION == 1


def test_unsupported_version_rejected() -> None:
    with pytest.raises(ContractValidationError) as exc_info:
        assert_supported_schema_version("domain_event", 99)
    assert exc_info.value.code == ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED
    assert exc_info.value.details["supportedVersions"] == [1]
