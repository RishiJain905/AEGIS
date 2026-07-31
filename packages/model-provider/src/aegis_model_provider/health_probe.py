"""Bounded, non-secret health probe for the configured model provider.

This is a **separate readiness axis** from infrastructure (postgres / redis /
object storage). The platform must stay usable with the model down, so this
probe never feeds :func:`aegis_observability.health.evaluate_readiness`; it is
reported alongside infrastructure readiness, not merged into it.

Two deliberate properties:

* **It lists, it never generates.** A ``GET {base_url}/models`` is cheap, has no
  token cost, and cannot mutate anything. It also returns the model ids the
  server *actually* serves, which is the only way to catch a stale
  ``AEGIS_PROVIDER_LOCAL_MODEL`` — the configured value is an operator claim, the
  listing is ground truth.
* **It fails soft.** Every failure path returns a ``FAILED`` result carrying a
  redacted, truncated reason. It never raises into its caller, so an admin page
  renders "failed" rather than a 500.

The vendor SDK import lives here, inside the model-provider adapter package —
domain code and API routes call :func:`probe_model_provider` and never import
``openai`` themselves.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from aegis_model_provider.config import ProviderKind, ProviderSettings
from aegis_model_provider.egress import assert_provider_destination_allowed
from aegis_model_provider.redaction import redact_string

PROBE_TIMEOUT_ENV_VAR = "AEGIS_PROVIDER_PROBE_TIMEOUT_MS"
DEFAULT_PROBE_TIMEOUT_MS = 3000
_MIN_PROBE_TIMEOUT_MS = 100
_MAX_PROBE_TIMEOUT_MS = 30_000
_MAX_REASON_CHARS = 256
_MAX_REPORTED_MODELS = 16

#: ``(base_url, api_key, timeout_seconds) -> model ids``. Injected by tests so the
#: probe stays fully offline in CI.
ModelLister = Callable[[str, str, float], Awaitable[Sequence[str]]]


class ProviderProbeState(StrEnum):
    OK = "ok"
    FAILED = "failed"
    #: Deterministic providers (mock/recorded) or a provider with no credentials
    #: configured — nothing to reach over the network, so nothing to report.
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class ProviderProbeResult:
    provider: str
    state: ProviderProbeState
    base_url: str | None
    configured_model: str | None
    reported_models: tuple[str, ...]
    latency_ms: float | None
    checked_at: str
    message: str | None

    @property
    def configured_model_served(self) -> bool | None:
        """Whether the configured model id appears in the server's listing.

        ``None`` when the probe did not get a listing back, so the panel can
        distinguish "not served" from "unknown".
        """
        if self.state is not ProviderProbeState.OK or not self.reported_models:
            return None
        return self.configured_model in self.reported_models

    def to_payload(self) -> dict[str, object]:
        """Non-secret JSON projection. Base URL and model ids are configuration."""
        reported = list(self.reported_models)
        return {
            "provider": self.provider,
            "state": self.state.value,
            "baseUrl": self.base_url,
            "configuredModel": self.configured_model,
            "reportedModels": reported,
            "reportedModel": reported[0] if reported else None,
            "configuredModelServed": self.configured_model_served,
            "latencyMs": self.latency_ms,
            "checkedAt": self.checked_at,
            "message": self.message,
        }


def resolve_probe_timeout_ms(raw: str | None = None) -> int:
    """Read ``AEGIS_PROVIDER_PROBE_TIMEOUT_MS``, clamped to a sane bound.

    Read from the environment rather than :class:`ProviderSettings` so the admin
    probe budget stays independent of ``AEGIS_PROVIDER_TIMEOUT_SECONDS`` (200s in
    this deployment) — an admin page must not hang on a wedged model server.
    """
    value = raw if raw is not None else os.environ.get(PROBE_TIMEOUT_ENV_VAR)
    if value is None or not value.strip():
        return DEFAULT_PROBE_TIMEOUT_MS
    try:
        parsed = int(value.strip())
    except ValueError:
        return DEFAULT_PROBE_TIMEOUT_MS
    return max(_MIN_PROBE_TIMEOUT_MS, min(_MAX_PROBE_TIMEOUT_MS, parsed))


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _safe_reason(text: str) -> str:
    """Redact credential-shaped material and bound the length before display."""
    redacted = redact_string(text).strip()
    if len(redacted) > _MAX_REASON_CHARS:
        redacted = redacted[: _MAX_REASON_CHARS - 1].rstrip() + "…"
    return redacted


def _result(
    *,
    provider: str,
    state: ProviderProbeState,
    base_url: str | None,
    configured_model: str | None,
    reported_models: tuple[str, ...] = (),
    latency_ms: float | None = None,
    message: str | None = None,
) -> ProviderProbeResult:
    return ProviderProbeResult(
        provider=provider,
        state=state,
        base_url=base_url,
        configured_model=configured_model,
        reported_models=reported_models,
        latency_ms=latency_ms,
        checked_at=_now(),
        message=message,
    )


async def _list_models_via_sdk(
    base_url: str,
    api_key: str,
    timeout_seconds: float,
) -> Sequence[str]:
    """Default lister: ``GET {base_url}/models`` through the OpenAI-compatible SDK."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        # llama-server ignores the key unless started with --api-key, but the SDK
        # requires a non-empty value.
        api_key=api_key or "unused",
        base_url=base_url,
        timeout=timeout_seconds,
        max_retries=0,
    )
    try:
        page = await client.models.list()
        return [str(model.id) for model in page.data]
    finally:
        await client.close()


def _endpoint_for(settings: ProviderSettings) -> tuple[str, str, str]:
    """(base_url, api_key, configured_model) for the configured provider kind."""
    if settings.AEGIS_PROVIDER_DEFAULT is ProviderKind.OPENAI:
        return (
            settings.AEGIS_PROVIDER_OPENAI_BASE_URL,
            settings.AEGIS_PROVIDER_OPENAI_API_KEY,
            settings.AEGIS_PROVIDER_OPENAI_MODEL,
        )
    return (
        settings.AEGIS_PROVIDER_LOCAL_BASE_URL,
        settings.AEGIS_PROVIDER_LOCAL_API_KEY,
        settings.AEGIS_PROVIDER_LOCAL_MODEL,
    )


async def probe_model_provider(
    settings: ProviderSettings,
    *,
    timeout_ms: int | None = None,
    list_models: ModelLister | None = None,
) -> ProviderProbeResult:
    """Probe the configured provider's model listing. Never raises."""
    kind = settings.AEGIS_PROVIDER_DEFAULT
    provider = kind.value

    if kind in {ProviderKind.MOCK, ProviderKind.RECORDED}:
        return _result(
            provider=provider,
            state=ProviderProbeState.SKIPPED,
            base_url=None,
            configured_model=None,
            message=f"Provider '{provider}' serves deterministic fixtures; no endpoint to probe.",
        )

    base_url, api_key, configured_model = _endpoint_for(settings)

    if not base_url.strip():
        return _result(
            provider=provider,
            state=ProviderProbeState.FAILED,
            base_url=None,
            configured_model=configured_model,
            message="Provider base URL is not configured.",
        )

    if kind is ProviderKind.OPENAI and not api_key.strip():
        return _result(
            provider=provider,
            state=ProviderProbeState.SKIPPED,
            base_url=base_url,
            configured_model=configured_model,
            message="No API key configured for the hosted provider; endpoint not contacted.",
        )

    try:
        assert_provider_destination_allowed(
            base_url=base_url,
            allowed_base_urls=settings.provider_egress_allowlist,
            provider_id=provider,
        )
    except Exception:  # noqa: BLE001 — fail closed, and never echo the destination
        return _result(
            provider=provider,
            state=ProviderProbeState.FAILED,
            base_url=base_url,
            configured_model=configured_model,
            message="Provider destination is not in the egress allowlist; not contacted.",
        )

    budget_ms = timeout_ms if timeout_ms is not None else resolve_probe_timeout_ms()
    budget_seconds = budget_ms / 1000.0
    lister = list_models if list_models is not None else _list_models_via_sdk

    started = time.perf_counter()
    try:
        models = await asyncio.wait_for(
            lister(base_url, api_key, budget_seconds),
            # Small grace so the client's own timeout wins and yields a better
            # message; the outer bound is what guarantees the route returns.
            timeout=budget_seconds + 0.5,
        )
    except TimeoutError:  # asyncio.TimeoutError is an alias since 3.11
        return _result(
            provider=provider,
            state=ProviderProbeState.FAILED,
            base_url=base_url,
            configured_model=configured_model,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            message=f"Provider did not answer within {budget_ms} ms.",
        )
    except asyncio.CancelledError:  # pragma: no cover - caller shutdown
        raise
    except Exception as exc:  # noqa: BLE001 — a probe must never break its caller
        return _result(
            provider=provider,
            state=ProviderProbeState.FAILED,
            base_url=base_url,
            configured_model=configured_model,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            message=_safe_reason(f"{type(exc).__name__}: {exc}"),
        )

    latency_ms = (time.perf_counter() - started) * 1000.0
    reported = tuple(str(model) for model in models)[:_MAX_REPORTED_MODELS]
    if not reported:
        return _result(
            provider=provider,
            state=ProviderProbeState.FAILED,
            base_url=base_url,
            configured_model=configured_model,
            latency_ms=latency_ms,
            message="Provider answered but reported no available models.",
        )
    return _result(
        provider=provider,
        state=ProviderProbeState.OK,
        base_url=base_url,
        configured_model=configured_model,
        reported_models=reported,
        latency_ms=latency_ms,
    )
