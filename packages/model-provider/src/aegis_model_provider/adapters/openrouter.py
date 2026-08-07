"""OpenRouter provider adapter.

OpenRouter fronts hundreds of models behind the OpenAI chat-completions wire format,
so the whole adapter is the hosted one pointed at a different base URL with a
different key. The key and model normally arrive per call — the run owner's stored
credential and the model their loadout pinned — rather than from the environment.
"""

from __future__ import annotations

from aegis_contracts.generation import ProviderErrorCode

from aegis_model_provider.adapters.openai_hosted import OpenAIHostedProvider
from aegis_model_provider.config import ProviderSettings
from aegis_model_provider.errors import ProviderRuntimeError, make_provider_error


class OpenRouterProvider(OpenAIHostedProvider):
    provider_id = "openrouter"

    @classmethod
    def configured_base_url(cls, settings: ProviderSettings) -> str:
        return settings.AEGIS_PROVIDER_OPENROUTER_BASE_URL

    def _configured_api_key(self) -> str | None:
        return self._settings.AEGIS_PROVIDER_OPENROUTER_API_KEY

    async def verify_credentials(self) -> None:
        """Prove the key against ``GET {base}/key``, which actually authenticates.

        The inherited default — list the catalogue and see whether it refuses — cannot
        work here: ``https://openrouter.ai/api/v1/models`` is a public global list that
        answers 200 with no credentials at all, so every string an operator pasted came
        back "verified". ``/key`` is OpenRouter's own key-introspection endpoint: 200
        with the key's metadata when it is real, 401 when it is not.

        It goes through the SDK client so the request inherits this adapter's timeout
        and its already-allowlisted base URL, rather than opening a second HTTP path
        with its own idea of where it may connect.
        """
        client = self._client()
        try:
            # cast_to=object: the answer is a live-key signal, not a payload we read.
            await client.get("/key", cast_to=object)
        except Exception as exc:
            raise self._verification_error(exc) from exc
        finally:
            await self._close_client(client)

    def _default_model_id(self) -> str:
        model_id = self._model_id_override or self._settings.AEGIS_PROVIDER_OPENROUTER_MODEL
        if not model_id:
            # OpenRouter has no house model to fall back to, and sending an empty one
            # would surface as an opaque 400 from the endpoint.
            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.VALIDATION_FAILED,
                    message="No model is selected for provider 'openrouter'",
                    details={"providerId": self.provider_id},
                )
            )
        return model_id
