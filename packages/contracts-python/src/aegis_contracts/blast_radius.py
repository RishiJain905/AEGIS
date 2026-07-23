"""Containment blast-radius preview contracts (pre-approval decision support).

A deterministic projection of the collateral of a Class 2/3 containment action, computed by
graph traversal over the run's current operator-visible graph snapshot — no LLM. Before an
operator (or a BASTION-proposal approver) commits, they see the severed/degraded edges, the
directly impacted neighbour assets, and the downstream service chain the action would touch.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis_contracts.entities import ActionClass
from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.primitives import AssetId, RunId
from aegis_contracts.proposals import ScenarioCommandTemplateV1
from aegis_contracts.versioning import (
    BLAST_RADIUS_PREVIEW_SCHEMA_VERSION,
    assert_supported_schema_version,
)

__all__ = [
    "BlastRadiusDownstreamV1",
    "BlastRadiusImpactKindV1",
    "BlastRadiusImpactV1",
    "BlastRadiusPreviewV1",
]


class BlastRadiusImpactKindV1(StrEnum):
    """How a containment action touches a neighbouring edge/asset."""

    SEVERED = "severed"
    DEGRADED = "degraded"
    OUTAGE = "outage"


class BlastRadiusImpactV1(BaseModel):
    """A single 1-hop neighbour affected by the action, via one graph edge."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    asset_id: AssetId = Field(alias="assetId")
    label: str
    criticality: float = Field(ge=0.0, le=1.0)
    status: str
    relationship_type: str = Field(alias="relationshipType")
    impact_kind: BlastRadiusImpactKindV1 = Field(alias="impactKind")
    edge_id: str = Field(alias="edgeId")


class BlastRadiusDownstreamV1(BaseModel):
    """A service reached transitively through the dependency chain from the target."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    asset_id: AssetId = Field(alias="assetId")
    label: str
    criticality: float = Field(ge=0.0, le=1.0)
    hops: int = Field(ge=1)


class BlastRadiusPreviewV1(BaseModel):
    """Projected collateral of a containment (command, target) over the current graph."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    command: ScenarioCommandTemplateV1
    target_asset_id: AssetId = Field(alias="targetAssetId")
    action_class: ActionClass = Field(alias="actionClass")
    severed_edge_count: int = Field(alias="severedEdgeCount", ge=0)
    degraded_edge_count: int = Field(alias="degradedEdgeCount", ge=0)
    impacted_assets: list[BlastRadiusImpactV1] = Field(
        alias="impactedAssets", default_factory=list
    )
    downstream_assets: list[BlastRadiusDownstreamV1] = Field(
        alias="downstreamAssets", default_factory=list
    )
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_schema_version(self) -> BlastRadiusPreviewV1:
        assert_supported_schema_version("blast_radius_preview", self.schema_version)
        if self.schema_version != BLAST_RADIUS_PREVIEW_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported blast radius preview schema: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self
