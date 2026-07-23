"""Integration: the ghost engine never mutates the real run (isolation) against PostgreSQL.

Drives the real persistence path — create/step/EXECUTE-contain/stop via ``RunCommandService``
and ``SimulationApplicationService`` — then runs a ghost counterfactual through the same
unit of work and asserts the run's persisted event stream and alert set are byte-for-byte
unchanged, while a valid counterfactual result is still produced.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from aegis_contracts import (
    GhostBranchRequestV1,
    RunCreateRequestV1,
    SimulationCommandType,
)
from aegis_contracts.ghost import GhostBranchModeV1
from aegis_contracts.proposals import ScenarioCommandTemplateV1
from aegis_contracts.versioning import GHOST_BRANCH_REQUEST_SCHEMA_VERSION
from aegis_persistence.repositories.streaming import PostgresEventQueryRepository
from aegis_simulation.application import SimulationApplicationService
from aegis_simulation.ghost_engine import GhostBranchEngine
from aegis_simulation.run_command_service import RunCommandService

PACKAGE_PATH = "scenarios/_fixtures/valid-minimal"
SEED = 90211
RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FD1"


@pytest.mark.asyncio
async def test_ghost_run_does_not_mutate_the_real_run(unit_of_work) -> None:
    service = RunCommandService(workspace_root=Path("."))
    await service.create_run(
        unit_of_work,
        RunCreateRequestV1(
            schema_version=1,
            scenario_package_path=PACKAGE_PATH,
            seed=SEED,
            run_id=RUN_ID,
        ),
    )
    for index in range(4):
        await service.execute_lifecycle_command(
            unit_of_work,
            RUN_ID,
            SimulationCommandType.STEP,
            idempotency_key=f"cmd-step-{index}",
        )

    live_runtime = service.runtime_cache[RUN_ID].runtime
    asset_id = next(iter(sorted(live_runtime.world.assets)))
    sim_service = SimulationApplicationService(unit_of_work)
    containment = SimulationApplicationService.build_command(
        command_id="cmd-contain",
        command_type=SimulationCommandType.EXECUTE,
        run_id=RUN_ID,
        payload={
            "pluginId": "effect.set_asset_status",
            "config": {"assetId": asset_id, "status": "isolated"},
            "targetAssetId": asset_id,
        },
    )
    await sim_service.execute_command(live_runtime, containment)
    await service.execute_lifecycle_command(
        unit_of_work, RUN_ID, SimulationCommandType.STOP, idempotency_key="cmd-stop"
    )
    await unit_of_work.commit()

    query = PostgresEventQueryRepository(unit_of_work.session)
    events_before = await query.list_by_run(RUN_ID, limit=100_000)
    count_before = len(events_before)
    max_seq_before = events_before[-1].sequence
    ids_before = [e.event_id for e in events_before]
    alerts_before = await unit_of_work.alerts.list_by_run(RUN_ID)

    engine = GhostBranchEngine(workspace_root=Path("."))
    points = await engine.enumerate_decision_points(unit_of_work, RUN_ID)
    execs = [p for p in points.decision_points if p.decision_ref.startswith("execact:")]
    assert execs, "expected the executed containment to be enumerated"
    assert execs[0].target_asset_id == asset_id
    assert execs[0].scenario_command == ScenarioCommandTemplateV1.ISOLATE

    result = await engine.run_ghost(
        unit_of_work,
        RUN_ID,
        GhostBranchRequestV1(
            schema_version=GHOST_BRANCH_REQUEST_SCHEMA_VERSION,
            decision_ref=execs[0].decision_ref,
            mode=GhostBranchModeV1.SUBSTITUTE,
            alternate_command=ScenarioCommandTemplateV1.REVOKE_CREDENTIALS,
        ),
    )
    assert result.run_id == RUN_ID
    assert result.result_hash
    diff = next((d for d in result.asset_diffs if d.asset_id == asset_id), None)
    assert diff is not None
    assert diff.real_status == "isolated"
    assert diff.ghost_status == "credentials_revoked"

    # Isolation: the real run's persisted history and alerts are untouched by the ghost.
    events_after = await query.list_by_run(RUN_ID, limit=100_000)
    assert len(events_after) == count_before
    assert events_after[-1].sequence == max_seq_before
    assert [e.event_id for e in events_after] == ids_before
    alerts_after = await unit_of_work.alerts.list_by_run(RUN_ID)
    assert len(alerts_after) == len(alerts_before)
