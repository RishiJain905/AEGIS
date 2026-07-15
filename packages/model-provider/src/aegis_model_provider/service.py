"""Canonical generation orchestration service."""

from __future__ import annotations

import time

from aegis_contracts.generation import (
    GenerationArtifactV1,
    GenerationRequestV1,
    GenerationResponseV1,
    ProviderErrorCode,
    ProviderGenerateResponseV1,
)
from aegis_contracts.versioning import PROVIDER_GENERATE_RESPONSE_SCHEMA_VERSION

from aegis_model_provider.config import ProviderSettings
from aegis_model_provider.errors import ProviderRuntimeError, make_provider_error
from aegis_model_provider.persistence import (
    GenerationArtifactRepository,
    build_generation_artifact,
)
from aegis_model_provider.protocol import ModelProvider
from aegis_model_provider.registry import ProviderRegistry
from aegis_model_provider.resilience import ResilienceContext, run_with_resilience
from aegis_model_provider.structured_output import (
    build_repair_messages,
    parse_json_content,
    validate_structured_output,
)


class GenerationService:
    def __init__(
        self,
        *,
        registry: ProviderRegistry,
        settings: ProviderSettings,
        artifact_repository: GenerationArtifactRepository,
    ) -> None:
        self._registry = registry
        self._settings = settings
        self._artifact_repository = artifact_repository
        self._resilience = ResilienceContext(settings)

    async def generate(
        self,
        request: GenerationRequestV1,
        *,
        dry_run: bool = False,
    ) -> ProviderGenerateResponseV1:
        started = time.perf_counter()
        try:
            self._validate_request(request)
            provider = self._registry.resolve(request)

            async def operation() -> GenerationResponseV1:
                return await self._generate_with_optional_repair(provider, request)

            response: GenerationResponseV1 = await run_with_resilience(
                self._resilience,
                trace_id=request.trace_id,
                timeout_ms=request.timeout_ms,
                operation=operation,
            )
            latency_ms = int((time.perf_counter() - started) * 1000)
            try:
                from aegis_observability.instrumentation import record_provider_call

                usage = getattr(response, "usage", None)
                tokens = None
                cost = None
                if usage is not None:
                    tokens = getattr(usage, "total_tokens", None) or getattr(
                        usage, "totalTokens", None
                    )
                    cost = getattr(usage, "estimated_cost", None) or getattr(
                        usage, "estimatedCost", None
                    )
                record_provider_call(
                    provider=str(
                        getattr(response, "provider_id", None)
                        or request.provider_id
                        or request.model_config_ref.provider_id
                        or "unknown"
                    ),
                    model_alias=str(
                        getattr(response, "model", None)
                        or request.model_config_ref.model_id
                        or "default"
                    ),
                    duration_ms=float(latency_ms),
                    status="ok",
                    tokens=int(tokens) if tokens is not None else None,
                    cost=float(cost) if cost is not None else None,
                )
            except Exception:  # noqa: BLE001
                pass
            if not dry_run:
                artifact = build_generation_artifact(
                    request=request,
                    response=response,
                    error=None,
                    latency_ms=latency_ms,
                )
                await self._artifact_repository.save(artifact)
                storage_ref = artifact.object_storage_ref
                if storage_ref is not None:
                    response = response.model_copy(update={"artifact_ref": storage_ref})
            return ProviderGenerateResponseV1(
                schema_version=PROVIDER_GENERATE_RESPONSE_SCHEMA_VERSION,
                response=response,
            )
        except ProviderRuntimeError as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            try:
                from aegis_observability.instrumentation import record_provider_call

                record_provider_call(
                    provider=str(
                        request.provider_id
                        or request.model_config_ref.provider_id
                        or "unknown"
                    ),
                    model_alias=str(request.model_config_ref.model_id or "default"),
                    duration_ms=float(latency_ms),
                    status="error",
                )
            except Exception:  # noqa: BLE001
                pass
            if not dry_run:
                artifact = build_generation_artifact(
                    request=request,
                    response=None,
                    error=exc.error,
                    latency_ms=latency_ms,
                )
                await self._artifact_repository.save(artifact)
            return ProviderGenerateResponseV1(
                schema_version=PROVIDER_GENERATE_RESPONSE_SCHEMA_VERSION,
                error=exc.error,
            )

    def _validate_request(self, request: GenerationRequestV1) -> None:
        if request.max_output_tokens > self._settings.AEGIS_PROVIDER_MAX_OUTPUT_TOKENS:
            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.OUTPUT_LIMIT_EXCEEDED,
                    message="Requested output exceeds configured provider limit",
                    trace_id=request.trace_id,
                )
            )

    async def _generate_with_optional_repair(
        self,
        provider: ModelProvider,
        request: GenerationRequestV1,
    ) -> GenerationResponseV1:
        response = await provider.generate(request)
        if request.structured_output is None:
            return response
        if response.structured_data is not None:
            validate_structured_output(response.structured_data, request.structured_output)
            return response
        if not response.content:
            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.STRUCTURED_OUTPUT_INVALID,
                    message="Provider returned empty structured output",
                    trace_id=request.trace_id,
                )
            )
        try:
            parsed = parse_json_content(response.content)
            validate_structured_output(parsed, request.structured_output)
            return response.model_copy(update={"structured_data": parsed})
        except ProviderRuntimeError as exc:
            if request.structured_output.max_repair_attempts < 1:
                raise
            repair_request = request.model_copy(
                update={
                    "messages": build_repair_messages(
                        request,
                        invalid_content=response.content,
                        validation_message=exc.error.message,
                    )
                }
            )
            repaired = await provider.generate(repair_request)
            if repaired.structured_data is None and repaired.content:
                repaired = repaired.model_copy(
                    update={
                        "structured_data": validate_structured_output(
                            parse_json_content(repaired.content),
                            request.structured_output,
                        )
                    }
                )
            if repaired.structured_data is None:
                raise
            validate_structured_output(repaired.structured_data, request.structured_output)
            return repaired

    async def get_artifact(self, request_id: str) -> GenerationArtifactV1 | None:
        return await self._artifact_repository.get_by_request_id(request_id)
