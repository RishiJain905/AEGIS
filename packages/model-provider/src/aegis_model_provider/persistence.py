"""Generation artifact persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from aegis_contracts.generation import (
    GenerationArtifactV1,
    GenerationRequestV1,
    GenerationResponseV1,
    ProviderErrorV1,
)
from aegis_contracts.versioning import GENERATION_ARTIFACT_SCHEMA_VERSION

from aegis_model_provider.redaction import sanitize_request_payload


class GenerationArtifactRepository(Protocol):
    async def save(self, artifact: GenerationArtifactV1) -> GenerationArtifactV1: ...

    async def get_by_request_id(self, request_id: str) -> GenerationArtifactV1 | None: ...


class InMemoryGenerationArtifactRepository:
    def __init__(self) -> None:
        self._artifacts: dict[str, GenerationArtifactV1] = {}

    async def save(self, artifact: GenerationArtifactV1) -> GenerationArtifactV1:
        self._artifacts[artifact.request_id] = artifact
        return artifact

    async def get_by_request_id(self, request_id: str) -> GenerationArtifactV1 | None:
        return self._artifacts.get(request_id)


def build_generation_artifact(
    *,
    request: GenerationRequestV1,
    response: GenerationResponseV1 | None,
    error: ProviderErrorV1 | None,
    latency_ms: int,
) -> GenerationArtifactV1:
    sanitized_request = sanitize_request_payload(request.model_dump(by_alias=True, mode="json"))
    sanitized_response: dict[str, Any] | None = None
    if response is not None:
        sanitized_response = {
            "finishReason": response.finish_reason.value,
            "structuredData": response.structured_data,
            "usage": response.usage.model_dump(by_alias=True, mode="json"),
        }
    return GenerationArtifactV1(
        schema_version=GENERATION_ARTIFACT_SCHEMA_VERSION,
        request_id=request.request_id,
        trace_id=request.trace_id,
        provider_id=response.provider_id
        if response is not None
        else request.model_config_ref.provider_id,
        model_id=response.model_id if response is not None else request.model_config_ref.model_id,
        prompt_version=request.model_config_ref.prompt_version,
        latency_ms=latency_ms,
        usage=response.usage if response is not None else None,
        error=error,
        sanitized_request=sanitized_request,
        sanitized_response=sanitized_response,
        object_storage_ref=f"generation-artifacts/{request.request_id}.json",
        recorded_at=datetime.now(UTC),
    )
