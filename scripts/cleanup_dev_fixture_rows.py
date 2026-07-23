"""Delete dev-only junk scenario/run rows from the local database.

The dev Postgres accumulated fixture-shaped junk that leaks into the app now that
the web client talks to the real API: a ``scenario:streaming-test`` scenario and an
ownerless ``run_01ARZ3NDEKTSV4RRFFQ69G5FAV`` run (seed 42) plus all of their
dependent rows. This script removes them.

It is idempotent (safe to re-run; a no-op once clean) and FK-safe: run-scoped
children delete via ``ON DELETE CASCADE`` when the run row is removed, and the
scenario's versions cascade when the scenario is removed. The scenario delete is
guarded so it never removes versions still referenced by some other run.

Usage (local dev, Postgres container up):

    uv run python scripts/cleanup_dev_fixture_rows.py

Connection settings come from the standard AEGIS environment (``load_settings``).
"""

from __future__ import annotations

import asyncio
import sys

from aegis_contracts import load_settings
from aegis_persistence.engine import create_engine, dispose_engine
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncConnection

JUNK_RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
JUNK_SCENARIO_ID = "scenario:streaming-test"


async def _run_scoped_tables(conn: AsyncConnection) -> list[str]:
    """Every public table with a ``run_id`` column, so reporting is not hardcoded."""
    result = await conn.execute(
        text(
            "SELECT table_name FROM information_schema.columns "
            "WHERE column_name = 'run_id' AND table_schema = 'public' "
            "ORDER BY table_name"
        )
    )
    return [row[0] for row in result]


async def _count_run_rows(conn: AsyncConnection, tables: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in tables:
        # table names come from information_schema (not user input); quote defensively.
        result = await conn.execute(
            text(f'SELECT count(*) FROM "{table}" WHERE run_id = :rid'),
            {"rid": JUNK_RUN_ID},
        )
        n = int(result.scalar_one())
        if n:
            counts[table] = n
    return counts


async def _cleanup(conn: AsyncConnection) -> int:
    run_tables = await _run_scoped_tables(conn)

    run_present = int(
        (
            await conn.execute(
                text("SELECT count(*) FROM runs WHERE id = :rid"), {"rid": JUNK_RUN_ID}
            )
        ).scalar_one()
    )
    scenario_present = int(
        (
            await conn.execute(
                text("SELECT count(*) FROM scenarios WHERE id = :sid"),
                {"sid": JUNK_SCENARIO_ID},
            )
        ).scalar_one()
    )

    if not run_present and not scenario_present:
        print("Nothing to clean: junk run and scenario are already absent.")
        return 0

    before = await _count_run_rows(conn, run_tables)
    print(f"Junk run {JUNK_RUN_ID}: present={bool(run_present)}")
    if before:
        print("Dependent run-scoped rows (will cascade on run delete):")
        for table, n in sorted(before.items()):
            print(f"  {table}: {n}")
    else:
        print("No dependent run-scoped rows found for the junk run.")

    deleted_runs = 0
    if run_present:
        result = await conn.execute(
            text("DELETE FROM runs WHERE id = :rid"), {"rid": JUNK_RUN_ID}
        )
        deleted_runs = result.rowcount or 0
        print(f"Deleted {deleted_runs} run row (cascaded dependents).")

    deleted_scenarios = 0
    if scenario_present:
        version_rows = await conn.execute(
            text("SELECT id FROM scenario_versions WHERE scenario_id = :sid"),
            {"sid": JUNK_SCENARIO_ID},
        )
        version_ids = [row[0] for row in version_rows]
        blocking = 0
        if version_ids:
            stmt = text(
                "SELECT count(*) FROM runs WHERE scenario_version_id IN :vids"
            ).bindparams(bindparam("vids", expanding=True))
            blocking = int(
                (await conn.execute(stmt, {"vids": version_ids})).scalar_one()
            )
        if blocking:
            print(
                f"WARNING: scenario {JUNK_SCENARIO_ID} still has {blocking} referencing "
                "run(s); leaving it in place to avoid deleting unrelated runs."
            )
        else:
            result = await conn.execute(
                text("DELETE FROM scenarios WHERE id = :sid"),
                {"sid": JUNK_SCENARIO_ID},
            )
            deleted_scenarios = result.rowcount or 0
            print(
                f"Deleted {deleted_scenarios} scenario row and "
                f"{len(version_ids)} version(s) (cascaded)."
            )

    remaining = await _count_run_rows(conn, run_tables)
    if remaining:
        print("ERROR: dependent rows still present after delete:")
        for table, n in sorted(remaining.items()):
            print(f"  {table}: {n}")
        return 1
    print("Verified: no run-scoped rows remain for the junk run.")
    return 0


async def main() -> int:
    settings = load_settings()
    engine = create_engine(settings)
    try:
        async with engine.begin() as conn:
            return await _cleanup(conn)
    finally:
        await dispose_engine(engine)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
