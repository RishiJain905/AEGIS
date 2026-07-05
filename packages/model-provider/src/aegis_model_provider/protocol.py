"""Canonical provider protocol."""

from __future__ import annotations

from typing import Protocol

from aegis_contracts.generation import (
    GenerationRequestV1,
    GenerationResponseV1,
    ProviderCapabilitiesV1,
)


class ModelProvider(Protocol):
    @property
    def provider_id(self) -> str: ...

    def capabilities(self) -> ProviderCapabilitiesV1: ...

    async def generate(self, request: GenerationRequestV1) -> GenerationResponseV1: ...
