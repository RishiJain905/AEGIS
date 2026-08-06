"""Phase 20 investigation tool handlers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aegis_agents.runtime.errors import AgentRuntimeError, AgentRuntimeErrorCode
from aegis_agents.runtime.grounding import (
    MAX_CATALOGUE_EVIDENCE,
    MAX_CATALOGUE_SOURCE_EVENTS,
    validate_citations,
)
from aegis_agents.runtime.ids import new_runtime_id
from aegis_agents.tools.context import ToolExecutionContext
from aegis_agents.tools.investigation.graph_queries import (
    get_asset_from_snapshot,
    get_relationships_on_snapshot,
    query_paths_on_snapshot,
)
from aegis_contracts.agent_runtime import EvidenceCitationV1
from aegis_contracts.entities import AlertV1
from aegis_contracts.event_query import (
    event_asset_id,
    event_evidence_summary,
    event_matches_filters,
)
from aegis_contracts.graph import GraphEdgeV1, GraphNodeV1, GraphSnapshotV1
from aegis_contracts.investigation import (
    EvidenceAttachmentV1,
    EvidenceProvenanceV1,
    EvidenceSourceType,
    InvestigationNoteV1,
)
from aegis_contracts.risk import AssetRiskScoreV1
from aegis_contracts.versioning import (
    EVIDENCE_ATTACHMENT_SCHEMA_VERSION,
    EVIDENCE_CITATION_SCHEMA_VERSION,
    INVESTIGATION_NOTE_SCHEMA_VERSION,
)
from aegis_persistence.repositories.postgres import PostgresGraphSnapshotRepository
from aegis_persistence.repositories.streaming import PostgresEventQueryRepository


def _serialize_node(node: GraphNodeV1) -> dict[str, Any]:
    return {
        "assetId": node.id,
        "label": node.label,
        "assetType": node.asset_type.value,
        "status": node.status.value,
        "riskScore": node.risk_score,
        "criticality": node.criticality,
        "clusterId": node.cluster_id,
    }


def _serialize_edge(edge: GraphEdgeV1) -> dict[str, Any]:
    return {
        "edgeId": edge.id,
        "sourceId": edge.source,
        "targetId": edge.target,
        "relationshipType": edge.relationship_type.value,
        "directed": edge.directed,
        "confidence": edge.confidence,
    }


def _serialize_alert(alert: AlertV1) -> dict[str, Any]:
    return {
        "alertId": alert.id,
        "title": alert.title,
        "severity": alert.severity,
        "assetId": alert.asset_id,
        "sourceEventId": alert.source_event_id,
        "confidence": alert.confidence,
        "createdAt": alert.created_at.isoformat(),
    }


def _serialize_risk_score(score: AssetRiskScoreV1) -> dict[str, Any]:
    return {
        "assetId": score.asset_id,
        "total": score.total,
        "direct": score.direct,
        "propagated": score.propagated,
        "computedAtSequence": score.computed_at_sequence,
    }


async def _load_latest_snapshot(ctx: ToolExecutionContext) -> GraphSnapshotV1:
    snapshot = await PostgresGraphSnapshotRepository(ctx.uow.session).get_latest_for_run(
        ctx.run_id
    )
    if snapshot is None:
        raise AgentRuntimeError(
            code=AgentRuntimeErrorCode.INTERNAL,
            message=f"No graph snapshot found for run: {ctx.run_id}",
            trace_id=ctx.trace_id,
        )
    return snapshot


async def _validate_source_reference(
    ctx: ToolExecutionContext,
    *,
    source_type: EvidenceSourceType,
    source_id: str,
) -> None:
    if source_type == EvidenceSourceType.EVENT:
        event = await ctx.uow.events.get_by_id(source_id)
        if event is None or event.run_id != ctx.run_id:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.TOOL_VALIDATION_FAILED,
                message=f"Event source not found for run: {source_id}",
                details={"sourceId": source_id, "sourceType": source_type.value},
                trace_id=ctx.trace_id,
            )
        return

    if source_type == EvidenceSourceType.ALERT:
        alert = await ctx.uow.alerts.get_by_id(source_id)
        if alert is None or alert.run_id != ctx.run_id:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.TOOL_VALIDATION_FAILED,
                message=f"Alert source not found for run: {source_id}",
                details={"sourceId": source_id, "sourceType": source_type.value},
                trace_id=ctx.trace_id,
            )
        return

    if source_type == EvidenceSourceType.ASSET:
        snapshot = await _load_latest_snapshot(ctx)
        if get_asset_from_snapshot(snapshot, source_id) is None:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.TOOL_VALIDATION_FAILED,
                message=f"Asset source not found in graph snapshot: {source_id}",
                details={"sourceId": source_id, "sourceType": source_type.value},
                trace_id=ctx.trace_id,
            )
        return

    if source_type == EvidenceSourceType.EXISTING_EVIDENCE:
        if source_id not in ctx.visible_evidence_ids:
            raise AgentRuntimeError(
                code=AgentRuntimeErrorCode.EVIDENCE_NOT_VISIBLE,
                message=f"Existing evidence source not visible: {source_id}",
                details={"sourceId": source_id, "sourceType": source_type.value},
                trace_id=ctx.trace_id,
            )
        return

    if source_type == EvidenceSourceType.RISK_PATH:
        scores = await ctx.uow.risk_scores.list_latest_by_run(ctx.run_id)
        for score in scores:
            for contribution in score.top_contributions:
                path = contribution.explanation_path
                if path.signal_id == source_id or source_id in path.node_ids:
                    return
        raise AgentRuntimeError(
            code=AgentRuntimeErrorCode.TOOL_VALIDATION_FAILED,
            message=f"Risk path source not found for run: {source_id}",
            details={"sourceId": source_id, "sourceType": source_type.value},
            trace_id=ctx.trace_id,
        )


# Bounded window scanned per search before in-Python filtering, mirroring the
# operator console's search (the two surfaces must answer the same queries the
# same way). The model pages past it with fromSequence/toSequence.
_SEARCH_SCAN_WINDOW = 2000


def _parse_sim_time(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


async def handle_search_events(
    ctx: ToolExecutionContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    limit = min(int(payload.get("limit", 200)), 200)
    from_sequence = payload.get("fromSequence")
    to_sequence = payload.get("toSequence")
    events = await PostgresEventQueryRepository(ctx.uow.session).list_by_run(
        ctx.run_id,
        from_sequence=from_sequence,
        to_sequence=to_sequence,
        limit=_SEARCH_SCAN_WINDOW,
    )
    matched = [
        event
        for event in events
        if event_matches_filters(
            event,
            asset_id=payload.get("assetId"),
            event_type_prefix=payload.get("eventTypePrefix"),
            text=payload.get("text"),
            from_sim_time=_parse_sim_time(payload.get("fromSimTime")),
            to_sim_time=_parse_sim_time(payload.get("toSimTime")),
        )
    ][:limit]
    return {
        "events": [
            {
                "eventId": event.event_id,
                "sequence": event.sequence,
                "type": event.type,
                "simTime": event.sim_time.isoformat(),
                "payload": event.payload,
            }
            for event in matched
        ],
        "count": len(matched),
        "fromSequence": from_sequence,
        "toSequence": to_sequence,
    }


async def handle_get_asset(
    ctx: ToolExecutionContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    asset_id = payload["assetId"]
    snapshot = await _load_latest_snapshot(ctx)
    node = get_asset_from_snapshot(snapshot, asset_id)
    if node is None:
        raise AgentRuntimeError(
            code=AgentRuntimeErrorCode.TOOL_VALIDATION_FAILED,
            message=f"Asset not found: {asset_id}",
            details={"assetId": asset_id},
            trace_id=ctx.trace_id,
        )
    return {"asset": _serialize_node(node), "snapshotSequence": snapshot.sequence}


async def handle_get_relationships(
    ctx: ToolExecutionContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    asset_id = payload["assetId"]
    max_degree = min(int(payload.get("maxDegree", 8)), 8)
    relationship_types = payload.get("relationshipTypes")
    directed_only = bool(payload.get("directedOnly", False))
    snapshot = await _load_latest_snapshot(ctx)
    try:
        neighborhood = get_relationships_on_snapshot(
            snapshot,
            asset_id,
            max_degree=max_degree,
            relationship_types=relationship_types,
            directed_only=directed_only,
        )
    except KeyError as exc:
        raise AgentRuntimeError(
            code=AgentRuntimeErrorCode.TOOL_VALIDATION_FAILED,
            message=str(exc),
            details={"assetId": asset_id},
            trace_id=ctx.trace_id,
        ) from exc

    nodes_by_id = {node.id: node for node in snapshot.nodes}
    edges_by_id = {edge.id: edge for edge in snapshot.edges}
    assets = [
        _serialize_node(nodes_by_id[node_id])
        for node_id in neighborhood.node_ids
        if node_id in nodes_by_id
    ]
    edges = [
        _serialize_edge(edges_by_id[edge_id])
        for edge_id in neighborhood.edge_ids
        if edge_id in edges_by_id
    ]
    return {
        "centerAssetId": neighborhood.center_node_id,
        "maxDegree": neighborhood.max_degree,
        "assets": assets,
        "edges": edges,
        "hopRings": neighborhood.hop_rings,
        "explanation": neighborhood.explanation,
    }


async def handle_get_paths(
    ctx: ToolExecutionContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    snapshot = await _load_latest_snapshot(ctx)
    return query_paths_on_snapshot(
        snapshot,
        source_id=payload["sourceId"],
        target_id=payload["targetId"],
        max_hops=min(int(payload.get("maxHops", 4)), 8),
        relationship_types=payload.get("relationshipTypes"),
        directed_only=bool(payload.get("directedOnly", True)),
    )


async def handle_get_risk_scores(
    ctx: ToolExecutionContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    scores = await ctx.uow.risk_scores.list_latest_by_run(ctx.run_id)
    asset_ids = payload.get("assetIds")
    if asset_ids:
        allowed = set(asset_ids)
        scores = [score for score in scores if score.asset_id in allowed]
    return {"scores": [_serialize_risk_score(score) for score in scores]}


async def handle_list_alerts(
    ctx: ToolExecutionContext,
    _payload: dict[str, Any],
) -> dict[str, Any]:
    alerts = await ctx.uow.alerts.list_by_run(ctx.run_id)
    return {"alerts": [_serialize_alert(alert) for alert in alerts]}


async def handle_get_alert(
    ctx: ToolExecutionContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    alert = await ctx.uow.alerts.get_by_id(payload["alertId"])
    if alert is None or alert.run_id != ctx.run_id:
        raise AgentRuntimeError(
            code=AgentRuntimeErrorCode.TOOL_VALIDATION_FAILED,
            message=f"Alert not found: {payload['alertId']}",
            details={"alertId": payload["alertId"]},
            trace_id=ctx.trace_id,
        )
    return {"alert": _serialize_alert(alert)}


async def _visible_evidence_items(ctx: ToolExecutionContext) -> list[dict[str, Any]]:
    """The evidence visible to the session, as the injected catalogue shows it.

    The run's events (the Evidence tab's pool, newest window first) plus any
    agent-created evidence records — the same items the request's
    AEGIS_EVIDENCE_CATALOGUE block lists, so what the tool returns and what the
    model was shown can never disagree.
    """
    events = await PostgresEventQueryRepository(ctx.uow.session).list_by_run(
        ctx.run_id, limit=MAX_CATALOGUE_SOURCE_EVENTS
    )
    attachments = await ctx.uow.evidence.list_for_run(ctx.run_id)
    visible_attachments = [
        item for item in attachments if item.id in ctx.visible_evidence_ids
    ]
    return [
        {
            "evidenceId": event.event_id,
            "summary": event_evidence_summary(event),
            "assetId": event_asset_id(event),
            "sourceEventId": event.event_id,
        }
        for event in events[-MAX_CATALOGUE_EVIDENCE:]
    ] + [
        {
            "evidenceId": item.id,
            "summary": item.summary,
            "assetId": item.asset_id,
            "sourceEventId": item.source_event_id,
        }
        for item in visible_attachments
    ]


async def handle_list_existing_evidence(
    ctx: ToolExecutionContext,
    _payload: dict[str, Any],
) -> dict[str, Any]:
    return {"evidence": await _visible_evidence_items(ctx)}


async def handle_attach_evidence(
    ctx: ToolExecutionContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    provenance_payload = payload["provenance"]
    source_type = EvidenceSourceType(provenance_payload["sourceType"])
    source_id = provenance_payload["sourceId"]
    await _validate_source_reference(ctx, source_type=source_type, source_id=source_id)

    evidence_id = payload.get("evidenceId")
    if evidence_id is not None:
        citations = [
            EvidenceCitationV1(
                schema_version=EVIDENCE_CITATION_SCHEMA_VERSION,
                evidence_id=evidence_id,
            )
        ]
        validate_citations(
            citations,
            visible_evidence_ids=ctx.visible_evidence_ids,
            trace_id=ctx.trace_id,
        )

    now = datetime.now(UTC)
    attachment = EvidenceAttachmentV1(
        schema_version=EVIDENCE_ATTACHMENT_SCHEMA_VERSION,
        id=new_runtime_id("eatt"),
        incident_id=ctx.incident_id,
        session_id=ctx.session_id,
        task_id=ctx.task_id,
        provenance=EvidenceProvenanceV1(
            source_type=source_type,
            source_id=source_id,
            summary=provenance_payload["summary"],
            collected_by_tool=provenance_payload.get("collectedByTool"),
            collected_at_sequence=provenance_payload.get("collectedAtSequence"),
        ),
        evidence_id=evidence_id,
        asset_id=payload.get("assetId"),
        is_contradiction=bool(payload.get("isContradiction", False)),
        confidence=payload["confidence"],
        rationale=payload["rationale"],
        created_at=now,
    )
    await ctx.uow.investigation.add_evidence_attachment(attachment)
    return {"attachmentId": attachment.id}


async def handle_create_investigation_note(
    ctx: ToolExecutionContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    evidence_ids = payload["evidenceIds"]
    citations = [
        EvidenceCitationV1(
            schema_version=EVIDENCE_CITATION_SCHEMA_VERSION,
            evidence_id=evidence_id,
        )
        for evidence_id in evidence_ids
    ]
    validate_citations(
        citations,
        visible_evidence_ids=ctx.visible_evidence_ids,
        trace_id=ctx.trace_id,
    )
    now = datetime.now(UTC)
    note = InvestigationNoteV1(
        schema_version=INVESTIGATION_NOTE_SCHEMA_VERSION,
        id=new_runtime_id("inote"),
        incident_id=ctx.incident_id,
        session_id=ctx.session_id,
        task_id=ctx.task_id,
        note=payload["note"],
        evidence_ids=evidence_ids,
        created_at=now,
    )
    await ctx.uow.investigation.add_note(note)
    return {"noteId": note.id}


INVESTIGATION_TOOL_HANDLERS = {
    "search_events": handle_search_events,
    "get_asset": handle_get_asset,
    "get_relationships": handle_get_relationships,
    "get_paths": handle_get_paths,
    "get_risk_scores": handle_get_risk_scores,
    "list_alerts": handle_list_alerts,
    "get_alert": handle_get_alert,
    "list_existing_evidence": handle_list_existing_evidence,
    "attach_evidence": handle_attach_evidence,
    "create_investigation_note": handle_create_investigation_note,
}
