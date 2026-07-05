#!/usr/bin/env python3
"""Run Phase 19 agent runtime harness checks."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from aegis_agents.runtime.errors import AgentRuntimeError
from aegis_agents.runtime.factory import create_task_executor
from aegis_agents.runtime.harness import seed_harness_incident
from aegis_agents.runtime.registry import DEFAULT_AGENT_REGISTRY
from aegis_agents.runtime.session_service import AgentSessionService
from aegis_agents.runtime.task_service import AgentTaskService
from aegis_agents.tools.permissions import authorize_tool_call
from aegis_agents.tools.registry import DEFAULT_TOOL_REGISTRY
from aegis_contracts import load_settings
from aegis_contracts.agent_runtime import CreateAgentSessionRequestV1, CreateAgentTaskRequestV1
from aegis_contracts.entities import AgentRole
from aegis_contracts.versioning import (
    CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
    CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
)
from aegis_persistence.engine import create_engine, dispose_engine, get_session_maker
from aegis_persistence.unit_of_work import PostgresUnitOfWork


async def run_harness(provider_id: str) -> int:
    settings = load_settings()
    engine = create_engine(settings)
    session_maker = get_session_maker(settings, engine=engine)
    checks: list[tuple[str, object]] = []

    definitions = DEFAULT_AGENT_REGISTRY.list_definitions()
    checks.append(
        ("registry", [item.model_dump(by_alias=True, mode="json") for item in definitions])
    )

    try:
        authorize_tool_call(
            registry=DEFAULT_TOOL_REGISTRY,
            definition=definitions[1],
            tool_name="execute_simulation_command",
        )
        checks.append(("unauthorized_tool", {"rejected": False}))
    except AgentRuntimeError as exc:
        checks.append(("unauthorized_tool", {"rejected": True, "code": exc.code.value}))

    async with PostgresUnitOfWork(session_maker) as uow:
        incident_id = await seed_harness_incident(uow)
        sessions = AgentSessionService()
        tasks = AgentTaskService()
        session = await sessions.create_session(
            uow,
            incident_id=incident_id,
            request=CreateAgentSessionRequestV1(
                schema_version=CREATE_AGENT_SESSION_REQUEST_SCHEMA_VERSION,
                role=AgentRole.TRACE,
                trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
                enqueue_initial_task=False,
                provider_id=provider_id,
            ),
        )
        task = await tasks.create_task(
            uow,
            session=session,
            request=CreateAgentTaskRequestV1(
                schema_version=CREATE_AGENT_TASK_REQUEST_SCHEMA_VERSION,
                idempotency_key=f"harness-{provider_id}",
                provider_id=provider_id,
            ),
        )
        task_id = task.id

    executor = create_task_executor()
    async with PostgresUnitOfWork(session_maker) as uow:
        await executor.execute(uow, task_id)
    async with PostgresUnitOfWork(session_maker) as uow:
        detail = await sessions.get_detail(uow, session.id)
        checks.append((f"{provider_id}_task", detail.model_dump(by_alias=True, mode="json")))

    await dispose_engine(engine)
    print(json.dumps(dict(checks), indent=2, default=str))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="mock", choices=["mock", "recorded"])
    args = parser.parse_args()
    return asyncio.run(run_harness(args.provider))


if __name__ == "__main__":
    sys.exit(main())
