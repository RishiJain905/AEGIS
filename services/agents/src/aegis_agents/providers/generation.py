"""Thin facade over GenerationService for future Phase 19 agent runtime."""

from __future__ import annotations

from aegis_contracts.generation import GenerationRequestV1, ProviderGenerateResponseV1
from aegis_model_provider.service import GenerationService


class AgentGenerationFacade:
    def __init__(self, service: GenerationService) -> None:
        self._service = service

    async def generate(
        self,
        request: GenerationRequestV1,
        *,
        dry_run: bool = False,
    ) -> ProviderGenerateResponseV1:
        return await self._service.generate(request, dry_run=dry_run)
