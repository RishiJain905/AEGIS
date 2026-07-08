#!/usr/bin/env python3
"""Run Phase 23 SCRIBE harness checks."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from aegis_agents.providers.generation import AgentGenerationFacade
from aegis_agents.roles.bastion.coordinator import BastionCoordinator
from aegis_agents.roles.oracle.coordinator import OracleCoordinator
from aegis_agents.roles.scribe.coordinator import ScribeCoordinator
from aegis_agents.roles.watchtower.coordinator import WatchtowerCoordinator
from aegis_agents.runtime.executor import TaskExecutor
from aegis_agents.runtime.registry import DEFAULT_AGENT_REGISTRY
from aegis_contracts import load_settings
from aegis_contracts.entities import AgentRole
from aegis_contracts.hypothesis import TriggerOracleRequestV1
from aegis_contracts.investigation import TriggerWatchtowerRequestV1
from aegis_contracts.proposals import TriggerBastionRequestV1
from aegis_contracts.reports import AfterActionReportSourceV1, TriggerScribeRequestV1
from aegis_contracts.versioning import (
    AFTER_ACTION_REPORT_SOURCE_SCHEMA_VERSION,
    TRIGGER_BASTION_REQUEST_SCHEMA_VERSION,
    TRIGGER_ORACLE_REQUEST_SCHEMA_VERSION,
    TRIGGER_SCRIBE_REQUEST_SCHEMA_VERSION,
    TRIGGER_WATCHTOWER_REQUEST_SCHEMA_VERSION,
)
from aegis_model_provider import build_provider_registry, load_provider_settings
from aegis_model_provider.persistence import InMemoryGenerationArtifactRepository
from aegis_model_provider.service import GenerationService
from aegis_persistence.engine import create_engine, dispose_engine, get_session_maker
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from aegis_reports.grounding import ground_narrative_claims
from tests.integration.agents.helpers import seed_investigation_run


async def run_harness(provider_id: str) -> int:
    settings = load_settings()
    engine = create_engine(settings)
    session_maker = get_session_maker(settings, engine=engine)
    checks: list[tuple[str, object]] = []

    scribe_definition = DEFAULT_AGENT_REGISTRY.get(AgentRole.SCRIBE)
    checks.append(("scribe_definition", scribe_definition.model_dump(by_alias=True, mode="json")))

    grounding = ground_narrative_claims(
        structured_claims=[
            {
                "claimId": "bad",
                "category": "observed_fact",
                "text": "Hallucinated",
                "citations": [
                    {
                        "kind": "evidence",
                        "referenceId": "evidence:missing",
                        "label": "missing",
                    }
                ],
            }
        ],
        source=AfterActionReportSourceV1(
            schema_version=AFTER_ACTION_REPORT_SOURCE_SCHEMA_VERSION,
            run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            incident_id="incident:inc_001",
            source_sequence_from=1,
            source_sequence_to=1,
            evidence_ids=["evidence:evt_auth_fail_001"],
        ),
    )
    checks.append(("grounding_rejects_hallucination", grounding.grounding_failed))

    generation_settings = load_provider_settings()
    service = GenerationService(
        registry=build_provider_registry(generation_settings),
        settings=generation_settings,
        artifact_repository=InMemoryGenerationArtifactRepository(),
    )
    executor = TaskExecutor(generation=AgentGenerationFacade(service))

    async with PostgresUnitOfWork(session_maker) as uow:
        incident_id, run_id, alert_ids, _ = await seed_investigation_run(uow)
        watchtower = WatchtowerCoordinator()
        watchtower_result = await watchtower.trigger_for_run(
            uow,
            TriggerWatchtowerRequestV1(
                schema_version=TRIGGER_WATCHTOWER_REQUEST_SCHEMA_VERSION,
                run_id=run_id,
                alert_ids=alert_ids,
                trace_id="trc_scribe_harness",
                provider_id=provider_id,
                idempotency_key="scribe:harness:watchtower",
            ),
        )
        trace_tasks = await uow.agent_tasks.list_for_session(watchtower_result.trace_session_id)
        if trace_tasks:
            await executor.execute(uow, trace_tasks[0].id)

        oracle = OracleCoordinator()
        oracle_result = await oracle.trigger_for_run(
            uow,
            TriggerOracleRequestV1(
                schema_version=TRIGGER_ORACLE_REQUEST_SCHEMA_VERSION,
                run_id=run_id,
                incident_id=incident_id,
                trace_id="trc_scribe_harness",
                provider_id=provider_id,
                idempotency_key="scribe:harness:oracle",
            ),
        )
        oracle_tasks = await uow.agent_tasks.list_for_session(oracle_result.oracle_session_id)
        if oracle_tasks:
            await executor.execute(uow, oracle_tasks[0].id)

        bastion = BastionCoordinator()
        bastion_result = await bastion.trigger_for_run(
            uow,
            TriggerBastionRequestV1(
                schema_version=TRIGGER_BASTION_REQUEST_SCHEMA_VERSION,
                run_id=run_id,
                incident_id=incident_id,
                trace_id="trc_scribe_harness",
                provider_id=provider_id,
                idempotency_key="scribe:harness:bastion",
            ),
        )
        await executor.execute(uow, bastion_result.bastion_task_id)
        if bastion_result.warden_task_id:
            await executor.execute(uow, bastion_result.warden_task_id)

        scribe = ScribeCoordinator()
        scribe_result = await scribe.trigger_for_run(
            uow,
            TriggerScribeRequestV1(
                schema_version=TRIGGER_SCRIBE_REQUEST_SCHEMA_VERSION,
                run_id=run_id,
                incident_id=incident_id,
                trace_id="trc_scribe_harness",
                provider_id=provider_id,
                idempotency_key="scribe:harness:scribe",
            ),
        )
        await executor.execute(uow, scribe_result.scribe_task_id)

        versions = await uow.reports.list_versions(run_id)
        report = await uow.reports.get_report(run_id)
        exports = await uow.reports.list_exports_for_run(run_id)
        checks.append(
            ("scribe_versions", [item.model_dump(by_alias=True, mode="json") for item in versions])
        )
        checks.append(("scribe_report_present", report is not None))
        checks.append(("scribe_exports", len(exports)))

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
