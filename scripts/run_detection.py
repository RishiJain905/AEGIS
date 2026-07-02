#!/usr/bin/env python3
"""Run detection pipeline for a persisted PostgreSQL run."""

from __future__ import annotations

import argparse
import asyncio
import json

from aegis_contracts import load_settings
from aegis_incidents.pipeline import run_detection_for_events
from aegis_ml.baselines.store import DEFAULT_BASELINE_DIR, load_baseline
from aegis_persistence.engine import create_engine, dispose_engine, get_session_maker
from aegis_persistence.repositories.streaming import PostgresEventQueryRepository
from aegis_persistence.unit_of_work import PostgresUnitOfWork


async def _run(*, run_id: str, dry_run: bool) -> dict[str, object]:
    settings = load_settings()
    engine = create_engine(settings)
    session_maker = get_session_maker(settings, engine=engine)
    baselines = None
    if (DEFAULT_BASELINE_DIR / "baseline.json").exists():
        baselines = load_baseline()
    try:
        async with session_maker() as session:
            repo = PostgresEventQueryRepository(session)
            events = await repo.list_by_run(run_id, limit=1_000_000)
        if not events:
            raise SystemExit(f"No events found for run: {run_id}")
        async with PostgresUnitOfWork(session_maker, settings=settings) as uow:
            response = await run_detection_for_events(
                uow,
                run_id=run_id,
                events=events,
                baselines=baselines,
                dry_run=dry_run,
            )
            await uow.commit()
    finally:
        await dispose_engine(engine)
    return response.model_dump(mode="json", by_alias=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate detection rules for a persisted run")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(_run(run_id=args.run_id, dry_run=args.dry_run)), indent=2))


if __name__ == "__main__":
    main()
