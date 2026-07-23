"""OpenAI-compatible local provider adapter."""

from __future__ import annotations

from typing import Any

from aegis_contracts.generation import GenerationRequestV1

from aegis_model_provider.adapters.openai_hosted import OpenAIHostedProvider
from aegis_model_provider.config import ProviderSettings


class OpenAICompatibleProvider(OpenAIHostedProvider):
    provider_id = "openai-compatible"

    def __init__(self, settings: ProviderSettings) -> None:
        super().__init__(settings, base_url=settings.AEGIS_PROVIDER_LOCAL_BASE_URL)
        self._settings = settings

    def _resolve_model_id(self, request: GenerationRequestV1) -> str:
        # The local endpoint serves whatever model llama-serve has loaded; agent
        # definitions carry synthetic ids like "openai-compatible-v1", so the env var
        # is the single source of truth for which local model is requested. A request
        # that explicitly names a real model (not the synthetic default) still wins.
        requested = request.model_config_ref.model_id
        if requested and requested != f"{self.provider_id}-v1":
            return requested
        return self._settings.AEGIS_PROVIDER_LOCAL_MODEL

    def _client(self) -> Any:
        if not self._base_url:
            from aegis_contracts.generation import ProviderErrorCode

            from aegis_model_provider.errors import ProviderRuntimeError, make_provider_error

            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.CREDENTIALS_MISSING,
                    message="Local provider endpoint is not configured",
                    details={"providerId": self.provider_id},
                )
            )
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            from aegis_contracts.generation import ProviderErrorCode

            from aegis_model_provider.errors import ProviderRuntimeError, make_provider_error

            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.INTERNAL,
                    message="OpenAI SDK is not installed",
                )
            ) from exc
        return AsyncOpenAI(
            api_key=self._settings.AEGIS_PROVIDER_LOCAL_API_KEY,
            base_url=self._base_url,
        )
