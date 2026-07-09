"""Background snapshot worker for Phase 25."""

from __future__ import annotations

import asyncio
import logging
import os
import signal

from aegis_contracts import SnapshotTriggerReasonV1, load_settings
from aegis_persistence.engine import create_engine, dispose_engine, get_session_maker
from aegis_persistence.object_storage import build_object_storage
from aegis_persistence.orm.tables import DomainEventRow, RunRow
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from aegis_replay.service import ReplayService
from aegis_replay.versioning import DEFAULT_SNAPSHOT_INTERVAL
from sqlalchemy import func, select

logger = logging.getLogger(__name__)


async def _latest_sequence(uow: PostgresUnitOfWork, run_id: str) -> int:
    result = await uow.session.execute(
        select(func.max(DomainEventRow.sequence)).where(DomainEventRow.run_id == run_id)
    )
    value = result.scalar_one_or_none()
    return int(value) if value is not None else 0


async def run_snapshot_worker(
    *,
    poll_interval_seconds: float = 5.0,
    snapshot_interval: int = DEFAULT_SNAPSHOT_INTERVAL,
) -> None:
    settings = load_settings()
    filesystem_root = os.environ.get("AEGIS_REPLAY_STORAGE_DIR")
    in_memory = os.environ.get("AEGIS_REPLAY_IN_MEMORY_STORAGE", "").lower() in {
        "1",
        "true",
        "yes",
    }
    storage = build_object_storage(
        settings,
        in_memory=in_memory and not filesystem_root,
        filesystem_root=filesystem_root,
    )
    service = ReplayService(storage, snapshot_interval=snapshot_interval)
    engine = create_engine(settings)
    session_maker = get_session_maker(settings, engine=engine)
    stop_event = asyncio.Event()

    def handle_signal() -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal)

    logger.info(
        "Snapshot worker started",
        extra={"snapshotInterval": snapshot_interval},
    )
    try:
        while not stop_event.is_set():
            async with PostgresUnitOfWork(session_maker) as uow:
                result = await uow.session.execute(select(RunRow.id, RunRow.status))
                runs = list(result.all())
                for run_id, status in runs:
                    latest = await _latest_sequence(uow, run_id)
                    if latest <= 0:
                        continue
                    created = await service.maybe_create_cadence_snapshot(
                        uow,
                        run_id=run_id,
                        latest_sequence=latest,
                        trigger_reason=SnapshotTriggerReasonV1.SEQUENCE_INTERVAL,
                    )
                    if created is not None:
                        logger.info(
                            "Created cadence snapshot",
                            extra={
                                "runId": run_id,
                                "sequence": created.sequence,
                                "snapshotId": created.snapshot_id,
                            },
                        )
                    if status in {"stopped", "completed", "failed"}:
                        terminal = await service.create_snapshot(
                            uow,
                            run_id=run_id,
                            sequence=latest,
                            trigger_reason=SnapshotTriggerReasonV1.RUN_COMPLETED,
                        )
                        logger.info(
                            "Ensured terminal snapshot",
                            extra={
                                "runId": run_id,
                                "sequence": terminal.sequence,
                                "snapshotId": terminal.snapshot_id,
                            },
                        )
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=poll_interval_seconds)
            except TimeoutError:
                continue
    finally:
        await dispose_engine(engine)
        logger.info("Snapshot worker stopped")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    interval = int(os.environ.get("AEGIS_SNAPSHOT_INTERVAL", str(DEFAULT_SNAPSHOT_INTERVAL)))
    poll = float(os.environ.get("AEGIS_SNAPSHOT_POLL_SECONDS", "5"))
    asyncio.run(run_snapshot_worker(poll_interval_seconds=poll, snapshot_interval=interval))
