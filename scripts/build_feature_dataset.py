#!/usr/bin/env python3
"""Build a content-addressed feature dataset from persisted run events."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from aegis_contracts import AegisSettings, load_settings
from aegis_ml.features.dataset_builder import build_dataset_from_events
from aegis_persistence.engine import create_engine, dispose_engine, get_session_maker
from aegis_persistence.repositories.postgres import PostgresRunRepository
from aegis_persistence.repositories.streaming import PostgresEventQueryRepository


async def _build(
    *,
    settings: AegisSettings,
    run_id: str,
    output_dir: Path,
    from_sequence: int | None,
    to_sequence: int | None,
) -> dict[str, object]:
    engine = create_engine(settings)
    session_maker = get_session_maker(settings, engine=engine)
    try:
        async with session_maker() as session:
            run = await PostgresRunRepository(session).get_by_id(run_id)
            if run is None:
                raise SystemExit(f"Run not found: {run_id}")
            events = await PostgresEventQueryRepository(session).list_by_run(
                run_id,
                from_sequence=from_sequence,
                to_sequence=to_sequence,
                limit=1_000_000,
            )
            manifest = build_dataset_from_events(run=run, events=events, output_dir=output_dir)
    finally:
        await dispose_engine(engine)
    return manifest.model_dump(mode="json", by_alias=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build feature dataset from persisted events")
    parser.add_argument("--run-id", required=True, help="Source run ID")
    parser.add_argument(
        "--output",
        help="Output directory (default: models/datasets/<run-id>)",
    )
    parser.add_argument("--from-sequence", type=int, default=None)
    parser.add_argument("--to-sequence", type=int, default=None)
    args = parser.parse_args()
    output_dir = Path(args.output or f"models/datasets/{args.run_id}")
    settings = load_settings()
    manifest = asyncio.run(
        _build(
            settings=settings,
            run_id=args.run_id,
            output_dir=output_dir,
            from_sequence=args.from_sequence,
            to_sequence=args.to_sequence,
        )
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
