"""Poll queued agent tasks and execute them."""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import time
from collections.abc import Awaitable, Callable

from aegis_agents.runtime.executor import TaskExecutor
from aegis_agents.runtime.factory import _resolve_task_timeout_seconds, create_task_executor
from aegis_agents.runtime.recovery import (
    DEFAULT_ORPHAN_GRACE_SECONDS,
    recover_orphaned_tasks,
    recover_running_tasks,
)
from aegis_contracts import load_settings
from aegis_persistence.engine import create_engine, dispose_engine, get_session_maker
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def _poll_once(
    session_maker: async_sessionmaker[AsyncSession],
    executor: TaskExecutor,
    *,
    stop_event: asyncio.Event | None = None,
) -> int:
    processed = 0
    async with PostgresUnitOfWork(session_maker) as uow:
        queued = await uow.agent_tasks.list_queued(limit=10)
    for task in queued:
        # Drain semantics: never start a new task once shutdown has been
        # requested. The task already in flight below is awaited to completion.
        if stop_event is not None and stop_event.is_set():
            break
        async with PostgresUnitOfWork(session_maker) as uow:
            try:
                await executor.execute(uow, task.id)
                processed += 1
            except Exception:
                # The executor owns its own commits and persists a terminal task
                # on every failure before re-raising, so nothing here should be
                # pending. Roll back defensively anyway: a bare ``continue`` inside
                # the context manager would otherwise COMMIT any partial, unhandled
                # write (e.g. a claim stranded by an unexpected error), orphaning
                # the task in 'running'.
                await uow.rollback()
                continue
    return processed


async def _recover_orphans_once(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    older_than_seconds: float,
) -> int:
    async with PostgresUnitOfWork(session_maker) as uow:
        return await recover_orphaned_tasks(uow, older_than_seconds=older_than_seconds)


async def _run_poll_loop(
    poll: Callable[[], Awaitable[int]],
    stop_event: asyncio.Event,
    *,
    interval: float,
) -> None:
    """Poll until ``stop_event`` is set, sleeping ``interval`` between passes.

    Each ``poll`` call is awaited to completion before the stop is honoured, so
    an in-flight task drains rather than being abandoned mid-transaction.
    """
    while not stop_event.is_set():
        await poll()
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=interval)


async def _run_loop(stop_event: asyncio.Event | None = None) -> None:
    settings = load_settings()
    engine = create_engine(settings)
    session_maker = get_session_maker(settings, engine=engine)
    executor = create_task_executor()
    stop_event = stop_event or asyncio.Event()
    # Startup recovery: any RUNNING task belongs to a prior (dead) process — requeue
    # it (attempt++) so it is retried, or fail it if it has exhausted retries.
    async with PostgresUnitOfWork(session_maker) as uow:
        await recover_running_tasks(uow)
    interval = float(os.environ.get("AEGIS_AGENT_RUNTIME_POLL_SECONDS", "1.0"))
    # Periodic orphan sweep: a task stranded in 'running' past the task timeout plus
    # a grace margin (so a live slow-model task is never stolen from its executor)
    # is requeued/failed. Cadence is env-tunable and independent of the fast poll.
    orphan_grace = float(
        os.environ.get("AEGIS_AGENT_ORPHAN_GRACE_SECONDS", str(DEFAULT_ORPHAN_GRACE_SECONDS))
    )
    orphan_age = _resolve_task_timeout_seconds() + orphan_grace
    recovery_interval = float(os.environ.get("AEGIS_AGENT_ORPHAN_SWEEP_SECONDS", "30.0"))
    last_recovery = time.monotonic()

    async def poll() -> int:
        nonlocal last_recovery
        processed = await _poll_once(session_maker, executor, stop_event=stop_event)
        now = time.monotonic()
        if now - last_recovery >= recovery_interval:
            last_recovery = now
            with contextlib.suppress(Exception):
                await _recover_orphans_once(session_maker, older_than_seconds=orphan_age)
        return processed

    try:
        await _run_poll_loop(poll, stop_event, interval=interval)
    finally:
        await dispose_engine(engine)


async def _amain() -> None:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            # add_signal_handler is unavailable on some platforms (e.g. Windows);
            # fall back to the signal module, which only sets a cooperative flag.
            signal.signal(sig, lambda _signum, _frame: stop_event.set())
    await _run_loop(stop_event)


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
