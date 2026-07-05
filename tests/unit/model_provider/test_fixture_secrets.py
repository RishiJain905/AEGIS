"""Recorded fixtures must not contain secret material."""

from __future__ import annotations

from pathlib import Path

from aegis_model_provider.redaction import contains_secret_material


def test_recorded_fixtures_have_no_secrets() -> None:
    root = Path("fixtures/model-responses")
    for path in root.rglob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert not contains_secret_material(text), f"Secret pattern found in {path}"
