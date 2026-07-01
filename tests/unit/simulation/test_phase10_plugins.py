"""Tests for new Phase 10 telemetry plugins."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_simulation_domain.handlers import execute_plugin
from aegis_simulation_domain.random_streams import SeededRandomStreams
from aegis_simulation_domain.world_state import WorldState


def _execute(plugin_id: str, config: dict, asset_id: str, seed: int = 42) -> list[str]:
    world = WorldState()
    rng = SeededRandomStreams(seed)
    sim_time = datetime(2026, 1, 1, tzinfo=UTC)
    result = execute_plugin(
        plugin_id=plugin_id,
        config=config,
        target_asset_id=asset_id,
        world=world,
        run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        run_seed=seed,
        sequence=1,
        sim_time=sim_time,
        recorded_at_epoch=sim_time,
        rng=rng,
    )
    return [event.type for event in result.events]


def test_database_query_plugin_emits_event() -> None:
    types = _execute(
        "telemetry.database_query",
        {"queriesPerInterval": 5, "anomalyRate": 1.0},
        "asset:database-audit-store",
    )
    assert types == ["telemetry.database.query"]


def test_deployment_event_plugin_emits_event() -> None:
    types = _execute(
        "telemetry.deployment_event",
        {"deploymentsPerInterval": 1, "failureRate": 1.0},
        "asset:svc-cicd-pipeline",
    )
    assert types == ["telemetry.deployment.event"]


def test_process_activity_plugin_emits_event() -> None:
    types = _execute(
        "telemetry.process_activity",
        {"eventsPerInterval": 3, "suspiciousRate": 1.0},
        "asset:device-analyst-01",
    )
    assert types == ["telemetry.process.activity"]


def test_ai_inference_plugin_emits_event() -> None:
    types = _execute(
        "telemetry.ai_inference",
        {"inferencesPerInterval": 4, "anomalyRate": 1.0},
        "asset:svc-routing-inference-gateway",
    )
    assert types == ["telemetry.ai.inference"]


def test_new_plugins_are_deterministic() -> None:
    first = _execute(
        "telemetry.database_query",
        {"queriesPerInterval": 5, "anomalyRate": 0.5},
        "asset:database-audit-store",
        seed=99,
    )
    second = _execute(
        "telemetry.database_query",
        {"queriesPerInterval": 5, "anomalyRate": 0.5},
        "asset:database-audit-store",
        seed=99,
    )
    assert first == second
