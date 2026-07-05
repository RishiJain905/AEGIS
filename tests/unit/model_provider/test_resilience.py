"""Resilience behavior tests."""

from __future__ import annotations

import asyncio

import pytest
from aegis_contracts.generation import ProviderErrorCode
from aegis_model_provider.config import ProviderSettings
from aegis_model_provider.errors import ProviderRuntimeError, make_provider_error
from aegis_model_provider.resilience import (
    ResilienceContext,
    is_retryable_error,
    run_with_resilience,
)


@pytest.mark.asyncio
async def test_timeout_is_retryable_and_normalized() -> None:
    settings = ProviderSettings(AEGIS_PROVIDER_MAX_RETRIES=0, AEGIS_PROVIDER_TIMEOUT_SECONDS=1)
    ctx = ResilienceContext(settings)

    async def slow() -> str:
        await asyncio.sleep(2)
        return "ok"

    with pytest.raises(ProviderRuntimeError) as exc_info:
        await run_with_resilience(
            ctx, trace_id="trc_01ARZ3NDEKTSV4RRFFQ69G5FAV", timeout_ms=100, operation=slow
        )
    assert exc_info.value.error.code in {
        ProviderErrorCode.TIMEOUT,
        ProviderErrorCode.RETRY_EXHAUSTED,
    }


def test_retryable_error_classification() -> None:
    error = ProviderRuntimeError(
        make_provider_error(
            code=ProviderErrorCode.PROVIDER_UNAVAILABLE, message="down", retryable=True
        )
    )
    assert is_retryable_error(error)
