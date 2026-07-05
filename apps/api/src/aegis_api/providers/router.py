"""Model provider HTTP routes."""

from __future__ import annotations

from aegis_agents.providers.factory import create_generation_service
from aegis_contracts.generation import (
    GenerationArtifactV1,
    ProviderGenerateRequestV1,
    ProviderGenerateResponseV1,
)
from aegis_contracts.versioning import PROVIDER_GENERATE_REQUEST_SCHEMA_VERSION
from aegis_model_provider import load_provider_settings
from aegis_model_provider.registry import build_provider_registry
from fastapi import APIRouter, HTTPException

from aegis_api.db.session import db_session

router = APIRouter(prefix="/api/v1/providers", tags=["providers"])


@router.get("/config")
async def get_provider_config() -> dict[str, object]:
    settings = load_provider_settings()
    registry = build_provider_registry(settings)
    return {
        "defaultProvider": settings.AEGIS_PROVIDER_DEFAULT.value,
        "providers": registry.list_providers(),
        "timeoutSeconds": settings.AEGIS_PROVIDER_TIMEOUT_SECONDS,
        "maxRetries": settings.AEGIS_PROVIDER_MAX_RETRIES,
        "maxOutputTokens": settings.AEGIS_PROVIDER_MAX_OUTPUT_TOKENS,
    }


@router.post("/generate", response_model=ProviderGenerateResponseV1)
async def generate(request: ProviderGenerateRequestV1) -> ProviderGenerateResponseV1:
    if request.schema_version != PROVIDER_GENERATE_REQUEST_SCHEMA_VERSION:
        raise HTTPException(status_code=400, detail="Unsupported schema version")
    settings = load_provider_settings()
    if settings.AEGIS_PROVIDER_IN_MEMORY_ARTIFACTS:
        service = create_generation_service(force_in_memory=True)
    else:
        async with db_session() as session:
            service = create_generation_service(session=session)
            resolved = request.request
            if request.provider_id is not None:
                resolved = resolved.model_copy(update={"provider_id": request.provider_id})
            return await service.generate(resolved, dry_run=request.dry_run)
    resolved = request.request
    if request.provider_id is not None:
        resolved = resolved.model_copy(update={"provider_id": request.provider_id})
    return await service.generate(resolved, dry_run=request.dry_run)


@router.get("/artifacts/{request_id}", response_model=GenerationArtifactV1)
async def get_artifact(request_id: str) -> GenerationArtifactV1:
    settings = load_provider_settings()
    if settings.AEGIS_PROVIDER_IN_MEMORY_ARTIFACTS:
        service = create_generation_service(force_in_memory=True)
        artifact = await service.get_artifact(request_id)
    else:
        async with db_session() as session:
            service = create_generation_service(session=session)
            artifact = await service.get_artifact(request_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Generation artifact not found")
    return artifact
