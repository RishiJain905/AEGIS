"""Runtime wiring helpers."""

from __future__ import annotations

import os

from aegis_agents.providers.factory import create_generation_service
from aegis_agents.providers.generation import AgentGenerationFacade
from aegis_agents.runtime.executor import TaskExecutor
from aegis_agents.runtime.tool_loop import DEFAULT_TOOL_LOOP_MAX_ITERATIONS
from sqlalchemy.ext.asyncio import AsyncSession

# Wall-clock ceiling for a single agent task. Kept generous by default because a
# local reasoning model (llama-serve) can take tens of seconds per turn; a task
# that exceeds this still fails soft (TIMED_OUT -> failed turn shown in the chat),
# so the ceiling only bounds how long the operator waits. Override with
# AEGIS_AGENT_TASK_TIMEOUT_SECONDS. The deterministic mock provider used in CI
# returns instantly, so this ceiling never affects offline tests.
#
# Note the ceiling is now shared across every model call a task makes, not just
# one: the tool loop spends the same budget on investigate-then-answer, and stops
# starting new rounds once too little of it is left (see MIN_LOOP_ITERATION_SECONDS).
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


def _resolve_tool_loop_max_iterations() -> int:
    """How many investigate-then-answer rounds one task may take.

    Each round costs an extra model call, so this is the main cost and latency
    lever on the loop. Lives beside the task timeout as a plain env read rather
    than in ``AegisSettings`` for the same reason that one does: the executor must
    stay constructible without a full settings object (harnesses and offline
    tests build one directly). Values below 1 are clamped up — 0 would silently
    restore the single-shot runtime, which is a regression, not a configuration.
    """
    raw = os.environ.get("AEGIS_AGENT_TOOL_LOOP_MAX_ITERATIONS")
    if raw is None:
        return DEFAULT_TOOL_LOOP_MAX_ITERATIONS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_TOOL_LOOP_MAX_ITERATIONS
    return max(1, value)


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
    tool_loop_max_iterations: int | None = None,
) -> TaskExecutor:
    return TaskExecutor(
        generation=create_generation_facade(session=session, force_in_memory=force_in_memory),
        timeout_seconds=(
            _resolve_task_timeout_seconds() if timeout_seconds is None else timeout_seconds
        ),
        tool_loop_max_iterations=(
            _resolve_tool_loop_max_iterations()
            if tool_loop_max_iterations is None
            else tool_loop_max_iterations
        ),
    )
