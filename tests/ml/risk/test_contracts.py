"""Contract fixture round-trip."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aegis_contracts import parse_contract
from aegis_contracts.risk import (
    AssetRiskScoreV1,
    RiskComputeRequestV1,
    RiskEngineConfigV1,
    RiskInputV1,
    RiskProjectionDeltaV1,
)

FIXTURE_DIR = Path("tests/contract/fixtures/valid")


@pytest.mark.parametrize(
    "fixture_name,model",
    [
        ("risk_input_v1.json", RiskInputV1),
        ("risk_engine_config_v1.json", RiskEngineConfigV1),
        ("asset_risk_score_v1.json", AssetRiskScoreV1),
        ("risk_projection_delta_v1.json", RiskProjectionDeltaV1),
        ("risk_compute_request_v1.json", RiskComputeRequestV1),
    ],
)
def test_risk_fixture_round_trip(fixture_name: str, model: type[object]) -> None:
    payload = json.loads((FIXTURE_DIR / fixture_name).read_text(encoding="utf-8"))
    parsed = parse_contract(model, payload)
    dumped = parsed.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert dumped == payload
