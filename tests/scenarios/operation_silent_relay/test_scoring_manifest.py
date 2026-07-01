"""Scoring manifest tests for Operation Silent Relay."""

from __future__ import annotations

import yaml

from .helpers import SCENARIO


def test_scoring_weights_valid() -> None:
    manifest = yaml.safe_load((SCENARIO / "manifest.yaml").read_text(encoding="utf-8"))
    criteria = manifest["scoring"]["criteria"]
    assert all(0.0 <= c["weight"] <= 1.0 for c in criteria)
    assert sum(c["weight"] for c in criteria) > 0
    assert manifest["scoring"]["rubric"]
