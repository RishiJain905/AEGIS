"""Cross-language golden fixture validation tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aegis_contracts.fixtures import FIXTURE_MODEL_MAP
from aegis_contracts.parsing import parse_contract

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "valid"


@pytest.mark.parametrize("fixture_name", sorted(FIXTURE_MODEL_MAP.keys()))
def test_valid_fixture_parses(fixture_name: str) -> None:
    fixture_path = FIXTURES_DIR / f"{fixture_name}.json"
    assert fixture_path.exists(), f"Missing fixture: {fixture_path}"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    model = FIXTURE_MODEL_MAP[fixture_name]
    parsed = parse_contract(model, payload)
    assert parsed is not None
