"""Integration tests for Alembic migrations."""

from __future__ import annotations

import pytest
from aegis_persistence.engine import create_engine
from sqlalchemy import inspect, text


@pytest.mark.asyncio
async def test_schema_reproducible_from_migrations(
    settings,
    migrated_database,
) -> None:
    engine = create_engine(settings)
    async with engine.connect() as connection:
        def collect_tables(sync_conn: object) -> set[str]:
            inspector = inspect(sync_conn)
            return set(inspector.get_table_names())

        tables = await connection.run_sync(collect_tables)

    expected = {
        "scenarios",
        "scenario_versions",
        "runs",
        "asset_instances",
        "relationship_instances",
        "domain_events",
        "outbox",
        "alerts",
        "incidents",
        "evidence",
        "hypotheses",
        "agent_sessions",
        "tools",
        "action_proposals",
        "approvals",
        "executed_actions",
        "model_manifests",
        "model_scores",
        "stored_objects",
        "graph_snapshots",
        "idempotency_records",
        "alembic_version",
    }
    assert expected.issubset(tables)

    async with engine.connect() as connection:
        result = await connection.execute(
            text(
                """
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'domain_events'
                AND indexname IN (
                    'uq_domain_events_run_sequence',
                    'ix_domain_events_run_sim_time',
                    'ix_domain_events_run_event_type'
                )
                """
            )
        )
        indexes = {row[0] for row in result.fetchall()}
        assert "uq_domain_events_run_sequence" in indexes
        assert "ix_domain_events_run_sim_time" in indexes
        assert "ix_domain_events_run_event_type" in indexes
