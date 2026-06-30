"""Allowlisted behavior plugins and typed configuration schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

PLUGIN_REGISTRY: dict[str, type[BaseModel]] = {}


class AuthAttemptTelemetryConfigV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    failure_rate: float = Field(alias="failureRate", ge=0.0, le=1.0, default=0.1)
    success_rate: float = Field(alias="successRate", ge=0.0, le=1.0, default=0.9)


class ApiRequestTelemetryConfigV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    requests_per_interval: int = Field(alias="requestsPerInterval", ge=1, default=10)
    error_rate: float = Field(alias="errorRate", ge=0.0, le=1.0, default=0.05)


class NetworkFlowTelemetryConfigV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    bytes_per_interval: int = Field(alias="bytesPerInterval", ge=1, default=1024)
    protocol: str = "tcp"


class HealthCheckTelemetryConfigV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    healthy_probability: float = Field(alias="healthyProbability", ge=0.0, le=1.0, default=0.95)


class SetAssetStatusEffectConfigV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    status: str = Field(min_length=1)


class AdjustRelationshipConfidenceEffectConfigV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    delta: float = Field(ge=-1.0, le=1.0)


class SeedSelectorBranchConfigV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    branch_group: str = Field(alias="branchGroup", min_length=1)


PLUGIN_REGISTRY.update(
    {
        "telemetry.auth_attempt": AuthAttemptTelemetryConfigV1,
        "telemetry.api_request": ApiRequestTelemetryConfigV1,
        "telemetry.network_flow": NetworkFlowTelemetryConfigV1,
        "telemetry.health_check": HealthCheckTelemetryConfigV1,
        "effect.set_asset_status": SetAssetStatusEffectConfigV1,
        "effect.adjust_relationship_confidence": AdjustRelationshipConfidenceEffectConfigV1,
        "branch.seed_selector": SeedSelectorBranchConfigV1,
    }
)


def is_known_plugin(plugin_id: str) -> bool:
    return plugin_id in PLUGIN_REGISTRY


def validate_plugin_config(plugin_id: str, config: dict[str, Any]) -> str | None:
    model = PLUGIN_REGISTRY.get(plugin_id)
    if model is None:
        return f"Unknown plugin: {plugin_id}"
    try:
        model.model_validate(config)
    except Exception as exc:  # noqa: BLE001 - surface plugin config errors
        return str(exc)
    return None


def list_plugin_ids() -> list[str]:
    return sorted(PLUGIN_REGISTRY.keys())
