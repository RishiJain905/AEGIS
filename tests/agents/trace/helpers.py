"""Shared helpers for TRACE agent tests."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis_contracts.graph import (
    AssetType,
    GraphEdgeV1,
    GraphNodeV1,
    GraphSnapshotV1,
    NodeStatus,
    RelationshipType,
)
from aegis_contracts.investigation import (
    EvidenceAttachmentV1,
    EvidenceProvenanceV1,
    EvidenceSourceType,
)
from aegis_contracts.versioning import (
    EVIDENCE_ATTACHMENT_SCHEMA_VERSION,
    GRAPH_EDGE_SCHEMA_VERSION,
    GRAPH_NODE_SCHEMA_VERSION,
    GRAPH_SNAPSHOT_SCHEMA_VERSION,
)


def make_linear_graph_snapshot(
    *,
    run_id: str = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
) -> GraphSnapshotV1:
    now = datetime(2026, 6, 30, 2, 0, 1, tzinfo=UTC)
    nodes = [
        GraphNodeV1(
            schema_version=GRAPH_NODE_SCHEMA_VERSION,
            id="asset:seed-01",
            entity_type="asset",
            asset_type=AssetType.DEVICE,
            label="Seed",
            cluster_id="business-unit:bu-platform",
            risk_score=0.5,
            criticality=0.5,
            status=NodeStatus.SUSPICIOUS,
            revision=1,
        ),
        GraphNodeV1(
            schema_version=GRAPH_NODE_SCHEMA_VERSION,
            id="asset:hop-01",
            entity_type="asset",
            asset_type=AssetType.SERVICE,
            label="Hop 1",
            cluster_id="business-unit:bu-platform",
            risk_score=0.6,
            criticality=0.6,
            status=NodeStatus.SUSPICIOUS,
            revision=1,
        ),
        GraphNodeV1(
            schema_version=GRAPH_NODE_SCHEMA_VERSION,
            id="asset:hop-02",
            entity_type="asset",
            asset_type=AssetType.SERVICE,
            label="Hop 2",
            cluster_id="business-unit:bu-platform",
            risk_score=0.7,
            criticality=0.7,
            status=NodeStatus.SUSPICIOUS,
            revision=1,
        ),
    ]
    edges = [
        GraphEdgeV1(
            schema_version=GRAPH_EDGE_SCHEMA_VERSION,
            id="edge:seed-hop1",
            source="asset:seed-01",
            target="asset:hop-01",
            relationship_type=RelationshipType.COMMUNICATED_WITH,
            directed=True,
            confidence=1.0,
            risk_contribution=0.2,
            first_seen_at=now,
            last_seen_at=now,
            event_count=1,
            revision=1,
        ),
        GraphEdgeV1(
            schema_version=GRAPH_EDGE_SCHEMA_VERSION,
            id="edge:hop1-hop2",
            source="asset:hop-01",
            target="asset:hop-02",
            relationship_type=RelationshipType.COMMUNICATED_WITH,
            directed=True,
            confidence=1.0,
            risk_contribution=0.2,
            first_seen_at=now,
            last_seen_at=now,
            event_count=1,
            revision=1,
        ),
    ]
    return GraphSnapshotV1(
        schema_version=GRAPH_SNAPSHOT_SCHEMA_VERSION,
        run_id=run_id,
        sequence=100,
        captured_at=now,
        nodes=nodes,
        edges=edges,
        clusters=[],
        revision=1,
    )


def make_evidence_attachment(
    *,
    attachment_id: str,
    source_id: str,
    is_contradiction: bool = False,
    evidence_id: str | None = None,
) -> EvidenceAttachmentV1:
    now = datetime(2026, 6, 30, 2, 10, 0, tzinfo=UTC)
    return EvidenceAttachmentV1(
        schema_version=EVIDENCE_ATTACHMENT_SCHEMA_VERSION,
        id=attachment_id,
        incident_id="incident:inc_synthetic_001",
        session_id="agent-session:ags_synthetic_001",
        task_id="atk_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        provenance=EvidenceProvenanceV1(
            source_type=EvidenceSourceType.EXISTING_EVIDENCE,
            source_id=source_id,
            summary="Grounded evidence attachment",
            collected_by_tool="attach_evidence",
        ),
        evidence_id=evidence_id,
        is_contradiction=is_contradiction,
        confidence=0.8,
        rationale="Synthetic attachment for tests",
        created_at=now,
    )
