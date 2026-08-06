"""Provider registry and capability checks."""

from __future__ import annotations

from aegis_contracts.generation import (
    GenerationRequestV1,
    ProviderCapabilitiesV1,
    ProviderCapability,
    ProviderErrorCode,
)

from aegis_model_provider.adapters.mock import MockProvider
from aegis_model_provider.adapters.ollama_cloud import OllamaCloudProvider
from aegis_model_provider.adapters.openai_compatible import OpenAICompatibleProvider
from aegis_model_provider.adapters.openai_hosted import OpenAIHostedProvider
from aegis_model_provider.adapters.openrouter import OpenRouterProvider
from aegis_model_provider.adapters.recorded import RecordedResponseProvider
from aegis_model_provider.config import ProviderKind, ProviderSettings
from aegis_model_provider.errors import ProviderRuntimeError, make_provider_error
from aegis_model_provider.protocol import ModelProvider

#: Adapters that accept per-call credentials. Mock and recorded serve fixtures and have
#: nothing to override, so ``resolve_with_credentials`` hands back their shared instance.
CREDENTIAL_AWARE_ADAPTERS: dict[str, type[OpenAIHostedProvider]] = {
    ProviderKind.OPENAI.value: OpenAIHostedProvider,
    ProviderKind.OPENAI_COMPATIBLE.value: OpenAICompatibleProvider,
    ProviderKind.OPENROUTER.value: OpenRouterProvider,
    ProviderKind.OLLAMA_CLOUD.value: OllamaCloudProvider,
}


class ProviderRegistry:
    def __init__(
        self,
        providers: dict[str, ModelProvider],
        *,
        default_provider_id: str,
        settings: ProviderSettings | None = None,
    ) -> None:
        self._providers = providers
        self._default_provider_id = default_provider_id
        self._settings = settings

    def list_providers(self) -> list[dict[str, object]]:
        return [
            {
                "providerId": provider.provider_id,
                "capabilities": provider.capabilities().model_dump(by_alias=True, mode="json"),
            }
            for provider in self._providers.values()
        ]

    def resolve(self, request: GenerationRequestV1) -> ModelProvider:
        provider_id = (
            request.provider_id or request.model_config_ref.provider_id or self._default_provider_id
        )
        provider = self._providers.get(provider_id)
        if provider is None:
            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.VALIDATION_FAILED,
                    message=f"Unknown provider: {provider_id}",
                    details={"providerId": provider_id},
                    trace_id=request.trace_id,
                )
            )
        self._assert_capabilities(provider.capabilities(), request)
        return provider

    def resolve_with_credentials(
        self,
        provider_id: str,
        *,
        api_key: str | None = None,
        model_id: str | None = None,
    ) -> ModelProvider:
        """A provider bound to one caller's credential and pinned model.

        The registry's own adapters read the environment, which is right for the
        default/admin path but wrong for a run driven by its owner's subscription. This
        returns a *fresh* adapter of the same kind carrying the overrides, so a key
        never leaks into shared state and concurrent runs on different accounts cannot
        see each other's. The key stays in the SDK client; nothing persists it.
        """
        if provider_id not in self._providers:
            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.VALIDATION_FAILED,
                    message=f"Unknown provider: {provider_id}",
                    details={"providerId": provider_id},
                )
            )
        adapter = CREDENTIAL_AWARE_ADAPTERS.get(provider_id)
        if adapter is None or self._settings is None:
            # Fixture-serving providers, and registries built without settings (tests,
            # narrow harnesses): there is nothing to bind, so the shared instance is it.
            return self._providers[provider_id]
        return adapter(
            self._settings,
            api_key_override=api_key,
            model_id_override=model_id,
        )

    def _assert_capabilities(
        self,
        capabilities: ProviderCapabilitiesV1,
        request: GenerationRequestV1,
    ) -> None:
        available = set(capabilities.capabilities)
        missing = [cap for cap in request.capabilities_required if cap not in available]
        if missing:
            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.CAPABILITY_UNSUPPORTED,
                    message="Provider does not support required capabilities",
                    details={"missing": [cap.value for cap in missing]},
                    trace_id=request.trace_id,
                )
            )
        if (
            request.structured_output is not None
            and ProviderCapability.STRUCTURED_OUTPUT not in available
        ):
            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.CAPABILITY_UNSUPPORTED,
                    message="Provider does not support structured output",
                    trace_id=request.trace_id,
                )
            )
        if request.tools and ProviderCapability.TOOLS not in available:
            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.CAPABILITY_UNSUPPORTED,
                    message="Provider does not support tools",
                    trace_id=request.trace_id,
                )
            )


def build_provider_registry(settings: ProviderSettings) -> ProviderRegistry:
    providers: dict[str, ModelProvider] = {
        ProviderKind.MOCK.value: MockProvider(),
        ProviderKind.RECORDED.value: RecordedResponseProvider(settings.recorded_fixtures_path),
        ProviderKind.OPENAI.value: OpenAIHostedProvider(settings),
        ProviderKind.OPENAI_COMPATIBLE.value: OpenAICompatibleProvider(settings),
    }
    for kind in (ProviderKind.OPENROUTER, ProviderKind.OLLAMA_CLOUD):
        try:
            providers[kind.value] = CREDENTIAL_AWARE_ADAPTERS[kind.value](settings)
        except ProviderRuntimeError:
            # These two point at fixed vendor endpoints, so a deployment that leaves
            # theirs out of AEGIS_PROVIDER_EGRESS_ALLOWLIST is declaring the provider
            # off-limits. That has to make the provider unavailable — resolving it says
            # "Unknown provider" — not stop the API from booting. The local and OpenAI
            # adapters stay strict above: their base URLs are deployment-specific, so a
            # rejected one is a misconfiguration worth failing loudly on.
            continue
    return ProviderRegistry(
        providers,
        default_provider_id=settings.AEGIS_PROVIDER_DEFAULT.value,
        settings=settings,
    )
