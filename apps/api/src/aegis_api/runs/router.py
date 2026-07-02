"""Run and scenario HTTP routes."""

from __future__ import annotations

from pathlib import Path

from aegis_contracts import (
    AlertV1,
    ApiErrorEnvelopeV1,
    GraphSnapshotV1,
    IncidentV1,
    RunCommandResponseV1,
    RunCreateRequestV1,
    RunV1,
    ScenarioV1,
    ScenarioVersionV1,
    SimulationCommandType,
    SnapshotBootstrapPayloadV1,
)
from aegis_contracts.errors import ContractErrorCode
from aegis_contracts.versioning import RUN_CREATE_REQUEST_SCHEMA_VERSION
from aegis_persistence.repositories.postgres import (
    PostgresAlertRepository,
    PostgresGraphSnapshotRepository,
    PostgresRunRepository,
    PostgresScenarioRepository,
    PostgresScenarioVersionRepository,
)
from aegis_persistence.unit_of_work import PostgresUnitOfWork
from aegis_simulation.run_command_service import RunCommandService
from aegis_simulation_domain.errors import SimulationError, SimulationErrorCode
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.db.session import db_session, get_db_session_maker

router = APIRouter(prefix="/api/v1", tags=["runs"])

WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
_run_service = RunCommandService(workspace_root=WORKSPACE_ROOT)


def _simulation_error_response(exc: SimulationError) -> JSONResponse:
    code_map = {
        SimulationErrorCode.VALIDATION_FAILED: ("VALIDATION_FAILED", 400),
        SimulationErrorCode.INVALID_STATE: ("CONFLICT", 409),
        SimulationErrorCode.DUPLICATE_COMMAND: ("CONFLICT", 409),
        SimulationErrorCode.PLATFORM_INCOMPATIBLE: ("VALIDATION_FAILED", 400),
    }
    api_code, status = code_map.get(exc.code, ("INTERNAL_ERROR", 500))
    envelope = ApiErrorEnvelopeV1(
        schema_version=1,
        code=api_code,
        message=exc.message,
        details=exc.details,
    )
    return JSONResponse(status_code=status, content=envelope.model_dump(by_alias=True))


async def _discover_scenarios(session: AsyncSession) -> list[ScenarioV1]:
    repo = PostgresScenarioRepository(session)
    existing = {scenario.id: scenario for scenario in await repo.list_all()}
    silent_relay_manifest = (
        WORKSPACE_ROOT / "scenarios" / "operation-silent-relay" / "manifest.yaml"
    )
    if silent_relay_manifest.exists() and "scenario:operation-silent-relay" not in existing:
        from datetime import UTC, datetime

        import yaml

        manifest_data = yaml.safe_load(silent_relay_manifest.read_text(encoding="utf-8"))
        metadata = manifest_data["metadata"]
        scenario = ScenarioV1(
            schema_version=1,
            id=metadata["scenario_id"],
            name=metadata["name"],
            description=metadata["description"],
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        existing[scenario.id] = scenario
    return list(existing.values())


@router.get("/health")
async def api_health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/workspace/status")
async def workspace_status() -> dict[str, bool]:
    return {"readOnly": False}


@router.get("/scenarios", response_model=list[ScenarioV1])
async def list_scenarios() -> list[ScenarioV1]:
    session_maker = get_db_session_maker()
    async with session_maker() as session:
        return await _discover_scenarios(session)


@router.get("/scenarios/{scenario_id}", response_model=ScenarioV1)
async def get_scenario(scenario_id: str) -> ScenarioV1 | JSONResponse:
    session_maker = get_db_session_maker()
    async with session_maker() as session:
        scenarios = await _discover_scenarios(session)
        for scenario in scenarios:
            if scenario.id == scenario_id:
                return scenario
    envelope = ApiErrorEnvelopeV1(
        schema_version=1,
        code=ContractErrorCode.VALIDATION_FAILED.value,
        message=f"Scenario not found: {scenario_id}",
    )
    return JSONResponse(status_code=404, content=envelope.model_dump(by_alias=True))


@router.get("/scenarios/{scenario_id}/versions", response_model=list[ScenarioVersionV1])
async def list_scenario_versions(scenario_id: str) -> list[ScenarioVersionV1]:
    from datetime import UTC, datetime

    if scenario_id == "scenario:operation-silent-relay":
        return [
            ScenarioVersionV1(
                schema_version=1,
                id="scenario-version:1.0.0-silent-relay",
                scenario_id=scenario_id,
                version="1.0.0-silent-relay",
                required_platform_version="0.0.0-phase10",
                published_at=datetime(2026, 6, 30, 12, 0, 0, tzinfo=UTC),
            )
        ]
    session_maker = get_db_session_maker()
    async with session_maker() as session:
        return await PostgresScenarioVersionRepository(session).list_for_scenario(scenario_id)


@router.get("/runs", response_model=list[RunV1])
async def list_runs() -> list[RunV1]:
    session_maker = get_db_session_maker()
    async with session_maker() as session:
        return await PostgresRunRepository(session).list_all()


@router.post("/runs", response_model=RunCommandResponseV1)
async def create_run(
    request: Request,
    body: RunCreateRequestV1,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> RunCommandResponseV1 | JSONResponse:
    if body.schema_version != RUN_CREATE_REQUEST_SCHEMA_VERSION:
        envelope = ApiErrorEnvelopeV1(
            schema_version=1,
            code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED.value,
            message="Unsupported run create request schema version",
        )
        return JSONResponse(status_code=400, content=envelope.model_dump(by_alias=True))

    session_maker = get_db_session_maker()
    try:
        async with PostgresUnitOfWork(session_maker, settings=request.app.state.settings) as uow:
            return await _run_service.create_run(uow, body, idempotency_key=idempotency_key)
    except SimulationError as exc:
        return _simulation_error_response(exc)


@router.get("/runs/{run_id}", response_model=RunV1)
async def get_run(run_id: str) -> RunV1 | JSONResponse:
    session_maker = get_db_session_maker()
    async with session_maker() as session:
        run = await PostgresRunRepository(session).get_by_id(run_id)
    if run is None:
        envelope = ApiErrorEnvelopeV1(
            schema_version=1,
            code=ContractErrorCode.VALIDATION_FAILED.value,
            message=f"Run not found: {run_id}",
        )
        return JSONResponse(status_code=404, content=envelope.model_dump(by_alias=True))
    return run


@router.get("/runs/{run_id}/graph", response_model=GraphSnapshotV1)
async def get_run_graph(run_id: str) -> GraphSnapshotV1 | JSONResponse:
    session_maker = get_db_session_maker()
    async with session_maker() as session:
        snapshot = await PostgresGraphSnapshotRepository(session).get_latest_for_run(run_id)
    if snapshot is None:
        envelope = ApiErrorEnvelopeV1(
            schema_version=1,
            code=ContractErrorCode.VALIDATION_FAILED.value,
            message=f"Graph snapshot not found for run: {run_id}",
        )
        return JSONResponse(status_code=404, content=envelope.model_dump(by_alias=True))
    return snapshot


@router.get("/runs/{run_id}/bootstrap", response_model=SnapshotBootstrapPayloadV1)
async def get_run_bootstrap(
    run_id: str, request: Request
) -> SnapshotBootstrapPayloadV1 | JSONResponse:
    session_maker = get_db_session_maker()
    try:
        async with PostgresUnitOfWork(session_maker, settings=request.app.state.settings) as uow:
            return await _run_service.get_bootstrap_payload(uow, run_id)
    except SimulationError as exc:
        return _simulation_error_response(exc)


async def _run_command(
    request: Request,
    run_id: str,
    command_type: SimulationCommandType,
    idempotency_key: str | None,
) -> RunCommandResponseV1 | JSONResponse:
    if idempotency_key is None or not idempotency_key.strip():
        envelope = ApiErrorEnvelopeV1(
            schema_version=1,
            code=ContractErrorCode.VALIDATION_FAILED.value,
            message="Idempotency-Key header is required",
        )
        return JSONResponse(status_code=400, content=envelope.model_dump(by_alias=True))

    session_maker = get_db_session_maker()
    try:
        async with PostgresUnitOfWork(session_maker, settings=request.app.state.settings) as uow:
            return await _run_service.execute_lifecycle_command(
                uow,
                run_id,
                command_type,
                idempotency_key=idempotency_key,
            )
    except SimulationError as exc:
        return _simulation_error_response(exc)


@router.post("/runs/{run_id}/pause", response_model=RunCommandResponseV1)
async def pause_run(
    request: Request,
    run_id: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> RunCommandResponseV1 | JSONResponse:
    return await _run_command(request, run_id, SimulationCommandType.PAUSE, idempotency_key)


@router.post("/runs/{run_id}/resume", response_model=RunCommandResponseV1)
async def resume_run(
    request: Request,
    run_id: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> RunCommandResponseV1 | JSONResponse:
    return await _run_command(request, run_id, SimulationCommandType.RESUME, idempotency_key)


@router.post("/runs/{run_id}/stop", response_model=RunCommandResponseV1)
async def stop_run(
    request: Request,
    run_id: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> RunCommandResponseV1 | JSONResponse:
    return await _run_command(request, run_id, SimulationCommandType.STOP, idempotency_key)


@router.post("/runs/{run_id}/step", response_model=RunCommandResponseV1)
async def step_run(
    request: Request,
    run_id: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> RunCommandResponseV1 | JSONResponse:
    return await _run_command(request, run_id, SimulationCommandType.STEP, idempotency_key)


@router.get("/runs/{run_id}/incidents", response_model=list[IncidentV1])
async def list_run_incidents(run_id: str) -> list[IncidentV1]:
    async with db_session() as session:
        from aegis_persistence.mappers import incident_to_domain
        from aegis_persistence.orm.tables import IncidentRow
        from sqlalchemy import select

        result = await session.execute(
            select(IncidentRow).where(IncidentRow.run_id == run_id).order_by(IncidentRow.created_at)
        )
        return [incident_to_domain(item) for item in result.scalars().all()]


@router.get("/runs/{run_id}/alerts", response_model=list[AlertV1])
async def list_run_alerts(run_id: str) -> list[AlertV1]:
    async with db_session() as session:
        return await PostgresAlertRepository(session).list_by_run(run_id)


@router.get("/alerts/{alert_id}", response_model=AlertV1)
async def get_alert(alert_id: str) -> AlertV1:
    async with db_session() as session:
        alert = await PostgresAlertRepository(session).get_by_id(alert_id)
        if alert is None:
            raise HTTPException(status_code=404, detail=f"Alert not found: {alert_id}")
        return alert


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: str) -> JSONResponse:
    envelope = ApiErrorEnvelopeV1(
        schema_version=1,
        code=ContractErrorCode.VALIDATION_FAILED.value,
        message=f"Incident not found: {incident_id}",
    )
    return JSONResponse(status_code=404, content=envelope.model_dump(by_alias=True))
