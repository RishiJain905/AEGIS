#!/usr/bin/env python3
"""Run graph risk propagation for a persisted PostgreSQL run."""

from __future__ import annotations

import argparse
import asyncio
import json

from aegis_contracts import load_settings
from aegis_incidents.risk_pipeline import run_risk_propagation_for_run
from aegis_persistence.engine import create_engine, dispose_engine, get_session_maker
from aegis_persistence.repositories.postgres import PostgresGraphSnapshotRepository
from aegis_persistence.unit_of_work import PostgresUnitOfWork


async def _run(*, run_id: str, dry_run: bool) -> dict[str, object]:
    settings = load_settings()
    engine = create_engine(settings)
    session_maker = get_session_maker(settings, engine=engine)
    try:
        async with session_maker() as session:
            snapshot = await PostgresGraphSnapshotRepository(session).get_latest_for_run(run_id)
        if snapshot is None:
            raise SystemExit(f"No graph snapshot found for run: {run_id}")
        async with PostgresUnitOfWork(session_maker, settings=settings) as uow:
            response = await run_risk_propagation_for_run(
                uow,
                run_id=run_id,
                snapshot=snapshot,
                dry_run=dry_run,
            )
            await uow.commit()
    finally:
        await dispose_engine(engine)
    return response.model_dump(mode="json", by_alias=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run graph risk propagation for a persisted run")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(_run(run_id=args.run_id, dry_run=args.dry_run)), indent=2))


if __name__ == "__main__":
    main()
