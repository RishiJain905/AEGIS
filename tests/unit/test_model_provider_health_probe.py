"""Bounded, non-secret health probe for the configured model provider.

The probe is a *separate readiness axis* from infrastructure: it must never raise
into its caller, never echo credentials, and must report the model ids the
provider server actually serves (not the configured env value, which drifts).
Fully offline — the network lister is always injected.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence

import pytest
from aegis_model_provider.config import ProviderKind, ProviderSettings
from aegis_model_provider.health_probe import (
    ProviderProbeState,
    probe_model_provider,
    resolve_probe_timeout_ms,
)


def _local_settings(**overrides: object) -> ProviderSettings:
    base: dict[str, object] = {
        "AEGIS_PROVIDER_DEFAULT": ProviderKind.OPENAI_COMPATIBLE,
        "AEGIS_PROVIDER_LOCAL_BASE_URL": "http://localhost:8086/v1",
        "AEGIS_PROVIDER_LOCAL_API_KEY": "local-api-key-secret-xyz",
        "AEGIS_PROVIDER_LOCAL_MODEL": "Gwimi-4-12B-IT-Q6_K.gguf",
        "AEGIS_PROVIDER_EGRESS_ALLOWLIST": "http://localhost:8086/v1",
    }
    base.update(overrides)
    return ProviderSettings(**base)  # type: ignore[arg-type]


async def _serves(*model_ids: str) -> Sequence[str]:
    return list(model_ids)


@pytest.mark.asyncio
async def test_probe_reports_the_model_the_server_actually_serves() -> None:
    settings = _local_settings()

    async def lister(base_url: str, api_key: str, timeout_seconds: float) -> Sequence[str]:
        assert base_url == "http://localhost:8086/v1"
        return await _serves("Qwimi-3.6-27B-Q3_K_S.gguf")

    result = await probe_model_provider(settings, list_models=lister)

    assert result.state is ProviderProbeState.OK
    assert result.reported_models == ("Qwimi-3.6-27B-Q3_K_S.gguf",)
    assert result.configured_model == "Gwimi-4-12B-IT-Q6_K.gguf"
    # The configured env value is stale relative to the served model — say so.
    assert result.configured_model_served is False
    assert result.latency_ms is not None


@pytest.mark.asyncio
async def test_probe_marks_configured_model_served_when_it_matches() -> None:
    settings = _local_settings(AEGIS_PROVIDER_LOCAL_MODEL="Qwimi-3.6-27B-Q3_K_S.gguf")

    async def lister(base_url: str, api_key: str, timeout_seconds: float) -> Sequence[str]:
        return await _serves("Qwimi-3.6-27B-Q3_K_S.gguf")

    result = await probe_model_provider(settings, list_models=lister)
    assert result.state is ProviderProbeState.OK
    assert result.configured_model_served is True


@pytest.mark.asyncio
async def test_probe_reports_failure_instead_of_raising() -> None:
    settings = _local_settings()

    async def lister(base_url: str, api_key: str, timeout_seconds: float) -> Sequence[str]:
        raise ConnectionError("Connection refused")

    result = await probe_model_provider(settings, list_models=lister)

    assert result.state is ProviderProbeState.FAILED
    assert result.message is not None
    assert "Connection refused" in result.message
    assert result.reported_models == ()


@pytest.mark.asyncio
async def test_probe_is_bounded_and_reports_a_timeout() -> None:
    settings = _local_settings()

    async def lister(base_url: str, api_key: str, timeout_seconds: float) -> Sequence[str]:
        await asyncio.sleep(30)
        return []

    result = await asyncio.wait_for(
        probe_model_provider(settings, timeout_ms=100, list_models=lister),
        timeout=5,
    )

    assert result.state is ProviderProbeState.FAILED
    assert result.message is not None
    assert "did not answer" in result.message


@pytest.mark.asyncio
async def test_probe_never_leaks_credentials_into_its_payload() -> None:
    settings = _local_settings()

    async def lister(base_url: str, api_key: str, timeout_seconds: float) -> Sequence[str]:
        # A provider client that echoes its own credential into the error text.
        raise RuntimeError(f"401 Unauthorized: api_key={api_key} sk-abcdefghijklmnop")

    result = await probe_model_provider(settings, list_models=lister)
    payload = json.dumps(result.to_payload())

    assert result.state is ProviderProbeState.FAILED
    assert "local-api-key-secret-xyz" not in payload
    assert "sk-abcdefghijklmnop" not in payload


@pytest.mark.asyncio
async def test_probe_skips_deterministic_providers() -> None:
    settings = _local_settings(AEGIS_PROVIDER_DEFAULT=ProviderKind.MOCK)

    async def lister(base_url: str, api_key: str, timeout_seconds: float) -> Sequence[str]:
        raise AssertionError("mock provider must not be probed over the network")

    result = await probe_model_provider(settings, list_models=lister)
    assert result.state is ProviderProbeState.SKIPPED
    assert result.provider == ProviderKind.MOCK.value


@pytest.mark.asyncio
async def test_probe_fails_closed_on_a_non_allowlisted_destination() -> None:
    settings = _local_settings(
        AEGIS_PROVIDER_LOCAL_BASE_URL="http://evil.example.com/v1",
        AEGIS_PROVIDER_EGRESS_ALLOWLIST="http://localhost:8086/v1",
    )

    async def lister(base_url: str, api_key: str, timeout_seconds: float) -> Sequence[str]:
        raise AssertionError("a non-allowlisted destination must never be contacted")

    result = await probe_model_provider(settings, list_models=lister)
    assert result.state is ProviderProbeState.FAILED
    assert result.message is not None
    assert "allowlist" in result.message.lower()


@pytest.mark.asyncio
async def test_probe_payload_is_camel_cased_and_json_safe() -> None:
    settings = _local_settings()

    async def lister(base_url: str, api_key: str, timeout_seconds: float) -> Sequence[str]:
        return await _serves("Qwimi-3.6-27B-Q3_K_S.gguf")

    payload = (await probe_model_provider(settings, list_models=lister)).to_payload()
    json.dumps(payload)

    assert payload["state"] == "ok"
    assert payload["provider"] == ProviderKind.OPENAI_COMPATIBLE.value
    assert payload["reportedModels"] == ["Qwimi-3.6-27B-Q3_K_S.gguf"]
    assert payload["reportedModel"] == "Qwimi-3.6-27B-Q3_K_S.gguf"
    assert payload["configuredModelServed"] is False
    assert isinstance(payload["checkedAt"], str)


def test_probe_timeout_is_configurable_and_clamped() -> None:
    assert resolve_probe_timeout_ms(None) == 3000
    assert resolve_probe_timeout_ms("5000") == 5000
    assert resolve_probe_timeout_ms("1") == 100
    assert resolve_probe_timeout_ms("999999") == 30000
    assert resolve_probe_timeout_ms("not-a-number") == 3000
