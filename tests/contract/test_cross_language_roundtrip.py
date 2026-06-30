"""Round-trip serialization tests for shared contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aegis_contracts.fixtures import FIXTURE_MODEL_MAP
from aegis_contracts.parsing import parse_contract

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "valid"


@pytest.mark.parametrize("fixture_name", sorted(FIXTURE_MODEL_MAP.keys()))
def test_python_round_trip_preserves_semantics(fixture_name: str) -> None:
    fixture_path = FIXTURES_DIR / f"{fixture_name}.json"
    original = json.loads(fixture_path.read_text(encoding="utf-8"))
    model = FIXTURE_MODEL_MAP[fixture_name]
    parsed = parse_contract(model, original)
    serialized = parsed.model_dump(by_alias=True, mode="json")
    reparsed = parse_contract(model, serialized)
    assert reparsed.model_dump(by_alias=True, mode="json") == serialized
