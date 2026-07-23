"""Run and scenario HTTP routes."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

from aegis_contracts import (
    AlertV1,
    ApiErrorEnvelopeV1,
    AuthenticatedActorV1,
    GraphSnapshotV1,
    IncidentV1,
    PermissionV1,
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
from aegis_simulation.disclosure_resolver import ACTIVE_RUN_STATUSES
from aegis_simulation.graph_projection import redact_snapshot_for_disclosure
from aegis_simulation_domain.errors import SimulationError, SimulationErrorCode
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.auth.deps import require_actor, require_permission
from aegis_api.auth.run_authz import actor_is_admin, has_run_access
from aegis_api.db.session import db_session, get_db_session_maker
from aegis_api.runs.lifecycle import finalize_stopped_run
from aegis_api.runs.service import get_run_command_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["runs"])

WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
# Process-wide shared instance: the manual lifecycle routes below and the background tick
# engine mutate the same cached runtimes and serialize on the same per-run locks.
_run_service = get_run_command_service()


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
        details=exc.details or {},
    )
    return JSONResponse(status_code=status, content=envelope.model_dump(by_alias=True))


def _run_not_found_response(run_id: str) -> JSONResponse:
    envelope = ApiErrorEnvelopeV1(
        schema_version=1,
        code=ContractErrorCode.VALIDATION_FAILED.value,
        message=f"Run not found: {run_id}",
    )
    return JSONResponse(status_code=404, content=envelope.model_dump(by_alias=True))


def _forbidden_run_response(run_id: str) -> JSONResponse:
    envelope = ApiErrorEnvelopeV1(
        schema_version=1,
        code="FORBIDDEN",
        message=f"Not authorized to access run: {run_id}",
    )
    return JSONResponse(status_code=403, content=envelope.model_dump(by_alias=True))


def _authorize_run(
    run: RunV1 | None, actor: AuthenticatedActorV1, run_id: str
) -> RunV1 | JSONResponse:
    """Owner-or-admin gate. Returns the run, or a 404 (absent) / 403 (not owner/admin).

    Ownership is anchored to the run's ``ownerUserId``. Admins (admin:manage) bypass the
    owner check. Legacy rows with a null owner are treated as admin-only (fail-closed for
    non-admins). See ADR 0034 / AEGIS-OITB-008.
    """
    if run is None:
        return _run_not_found_response(run_id)
    if has_run_access(run, actor):
        return run
    return _forbidden_run_response(run_id)


# Packages surfaced in the catalogue even before their first run persists a DB row.
_FALLBACK_SCENARIO_PACKAGES = ("synthetic-training", "operation-silent-relay")


async def _discover_scenarios(session: AsyncSession) -> list[ScenarioV1]:
    repo = PostgresScenarioRepository(session)
    existing = {scenario.id: scenario for scenario in await repo.list_all()}
    from datetime import UTC, datetime

    import yaml

    for package in _FALLBACK_SCENARIO_PACKAGES:
        manifest_path = WORKSPACE_ROOT / "scenarios" / package / "manifest.yaml"
        if not manifest_path.exists():
            continue
        try:
            manifest_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            metadata = manifest_data["metadata"]
            scenario_id = metadata.get("scenarioId") or metadata["scenario_id"]
        except (KeyError, TypeError, yaml.YAMLError) as exc:
            logger.warning("Skipping catalogue fallback for %s: %s", package, exc)
            continue
        if scenario_id in existing:
            continue
        scenario = ScenarioV1(
            schema_version=1,
            id=scenario_id,
            name=metadata.get("name", scenario_id),
            description=metadata.get("description", ""),
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
async def list_runs(
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
) -> list[RunV1]:
    session_maker = get_db_session_maker()
    async with session_maker() as session:
        repo = PostgresRunRepository(session)
        if actor_is_admin(actor):
            return await repo.list_all()
        return await repo.list_for_owner(actor.user_id)


@router.post("/runs", response_model=RunCommandResponseV1)
async def create_run(
    request: Request,
    body: RunCreateRequestV1,
    actor: Annotated[
        AuthenticatedActorV1, Depends(require_permission(PermissionV1.RUNS_WRITE))
    ],
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
            return await _run_service.create_run(
                uow, body, idempotency_key=idempotency_key, owner_user_id=actor.user_id
            )
    except SimulationError as exc:
        return _simulation_error_response(exc)


@router.get("/runs/{run_id}", response_model=RunV1)
async def get_run(
    run_id: str,
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
) -> RunV1 | JSONResponse:
    session_maker = get_db_session_maker()
    async with session_maker() as session:
        run = await PostgresRunRepository(session).get_by_id(run_id)
    return _authorize_run(run, actor, run_id)


@router.get("/runs/{run_id}/graph", response_model=GraphSnapshotV1)
async def get_run_graph(
    run_id: str,
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
) -> GraphSnapshotV1 | JSONResponse:
    session_maker = get_db_session_maker()
    async with session_maker() as session:
        run = await PostgresRunRepository(session).get_by_id(run_id)
        authorized = _authorize_run(run, actor, run_id)
        if isinstance(authorized, JSONResponse):
            return authorized
        snapshot = await PostgresGraphSnapshotRepository(session).get_latest_for_run(run_id)
        if snapshot is None:
            envelope = ApiErrorEnvelopeV1(
                schema_version=1,
                code=ContractErrorCode.VALIDATION_FAILED.value,
                message=f"Graph snapshot not found for run: {run_id}",
            )
            return JSONResponse(status_code=404, content=envelope.model_dump(by_alias=True))
        # Fog of war: redact undisclosed attacker state while the run is active; serve full
        # ground truth once the run is terminal (debrief). The persisted snapshot is always
        # the truth — redaction happens only on this operator-facing read.
        if authorized.status in ACTIVE_RUN_STATUSES:
            disclosure = await _run_service.resolve_disclosure(session, authorized)
            snapshot = redact_snapshot_for_disclosure(snapshot, disclosure)
    return snapshot


@router.get("/runs/{run_id}/bootstrap", response_model=SnapshotBootstrapPayloadV1)
async def get_run_bootstrap(
    run_id: str,
    request: Request,
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
) -> SnapshotBootstrapPayloadV1 | JSONResponse:
    session_maker = get_db_session_maker()
    try:
        async with PostgresUnitOfWork(session_maker, settings=request.app.state.settings) as uow:
            run = await uow.runs.get_by_id(run_id)
            authorized = _authorize_run(run, actor, run_id)
            if isinstance(authorized, JSONResponse):
                return authorized
            return await _run_service.get_bootstrap_payload(uow, run_id)
    except SimulationError as exc:
        return _simulation_error_response(exc)


async def _run_command(
    request: Request,
    run_id: str,
    command_type: SimulationCommandType,
    idempotency_key: str | None,
    actor: AuthenticatedActorV1,
) -> RunCommandResponseV1 | JSONResponse:
    if idempotency_key is None or not idempotency_key.strip():
        envelope = ApiErrorEnvelopeV1(
            schema_version=1,
            code=ContractErrorCode.VALIDATION_FAILED.value,
            message="Idempotency-Key header is required",
        )
        return JSONResponse(status_code=400, content=envelope.model_dump(by_alias=True))

    session_maker = get_db_session_maker()
    settings = request.app.state.settings
    try:
        # Serialize with the tick engine and any other manual command on the same run so
        # they never mutate the shared cached runtime concurrently. The lock is held across
        # the whole transaction (including commit) so a tick cannot interleave a run-row
        # update between this command's persist and its commit.
        async with (
            _run_service.lock_for(run_id),
            PostgresUnitOfWork(session_maker, settings=settings) as uow,
        ):
            run = await uow.runs.get_by_id(run_id)
            authorized = _authorize_run(run, actor, run_id)
            if isinstance(authorized, JSONResponse):
                return authorized
            response = await _run_service.execute_lifecycle_command(
                uow,
                run_id,
                command_type,
                idempotency_key=idempotency_key,
            )
    except SimulationError as exc:
        # A failed command may have left the cached runtime mutated but unpersisted; evict
        # it so the next access re-restores clean state from the checkpoint + event stream.
        _run_service.evict(run_id)
        return _simulation_error_response(exc)

    # After a stop commits, produce the after-action artifacts (best-effort, own
    # transaction) so a manually stopped run finalizes exactly like a ticker-completed one.
    if command_type == SimulationCommandType.STOP and response.run.status == "stopped":
        await finalize_stopped_run(
            session_maker,
            run_id=run_id,
            settings=settings,
        )
    return response


_RunWriteActor = Annotated[
    AuthenticatedActorV1, Depends(require_permission(PermissionV1.RUNS_WRITE))
]


@router.post("/runs/{run_id}/pause", response_model=RunCommandResponseV1)
async def pause_run(
    request: Request,
    run_id: str,
    actor: _RunWriteActor,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> RunCommandResponseV1 | JSONResponse:
    return await _run_command(request, run_id, SimulationCommandType.PAUSE, idempotency_key, actor)


@router.post("/runs/{run_id}/resume", response_model=RunCommandResponseV1)
async def resume_run(
    request: Request,
    run_id: str,
    actor: _RunWriteActor,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> RunCommandResponseV1 | JSONResponse:
    return await _run_command(request, run_id, SimulationCommandType.RESUME, idempotency_key, actor)


@router.post("/runs/{run_id}/stop", response_model=RunCommandResponseV1)
async def stop_run(
    request: Request,
    run_id: str,
    actor: _RunWriteActor,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> RunCommandResponseV1 | JSONResponse:
    return await _run_command(request, run_id, SimulationCommandType.STOP, idempotency_key, actor)


@router.post("/runs/{run_id}/step", response_model=RunCommandResponseV1)
async def step_run(
    request: Request,
    run_id: str,
    actor: _RunWriteActor,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> RunCommandResponseV1 | JSONResponse:
    return await _run_command(request, run_id, SimulationCommandType.STEP, idempotency_key, actor)


@router.get("/runs/{run_id}/incidents", response_model=list[IncidentV1])
async def list_run_incidents(
    run_id: str,
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
) -> list[IncidentV1] | JSONResponse:
    async with db_session() as session:
        from aegis_persistence.mappers import incident_to_domain
        from aegis_persistence.orm.tables import IncidentRow
        from sqlalchemy import select

        run = await PostgresRunRepository(session).get_by_id(run_id)
        authorized = _authorize_run(run, actor, run_id)
        if isinstance(authorized, JSONResponse):
            return authorized
        result = await session.execute(
            select(IncidentRow).where(IncidentRow.run_id == run_id).order_by(IncidentRow.created_at)
        )
        return [incident_to_domain(item) for item in result.scalars().all()]


@router.get("/runs/{run_id}/alerts", response_model=list[AlertV1])
async def list_run_alerts(
    run_id: str,
    actor: Annotated[AuthenticatedActorV1, Depends(require_actor)],
) -> list[AlertV1] | JSONResponse:
    async with db_session() as session:
        run = await PostgresRunRepository(session).get_by_id(run_id)
        authorized = _authorize_run(run, actor, run_id)
        if isinstance(authorized, JSONResponse):
            return authorized
        return await PostgresAlertRepository(session).list_by_run(run_id)


@router.get("/alerts/{alert_id}", response_model=AlertV1)
async def get_alert(alert_id: str) -> AlertV1:
    async with db_session() as session:
        alert = await PostgresAlertRepository(session).get_by_id(alert_id)
        if alert is None:
            raise HTTPException(status_code=404, detail=f"Alert not found: {alert_id}")
        return alert


