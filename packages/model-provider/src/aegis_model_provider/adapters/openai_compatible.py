"""OpenAI-compatible local provider adapter."""

from __future__ import annotations

from aegis_model_provider.adapters.openai_hosted import OpenAIHostedProvider
from aegis_model_provider.config import ProviderSettings


class OpenAICompatibleProvider(OpenAIHostedProvider):
    provider_id = "openai-compatible"

    # llama-server's json_schema grammar cannot coexist with this model's forced
    # <think> opener (see OpenAIHostedProvider._use_server_response_format).
    _use_server_response_format = False

    @classmethod
    def configured_base_url(cls, settings: ProviderSettings) -> str:
        return settings.AEGIS_PROVIDER_LOCAL_BASE_URL

    def _configured_api_key(self) -> str | None:
        return self._settings.AEGIS_PROVIDER_LOCAL_API_KEY

    def _default_model_id(self) -> str:
        # The local endpoint serves whatever model llama-server has loaded, so the env
        # var is the source of truth for which local model is requested.
        return self._model_id_override or self._settings.AEGIS_PROVIDER_LOCAL_MODEL
