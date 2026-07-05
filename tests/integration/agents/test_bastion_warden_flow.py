"""Integration flow for Phase 22 BASTION and WARDEN."""

from __future__ import annotations

import os

import pytest
from aegis_agents.providers.generation import AgentGenerationFacade
from aegis_agents.roles.bastion.coordinator import BastionCoordinator
from aegis_agents.roles.oracle.coordinator import OracleCoordinator
from aegis_agents.roles.warden.coordinator import WardenCoordinator
from aegis_agents.roles.watchtower.coordinator import WatchtowerCoordinator
from aegis_agents.runtime.executor import TaskExecutor
from aegis_contracts.hypothesis import TriggerOracleRequestV1
from aegis_contracts.investigation import TriggerWatchtowerRequestV1
from aegis_contracts.proposals import (
    PolicyOutcomeV1,
    TriggerBastionRequestV1,
    TriggerWardenRequestV1,
)
from aegis_contracts.versioning import (
    TRIGGER_BASTION_REQUEST_SCHEMA_VERSION,
    TRIGGER_ORACLE_REQUEST_SCHEMA_VERSION,
    TRIGGER_WARDEN_REQUEST_SCHEMA_VERSION,
    TRIGGER_WATCHTOWER_REQUEST_SCHEMA_VERSION,
)
from aegis_model_provider import build_provider_registry, load_provider_settings
from aegis_model_provider.persistence import InMemoryGenerationArtifactRepository
from aegis_model_provider.service import GenerationService
from aegis_persistence.engine import create_engine, dispose_engine, get_session_maker
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from tests.integration.agents.helpers import seed_investigation_run

pytestmark = pytest.mark.skipif(
    os.getenv("AEGIS_INTEGRATION_POSTGRES") != "1",
    reason="Requires PostgreSQL integration environment",
)


@pytest.mark.asyncio
async def test_bastion_warden_flow_with_mock_provider() -> None:
    from aegis_contracts import load_settings

    settings = load_settings()
    engine = create_engine(settings)
    session_maker = get_session_maker(settings, engine=engine)
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
                trace_id="trc_bastion_flow",
                provider_id="mock",
                idempotency_key="harness-watchtower-bastion",
            ),
        )
        trace_tasks = await uow.agent_tasks.list_for_session(watchtower_result.trace_session_id)
        await executor.execute(uow, trace_tasks[0].id)

        oracle = OracleCoordinator()
        oracle_result = await oracle.trigger_for_run(
            uow,
            TriggerOracleRequestV1(
                schema_version=TRIGGER_ORACLE_REQUEST_SCHEMA_VERSION,
                run_id=run_id,
                trace_id="trc_bastion_flow",
                provider_id="mock",
                idempotency_key="harness-oracle-bastion",
            ),
        )
        oracle_tasks = await uow.agent_tasks.list_for_session(oracle_result.oracle_session_id)
        await executor.execute(uow, oracle_tasks[0].id)

        bastion = BastionCoordinator()
        bastion_result = await bastion.trigger_for_run(
            uow,
            TriggerBastionRequestV1(
                schema_version=TRIGGER_BASTION_REQUEST_SCHEMA_VERSION,
                run_id=run_id,
                trace_id="trc_bastion_flow",
                provider_id="mock",
                idempotency_key="harness-bastion-warden",
            ),
        )
        await executor.execute(uow, bastion_result.bastion_task_id)
        if bastion_result.warden_task_id:
            await executor.execute(uow, bastion_result.warden_task_id)

        detail = await uow.investigation.get_detail(incident_id, run_id)
        assert detail.proposals
        assert detail.proposal_revisions
        assert detail.policy_decisions
        assert any(
            decision.outcome == PolicyOutcomeV1.APPROVAL_REQUIRED
            for decision in detail.policy_decisions
        )

        warden = WardenCoordinator()
        reeval = await warden.trigger_for_run(
            uow,
            TriggerWardenRequestV1(
                schema_version=TRIGGER_WARDEN_REQUEST_SCHEMA_VERSION,
                run_id=run_id,
                proposal_id=detail.proposals[0].id,
                trace_id="trc_bastion_flow",
                provider_id="mock",
                idempotency_key="harness-warden-reeval",
            ),
        )
        await executor.execute(uow, reeval.warden_task_id)

    await dispose_engine(engine)
