"""OpenAI-compatible local provider adapter."""

from __future__ import annotations

from aegis_model_provider.adapters.openai_hosted import OpenAIHostedProvider
from aegis_model_provider.config import ProviderSettings


class OpenAICompatibleProvider(OpenAIHostedProvider):
    provider_id = "openai-compatible"

    def __init__(self, settings: ProviderSettings) -> None:
        super().__init__(settings)
        self._settings = settings

    def _client(self):
        if not self._settings.AEGIS_PROVIDER_LOCAL_BASE_URL.strip():
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
            base_url=self._settings.AEGIS_PROVIDER_LOCAL_BASE_URL,
        )
