"""Behavior plugin registry tests."""

from __future__ import annotations

from aegis_scenario_sdk.plugins.registry import (
    is_known_plugin,
    list_plugin_ids,
    validate_plugin_config,
)


def test_allowlisted_plugins_are_known() -> None:
    for plugin_id in list_plugin_ids():
        assert is_known_plugin(plugin_id)


def test_unknown_plugin_config_rejected() -> None:
    error = validate_plugin_config("telemetry.unapproved", {})
    assert error is not None


def test_valid_plugin_config_accepted() -> None:
    error = validate_plugin_config(
        "telemetry.auth_attempt",
        {"failureRate": 0.1, "successRate": 0.9},
    )
    assert error is None
