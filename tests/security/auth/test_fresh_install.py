"""Offline guardrails proving the default boot is a fresh, de-mocked install.

A fresh database + fresh containers must load EMPTY: no pre-seeded runs, incidents,
alerts, or reports. Scenario *definitions* are content and are kept. These tests fail
closed if a migration starts inserting demo domain rows, or if app startup wires the
manual dev seed into the boot path.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MIGRATIONS = _REPO_ROOT / "migrations" / "versions"

# Domain tables whose rows are RUN artifacts (demo data), not content. A migration
# must never INSERT these; scenario/scenario_version content lives in scenario files,
# not migrations.
_FORBIDDEN_INSERT_TABLES = ("runs", "incidents", "alerts", "domain_events", "report_versions")


def test_no_migration_seeds_demo_domain_rows() -> None:
    offenders: list[str] = []
    for path in sorted(_MIGRATIONS.glob("*.py")):
        source = path.read_text(encoding="utf-8").lower()
        for table in _FORBIDDEN_INSERT_TABLES:
            if re.search(rf"insert\s+into\s+{table}\b", source):
                offenders.append(f"{path.name}: INSERT INTO {table}")
    assert not offenders, f"Migrations must not seed demo domain data: {offenders}"


def test_startup_does_not_wire_the_manual_domain_seed() -> None:
    # The demo domain seed (aegis_persistence.seed / seed_database) is a manual CLI
    # only; app startup must never call it, so a fresh boot stays empty.
    main_source = (_REPO_ROOT / "apps" / "api" / "src" / "aegis_api" / "main.py").read_text(
        encoding="utf-8"
    )
    assert "seed_database" not in main_source
    assert "aegis_persistence.seed" not in main_source


def test_docker_compose_ships_real_backend_and_dev_picker_off() -> None:
    compose = (_REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    # Web talks to the real backend (empty until a run produces data), not fixtures.
    assert "NEXT_PUBLIC_AEGIS_DATA_SOURCE: api" in compose
    # The dev identity picker defaults OFF in the shipped stack.
    assert "AEGIS_DEV_AUTH_ENABLED: ${AEGIS_DEV_AUTH_ENABLED:-false}" in compose
