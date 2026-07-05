"""Build provider registry and generation service for agent runtime."""

from __future__ import annotations

from aegis_model_provider import GenerationService, build_provider_registry, load_provider_settings
from aegis_model_provider.persistence import (
    GenerationArtifactRepository,
    InMemoryGenerationArtifactRepository,
)
from aegis_persistence.repositories.postgres import PostgresGenerationArtifactRepository
from sqlalchemy.ext.asyncio import AsyncSession


def create_generation_service(
    *,
    session: AsyncSession | None = None,
    force_in_memory: bool = False,
) -> GenerationService:
    settings = load_provider_settings()
    registry = build_provider_registry(settings)
    use_memory = force_in_memory or settings.AEGIS_PROVIDER_IN_MEMORY_ARTIFACTS or session is None
    repository: GenerationArtifactRepository
    if use_memory:
        repository = InMemoryGenerationArtifactRepository()
    else:
        assert session is not None
        repository = PostgresGenerationArtifactRepository(session)
    return GenerationService(
        registry=registry,
        settings=settings,
        artifact_repository=repository,
    )
