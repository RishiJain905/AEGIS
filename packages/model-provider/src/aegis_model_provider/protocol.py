"""Canonical provider protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

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


@runtime_checkable
class ModelListingProvider(ModelProvider, Protocol):
    """A provider that can enumerate the models its endpoint serves.

    Only the endpoint-backed adapters can: the fixture-serving ones (mock, recorded)
    have no catalogue to report. Callers that need a live list — the loadout dialog's
    model picker — narrow with ``isinstance`` and say so honestly when they cannot.
    """

    async def list_models(self) -> list[str]: ...
