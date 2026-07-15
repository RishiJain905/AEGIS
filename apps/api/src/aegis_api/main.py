from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aegis_contracts import WORKSPACE_VERSION, AegisSettings, PermissionV1, load_settings
from aegis_persistence.health import check_postgres
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from aegis_api.agents.observability import router as agents_observability_router
from aegis_api.agents.router import router as agents_router
from aegis_api.approvals.router import router as approvals_router
from aegis_api.auth.deps import AuthDependencyError, auth_error_response, require_permission
from aegis_api.auth.router import router as auth_router
from aegis_api.auth.service import AuthServiceError
from aegis_api.auth.startup import assert_secure_auth_configuration, seed_dev_identities
from aegis_api.db.session import init_db, shutdown_db
from aegis_api.detection.observability import router as detection_observability_router
from aegis_api.detection.router import router as detection_router
from aegis_api.features.observability import router as feature_observability_router
from aegis_api.features.router import router as features_router
from aegis_api.investigation.router import router as investigation_router
from aegis_api.models.observability import router as models_observability_router
from aegis_api.models.router import router as models_router
from aegis_api.providers.observability import router as providers_observability_router
from aegis_api.providers.router import router as providers_router
from aegis_api.realtime.backfill import router as backfill_router
from aegis_api.realtime.events import router as events_router
from aegis_api.realtime.observability import router as observability_router
from aegis_api.realtime.status import router as status_router
from aegis_api.replay.router import router as replay_router
from aegis_api.reports.router import router as reports_router
from aegis_api.risk.observability import router as risk_observability_router
from aegis_api.risk.router import router as risk_router
from aegis_api.runs.router import router as runs_router
from aegis_api.scoring.router import router as scoring_router
from aegis_api.websocket.demo import router as websocket_demo_router
from aegis_api.websocket.manager import WebSocketGatewayManager
from aegis_api.websocket.router import create_websocket_router


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class ReadyResponse(BaseModel):
    status: str
    service: str
    environment: str
    database: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = app.state.settings
    assert_secure_auth_configuration(settings)
    init_db(settings)
    await seed_dev_identities(settings)
    gateway: WebSocketGatewayManager = app.state.gateway
    await gateway.start()
    yield
    await gateway.stop()
    await shutdown_db(settings)


def create_app(settings: AegisSettings | None = None) -> FastAPI:
    resolved_settings = settings or load_settings()
    gateway = WebSocketGatewayManager(resolved_settings)
    app = FastAPI(title="AEGIS API", version=WORKSPACE_VERSION, lifespan=lifespan)
    app.state.settings = resolved_settings
    app.state.gateway = gateway

    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Accept",
            "Content-Type",
            "X-CSRF-Token",
            "X-Request-Id",
            "Idempotency-Key",
            "Authorization",
        ],
        expose_headers=["X-Request-Id"],
    )

    @app.exception_handler(AuthDependencyError)
    async def handle_auth_dependency_error(
        _request: object,
        exc: AuthDependencyError,
    ) -> JSONResponse:
        return auth_error_response(exc.exc)

    @app.exception_handler(AuthServiceError)
    async def handle_auth_service_error(
        _request: object,
        exc: AuthServiceError,
    ) -> JSONResponse:
        return auth_error_response(exc)

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", service="api", version=WORKSPACE_VERSION)

    @app.get("/ready", response_model=ReadyResponse)
    async def ready() -> ReadyResponse | JSONResponse:
        db_ok = await check_postgres(resolved_settings)
        if not db_ok:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "service": "api",
                    "environment": resolved_settings.AEGIS_ENV.value,
                    "database": "unavailable",
                },
            )
        return ReadyResponse(
            status="ready",
            service="api",
            environment=resolved_settings.AEGIS_ENV.value,
            database="ok",
        )

    # Auth routes are public (login/session/dev); all other API routers require auth.
    app.include_router(auth_router)

    read_runs = [Depends(require_permission(PermissionV1.RUNS_READ))]
    write_runs = [Depends(require_permission(PermissionV1.RUNS_WRITE))]
    read_investigation = [Depends(require_permission(PermissionV1.INVESTIGATION_READ))]
    trigger_investigation = [Depends(require_permission(PermissionV1.INVESTIGATION_TRIGGER))]
    decide_approvals = [Depends(require_permission(PermissionV1.APPROVALS_DECIDE))]
    read_reports = [Depends(require_permission(PermissionV1.REPORTS_READ))]
    export_reports = [Depends(require_permission(PermissionV1.REPORTS_EXPORT))]
    trigger_reports = [Depends(require_permission(PermissionV1.REPORTS_TRIGGER))]
    read_replay = [Depends(require_permission(PermissionV1.REPLAY_READ))]
    write_replay = [Depends(require_permission(PermissionV1.REPLAY_WRITE))]
    read_scoring = [Depends(require_permission(PermissionV1.SCORING_READ))]
    compute_scoring = [Depends(require_permission(PermissionV1.SCORING_COMPUTE))]
    export_scoring = [Depends(require_permission(PermissionV1.SCORING_EXPORT))]
    admin_manage = [Depends(require_permission(PermissionV1.ADMIN_MANAGE))]

    # Apply default read protection at include time; mutation routes add stronger deps in routers.
    app.include_router(backfill_router, dependencies=read_runs)
    app.include_router(events_router, dependencies=read_runs)
    app.include_router(status_router, dependencies=read_runs)
    app.include_router(observability_router, dependencies=admin_manage)
    app.include_router(runs_router, dependencies=read_runs)
    app.include_router(features_router, dependencies=read_investigation)
    app.include_router(feature_observability_router, dependencies=admin_manage)
    app.include_router(detection_router, dependencies=read_investigation)
    app.include_router(detection_observability_router, dependencies=admin_manage)
    app.include_router(models_router, dependencies=read_investigation)
    app.include_router(models_observability_router, dependencies=admin_manage)
    app.include_router(risk_router, dependencies=read_investigation)
    app.include_router(risk_observability_router, dependencies=admin_manage)
    app.include_router(providers_router, dependencies=admin_manage)
    app.include_router(providers_observability_router, dependencies=admin_manage)
    app.include_router(agents_router, dependencies=read_investigation)
    app.include_router(investigation_router, dependencies=read_investigation)
    app.include_router(approvals_router, dependencies=decide_approvals)
    app.include_router(reports_router, dependencies=read_reports)
    app.include_router(replay_router, dependencies=read_replay)
    app.include_router(scoring_router, dependencies=read_scoring)
    app.include_router(agents_observability_router, dependencies=admin_manage)
    app.include_router(create_websocket_router(gateway))
    app.include_router(websocket_demo_router, dependencies=admin_manage)

    # Keep permission symbols referenced for clarity / lint.
    _ = (
        write_runs,
        trigger_investigation,
        export_reports,
        trigger_reports,
        write_replay,
        compute_scoring,
        export_scoring,
    )

    return app


app = create_app()
