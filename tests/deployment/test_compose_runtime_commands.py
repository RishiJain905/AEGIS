"""Regression tests for long-running Compose service commands."""

from __future__ import annotations

from pathlib import Path

import yaml


def test_base_compose_starts_simulator_in_managed_service_mode() -> None:
    compose = yaml.safe_load(Path("docker-compose.yml").read_text(encoding="utf-8"))

    assert compose["services"]["simulator"]["command"] == ["aegis-simulator", "service"]
