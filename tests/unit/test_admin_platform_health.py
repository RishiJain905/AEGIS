"""Admin → Platform health payload coherence (BUG-021), fully offline.

Two properties:
  * the readiness summary the panel renders is derivable from the very same
    dependency records rendered beneath it — the API must emit dependency states
    the client can count, and the aggregate must agree with them;
  * the model-provider probe is a separate axis: a failing (or exploding) probe
    renders as ``failed`` and never changes infrastructure readiness or 500s the
    route.
"""

from __future__ import annotations

from importlib import import_module
from types import SimpleNamespace
from typing import Any, cast

import pytest
from aegis_contracts import AegisEnvironment, AegisSettings
from aegis_contracts.observability import DependencyStateV1
from aegis_model_provider.config import ProviderKind, ProviderSettings
from aegis_model_provider.health_probe import ProviderProbeResult, ProviderProbeState
from aegis_observability.health import DependencyProbeResult

# ``aegis_api.admin.__init__`` re-exports the APIRouter object under the name
# ``router``, shadowing the submodule attribute — reach the module explicitly.
admin_router = import_module("aegis_api.admin.router")


def _settings() -> AegisSettings:
    return AegisSettings(  # type: ignore[arg-type]
        AEGIS_ENV=AegisEnvironment.TEST,
        POSTGRES_HOST="localhost",
        POSTGRES_PORT=5432,
        POSTGRES_DB="aegis",
        POSTGRES_USER="aegis",
        POSTGRES_PASSWORD="pg-secret-value-xyz",
        REDIS_URL="redis://localhost:6379/0",
        S3_ENDPOINT="http://localhost:9000",
        S3_ACCESS_KEY="minio",
        S3_SECRET_KEY="s3-secret-value-xyz",
        S3_BUCKET="aegis",
        AEGIS_DEV_AUTH_ENABLED=False,
        AEGIS_WS_ENABLED=False,
        AEGIS_OIDC_ENABLED=False,
    )


def _healthy_dependencies() -> list[DependencyProbeResult]:
    return [
        DependencyProbeResult(
            name=name,
            state=DependencyStateV1.OK,
            required=True,
            latency_ms=1.0,
        )
        for name in ("postgres", "redis", "object_storage")
    ]


def _request() -> Any:
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=_settings())))


def _install(
    monkeypatch: pytest.MonkeyPatch,
    *,
    dependencies: list[DependencyProbeResult],
    probe: Any,
) -> None:
    async def collect(_settings: AegisSettings) -> list[Any]:
        return cast(list[Any], dependencies)

    monkeypatch.setattr(admin_router, "collect_dependency_statuses", collect)
    monkeypatch.setattr(admin_router, "probe_model_provider", probe)
    monkeypatch.setattr(
        admin_router,
        "load_provider_settings",
        lambda: ProviderSettings(AEGIS_PROVIDER_DEFAULT=ProviderKind.MOCK),  # type: ignore[arg-type]
    )


async def _ok_probe(*args: object, **kwargs: object) -> ProviderProbeResult:
    return ProviderProbeResult(
        provider="openai-compatible",
        state=ProviderProbeState.OK,
        base_url="http://localhost:8086/v1",
        configured_model="Gwimi-4-12B-IT-Q6_K.gguf",
        reported_models=("Qwimi-3.6-27B-Q3_K_S.gguf",),
        latency_ms=4.2,
        checked_at="2026-07-31T00:00:00Z",
        message=None,
    )


async def test_summary_count_is_derivable_from_the_rendered_dependency_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch, dependencies=_healthy_dependencies(), probe=_ok_probe)

    response = await admin_router.get_settings(_request())
    health = response.health
    dependencies = cast(list[dict[str, Any]], health["dependencies"])

    assert health["status"] == "ready"
    # The panel counts healthy dependencies from these very records; with an
    # aggregate of "ready" every record must read as healthy (3/3, never 0/3).
    healthy = [entry for entry in dependencies if entry["state"] == DependencyStateV1.OK.value]
    assert len(healthy) == len(dependencies) == 3


async def test_degraded_dependency_is_reflected_in_both_summary_and_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dependencies = _healthy_dependencies()
    dependencies[1] = DependencyProbeResult(
        name="redis",
        state=DependencyStateV1.DEGRADED,
        required=True,
        latency_ms=99.0,
    )
    _install(monkeypatch, dependencies=dependencies, probe=_ok_probe)

    response = await admin_router.get_settings(_request())
    health = response.health
    records = cast(list[dict[str, Any]], health["dependencies"])

    assert health["status"] == "degraded"
    healthy = [entry for entry in records if entry["state"] == DependencyStateV1.OK.value]
    assert len(healthy) == 2


async def test_model_provider_probe_is_a_separate_axis_from_infrastructure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def failing_probe(*args: object, **kwargs: object) -> ProviderProbeResult:
        return ProviderProbeResult(
            provider="openai-compatible",
            state=ProviderProbeState.FAILED,
            base_url="http://localhost:8086/v1",
            configured_model="Gwimi-4-12B-IT-Q6_K.gguf",
            reported_models=(),
            latency_ms=None,
            checked_at="2026-07-31T00:00:00Z",
            message="ConnectionError: Connection refused",
        )

    _install(monkeypatch, dependencies=_healthy_dependencies(), probe=failing_probe)

    response = await admin_router.get_settings(_request())
    health = response.health

    # Infrastructure readiness is untouched by a dead model provider.
    assert health["status"] == "ready"
    provider_health = cast(dict[str, Any], health["modelProvider"])
    assert provider_health["state"] == "failed"
    assert provider_health["message"] == "ConnectionError: Connection refused"
    assert provider_health["checkedAt"] == "2026-07-31T00:00:00Z"


async def test_an_exploding_probe_renders_as_failed_and_never_500s_the_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def exploding_probe(*args: object, **kwargs: object) -> ProviderProbeResult:
        raise RuntimeError("probe blew up with key sk-abcdefghijklmnop")

    _install(monkeypatch, dependencies=_healthy_dependencies(), probe=exploding_probe)

    response = await admin_router.get_settings(_request())
    health = response.health

    assert health["status"] == "ready"
    provider_health = cast(dict[str, Any], health["modelProvider"])
    assert provider_health["state"] == "failed"
    assert "sk-abcdefghijklmnop" not in str(provider_health)
