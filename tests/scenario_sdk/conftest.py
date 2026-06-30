"""Scenario SDK test path constants."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "scenarios" / "_fixtures"
SILENT_RELAY = ROOT / "scenarios" / "operation-silent-relay"
