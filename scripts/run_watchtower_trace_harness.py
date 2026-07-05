#!/usr/bin/env python3
"""Run Phase 20 WATCHTOWER and TRACE harness checks."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from aegis_agents.providers.generation import AgentGenerationFacade
from aegis_agents.roles.watchtower.coordinator import WatchtowerCoordinator
from aegis_agents.runtime.errors import AgentRuntimeError
from aegis_agents.runtime.executor import TaskExecutor
from aegis_agents.runtime.registry import DEFAULT_AGENT_REGISTRY
from aegis_agents.runtime.task_service import AgentTaskService
from aegis_agents.tools.investigation.definitions import INVESTIGATION_TOOL_DEFINITIONS
from aegis_agents.tools.permissions import authorize_tool_call
from aegis_agents.tools.registry import ToolRegistry
from aegis_contracts import load_settings
from aegis_contracts.entities import AgentRole
from aegis_contracts.investigation import TriggerWatchtowerRequestV1
from aegis_contracts.versioning import TRIGGER_WATCHTOWER_REQUEST_SCHEMA_VERSION
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

    watchtower_definition = DEFAULT_AGENT_REGISTRY.get(AgentRole.WATCHTOWER)
    trace_definition = DEFAULT_AGENT_REGISTRY.get(AgentRole.TRACE)
    checks.append(
        (
            "definitions",
            {
                "watchtower": watchtower_definition.model_dump(by_alias=True, mode="json"),
                "trace": trace_definition.model_dump(by_alias=True, mode="json"),
            },
        )
    )

    tool_registry = ToolRegistry(INVESTIGATION_TOOL_DEFINITIONS)
    try:
        authorize_tool_call(
            registry=tool_registry,
            definition=trace_definition,
            tool_name="execute_simulation_command",
        )
        checks.append(("unauthorized_tool", {"rejected": False}))
    except AgentRuntimeError as exc:
        checks.append(("unauthorized_tool", {"rejected": True, "code": exc.code.value}))

    coordinator = WatchtowerCoordinator()
    tasks = AgentTaskService()
    provider_settings = load_provider_settings()
    executor = TaskExecutor(
        generation=AgentGenerationFacade(
            GenerationService(
                registry=build_provider_registry(provider_settings),
                settings=provider_settings,
                artifact_repository=InMemoryGenerationArtifactRepository(),
            )
        )
    )

    async with PostgresUnitOfWork(session_maker) as uow:
        incident_id, run_id, alert_ids, evidence_id = await seed_investigation_run(uow)
        trigger = await coordinator.trigger_for_run(
            uow,
            TriggerWatchtowerRequestV1(
                schema_version=TRIGGER_WATCHTOWER_REQUEST_SCHEMA_VERSION,
                run_id=run_id,
                alert_ids=alert_ids,
                trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
                provider_id=provider_id,
                idempotency_key=f"harness-watchtower-{provider_id}",
            ),
        )
        checks.append(
            (
                "watchtower_triage",
                {
                    "incidentId": trigger.incident_id,
                    "triageId": trigger.triage.id,
                    "escalation": trigger.triage.escalation.value,
                    "groupedAlertIds": trigger.triage.grouped_alert_ids,
                },
            )
        )

        trace_session_id = trigger.trace_session_id
        if trace_session_id is None:
            checks.append(("trace_execution", {"skipped": True, "reason": "monitor_escalation"}))
        else:
            trace_tasks = await uow.agent_tasks.list_for_session(trace_session_id)
            if trace_tasks:
                await executor.execute(uow, trace_tasks[0].id)
                completed = await tasks.get_task(uow, trace_tasks[0].id)
                checks.append(
                    (
                        f"{provider_id}_trace_task",
                        {
                            "status": completed.status.value,
                            "taskId": completed.id,
                        },
                    )
                )

        detail = await uow.investigation.get_detail(incident_id, run_id)
        checks.append(
            (
                "investigation_detail",
                {
                    "incidentId": detail.incident_id,
                    "triageCount": len(detail.triage_results),
                    "planCount": len(detail.plans),
                    "attachmentCount": len(detail.evidence_attachments),
                    "evidenceId": evidence_id,
                },
            )
        )

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
