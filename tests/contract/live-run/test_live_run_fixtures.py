"""Contract tests for Phase 13 live-run fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aegis_contracts.fixtures import FIXTURE_MODEL_MAP
from aegis_contracts.parsing import parse_contract

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "contract" / "fixtures" / "valid"


@pytest.mark.parametrize(
    "fixture_name",
    [
        "live_run_v1",
        "snapshot_bootstrap_v1",
        "connection_health_v1",
        "run_create_request_v1",
        "run_command_response_v1",
    ],
)
def test_live_run_fixture_roundtrip(fixture_name: str) -> None:
    model = FIXTURE_MODEL_MAP[fixture_name]
    payload = json.loads((FIXTURES / f"{fixture_name}.json").read_text(encoding="utf-8"))
    parsed = parse_contract(model, payload)
    assert parsed.model_dump(by_alias=True)["schemaVersion"] == payload["schemaVersion"]
