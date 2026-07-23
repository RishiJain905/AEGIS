"""Runtime wiring helpers."""

from __future__ import annotations

import os

from aegis_agents.providers.factory import create_generation_service
from aegis_agents.providers.generation import AgentGenerationFacade
from aegis_agents.runtime.executor import TaskExecutor
from sqlalchemy.ext.asyncio import AsyncSession

# Wall-clock ceiling for a single agent task. Kept generous by default because a
# local reasoning model (llama-serve) can take tens of seconds per turn; a task
# that exceeds this still fails soft (TIMED_OUT -> failed turn shown in the chat),
# so the ceiling only bounds how long the operator waits. Override with
# AEGIS_AGENT_TASK_TIMEOUT_SECONDS. The deterministic mock provider used in CI
# returns instantly, so this ceiling never affects offline tests.
_DEFAULT_TASK_TIMEOUT_SECONDS = 120.0


def _resolve_task_timeout_seconds() -> float:
    raw = os.environ.get("AEGIS_AGENT_TASK_TIMEOUT_SECONDS")
    if raw is None:
        return _DEFAULT_TASK_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return _DEFAULT_TASK_TIMEOUT_SECONDS
    return value if value > 0 else _DEFAULT_TASK_TIMEOUT_SECONDS


def create_generation_facade(
    *,
    session: AsyncSession | None = None,
    force_in_memory: bool = False,
) -> AgentGenerationFacade:
    service = create_generation_service(session=session, force_in_memory=force_in_memory)
    return AgentGenerationFacade(service)


def create_task_executor(
    *,
    session: AsyncSession | None = None,
    force_in_memory: bool = False,
    timeout_seconds: float | None = None,
) -> TaskExecutor:
    return TaskExecutor(
        generation=create_generation_facade(session=session, force_in_memory=force_in_memory),
        timeout_seconds=(
            _resolve_task_timeout_seconds() if timeout_seconds is None else timeout_seconds
        ),
    )
