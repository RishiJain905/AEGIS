"""Ollama Cloud provider adapter.

Ollama's hosted service exposes the same OpenAI-compatible surface as the local
llama-server, so this is the hosted adapter pointed at ollama.com with the operator's
own subscription key. The key and model normally arrive per call — the run owner's
stored credential and the model their loadout pinned — rather than from the environment.
"""

from __future__ import annotations

from aegis_contracts.generation import ProviderErrorCode

from aegis_model_provider.adapters.openai_hosted import OpenAIHostedProvider
from aegis_model_provider.config import ProviderSettings
from aegis_model_provider.errors import ProviderRuntimeError, make_provider_error


class OllamaCloudProvider(OpenAIHostedProvider):
    provider_id = "ollama-cloud"

    def __init__(
        self,
        settings: ProviderSettings,
        *,
        api_key_override: str | None = None,
        model_id_override: str | None = None,
    ) -> None:
        super().__init__(
            settings,
            base_url=settings.AEGIS_PROVIDER_OLLAMA_CLOUD_BASE_URL,
            api_key_override=api_key_override,
            model_id_override=model_id_override,
        )

    def _configured_api_key(self) -> str | None:
        return self._settings.AEGIS_PROVIDER_OLLAMA_CLOUD_API_KEY

    def _default_model_id(self) -> str:
        model_id = self._model_id_override or self._settings.AEGIS_PROVIDER_OLLAMA_CLOUD_MODEL
        if not model_id:
            # Which models an account can serve varies by subscription, so there is no
            # safe default; an empty model would surface as an opaque 400.
            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.VALIDATION_FAILED,
                    message="No model is selected for provider 'ollama-cloud'",
                    details={"providerId": self.provider_id},
                )
            )
        return model_id
