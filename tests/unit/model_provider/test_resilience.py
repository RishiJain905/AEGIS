"""Resilience behavior tests."""

from __future__ import annotations

import asyncio
import time

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


@pytest.mark.asyncio
async def test_caller_cancellation_propagates_instead_of_becoming_a_provider_error() -> None:
    """A caller's deadline must surface as its own TimeoutError, not PROVIDER_FAILURE.

    The agent runtime wraps ``generate`` in its own ``wait_for``. When the
    resilience loop swallowed ``CancelledError`` into a returned error object, that
    outer deadline reached the operator as "Provider request was cancelled
    (PROVIDER_FAILURE)" instead of an honest agent-task timeout.
    """
    settings = ProviderSettings(
        AEGIS_PROVIDER_MAX_RETRIES=3,
        AEGIS_PROVIDER_TIMEOUT_SECONDS=30,
    )
    ctx = ResilienceContext(settings)

    async def slow() -> str:
        await asyncio.sleep(30)
        return "ok"

    with pytest.raises(TimeoutError):
        await asyncio.wait_for(
            run_with_resilience(ctx, trace_id=None, timeout_ms=None, operation=slow),
            timeout=0.1,
        )


@pytest.mark.asyncio
async def test_total_budget_bounds_every_attempt_and_backoff() -> None:
    """``timeout_ms`` is the budget for the whole call, retries and backoff included.

    Per-attempt-only budgeting let 4 attempts of 200s plus backoff run for ~14
    minutes behind a 240s caller deadline, which is exactly how the caller's
    deadline came to fire mid-retry in production.
    """
    settings = ProviderSettings(
        AEGIS_PROVIDER_MAX_RETRIES=3,
        AEGIS_PROVIDER_TIMEOUT_SECONDS=30,
        AEGIS_PROVIDER_RETRY_BACKOFF_SECONDS=0.5,
    )
    ctx = ResilienceContext(settings)

    async def slow() -> str:
        await asyncio.sleep(30)
        return "ok"

    started = time.monotonic()
    with pytest.raises(ProviderRuntimeError) as exc_info:
        await run_with_resilience(ctx, trace_id=None, timeout_ms=400, operation=slow)
    elapsed = time.monotonic() - started

    assert elapsed < 1.5, f"budget overrun: {elapsed:.2f}s for a 0.4s budget"
    assert exc_info.value.error.code in {
        ProviderErrorCode.TIMEOUT,
        ProviderErrorCode.RETRY_EXHAUSTED,
    }


@pytest.mark.asyncio
async def test_warming_up_backoff_still_respects_the_total_budget() -> None:
    """A cold-loading endpoint gets a longer backoff, but never past the deadline."""
    settings = ProviderSettings(
        AEGIS_PROVIDER_MAX_RETRIES=3,
        AEGIS_PROVIDER_TIMEOUT_SECONDS=30,
        AEGIS_PROVIDER_COLD_START_BACKOFF_SECONDS=20.0,
    )
    ctx = ResilienceContext(settings)

    async def loading() -> str:
        raise ProviderRuntimeError(
            make_provider_error(
                code=ProviderErrorCode.PROVIDER_UNAVAILABLE,
                message="Local model endpoint is still loading the model",
                retryable=True,
                details={"warmingUp": True},
            )
        )

    started = time.monotonic()
    with pytest.raises(ProviderRuntimeError):
        await run_with_resilience(ctx, trace_id=None, timeout_ms=600, operation=loading)
    elapsed = time.monotonic() - started

    assert elapsed < 1.5, f"warm-up backoff ignored the budget: {elapsed:.2f}s"


def test_retryable_error_classification() -> None:
    error = ProviderRuntimeError(
        make_provider_error(
            code=ProviderErrorCode.PROVIDER_UNAVAILABLE, message="down", retryable=True
        )
    )
    assert is_retryable_error(error)


async def _always_fails(ctx: ResilienceContext, code: ProviderErrorCode) -> None:
    async def failing() -> str:
        raise ProviderRuntimeError(make_provider_error(code=code, message="nope"))

    with pytest.raises(ProviderRuntimeError):
        await run_with_resilience(ctx, trace_id=None, timeout_ms=1000, operation=failing)


@pytest.mark.asyncio
async def test_malformed_model_output_never_opens_the_circuit() -> None:
    """A model that cannot follow its schema must not lock out a healthy endpoint.

    The breaker's job is to stop hammering a provider that is down. Counting
    model-output faults against it meant a local model missing its schema five
    turns running would fail every unrelated call for the reset window — while
    the endpoint it was protecting had answered all five requests correctly.
    """
    ctx = ResilienceContext(
        ProviderSettings(
            AEGIS_PROVIDER_MAX_RETRIES=0,
            AEGIS_PROVIDER_CIRCUIT_BREAKER_THRESHOLD=2,
        )
    )

    for _ in range(4):
        await _always_fails(ctx, ProviderErrorCode.STRUCTURED_OUTPUT_INVALID)

    assert not ctx.circuit_breaker.is_open()
    ctx.assert_circuit_closed(trace_id=None)


@pytest.mark.asyncio
async def test_a_genuinely_sick_endpoint_still_opens_the_circuit() -> None:
    """The protection the breaker actually exists for is untouched."""
    ctx = ResilienceContext(
        ProviderSettings(
            AEGIS_PROVIDER_MAX_RETRIES=0,
            AEGIS_PROVIDER_CIRCUIT_BREAKER_THRESHOLD=2,
        )
    )

    for _ in range(2):
        await _always_fails(ctx, ProviderErrorCode.PROVIDER_UNAVAILABLE)

    assert ctx.circuit_breaker.is_open()
    with pytest.raises(ProviderRuntimeError) as exc_info:
        ctx.assert_circuit_closed(trace_id=None)
    assert exc_info.value.error.code is ProviderErrorCode.CIRCUIT_OPEN
