"""Operational graph contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis_contracts.errors import ContractErrorCode, ContractValidationError
from aegis_contracts.primitives import (
    AssetId,
    ClusterId,
    EdgeId,
    Revision,
    RunId,
    Sequence,
    UtcTimestamp,
)
from aegis_contracts.versioning import (
    GRAPH_DELTA_SCHEMA_VERSION,
    GRAPH_EDGE_SCHEMA_VERSION,
    GRAPH_NODE_SCHEMA_VERSION,
    GRAPH_PATH_QUERY_SCHEMA_VERSION,
    GRAPH_PATH_RESULT_SCHEMA_VERSION,
    GRAPH_SNAPSHOT_SCHEMA_VERSION,
    assert_supported_schema_version,
)


class EntityType(StrEnum):
    ASSET = "asset"
    CLUSTER = "cluster"


class AssetType(StrEnum):
    SERVICE = "service"
    DEVICE = "device"
    USER = "user"
    IDENTITY = "identity"
    DATABASE = "database"
    CONTROL = "control"
    AI_MODEL = "ai_model"


class NodeStatus(StrEnum):
    NORMAL = "normal"
    SUSPICIOUS = "suspicious"
    UNDER_INVESTIGATION = "under_investigation"
    CONTAINED = "contained"
    COMPROMISED = "compromised"


class RelationshipType(StrEnum):
    COMMUNICATED_WITH = "COMMUNICATED_WITH"
    AUTHENTICATED_TO = "AUTHENTICATED_TO"
    DEPENDS_ON = "DEPENDS_ON"
    ADMINISTERS = "ADMINISTERS"
    HOSTS = "HOSTS"


class GraphNodeV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: AssetId
    entity_type: EntityType = Field(alias="entityType")
    asset_type: AssetType = Field(alias="assetType")
    label: str = Field(min_length=1)
    cluster_id: ClusterId | None = Field(default=None, alias="clusterId")
    risk_score: float = Field(alias="riskScore", ge=0.0, le=1.0)
    criticality: float = Field(ge=0.0, le=1.0)
    #: The asset's composed operator-facing status: a containing control reads CONTAINED,
    #: otherwise the security posture underneath shows through. See
    #: ``aegis_contracts.killchain.project_effective_status``.
    status: NodeStatus
    revision: Revision
    #: Defensive controls currently applied, in application order ("observed",
    #: "isolated", ...). Additive (schemaVersion stays 1) and empty by default, so legacy
    #: producers and fixtures are unaffected. Carried beside ``status`` rather than folded
    #: into it because the two answer different questions — what is wrong with this asset,
    #: and what have we done about it — and folding them lost the first one.
    applied_controls: list[str] = Field(default_factory=list, alias="appliedControls")
    # Fog of war: whether the operator may see this node's *true* security state yet.
    # Additive (schemaVersion stays 1); defaults true so unredacted producers and legacy
    # payloads are unaffected. Undisclosed nodes are served with a redacted (baseline)
    # status; the authoritative event log and post-run/debrief projections keep full truth.
    disclosed: bool = True

    @model_validator(mode="after")
    def validate_schema_version(self) -> GraphNodeV1:
        assert_supported_schema_version("graph_node", self.schema_version)
        if self.schema_version != GRAPH_NODE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported graph node schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class GraphEdgeV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: EdgeId
    source: AssetId
    target: AssetId
    relationship_type: RelationshipType = Field(alias="relationshipType")
    directed: bool
    confidence: float = Field(ge=0.0, le=1.0)
    risk_contribution: float = Field(alias="riskContribution", ge=0.0, le=1.0)
    first_seen_at: UtcTimestamp = Field(alias="firstSeenAt")
    last_seen_at: UtcTimestamp = Field(alias="lastSeenAt")
    event_count: int = Field(alias="eventCount", ge=0)
    revision: Revision

    @model_validator(mode="after")
    def validate_schema_version(self) -> GraphEdgeV1:
        assert_supported_schema_version("graph_edge", self.schema_version)
        if self.schema_version != GRAPH_EDGE_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported graph edge schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class GraphClusterV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    id: ClusterId
    label: str = Field(min_length=1)
    member_node_ids: list[AssetId] = Field(alias="memberNodeIds")
    revision: Revision


class GraphSnapshotV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    sequence: Sequence
    captured_at: UtcTimestamp = Field(alias="capturedAt")
    nodes: list[GraphNodeV1]
    edges: list[GraphEdgeV1]
    clusters: list[GraphClusterV1] = Field(default_factory=list)
    revision: Revision

    @model_validator(mode="after")
    def validate_schema_version(self) -> GraphSnapshotV1:
        assert_supported_schema_version("graph_snapshot", self.schema_version)
        if self.schema_version != GRAPH_SNAPSHOT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported graph snapshot schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class GraphDeltaOperation(StrEnum):
    UPSERT_NODE = "upsert_node"
    UPSERT_EDGE = "upsert_edge"
    DELETE_NODE = "delete_node"
    DELETE_EDGE = "delete_edge"
    UPSERT_CLUSTER = "upsert_cluster"


class GraphDeltaV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    sequence: Sequence
    revision: Revision
    operation: GraphDeltaOperation
    node: GraphNodeV1 | None = None
    edge: GraphEdgeV1 | None = None
    cluster: GraphClusterV1 | None = None
    target_id: AssetId | EdgeId | None = Field(default=None, alias="targetId")

    @model_validator(mode="after")
    def validate_delta(self) -> GraphDeltaV1:
        assert_supported_schema_version("graph_delta", self.schema_version)
        if self.schema_version != GRAPH_DELTA_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported graph delta schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        if self.operation in {GraphDeltaOperation.UPSERT_NODE} and self.node is None:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="upsert_node requires node payload",
                details={"operation": self.operation.value},
            )
        if self.operation in {GraphDeltaOperation.UPSERT_EDGE} and self.edge is None:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="upsert_edge requires edge payload",
                details={"operation": self.operation.value},
            )
        if self.operation in {
            GraphDeltaOperation.DELETE_NODE,
            GraphDeltaOperation.DELETE_EDGE,
        } and self.target_id is None:
            raise ContractValidationError(
                code=ContractErrorCode.VALIDATION_FAILED,
                message="delete operations require targetId",
                details={"operation": self.operation.value},
            )
        return self


class GraphPathQueryV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    source_id: AssetId = Field(alias="sourceId")
    target_id: AssetId = Field(alias="targetId")
    max_hops: int = Field(alias="maxHops", ge=1, le=32)
    relationship_types: list[RelationshipType] = Field(
        default_factory=list,
        alias="relationshipTypes",
    )
    directed_only: bool = Field(default=True, alias="directedOnly")

    @model_validator(mode="after")
    def validate_schema_version(self) -> GraphPathQueryV1:
        assert_supported_schema_version("graph_path_query", self.schema_version)
        if self.schema_version != GRAPH_PATH_QUERY_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported graph path query schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self


class GraphPathResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion", ge=1)
    run_id: RunId = Field(alias="runId")
    source_id: AssetId = Field(alias="sourceId")
    target_id: AssetId = Field(alias="targetId")
    paths: list[list[AssetId]]
    explanation: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_schema_version(self) -> GraphPathResultV1:
        assert_supported_schema_version("graph_path_result", self.schema_version)
        if self.schema_version != GRAPH_PATH_RESULT_SCHEMA_VERSION:
            raise ContractValidationError(
                code=ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                message=f"Unsupported graph path result schema version: {self.schema_version}",
                details={"schemaVersion": self.schema_version},
            )
        return self
