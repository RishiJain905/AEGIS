"""OpenAI hosted provider adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aegis_contracts.generation import (
    GenerationRequestV1,
    GenerationResponseV1,
    ProviderCapabilitiesV1,
    ProviderCapability,
    ProviderErrorCode,
    ProviderFinishReason,
    ProviderUsageV1,
)
from aegis_contracts.versioning import (
    GENERATION_RESPONSE_SCHEMA_VERSION,
    PROVIDER_CAPABILITIES_SCHEMA_VERSION,
    PROVIDER_USAGE_SCHEMA_VERSION,
)

from aegis_model_provider.config import ProviderSettings
from aegis_model_provider.cost import with_estimated_cost
from aegis_model_provider.egress import assert_provider_destination_allowed
from aegis_model_provider.errors import ProviderRuntimeError, make_provider_error
from aegis_model_provider.structured_output import parse_json_content, validate_structured_output


def _map_finish_reason(value: str | None) -> ProviderFinishReason:
    if value in {"stop", "tool_calls", "length", "content_filter"}:
        return ProviderFinishReason(value)
    return ProviderFinishReason.ERROR


class OpenAIHostedProvider:
    provider_id = "openai"

    def __init__(self, settings: ProviderSettings, *, base_url: str | None = None) -> None:
        self._settings = settings
        configured_base_url = (
            settings.AEGIS_PROVIDER_OPENAI_BASE_URL if base_url is None else base_url
        )
        self._base_url = assert_provider_destination_allowed(
            base_url=configured_base_url,
            allowed_base_urls=settings.provider_egress_allowlist,
            provider_id=self.provider_id,
        )

    def capabilities(self) -> ProviderCapabilitiesV1:
        return ProviderCapabilitiesV1(
            schema_version=PROVIDER_CAPABILITIES_SCHEMA_VERSION,
            capabilities=[
                ProviderCapability.STRUCTURED_OUTPUT,
                ProviderCapability.TOOLS,
            ],
        )

    def _client(self) -> Any:
        if not self._settings.AEGIS_PROVIDER_OPENAI_API_KEY.strip():
            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.CREDENTIALS_MISSING,
                    message="OpenAI provider credentials are not configured",
                    details={"providerId": self.provider_id},
                )
            )
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.INTERNAL,
                    message="OpenAI SDK is not installed",
                )
            ) from exc
        return AsyncOpenAI(
            api_key=self._settings.AEGIS_PROVIDER_OPENAI_API_KEY,
            base_url=self._base_url,
        )

    def _resolve_model_id(self, request: GenerationRequestV1) -> str:
        return request.model_config_ref.model_id or self._settings.AEGIS_PROVIDER_OPENAI_MODEL

    async def generate(self, request: GenerationRequestV1) -> GenerationResponseV1:
        client = self._client()
        model_id = self._resolve_model_id(request)
        messages = [
            {"role": message.role.value, "content": message.content} for message in request.messages
        ]
        kwargs: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "max_tokens": min(
                request.max_output_tokens, self._settings.AEGIS_PROVIDER_MAX_OUTPUT_TOKENS
            ),
        }
        if request.model_config_ref.temperature is not None:
            kwargs["temperature"] = request.model_config_ref.temperature
        if request.structured_output is not None:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "aegis_structured_output",
                    "schema": request.structured_output.json_schema,
                    "strict": request.structured_output.strict,
                },
            }
        started = datetime.now(UTC)
        try:
            completion = await client.chat.completions.create(**kwargs)
        except Exception as exc:
            error_type = type(exc).__name__
            message = str(exc)
            if "authentication" in message.lower() or "api key" in message.lower():
                raise ProviderRuntimeError(
                    make_provider_error(
                        code=ProviderErrorCode.CREDENTIALS_MISSING,
                        message="OpenAI authentication failed",
                        details={"errorType": error_type},
                        trace_id=request.trace_id,
                    )
                ) from exc
            if "timeout" in message.lower():
                raise ProviderRuntimeError(
                    make_provider_error(
                        code=ProviderErrorCode.TIMEOUT,
                        message="OpenAI request timed out",
                        retryable=True,
                        trace_id=request.trace_id,
                    )
                ) from exc
            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.PROVIDER_UNAVAILABLE,
                    message="OpenAI provider request failed",
                    retryable=True,
                    details={"errorType": error_type},
                    trace_id=request.trace_id,
                )
            ) from exc

        choice = completion.choices[0]
        content = choice.message.content or ""
        structured_data = None
        if request.structured_output is not None and content:
            structured_data = validate_structured_output(
                parse_json_content(content),
                request.structured_output,
            )
        usage = with_estimated_cost(
            model_id=model_id,
            usage=ProviderUsageV1(
                schema_version=PROVIDER_USAGE_SCHEMA_VERSION,
                prompt_tokens=completion.usage.prompt_tokens if completion.usage else 0,
                completion_tokens=completion.usage.completion_tokens if completion.usage else 0,
                total_tokens=completion.usage.total_tokens if completion.usage else 0,
            ),
        )
        latency_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
        return GenerationResponseV1(
            schema_version=GENERATION_RESPONSE_SCHEMA_VERSION,
            request_id=request.request_id,
            trace_id=request.trace_id,
            provider_id=self.provider_id,
            model_id=model_id,
            prompt_version=request.model_config_ref.prompt_version,
            content=content,
            structured_data=structured_data,
            finish_reason=_map_finish_reason(choice.finish_reason),
            usage=usage,
            latency_ms=latency_ms,
            completed_at=datetime.now(UTC),
        )
