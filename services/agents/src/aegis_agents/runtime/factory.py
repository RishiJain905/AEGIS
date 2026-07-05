"""Runtime wiring helpers."""

from __future__ import annotations

from aegis_agents.providers.factory import create_generation_service
from aegis_agents.providers.generation import AgentGenerationFacade
from aegis_agents.runtime.executor import TaskExecutor
from sqlalchemy.ext.asyncio import AsyncSession


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
    timeout_seconds: float = 30.0,
) -> TaskExecutor:
    return TaskExecutor(
        generation=create_generation_facade(session=session, force_in_memory=force_in_memory),
        timeout_seconds=timeout_seconds,
    )
