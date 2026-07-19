"""Alembic empty/prior-head upgrade and one-step downgrade behavior."""

from __future__ import annotations

import uuid

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from psycopg import sql

pytestmark = pytest.mark.failure_injection


def test_migrations_upgrade_empty_downgrade_and_reupgrade_prior_head(
    settings,
    docker_available,
    monkeypatch,
) -> None:
    database = f"aegis_phase34_{uuid.uuid4().hex[:12]}"
    admin = psycopg.connect(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        dbname=settings.POSTGRES_DB,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        autocommit=True,
    )
    try:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        monkeypatch.setenv("POSTGRES_DB", database)
        config = Config("alembic.ini")
        # Derive the expected head from the migration scripts so this test does
        # not go stale each time a migration is added.
        expected_head = ScriptDirectory.from_config(config).get_current_head()
        command.upgrade(config, "head")
        with psycopg.connect(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            dbname=database,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
        ) as connection:
            head = connection.execute("SELECT version_num FROM alembic_version").fetchone()
            assert head == (expected_head,)

        command.downgrade(config, "-1")
        command.upgrade(config, "head")
        with psycopg.connect(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            dbname=database,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
        ) as connection:
            restored = connection.execute("SELECT version_num FROM alembic_version").fetchone()
            assert restored == (expected_head,)
    finally:
        monkeypatch.setenv("POSTGRES_DB", settings.POSTGRES_DB)
        drop = sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database))
        admin.execute(drop)
        admin.close()
