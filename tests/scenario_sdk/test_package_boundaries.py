"""Package boundary tests."""

from __future__ import annotations

import importlib.metadata


def test_scenario_sdk_has_no_application_dependencies() -> None:
    requires = importlib.metadata.requires("aegis-scenario-sdk") or []
    dependency_names = {requirement.split()[0] for requirement in requires}
    forbidden = {"aegis-api", "aegis-persistence", "aegis-simulation", "aegis-workers"}
    assert forbidden.isdisjoint(dependency_names)
    assert "aegis-contracts" in dependency_names
