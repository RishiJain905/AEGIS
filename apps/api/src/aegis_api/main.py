from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aegis_contracts import WORKSPACE_VERSION, AegisSettings, load_settings
from aegis_persistence.health import check_postgres
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from aegis_api.db.session import init_db, shutdown_db
from aegis_api.realtime.backfill import router as backfill_router
from aegis_api.realtime.events import router as events_router
from aegis_api.realtime.observability import router as observability_router
from aegis_api.realtime.status import router as status_router


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
    yield
    await shutdown_db(settings)


def create_app(settings: AegisSettings | None = None) -> FastAPI:
    resolved_settings = settings or load_settings()
    app = FastAPI(title="AEGIS API", version=WORKSPACE_VERSION, lifespan=lifespan)
    app.state.settings = resolved_settings

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
