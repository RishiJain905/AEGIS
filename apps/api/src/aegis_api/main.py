from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from aegis_contracts import WORKSPACE_VERSION, AegisSettings, PermissionV1, load_settings
from aegis_contracts.observability import HealthResponseV1, HealthStatusV1
from aegis_contracts.versioning import HEALTH_RESPONSE_SCHEMA_VERSION
from aegis_observability.middleware import create_observability_middleware
from aegis_observability.setup import init_observability, shutdown_observability
from fastapi import Depends, FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from aegis_api.admin.router import router as admin_router
from aegis_api.agents.observability import router as agents_observability_router
from aegis_api.agents.router import router as agents_router
from aegis_api.approvals.router import router as approvals_router
from aegis_api.auth.deps import AuthDependencyError, auth_error_response, require_permission
from aegis_api.auth.router import router as auth_router
from aegis_api.auth.service import AuthServiceError
from aegis_api.auth.startup import seed_dev_identities
from aegis_api.autonomy.poller import AutonomyPoller
from aegis_api.blast_radius.router import router as blast_radius_router
from aegis_api.console.router import router as console_router
from aegis_api.db.session import get_db_session_maker, init_db, shutdown_db
from aegis_api.detection.observability import router as detection_observability_router
from aegis_api.detection.router import router as detection_router
from aegis_api.directives.router import router as directives_router
from aegis_api.errors import UnhandledErrorMiddleware
from aegis_api.features.observability import router as feature_observability_router
from aegis_api.features.router import router as features_router
from aegis_api.ghost.router import router as ghost_router
from aegis_api.investigation.router import router as investigation_router
from aegis_api.models.observability import router as models_observability_router
from aegis_api.models.router import router as models_router
from aegis_api.observability import build_ready_response
from aegis_api.observability import protected_router as ops_protected_router
from aegis_api.observability import public_router as ops_public_router
from aegis_api.operator_actions.router import router as operator_router
from aegis_api.profile.router import router as profile_router
from aegis_api.provider_credentials.router import router as provider_credentials_router
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
from aegis_api.runs.service import get_run_command_service
from aegis_api.runs.tick_engine import SimulationTicker
from aegis_api.scoring.router import router as scoring_router
from aegis_api.security.middleware import (
    RequestBodyLimitMiddleware,
    SecurityHeadersMiddleware,
    TokenBucketRateLimitMiddleware,
)
from aegis_api.security.startup import assert_secure_startup_configuration
from aegis_api.websocket.demo import router as websocket_demo_router
from aegis_api.websocket.manager import WebSocketGatewayManager
from aegis_api.websocket.router import create_websocket_router


class HealthResponse(BaseModel):
    """Legacy shape retained for Docker HEALTHCHECK compatibility."""

    status: str
    service: str
    version: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = app.state.settings
    init_observability(
        service_name=settings.OTEL_SERVICE_NAME,
        enabled=settings.OTEL_ENABLED,
        otlp_endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
        otlp_protocol=settings.OTEL_EXPORTER_OTLP_PROTOCOL,
        sampler_arg=settings.OTEL_TRACES_SAMPLER_ARG,
        metrics_export_interval_ms=settings.OTEL_METRICS_EXPORT_INTERVAL_MS,
        log_level=settings.LOG_LEVEL.value,
        json_logs=settings.AEGIS_LOG_JSON,
    )
    assert_secure_startup_configuration(settings)
    init_db(settings)
    await seed_dev_identities(settings)
    gateway: WebSocketGatewayManager = app.state.gateway
    await gateway.start()
    # Single-writer simulation tick engine: advances every RUNNING run on a cadence,
    # sharing the runs router's RunCommandService (and its per-run locks) so ticks and
    # manual commands never race on the same runtime.
    ticker = SimulationTicker(
        command_service=get_run_command_service(),
        session_maker=get_db_session_maker(),
        settings=settings,
    )
    app.state.sim_ticker = ticker
    await ticker.start()
    # Event-driven autonomous triage loop: consumes newly-persisted alerts and enqueues
    # bounded, RoE-gated WATCHTOWER auto-tasks. Decoupled from the tick engine; enqueue-only
    # so it never runs the model inline.
    autonomy_poller = AutonomyPoller(
        session_maker=get_db_session_maker(),
        settings=settings,
    )
    app.state.autonomy_poller = autonomy_poller
    await autonomy_poller.start()
    yield
    await autonomy_poller.stop()
    await ticker.stop()
    await gateway.stop()
    await shutdown_db(settings)
    shutdown_observability()


def create_app(settings: AegisSettings | None = None) -> FastAPI:
    resolved_settings = settings or load_settings()
    gateway = WebSocketGatewayManager(resolved_settings)
    app = FastAPI(title="AEGIS API", version=WORKSPACE_VERSION, lifespan=lifespan)
    app.state.settings = resolved_settings
    app.state.gateway = gateway

    # Middleware order matters for CORS, and `add_middleware` prepends: the LAST call below
    # ends up outermost. CORS is added last on purpose, so every response the stack can
    # produce leaves through it and carries `Access-Control-Allow-Origin`.
    #
    # A response emitted *above* CORS is invisible to the browser: it fails the CORS check
    # before JavaScript ever sees the status, so the client reports an opaque network error
    # and — because a network error looks retryable where a 429 does not — retries, which
    # produces another header-less rejection. That is how an operator's failing run bootstrap
    # turned into hundreds of `ERR_FAILED` requests. The rate limiter and the body limiter
    # both answer requests themselves (429/413/400), so they have to sit below CORS too, not
    # just the unhandled-500 path.
    app.add_middleware(UnhandledErrorMiddleware)
    app.add_middleware(create_observability_middleware(resolved_settings.OTEL_SERVICE_NAME))
    app.add_middleware(
        RequestBodyLimitMiddleware,
        max_bytes=resolved_settings.AEGIS_REQUEST_BODY_MAX_BYTES,
    )
    app.add_middleware(
        TokenBucketRateLimitMiddleware,
        session_cookie_name=resolved_settings.AEGIS_SESSION_COOKIE_NAME,
        requests_per_minute=resolved_settings.AEGIS_RATE_LIMIT_REQUESTS_PER_MINUTE,
        burst=resolved_settings.AEGIS_RATE_LIMIT_BURST,
        max_buckets=resolved_settings.AEGIS_RATE_LIMIT_MAX_BUCKETS,
    )
    app.add_middleware(
        SecurityHeadersMiddleware,
        environment=resolved_settings.AEGIS_ENV,
        hsts_enabled=resolved_settings.AEGIS_SECURITY_HSTS_ENABLED,
        hsts_max_age_seconds=resolved_settings.AEGIS_SECURITY_HSTS_MAX_AGE_SECONDS,
    )
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
            "X-Correlation-Id",
            "traceparent",
            "tracestate",
            "Idempotency-Key",
            "Authorization",
            "X-Aegis-Run-Id",
            "X-Aegis-Incident-Id",
        ],
        expose_headers=["X-Request-Id", "X-Correlation-Id", "traceparent"],
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

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        _request: object,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """A 422 that does not read the request body back to the caller.

        FastAPI's default includes the offending value in the response, so a malformed
        login or a mistyped provider API key comes straight back out — and into
        anything that records response bodies. Where the error is and what is wrong
        with it is enough to fix a request; the value itself is the caller's already.
        """
        errors = [
            {key: value for key, value in error.items() if key not in {"input", "ctx"}}
            for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content=jsonable_encoder({"detail": errors}))

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        # Liveness: process is alive. Does not check dependencies.
        _ = HealthResponseV1.model_validate(
            {
                "schemaVersion": HEALTH_RESPONSE_SCHEMA_VERSION,
                "status": HealthStatusV1.OK.value,
                "service": "api",
                "version": WORKSPACE_VERSION,
                "checkedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            }
        )
        return HealthResponse(status="ok", service="api", version=WORKSPACE_VERSION)

    @app.get("/ready")
    async def ready() -> JSONResponse:
        payload, status_code = await build_ready_response(resolved_settings)
        return JSONResponse(status_code=status_code, content=payload.model_dump(by_alias=True))

    # Auth routes are public (login/session/dev); all other API routers require auth.
    app.include_router(auth_router)
    app.include_router(ops_public_router)

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

    app.include_router(ops_protected_router, dependencies=admin_manage)
    # Backfill republishes persisted events to Redis (mass WS re-delivery to all
    # subscribers) — a privileged operational action, not a read; gate admin:manage.
    app.include_router(backfill_router, dependencies=admin_manage)
    app.include_router(events_router, dependencies=read_runs)
    app.include_router(status_router, dependencies=read_runs)
    app.include_router(observability_router, dependencies=admin_manage)
    app.include_router(runs_router, dependencies=read_runs)
    app.include_router(operator_router, dependencies=read_runs)
    app.include_router(console_router, dependencies=read_runs)
    app.include_router(blast_radius_router, dependencies=read_runs)
    app.include_router(directives_router, dependencies=read_investigation)
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
    # Provider credentials belong to the operator launching runs, not to an admin: the
    # picker in the launch dialog has to be readable by anyone who can start a run.
    # Connecting and disconnecting a key additionally demands runs:write, declared on
    # those routes, so a read-only viewer can see the picker but not spend anything.
    app.include_router(provider_credentials_router, dependencies=read_runs)
    app.include_router(agents_router, dependencies=read_investigation)
    app.include_router(investigation_router, dependencies=read_investigation)
    app.include_router(approvals_router, dependencies=decide_approvals)
    app.include_router(reports_router, dependencies=read_reports)
    app.include_router(replay_router, dependencies=read_replay)
    app.include_router(scoring_router, dependencies=read_scoring)
    app.include_router(profile_router, dependencies=read_scoring)
    # Ghost branch (post-run counterfactual replay) is an after-action read feature; it
    # never mutates run state, so it rides the scoring read permission + run ownership gate.
    app.include_router(ghost_router, dependencies=read_scoring)
    app.include_router(agents_observability_router, dependencies=admin_manage)
    app.include_router(admin_router, dependencies=admin_manage)
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
        admin_manage,
    )

    return app


app = create_app()
