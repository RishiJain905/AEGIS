"""Shared provider conformance tests."""

from __future__ import annotations

import os

import pytest
from aegis_contracts.generation import (
    GenerationMessageRole,
    GenerationMessageV1,
    GenerationRequestV1,
    ModelConfigV1,
    ProviderCapability,
    ProviderErrorCode,
    StructuredOutputSpecV1,
)
from aegis_contracts.versioning import (
    GENERATION_REQUEST_SCHEMA_VERSION,
    MODEL_CONFIG_SCHEMA_VERSION,
    STRUCTURED_OUTPUT_SPEC_SCHEMA_VERSION,
)
from aegis_model_provider.adapters.mock import MockProvider
from aegis_model_provider.adapters.openai_compatible import OpenAICompatibleProvider
from aegis_model_provider.adapters.openai_hosted import OpenAIHostedProvider
from aegis_model_provider.adapters.recorded import RecordedResponseProvider
from aegis_model_provider.config import ProviderSettings
from aegis_model_provider.errors import ProviderRuntimeError
from aegis_model_provider.fingerprint import request_fingerprint
from aegis_model_provider.persistence import InMemoryGenerationArtifactRepository
from aegis_model_provider.registry import ProviderRegistry
from aegis_model_provider.service import GenerationService


def sample_request(
    *, provider_id: str = "mock", user_content: str = "Summarize"
) -> GenerationRequestV1:
    return GenerationRequestV1(
        schema_version=GENERATION_REQUEST_SCHEMA_VERSION,
        request_id="gen_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        model_config_ref=ModelConfigV1(
            schema_version=MODEL_CONFIG_SCHEMA_VERSION,
            provider_id=provider_id,
            model_id=f"{provider_id}-v1",
            prompt_version="phase18-v1",
        ),
        messages=[
            GenerationMessageV1(role=GenerationMessageRole.SYSTEM, content="System prompt"),
            GenerationMessageV1(role=GenerationMessageRole.USER, content=user_content),
        ],
        structured_output=StructuredOutputSpecV1(
            schema_version=STRUCTURED_OUTPUT_SPEC_SCHEMA_VERSION,
            json_schema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["summary", "confidence"],
                "additionalProperties": False,
            },
            strict=True,
            max_repair_attempts=0,
        ),
        capabilities_required=[ProviderCapability.STRUCTURED_OUTPUT],
    )


@pytest.mark.asyncio
async def test_mock_provider_structured_success() -> None:
    provider = MockProvider()
    response = await provider.generate(sample_request())
    assert response.provider_id == "mock"
    assert response.structured_data is not None
    assert "summary" in response.structured_data


@pytest.mark.asyncio
async def test_recorded_provider_deterministic_replay() -> None:
    settings = ProviderSettings(AEGIS_PROVIDER_RECORDED_FIXTURES_DIR="fixtures/model-responses")
    provider = RecordedResponseProvider(settings.recorded_fixtures_path)
    request = sample_request(provider_id="recorded")
    first = await provider.generate(request)
    second = await provider.generate(request)
    assert first.structured_data == second.structured_data
    assert first.usage.total_tokens == second.usage.total_tokens


@pytest.mark.asyncio
async def test_registry_rejects_unsupported_capability() -> None:
    registry = ProviderRegistry({"mock": MockProvider()}, default_provider_id="mock")
    request = sample_request()
    request = request.model_copy(update={"capabilities_required": [ProviderCapability.VISION]})
    with pytest.raises(ProviderRuntimeError) as exc_info:
        registry.resolve(request)
    assert exc_info.value.error.code == ProviderErrorCode.CAPABILITY_UNSUPPORTED


@pytest.mark.asyncio
async def test_service_rejects_malformed_structured_output() -> None:
    service = GenerationService(
        registry=ProviderRegistry({"mock": MockProvider()}, default_provider_id="mock"),
        settings=ProviderSettings(),
        artifact_repository=InMemoryGenerationArtifactRepository(),
    )
    result = await service.generate(
        sample_request(user_content="Return invalid structured output please"),
        dry_run=True,
    )
    assert result.error is not None
    assert result.error.code == ProviderErrorCode.STRUCTURED_OUTPUT_INVALID


@pytest.mark.asyncio
async def test_openai_missing_credentials_fail_closed() -> None:
    settings = ProviderSettings(AEGIS_PROVIDER_OPENAI_API_KEY="")
    provider = OpenAIHostedProvider(settings)
    with pytest.raises(ProviderRuntimeError) as exc_info:
        await provider.generate(sample_request(provider_id="openai"))
    assert exc_info.value.error.code == ProviderErrorCode.CREDENTIALS_MISSING
    assert "sk-" not in exc_info.value.error.message


@pytest.mark.skipif(
    not os.environ.get("AEGIS_PROVIDER_OPENAI_API_KEY"),
    reason="Hosted OpenAI credentials not configured",
)
@pytest.mark.asyncio
async def test_openai_hosted_adapter_when_configured() -> None:
    settings = ProviderSettings()
    provider = OpenAIHostedProvider(settings)
    request = sample_request(provider_id="openai")
    request = request.model_copy(
        update={
            "structured_output": None,
            "capabilities_required": [],
            "messages": [
                GenerationMessageV1(
                    role=GenerationMessageRole.USER, content="Say hello in one word."
                )
            ],
        }
    )
    response = await provider.generate(request)
    assert response.provider_id == "openai"
    assert response.content


@pytest.mark.skipif(
    os.environ.get("AEGIS_PROVIDER_LOCAL_SKIP", "1") == "1",
    reason="Local OpenAI-compatible endpoint not available in CI",
)
@pytest.mark.asyncio
async def test_openai_compatible_adapter_when_available() -> None:
    settings = ProviderSettings()
    provider = OpenAICompatibleProvider(settings)
    request = sample_request(provider_id="openai-compatible")
    request = request.model_copy(
        update={
            "structured_output": None,
            "capabilities_required": [],
            "messages": [
                GenerationMessageV1(
                    role=GenerationMessageRole.USER, content="Say hello in one word."
                )
            ],
        }
    )
    response = await provider.generate(request)
    assert response.provider_id == "openai-compatible"


def test_request_fingerprint_is_stable() -> None:
    request = sample_request(provider_id="recorded")
    assert request_fingerprint(request) == "541d3a346b0c2427"
