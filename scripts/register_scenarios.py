#!/usr/bin/env python3
"""Idempotently register scenario packages into the operations catalogue.

Upserts a ``scenarios`` row and a ``scenario_versions`` row (the tables backing
``GET /api/v1/scenarios``) from one or more scenario package directories, so a
package authored under ``scenarios/`` becomes visible in the catalogue without a
run having to be created first.

Idempotent: re-running updates the name/description/version metadata in place
rather than failing on the existing primary key.

Usage::

    uv run python scripts/register_scenarios.py scenarios/synthetic-training
    uv run python scripts/register_scenarios.py            # registers the defaults below
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
from pathlib import Path

from aegis_contracts import load_settings
from aegis_contracts.entities import ScenarioV1, ScenarioVersionV1
from aegis_contracts.versioning import (
    SCENARIO_SCHEMA_VERSION,
    SCENARIO_VERSION_SCHEMA_VERSION,
)
from aegis_persistence.engine import create_engine, dispose_engine, get_session_maker
from aegis_persistence.mappers import domain_to_payload
from aegis_persistence.orm.tables import ScenarioRow, ScenarioVersionRow
from aegis_simulation_domain import SimulationEngine
from sqlalchemy.ext.asyncio import AsyncSession

# Package directories registered when no explicit path is supplied on the CLI.
DEFAULT_PACKAGES: tuple[str, ...] = ("scenarios/synthetic-training",)

# Registration is authored deterministically so re-runs do not churn timestamps.
_REGISTERED_AT = datetime(2026, 1, 1, tzinfo=UTC)


async def _register_package(session: AsyncSession, package_dir: Path) -> dict[str, str]:
    manifest = SimulationEngine.load_manifest(package_dir)
    scenario_id = manifest.metadata.scenario_id
    scenario_version_id = f"scenario-version:{manifest.metadata.version}"

    scenario = ScenarioV1(
        schema_version=SCENARIO_SCHEMA_VERSION,
        id=scenario_id,
        name=manifest.metadata.name,
        description=manifest.metadata.description,
        created_at=_REGISTERED_AT,
    )
    scenario_version = ScenarioVersionV1(
        schema_version=SCENARIO_VERSION_SCHEMA_VERSION,
        id=scenario_version_id,
        scenario_id=scenario_id,
        version=manifest.metadata.version,
        required_platform_version=manifest.metadata.required_platform_version,
        published_at=_REGISTERED_AT,
    )

    # session.merge performs an upsert keyed on the primary key: it inserts when the
    # row is absent and updates the mutable columns when it already exists.
    await session.merge(
        ScenarioRow(
            id=scenario.id,
            name=scenario.name,
            payload=domain_to_payload(scenario),
            created_at=scenario.created_at,
        )
    )
    await session.merge(
        ScenarioVersionRow(
            id=scenario_version.id,
            scenario_id=scenario_version.scenario_id,
            version=scenario_version.version,
            payload=domain_to_payload(scenario_version),
            published_at=scenario_version.published_at,
        )
    )
    return {
        "scenarioId": scenario_id,
        "name": manifest.metadata.name,
        "scenarioVersionId": scenario_version_id,
        "version": manifest.metadata.version,
    }


async def _run(package_dirs: list[Path]) -> list[dict[str, str]]:
    settings = load_settings()
    engine = create_engine(settings)
    session_maker = get_session_maker(settings, engine=engine)
    registered: list[dict[str, str]] = []
    try:
        async with session_maker() as session:
            for package_dir in package_dirs:
                registered.append(await _register_package(session, package_dir))
            await session.commit()
    finally:
        await dispose_engine(engine)
    return registered


def main() -> None:
    parser = argparse.ArgumentParser(description="Register scenario packages into the catalogue")
    parser.add_argument(
        "packages",
        nargs="*",
        help="Scenario package directories (defaults to the built-in tutorial scenario)",
    )
    args = parser.parse_args()

    raw_paths = args.packages or list(DEFAULT_PACKAGES)
    package_dirs = [Path(path) for path in raw_paths]
    for package_dir in package_dirs:
        if not (package_dir / "manifest.yaml").exists():
            parser.error(f"No manifest.yaml under {package_dir}")

    registered = asyncio.run(_run(package_dirs))
    for row in registered:
        print(
            f"registered {row['scenarioId']} ({row['name']}) "
            f"version={row['version']} -> {row['scenarioVersionId']}"
        )


if __name__ == "__main__":
    main()
