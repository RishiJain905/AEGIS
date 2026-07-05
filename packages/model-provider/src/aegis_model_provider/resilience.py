"""Resilience primitives for provider calls."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from aegis_contracts.generation import ProviderErrorCode

from aegis_model_provider.config import ProviderSettings
from aegis_model_provider.errors import ProviderRuntimeError, make_provider_error


@dataclass
class CircuitBreakerState:
    failure_threshold: int
    reset_seconds: float
    failures: int = 0
    opened_at: float | None = None

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.opened_at = time.monotonic()

    def is_open(self) -> bool:
        if self.opened_at is None:
            return False
        if time.monotonic() - self.opened_at >= self.reset_seconds:
            self.failures = 0
            self.opened_at = None
            return False
        return True


@dataclass
class ResilienceContext:
    settings: ProviderSettings
    circuit_breaker: CircuitBreakerState = field(init=False)
    semaphore: asyncio.Semaphore = field(init=False)

    def __post_init__(self) -> None:
        self.circuit_breaker = CircuitBreakerState(
            failure_threshold=self.settings.AEGIS_PROVIDER_CIRCUIT_BREAKER_THRESHOLD,
            reset_seconds=float(self.settings.AEGIS_PROVIDER_CIRCUIT_BREAKER_RESET_SECONDS),
        )
        self.semaphore = asyncio.Semaphore(self.settings.AEGIS_PROVIDER_MAX_CONCURRENT_REQUESTS)

    def assert_circuit_closed(self, *, trace_id: str | None) -> None:
        if self.circuit_breaker.is_open():
            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.CIRCUIT_OPEN,
                    message="Provider circuit breaker is open",
                    retryable=True,
                    trace_id=trace_id,
                )
            )


def is_retryable_error(error: ProviderRuntimeError) -> bool:
    return error.error.retryable or error.error.code in {
        ProviderErrorCode.PROVIDER_UNAVAILABLE,
        ProviderErrorCode.TIMEOUT,
    }


async def run_with_resilience[T](
    ctx: ResilienceContext,
    *,
    trace_id: str | None,
    timeout_ms: int | None,
    operation: Callable[[], Awaitable[T]],
) -> T:
    ctx.assert_circuit_closed(trace_id=trace_id)
    timeout_seconds = (
        timeout_ms / 1000.0
        if timeout_ms is not None
        else float(ctx.settings.AEGIS_PROVIDER_TIMEOUT_SECONDS)
    )
    attempt = 0
    max_attempts = ctx.settings.AEGIS_PROVIDER_MAX_RETRIES + 1
    last_error: ProviderRuntimeError | None = None

    async with ctx.semaphore:
        while attempt < max_attempts:
            attempt += 1
            try:
                result = await asyncio.wait_for(operation(), timeout=timeout_seconds)
                ctx.circuit_breaker.record_success()
                return result
            except TimeoutError:
                last_error = ProviderRuntimeError(
                    make_provider_error(
                        code=ProviderErrorCode.TIMEOUT,
                        message="Provider request timed out",
                        retryable=True,
                        trace_id=trace_id,
                    )
                )
            except asyncio.CancelledError:
                raise ProviderRuntimeError(
                    make_provider_error(
                        code=ProviderErrorCode.CANCELLATION,
                        message="Provider request was cancelled",
                        retryable=False,
                        trace_id=trace_id,
                    )
                ) from None
            except ProviderRuntimeError as exc:
                last_error = exc
                if not is_retryable_error(exc) or attempt >= max_attempts:
                    ctx.circuit_breaker.record_failure()
                    raise
            except Exception as exc:
                last_error = ProviderRuntimeError(
                    make_provider_error(
                        code=ProviderErrorCode.INTERNAL,
                        message="Unexpected provider failure",
                        retryable=False,
                        details={"errorType": type(exc).__name__},
                        trace_id=trace_id,
                    )
                )
                ctx.circuit_breaker.record_failure()
                raise last_error from exc

            ctx.circuit_breaker.record_failure()
            await asyncio.sleep(
                ctx.settings.AEGIS_PROVIDER_RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
            )

    if last_error is not None:
        if last_error.error.code == ProviderErrorCode.TIMEOUT and attempt >= max_attempts:
            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.RETRY_EXHAUSTED,
                    message="Provider request timed out after retries",
                    retryable=False,
                    trace_id=trace_id,
                )
            ) from None
        if attempt >= max_attempts and is_retryable_error(last_error):
            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.RETRY_EXHAUSTED,
                    message="Provider retries exhausted",
                    retryable=False,
                    trace_id=trace_id,
                )
            ) from last_error
        raise last_error
    raise ProviderRuntimeError(
        make_provider_error(
            code=ProviderErrorCode.INTERNAL,
            message="Provider resilience loop exited unexpectedly",
            trace_id=trace_id,
        )
    )
