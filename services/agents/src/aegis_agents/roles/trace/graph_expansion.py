"""Bounded graph expansion for TRACE overlays."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from typing import Any

from aegis_contracts.graph import GraphSnapshotV1
from aegis_contracts.investigation import AgentGraphOverlayV1, GraphOverlayHighlightV1
from aegis_contracts.versioning import AGENT_GRAPH_OVERLAY_SCHEMA_VERSION

from aegis_agents.runtime.ids import new_runtime_id


def _expand_neighbors(snapshot: GraphSnapshotV1, asset_id: str) -> list[tuple[str, str]]:
    neighbors: list[tuple[str, str]] = []
    for edge in snapshot.edges:
        if edge.source == asset_id:
            neighbors.append((edge.target, edge.id))
        elif edge.target == asset_id:
            neighbors.append((edge.source, edge.id))
        elif not edge.directed and edge.source == asset_id:
            neighbors.append((edge.target, edge.id))
    return neighbors


def _bfs_highlights(
    snapshot: GraphSnapshotV1,
    *,
    seed_asset_ids: list[str],
    max_hops: int,
) -> tuple[list[GraphOverlayHighlightV1], list[GraphOverlayHighlightV1]]:
    node_ids = {node.id for node in snapshot.nodes}
    seeds = [asset_id for asset_id in seed_asset_ids if asset_id in node_ids]
    if not seeds:
        return [], []

    visited_nodes: set[str] = set()
    visited_edges: set[str] = set()
    node_highlights: list[GraphOverlayHighlightV1] = []
    edge_highlights: list[GraphOverlayHighlightV1] = []

    queue: deque[tuple[str, int]] = deque((seed, 0) for seed in seeds)
    while queue:
        node_id, depth = queue.popleft()
        if node_id in visited_nodes:
            continue
        visited_nodes.add(node_id)
        node_highlights.append(
            GraphOverlayHighlightV1(
                entity_id=node_id,
                entity_type="asset",
                highlight_kind="seed" if depth == 0 else "expanded",
                label="",
            )
        )
        if depth >= max_hops:
            continue
        for neighbor_id, edge_id in _expand_neighbors(snapshot, node_id):
            if edge_id not in visited_edges:
                visited_edges.add(edge_id)
                edge_highlights.append(
                    GraphOverlayHighlightV1(
                        entity_id=edge_id,
                        entity_type="edge",
                        highlight_kind="traversed",
                        label="",
                    )
                )
            if neighbor_id not in visited_nodes:
                queue.append((neighbor_id, depth + 1))

    return node_highlights, edge_highlights


def _model_highlights(
    items: list[dict[str, Any]],
    *,
    entity_type: str,
    default_kind: str,
) -> list[GraphOverlayHighlightV1]:
    highlights: list[GraphOverlayHighlightV1] = []
    for item in items:
        entity_id = item.get("entityId")
        if not entity_id:
            continue
        highlights.append(
            GraphOverlayHighlightV1(
                entity_id=entity_id,
                entity_type=item.get("entityType", entity_type),
                highlight_kind=item.get("highlightKind", default_kind),
                label=item.get("label", ""),
            )
        )
    return highlights


def expand_graph(
    *,
    snapshot: GraphSnapshotV1 | None,
    seed_asset_ids: list[str],
    max_hops: int,
    graph_highlights: list[dict[str, Any]],
    edge_highlights: list[dict[str, Any]],
    overlay_rationale: str,
    incident_id: str,
    run_id: str,
    session_id: str,
    task_id: str,
) -> AgentGraphOverlayV1:
    highlights: list[GraphOverlayHighlightV1] = _model_highlights(
        graph_highlights,
        entity_type="asset",
        default_kind="focus",
    )
    edge_overlay_highlights: list[GraphOverlayHighlightV1] = _model_highlights(
        edge_highlights,
        entity_type="edge",
        default_kind="focus",
    )

    if snapshot is not None:
        expanded_nodes, expanded_edges = _bfs_highlights(
            snapshot,
            seed_asset_ids=seed_asset_ids,
            max_hops=max_hops,
        )
        seen_node_ids = {item.entity_id for item in highlights}
        for item in expanded_nodes:
            if item.entity_id not in seen_node_ids:
                highlights.append(item)
                seen_node_ids.add(item.entity_id)
        seen_edge_ids = {item.entity_id for item in edge_overlay_highlights}
        for item in expanded_edges:
            if item.entity_id not in seen_edge_ids:
                edge_overlay_highlights.append(item)
                seen_edge_ids.add(item.entity_id)

    return AgentGraphOverlayV1(
        schema_version=AGENT_GRAPH_OVERLAY_SCHEMA_VERSION,
        id=new_runtime_id("golv"),
        incident_id=incident_id,
        run_id=run_id,
        session_id=session_id,
        task_id=task_id,
        highlights=highlights,
        edge_highlights=edge_overlay_highlights,
        rationale=overlay_rationale,
        created_at=datetime.now(UTC),
    )
