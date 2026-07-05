#!/usr/bin/env python3
"""Run Phase 21 ORACLE harness checks."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from aegis_agents.providers.generation import AgentGenerationFacade
from aegis_agents.roles.oracle.coordinator import OracleCoordinator
from aegis_agents.roles.watchtower.coordinator import WatchtowerCoordinator
from aegis_agents.runtime.errors import AgentRuntimeError
from aegis_agents.runtime.executor import TaskExecutor
from aegis_agents.runtime.registry import DEFAULT_AGENT_REGISTRY
from aegis_agents.runtime.task_service import AgentTaskService
from aegis_agents.tools.definitions import CANONICAL_TOOL_DEFINITIONS
from aegis_agents.tools.permissions import authorize_tool_call
from aegis_agents.tools.registry import ToolRegistry
from aegis_contracts import load_settings
from aegis_contracts.entities import AgentRole
from aegis_contracts.hypothesis import TriggerOracleRequestV1
from aegis_contracts.investigation import TriggerWatchtowerRequestV1
from aegis_contracts.versioning import (
    TRIGGER_ORACLE_REQUEST_SCHEMA_VERSION,
    TRIGGER_WATCHTOWER_REQUEST_SCHEMA_VERSION,
)
from aegis_model_provider import build_provider_registry, load_provider_settings
from aegis_model_provider.persistence import InMemoryGenerationArtifactRepository
from aegis_model_provider.service import GenerationService
from aegis_persistence.engine import create_engine, dispose_engine, get_session_maker
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from tests.integration.agents.helpers import seed_investigation_run


async def run_harness(provider_id: str) -> int:
    settings = load_settings()
    engine = create_engine(settings)
    session_maker = get_session_maker(settings, engine=engine)
    checks: list[tuple[str, object]] = []

    oracle_definition = DEFAULT_AGENT_REGISTRY.get(AgentRole.ORACLE)
    checks.append(("oracle_definition", oracle_definition.model_dump(by_alias=True, mode="json")))

    tool_registry = ToolRegistry(CANONICAL_TOOL_DEFINITIONS)
    try:
        authorize_tool_call(
            registry=tool_registry,
            definition=oracle_definition,
            tool_name="create_action_proposal",
        )
        checks.append(("unauthorized_tool", {"rejected": False}))
    except AgentRuntimeError as exc:
        checks.append(("unauthorized_tool", {"rejected": True, "code": exc.code.value}))

    generation_settings = load_provider_settings()
    service = GenerationService(
        registry=build_provider_registry(generation_settings),
        settings=generation_settings,
        artifact_repository=InMemoryGenerationArtifactRepository(),
    )
    executor = TaskExecutor(generation=AgentGenerationFacade(service))
    tasks = AgentTaskService()

    async with PostgresUnitOfWork(session_maker) as uow:
        incident_id, run_id, alert_ids, _ = await seed_investigation_run(uow)
        watchtower = WatchtowerCoordinator()
        watchtower_request = TriggerWatchtowerRequestV1(
            schema_version=TRIGGER_WATCHTOWER_REQUEST_SCHEMA_VERSION,
            run_id=run_id,
            alert_ids=alert_ids,
            trace_id="trc_oracle_harness",
            provider_id=provider_id,
            idempotency_key="harness-watchtower-oracle",
        )
        watchtower_result = await watchtower.trigger_for_run(uow, watchtower_request)
        trace_tasks = await uow.agent_tasks.list_for_session(watchtower_result.trace_session_id)
        await executor.execute(uow, trace_tasks[0].id)

        oracle = OracleCoordinator()
        oracle_request = TriggerOracleRequestV1(
            schema_version=TRIGGER_ORACLE_REQUEST_SCHEMA_VERSION,
            run_id=run_id,
            incident_id=incident_id,
            trace_id="trc_oracle_harness",
            provider_id=provider_id,
            idempotency_key="harness-oracle-001",
        )
        oracle_result = await oracle.trigger_for_run(uow, oracle_request)
        oracle_tasks = await uow.agent_tasks.list_for_session(oracle_result.oracle_session_id)
        await executor.execute(uow, oracle_tasks[0].id)
        detail = await uow.investigation.get_detail(incident_id, run_id)
        checks.append(
            (
                "oracle_flow",
                {
                    "hypothesisCount": len(detail.hypotheses),
                    "revisionCount": len(detail.hypothesis_revisions),
                    "comparisonCount": len(detail.hypothesis_comparisons),
                    "taskStatus": (await tasks.get_task(uow, oracle_tasks[0].id)).status.value,
                },
            )
        )

    await dispose_engine(engine)
    print(json.dumps({"checks": checks}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="mock")
    args = parser.parse_args()
    return asyncio.run(run_harness(args.provider))


if __name__ == "__main__":
    sys.exit(main())
