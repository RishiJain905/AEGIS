"""Poll queued agent tasks and execute them."""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
from collections.abc import Awaitable, Callable

from aegis_agents.runtime.executor import TaskExecutor
from aegis_agents.runtime.factory import create_task_executor
from aegis_agents.runtime.recovery import recover_running_tasks
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
                continue
    return processed


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
    async with PostgresUnitOfWork(session_maker) as uow:
        await recover_running_tasks(uow)
    interval = float(os.environ.get("AEGIS_AGENT_RUNTIME_POLL_SECONDS", "1.0"))

    async def poll() -> int:
        return await _poll_once(session_maker, executor, stop_event=stop_event)

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
