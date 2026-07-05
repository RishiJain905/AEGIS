"""Approximate provider cost estimation for audit metadata."""

from __future__ import annotations

from aegis_contracts.generation import ProviderUsageV1
from aegis_contracts.versioning import PROVIDER_USAGE_SCHEMA_VERSION

# USD per 1M tokens — audit estimates only, not billing authority.
RATE_TABLE: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "llama3.2": (0.0, 0.0),
    "mock-v1": (0.0, 0.0),
    "recorded-v1": (0.0, 0.0),
}


def estimate_cost_usd(*, model_id: str, prompt_tokens: int, completion_tokens: int) -> float:
    prompt_rate, completion_rate = RATE_TABLE.get(model_id, (0.0, 0.0))
    return round(
        (prompt_tokens * prompt_rate + completion_tokens * completion_rate) / 1_000_000,
        8,
    )


def with_estimated_cost(*, model_id: str, usage: ProviderUsageV1) -> ProviderUsageV1:
    estimated = estimate_cost_usd(
        model_id=model_id,
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
    )
    return ProviderUsageV1(
        schema_version=PROVIDER_USAGE_SCHEMA_VERSION,
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        estimated_cost_usd=estimated,
    )
