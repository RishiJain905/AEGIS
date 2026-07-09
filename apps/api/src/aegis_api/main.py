from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aegis_contracts import WORKSPACE_VERSION, AegisSettings, load_settings
from aegis_persistence.health import check_postgres
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from aegis_api.agents.observability import router as agents_observability_router
from aegis_api.agents.router import router as agents_router
from aegis_api.approvals.router import router as approvals_router
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
    init_db(settings)
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

    app.include_router(backfill_router)
    app.include_router(events_router)
    app.include_router(status_router)
    app.include_router(observability_router)
    app.include_router(runs_router)
    app.include_router(features_router)
    app.include_router(feature_observability_router)
    app.include_router(detection_router)
    app.include_router(detection_observability_router)
    app.include_router(models_router)
    app.include_router(models_observability_router)
    app.include_router(risk_router)
    app.include_router(risk_observability_router)
    app.include_router(providers_router)
    app.include_router(providers_observability_router)
    app.include_router(agents_router)
    app.include_router(investigation_router)
    app.include_router(approvals_router)
    app.include_router(reports_router)
    app.include_router(replay_router)
    app.include_router(agents_observability_router)
    app.include_router(create_websocket_router(gateway))
    app.include_router(websocket_demo_router)

    return app


def run() -> None:
    import uvicorn

    settings = load_settings()
    uvicorn.run(
        "aegis_api.main:create_app",
        factory=True,
        host="0.0.0.0",
        port=settings.API_PORT,
        reload=settings.AEGIS_ENV.value == "development",
    )


if __name__ == "__main__":
    run()
