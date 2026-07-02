#!/usr/bin/env python3
"""Run Isolation Forest anomaly detection on a persisted run."""

from __future__ import annotations

import argparse
import asyncio
import json

from aegis_contracts import AegisSettings, load_settings
from aegis_incidents.model_pipeline import run_model_detection_for_events
from aegis_persistence.engine import create_engine, dispose_engine, get_session_maker
from aegis_persistence.repositories.streaming import PostgresEventQueryRepository
from aegis_persistence.unit_of_work import PostgresUnitOfWork


async def _run(
    *,
    settings: AegisSettings,
    run_id: str,
    dry_run: bool,
) -> dict[str, object]:
    engine = create_engine(settings)
    session_maker = get_session_maker(settings, engine=engine)
    try:
        async with session_maker() as session:
            events = await PostgresEventQueryRepository(session).list_by_run(
                run_id,
                limit=1_000_000,
            )
        if not events:
            raise SystemExit(f"No events found for run: {run_id}")
        async with PostgresUnitOfWork(session_maker, settings=settings) as uow:
            response = await run_model_detection_for_events(
                uow,
                run_id=run_id,
                events=events,
                dry_run=dry_run,
            )
    finally:
        await dispose_engine(engine)
    return response.model_dump(mode="json", by_alias=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run anomaly detection on persisted run")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    settings = load_settings()
    result = asyncio.run(_run(settings=settings, run_id=args.run_id, dry_run=args.dry_run))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
