from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aegis_contracts import WORKSPACE_VERSION, AegisSettings, load_settings
from fastapi import FastAPI
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class ReadyResponse(BaseModel):
    status: str
    service: str
    environment: str

@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield


def create_app(settings: AegisSettings | None = None) -> FastAPI:
    app = FastAPI(title="AEGIS API", version=WORKSPACE_VERSION, lifespan=lifespan)
    resolved_settings = settings or load_settings()

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", service="api", version=WORKSPACE_VERSION)

    @app.get("/ready", response_model=ReadyResponse)
    def ready() -> ReadyResponse:
        _ = resolved_settings.AEGIS_ENV
        return ReadyResponse(
            status="ready",
            service="api",
            environment=resolved_settings.AEGIS_ENV.value,
        )

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
