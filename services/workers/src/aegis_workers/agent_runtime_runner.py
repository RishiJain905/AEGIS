"""Poll queued agent tasks and execute them."""

from __future__ import annotations

import asyncio
import os
import signal
import sys

from aegis_agents.runtime.factory import create_task_executor
from aegis_agents.runtime.recovery import recover_running_tasks
from aegis_contracts import load_settings
from aegis_persistence.engine import create_engine, dispose_engine, get_session_maker
from aegis_persistence.unit_of_work import PostgresUnitOfWork


async def _poll_once(session_maker, executor) -> int:
    processed = 0
    async with PostgresUnitOfWork(session_maker) as uow:
        queued = await uow.agent_tasks.list_queued(limit=10)
    for task in queued:
        async with PostgresUnitOfWork(session_maker) as uow:
            try:
                await executor.execute(uow, task.id)
                processed += 1
            except Exception:
                continue
    return processed


async def _run_loop() -> None:
    settings = load_settings()
    engine = create_engine(settings)
    session_maker = get_session_maker(settings, engine=engine)
    executor = create_task_executor()
    async with PostgresUnitOfWork(session_maker) as uow:
        await recover_running_tasks(uow)
    interval = float(os.environ.get("AEGIS_AGENT_RUNTIME_POLL_SECONDS", "1.0"))
    try:
        while True:
            await _poll_once(session_maker, executor)
            await asyncio.sleep(interval)
    finally:
        await dispose_engine(engine)


def main() -> None:
    def handle_signal(_signum: int, _frame: object) -> None:
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    asyncio.run(_run_loop())


if __name__ == "__main__":
    main()
