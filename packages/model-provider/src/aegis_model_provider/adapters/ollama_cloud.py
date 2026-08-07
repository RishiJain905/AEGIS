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

#: The model the credential probe asks for. Deliberately synthetic and deliberately
#: absent from every catalogue: the probe needs a request that authenticates and then
#: fails for a reason that is not the key, so nothing generates and nothing is billed.
CREDENTIAL_PROBE_MODEL_ID = "aegis-credential-probe-nonexistent"

_UNKNOWN_MODEL_PHRASES = (
    "not found",
    "does not exist",
    "unknown model",
    "no such model",
)


def _is_unknown_model(message: str, exc: Exception) -> bool:
    """Whether the endpoint answered "there is no such model" rather than refusing us.

    That answer is the probe's success signal, so read it narrowly. A 404 counts on its
    own — the request reached the chat endpoint and was told the model is absent. A 400
    counts only when it says so in words, because 400 is also how this endpoint
    complains about a malformed request, which proves nothing either way. No HTTP
    status at all (connection/timeout/DNS failure) never counts — the endpoint
    rendered no verdict, so the key stays unproven no matter how the message reads.
    """
    status = getattr(exc, "status_code", None)
    if status == 404:
        return True
    if status == 400:
        lowered = message.lower()
        return any(phrase in lowered for phrase in _UNKNOWN_MODEL_PHRASES)
    return False


class OllamaCloudProvider(OpenAIHostedProvider):
    provider_id = "ollama-cloud"

    @classmethod
    def configured_base_url(cls, settings: ProviderSettings) -> str:
        return settings.AEGIS_PROVIDER_OLLAMA_CLOUD_BASE_URL

    def _configured_api_key(self) -> str | None:
        return self._settings.AEGIS_PROVIDER_OLLAMA_CLOUD_API_KEY

    async def verify_credentials(self) -> None:
        """Prove the key by asking for a model that cannot exist.

        The inherited default — list the catalogue — cannot work here:
        ``https://ollama.com/v1/models`` is a public list that answers 200 with no
        credentials, so it accepted any string as a verified key. Ollama Cloud has no
        key-introspection endpoint to ask instead, so the smallest *authenticated*
        request stands in for one.

        The trick is which failure we are hoping for. A chat completion for
        ``CREDENTIAL_PROBE_MODEL_ID`` can only come back two ways: refused at the door
        (401/403 — the key is bad) or refused for the model (404, or a 400 that names
        it — the key got in, which is the entire question). The second is success. No
        model runs either way, and ``max_tokens=1`` bounds the request that never
        happens.
        """
        client = self._client()
        try:
            await client.chat.completions.create(
                model=CREDENTIAL_PROBE_MODEL_ID,
                messages=[{"role": "user", "content": "."}],
                max_tokens=1,
            )
        except Exception as exc:
            if _is_unknown_model(str(exc), exc):
                return
            raise self._verification_error(exc) from exc
        finally:
            await self._close_client(client)

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
