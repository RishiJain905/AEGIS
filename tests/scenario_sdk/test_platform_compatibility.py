"""Platform compatibility tests."""

from __future__ import annotations

from aegis_scenario_sdk.compatibility import is_platform_version_compatible


def test_current_platform_version_is_compatible() -> None:
    assert is_platform_version_compatible("0.0.0-phase08")


def test_older_phase_workspace_version_satisfies_requirement() -> None:
    assert is_platform_version_compatible("0.0.0-phase08", platform="0.0.0-phase09")


def test_future_platform_version_is_incompatible() -> None:
    assert not is_platform_version_compatible("99.0.0-phase99")
