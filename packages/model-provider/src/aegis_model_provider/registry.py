"""Provider registry and capability checks."""

from __future__ import annotations

import logging

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
from aegis_model_provider.egress import provider_destination_excluded
from aegis_model_provider.errors import ProviderRuntimeError, make_provider_error
from aegis_model_provider.protocol import ModelProvider

logger = logging.getLogger(__name__)

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
        self.assert_capabilities(provider.capabilities(), request)
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
        if api_key is not None and self._settings is None:
            # A fresh adapter is built *from* the settings, so without them the only thing
            # to hand back is the shared env-configured instance — which would run this
            # caller's request on the deployment's own credential and say nothing.
            # Registries built without settings are test/harness constructions; every
            # production one comes from build_provider_registry. Fail loudly so a future
            # refactor that reaches here is a crash, not a silently wrong credential.
            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.VALIDATION_FAILED,
                    message=(
                        f"Provider '{provider_id}' cannot be bound to a caller's key: this "
                        "registry was built without provider settings."
                    ),
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

    def assert_capabilities(
        self,
        capabilities: ProviderCapabilitiesV1,
        request: GenerationRequestV1,
    ) -> None:
        """Refuse a request the provider cannot honour.

        Public because a per-call credential-bound adapter never passes through
        :meth:`resolve`, and skipping resolution must not mean skipping this gate.
        """
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
        adapter = CREDENTIAL_AWARE_ADAPTERS[kind.value]
        # These two point at fixed vendor endpoints, so a deployment that leaves one out
        # of AEGIS_PROVIDER_EGRESS_ALLOWLIST is declaring that provider off-limits. That
        # should make the provider unavailable, not stop the API from booting — but only
        # when the deployment is not *running on* it, and only when the destination is
        # genuinely absent rather than malformed. Both of those still construct, and
        # construction raises loudly. The local and OpenAI adapters skip this check
        # entirely: their base URLs are deployment-specific, so a rejected one is always
        # a misconfiguration.
        if kind is not settings.AEGIS_PROVIDER_DEFAULT and provider_destination_excluded(
            base_url=adapter.configured_base_url(settings),
            allowed_base_urls=settings.provider_egress_allowlist,
        ):
            logger.warning(
                "Provider %r is not registered: its endpoint is absent from "
                "AEGIS_PROVIDER_EGRESS_ALLOWLIST. Add it there to offer this provider.",
                kind.value,
            )
            continue
        providers[kind.value] = adapter(settings)
    return ProviderRegistry(
        providers,
        default_provider_id=settings.AEGIS_PROVIDER_DEFAULT.value,
        settings=settings,
    )
