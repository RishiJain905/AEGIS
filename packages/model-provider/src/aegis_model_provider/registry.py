"""Provider registry and capability checks."""

from __future__ import annotations

from aegis_contracts.generation import (
    GenerationRequestV1,
    ProviderCapabilitiesV1,
    ProviderCapability,
    ProviderErrorCode,
)

from aegis_model_provider.adapters.mock import MockProvider
from aegis_model_provider.adapters.openai_compatible import OpenAICompatibleProvider
from aegis_model_provider.adapters.openai_hosted import OpenAIHostedProvider
from aegis_model_provider.adapters.recorded import RecordedResponseProvider
from aegis_model_provider.config import ProviderKind, ProviderSettings
from aegis_model_provider.errors import ProviderRuntimeError, make_provider_error
from aegis_model_provider.protocol import ModelProvider


class ProviderRegistry:
    def __init__(self, providers: dict[str, ModelProvider], *, default_provider_id: str) -> None:
        self._providers = providers
        self._default_provider_id = default_provider_id

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
    return ProviderRegistry(providers, default_provider_id=settings.AEGIS_PROVIDER_DEFAULT.value)
