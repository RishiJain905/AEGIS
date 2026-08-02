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


#: Failures that say nothing about whether the endpoint is healthy: the call
#: reached the provider and the provider answered. What went wrong was the
#: caller's request or the model's own output.
_HEALTHY_ENDPOINT_CODES = frozenset(
    {
        ProviderErrorCode.STRUCTURED_OUTPUT_INVALID,
        ProviderErrorCode.OUTPUT_LIMIT_EXCEEDED,
        ProviderErrorCode.VALIDATION_FAILED,
        ProviderErrorCode.CAPABILITY_UNSUPPORTED,
    }
)


def counts_against_endpoint_health(error: ProviderRuntimeError) -> bool:
    """Whether this failure is evidence the provider itself is sick.

    The breaker exists to stop hammering an endpoint that is down. Feeding it
    model-output faults instead inverts that: a local model that misses its
    schema five turns running would trip the breaker and lock out every caller
    for the reset window, while the endpoint it was "protecting" answered all
    five requests perfectly. That is the same misdiagnosis as reporting malformed
    JSON as ``PROVIDER_FAILURE``, one layer down and with a much wider blast
    radius, because an open circuit fails calls that had nothing to do with it.
    """
    return error.error.code not in _HEALTHY_ENDPOINT_CODES


# Below this much remaining budget there is no point starting another attempt:
# the model would be cut off before it could produce anything usable, and the
# turn is better spent reporting an honest timeout.
MIN_ATTEMPT_SECONDS = 1.0


def _is_warming_up(error: ProviderRuntimeError) -> bool:
    """Whether the endpoint said it is still loading its weights."""
    return bool(error.error.details.get("warmingUp"))


async def run_with_resilience[T](
    ctx: ResilienceContext,
    *,
    trace_id: str | None,
    timeout_ms: int | None,
    operation: Callable[[], Awaitable[T]],
) -> T:
    """Run ``operation`` under a retry/circuit/concurrency budget.

    ``timeout_ms`` is the budget for the WHOLE call — every attempt plus the
    backoff between them — not one attempt. That is the contract the caller
    actually needs: the agent runtime holds its own task deadline over this call,
    and per-attempt-only budgeting made it arithmetically certain that the
    caller's deadline would fire mid-retry (4 attempts x 200s behind a 240s
    deadline). When it did, the loop reported "Provider request was cancelled"
    and the operator saw a PROVIDER_FAILURE for what was really a timeout.

    Each attempt therefore gets ``min(per-attempt ceiling, budget remaining)``,
    and no attempt starts without enough runway to matter. When the budget runs
    out the caller gets TIMEOUT/RETRY_EXHAUSTED — a real, retryable provider
    error with a persisted artifact — rather than being killed mid-flight.

    ``CancelledError`` is re-raised untouched. Cancellation belongs to whoever
    requested it (an outer deadline, a disconnected client); converting it into a
    returned error object both lies about the cause and breaks structured
    concurrency for every caller above.
    """
    ctx.assert_circuit_closed(trace_id=trace_id)
    attempt_ceiling = float(ctx.settings.AEGIS_PROVIDER_TIMEOUT_SECONDS)
    total_budget = timeout_ms / 1000.0 if timeout_ms is not None else attempt_ceiling
    deadline = time.monotonic() + total_budget
    attempt = 0
    max_attempts = ctx.settings.AEGIS_PROVIDER_MAX_RETRIES + 1
    last_error: ProviderRuntimeError | None = None

    async with ctx.semaphore:
        while attempt < max_attempts:
            remaining = deadline - time.monotonic()
            if attempt > 0 and remaining < MIN_ATTEMPT_SECONDS:
                break
            attempt += 1
            try:
                result = await asyncio.wait_for(
                    operation(), timeout=max(MIN_ATTEMPT_SECONDS, min(attempt_ceiling, remaining))
                )
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
            except ProviderRuntimeError as exc:
                last_error = exc
                if not is_retryable_error(exc) or attempt >= max_attempts:
                    if counts_against_endpoint_health(exc):
                        ctx.circuit_breaker.record_failure()
                    raise
            except asyncio.CancelledError:
                # Not ours to convert — see the docstring.
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

            if counts_against_endpoint_health(last_error):
                ctx.circuit_breaker.record_failure()
            backoff = (
                ctx.settings.AEGIS_PROVIDER_COLD_START_BACKOFF_SECONDS
                if _is_warming_up(last_error)
                else ctx.settings.AEGIS_PROVIDER_RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
            )
            # Sleeping past the deadline would only delay the timeout the caller
            # is already owed, so the backoff is clamped to what is left.
            sleep_for = min(backoff, max(0.0, deadline - time.monotonic()))
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)

    # The loop exits either because the attempts ran out or because the budget
    # did; both mean "we gave the provider everything it was allotted", so both
    # normalize to RETRY_EXHAUSTED rather than leaving a bare per-attempt error.
    exhausted = attempt >= max_attempts or time.monotonic() >= deadline
    if last_error is not None:
        if last_error.error.code == ProviderErrorCode.TIMEOUT and exhausted:
            raise ProviderRuntimeError(
                make_provider_error(
                    code=ProviderErrorCode.RETRY_EXHAUSTED,
                    message="Provider request timed out after retries",
                    retryable=False,
                    trace_id=trace_id,
                )
            ) from None
        if exhausted and is_retryable_error(last_error):
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
