"""Thin facade over GenerationService for future Phase 19 agent runtime."""

from __future__ import annotations

from aegis_contracts.generation import GenerationRequestV1, ProviderGenerateResponseV1
from aegis_model_provider.protocol import ModelProvider
from aegis_model_provider.service import GenerationService


class AgentGenerationFacade:
    def __init__(self, service: GenerationService) -> None:
        self._service = service

    def bind_provider(
        self,
        provider_id: str,
        *,
        api_key: str | None = None,
        model_id: str | None = None,
    ) -> ModelProvider:
        """The adapter a run pinned, carrying its owner's key and chosen model.

        The returned object is the only place that key lives. Hand it straight back to
        :meth:`generate`; never store it on a task, a request, or the executor.
        """
        return self._service.bind_provider(provider_id, api_key=api_key, model_id=model_id)

    async def generate(
        self,
        request: GenerationRequestV1,
        *,
        dry_run: bool = False,
        provider: ModelProvider | None = None,
    ) -> ProviderGenerateResponseV1:
        return await self._service.generate(request, dry_run=dry_run, provider=provider)
