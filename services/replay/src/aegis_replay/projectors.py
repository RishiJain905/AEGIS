"""Deterministic multi-domain projectors for historical reconstruction."""

from __future__ import annotations

import contextlib
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from aegis_contracts import (
    ActionProposalV1,
    AgentSessionV1,
    ApprovalV1,
    DomainEventEnvelopeV1,
    EvidenceV1,
    ExecutedActionV1,
    GraphNodeV1,
    GraphSnapshotV1,
    IncidentV1,
    ReplayAgentArtifactRefV1,
    ReplayAuditEventRefV1,
    ReplayCursorV1,
    ReplayModeV1,
    ReplayProvenanceV1,
    ReplayReportRefV1,
    ReplayRiskScoreV1,
    ReplayStateV1,
    RunV1,
)
from aegis_contracts.entities import (
    ActionClass,
    AgentRole,
    AgentSessionState,
    ApprovalDecision,
    IncidentState,
    ProposalStatus,
)
from aegis_contracts.graph import AssetType, EntityType, NodeStatus
from aegis_contracts.killchain import is_control_status, project_effective_status
from aegis_contracts.replay import ReplayErrorCode
from aegis_contracts.versioning import (
    ACTION_PROPOSAL_SCHEMA_VERSION,
    AGENT_SESSION_SCHEMA_VERSION,
    APPROVAL_SCHEMA_VERSION,
    EVIDENCE_SCHEMA_VERSION,
    EXECUTED_ACTION_SCHEMA_VERSION,
    GRAPH_NODE_SCHEMA_VERSION,
    GRAPH_SNAPSHOT_SCHEMA_VERSION,
    INCIDENT_SCHEMA_VERSION,
    REPLAY_CURSOR_SCHEMA_VERSION,
    REPLAY_PROVENANCE_SCHEMA_VERSION,
    REPLAY_STATE_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
)

from aegis_replay.checksum import compute_state_digest
from aegis_replay.errors import ReplayEngineError

AUDIT_EVENT_PREFIXES = (
    "action.proposal.",
    "action.executed",
    "agent.",
    "report.",
    "incident.",
    "sim.run.",
    "sim.asset.",
    "sim.branch.",
    "alert.",
    "telemetry.",
    "risk.",
)


def _as_str(value: object, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _as_int(value: object, default: int = 0) -> int:
    return value if isinstance(value, int) else default


def _as_float(value: object, default: float = 0.0) -> float:
    return value if isinstance(value, (int, float)) else default


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


@dataclass
class ProjectorState:
    run_id: str
    run: RunV1 | None = None
    graph_nodes: dict[str, GraphNodeV1] = field(default_factory=dict)
    #: Security posture per asset, tracked beside the nodes because ``GraphNodeV1.status``
    #: is the *composed* status. Without it a containment would overwrite the posture in
    #: the projection and replay would forget what the attacker had done — the same defect
    #: the world state carries this split to avoid.
    asset_postures: dict[str, str] = field(default_factory=dict)
    graph_edges: list[dict[str, Any]] = field(default_factory=list)
    graph_revision: int = 0
    incidents: dict[str, IncidentV1] = field(default_factory=dict)
    evidence: dict[str, EvidenceV1] = field(default_factory=dict)
    risk_scores: dict[str, ReplayRiskScoreV1] = field(default_factory=dict)
    agent_sessions: dict[str, AgentSessionV1] = field(default_factory=dict)
    agent_artifacts: dict[str, ReplayAgentArtifactRefV1] = field(default_factory=dict)
    proposals: dict[str, ActionProposalV1] = field(default_factory=dict)
    approvals: dict[str, ApprovalV1] = field(default_factory=dict)
    executed_actions: dict[str, ExecutedActionV1] = field(default_factory=dict)
    reports: dict[str, ReplayReportRefV1] = field(default_factory=dict)
    audit_events: list[ReplayAuditEventRefV1] = field(default_factory=list)
    applied_event_ids: set[str] = field(default_factory=set)
    last_sequence: int = 0
    last_sim_time: datetime | None = None
    model_call_attempts: int = 0

    def clone(self) -> ProjectorState:
        return deepcopy(self)


class ReplayProjector:
    """Apply domain events idempotently into a multi-domain projection."""

    def __init__(self, run_id: str) -> None:
        self.state = ProjectorState(run_id=run_id)

    @classmethod
    def from_replay_state(cls, state: ReplayStateV1) -> ReplayProjector:
        projector = cls(state.run_id)
        projector.state.run = state.run
        if state.graph is not None:
            projector.state.graph_nodes = {node.id: node for node in state.graph.nodes}
            # A checkpointed projection only carries composed statuses; seeding posture
            # from them is exact wherever no containing control is masking one.
            projector.state.asset_postures = {
                node.id: node.status.value for node in state.graph.nodes
            }
            projector.state.graph_edges = [
                edge.model_dump(mode="json", by_alias=True) for edge in state.graph.edges
            ]
            projector.state.graph_revision = state.graph.revision
        projector.state.incidents = {item.id: item for item in state.incidents}
        projector.state.evidence = {item.id: item for item in state.evidence}
        projector.state.risk_scores = {item.asset_id: item for item in state.risk_scores}
        projector.state.agent_sessions = {item.id: item for item in state.agent_sessions}
        projector.state.agent_artifacts = {
            item.artifact_id: item for item in state.agent_artifacts
        }
        projector.state.proposals = {item.id: item for item in state.proposals}
        projector.state.approvals = {item.id: item for item in state.approvals}
        projector.state.executed_actions = {item.id: item for item in state.executed_actions}
        projector.state.reports = {item.report_id: item for item in state.reports}
        projector.state.audit_events = list(state.audit_events)
        projector.state.last_sequence = state.cursor.sequence
        projector.state.last_sim_time = state.cursor.sim_time
        return projector

    def apply_event(self, event: DomainEventEnvelopeV1) -> None:
        if event.run_id != self.state.run_id:
            raise ReplayEngineError(
                ReplayErrorCode.REPLAY_VALIDATION_FAILED,
                "Event runId does not match projector run",
                details={"runId": self.state.run_id, "eventRunId": event.run_id},
            )
        if event.event_id in self.state.applied_event_ids:
            # Idempotent: duplicates do not mutate reconstructed state.
            return
        if self.state.last_sequence > 0 and event.sequence < self.state.last_sequence:
            raise ReplayEngineError(
                ReplayErrorCode.REPLAY_SEQUENCE_GAP,
                "Event sequence moved backwards during reconstruction",
                details={
                    "lastSequence": self.state.last_sequence,
                    "eventSequence": event.sequence,
                },
            )
        if (
            self.state.last_sequence > 0
            and event.sequence > self.state.last_sequence + 1
            and event.sequence != self.state.last_sequence
        ):
            # Allow non-contiguous only when starting from snapshot boundary;
            # contiguous gap detection is handled by the reconstruction service.
            pass

        self.state.applied_event_ids.add(event.event_id)
        self.state.last_sequence = event.sequence
        self.state.last_sim_time = event.sim_time

        handler = {
            "sim.run.started": self._on_run_started,
            "sim.run.paused": self._on_run_status("paused"),
            "sim.run.resumed": self._on_run_status("running"),
            "sim.run.stopped": self._on_run_status("stopped"),
            "sim.asset.status_changed": self._on_asset_status_changed,
            "graph.snapshot.created": self._on_graph_snapshot_created,
            "alert.created": self._on_alert_created,
            "incident.created": self._on_incident_created,
            "incident.state_changed": self._on_incident_state_changed,
            "risk.score.computed": self._on_risk_score,
            "risk.projection.updated": self._on_risk_projection,
            "agent.session.started": self._on_agent_session_started,
            "agent.session.state_changed": self._on_agent_session_state,
            "agent.session.completed": self._on_agent_session_completed,
            "action.proposal.created": self._on_proposal_created,
            "action.proposal.approved": self._on_proposal_status(ProposalStatus.APPROVED),
            "action.proposal.rejected": self._on_proposal_status(ProposalStatus.REJECTED),
            "action.proposal.cancelled": self._on_proposal_status(ProposalStatus.CANCELLED),
            "action.proposal.modified": self._on_proposal_modified,
            "action.executed": self._on_action_executed,
            "report.version.created": self._on_report_version,
            "report.generation.completed": self._on_report_completed,
            "report.generation.failed": self._on_report_failed,
        }.get(event.type)

        if handler is not None:
            handler(event)
        elif event.type.startswith("telemetry."):
            self._on_telemetry(event)
        elif event.type == "sim.branch.selected":
            self._on_branch_selected(event)

        if event.type.startswith(AUDIT_EVENT_PREFIXES) or event.type in {
            "action.executed",
            "sim.run.started",
            "sim.run.stopped",
        }:
            self.state.audit_events.append(
                ReplayAuditEventRefV1(
                    event_id=event.event_id,
                    sequence=event.sequence,
                    event_type=event.type,
                    summary=self._audit_summary(event),
                )
            )

        # Evidence from alert/investigation payloads when present.
        self._maybe_project_evidence(event)

    def forbid_model_calls(self) -> None:
        """Historical replay must never invoke external models."""
        self.state.model_call_attempts += 1
        raise ReplayEngineError(
            ReplayErrorCode.REPLAY_LIVE_MUTATION_FORBIDDEN,
            "Historical replay forbids external model calls",
            details={"modelCallAttempts": self.state.model_call_attempts},
        )

    def to_replay_state(
        self,
        *,
        provenance: ReplayProvenanceV1,
        incident_id: str | None = None,
    ) -> ReplayStateV1:
        cursor = ReplayCursorV1(
            schema_version=REPLAY_CURSOR_SCHEMA_VERSION,
            run_id=self.state.run_id,  # type: ignore[arg-type]
            sequence=self.state.last_sequence,
            sim_time=self.state.last_sim_time,
            incident_id=incident_id,  # type: ignore[arg-type]
        )
        graph = self._build_graph_snapshot()
        incidents = sorted(self.state.incidents.values(), key=lambda item: item.id)
        evidence = sorted(self.state.evidence.values(), key=lambda item: item.id)
        if incident_id is not None:
            incidents = [item for item in incidents if item.id == incident_id]
            evidence = [
                item
                for item in evidence
                if any(
                    incident.id == incident_id
                    and item.asset_id is not None
                    for incident in incidents
                )
                or True
            ]
            # Keep evidence linked by run; filter only when asset matches focused incident alerts.
            focused = {incident_id}
            evidence = [
                item
                for item in evidence
                if item.run_id == self.state.run_id
                and (
                    not focused
                    or item.asset_id is None
                    or any(
                        item.asset_id in (inc.alert_ids or [])  # type: ignore[operator]
                        for inc in incidents
                    )
                    or True
                )
            ]
            # Simpler focus: keep all evidence for run when incident focus set;
            # Phase 26 can refine correlation. Keep incidents filtered.
            evidence = sorted(self.state.evidence.values(), key=lambda item: item.id)

        state = ReplayStateV1(
            schema_version=REPLAY_STATE_SCHEMA_VERSION,
            run_id=self.state.run_id,  # type: ignore[arg-type]
            cursor=cursor,
            run=self.state.run,
            graph=graph,
            incidents=incidents,
            evidence=evidence,
            risk_scores=sorted(
                self.state.risk_scores.values(),
                key=lambda item: item.asset_id,
            ),
            agent_sessions=sorted(
                self.state.agent_sessions.values(),
                key=lambda item: item.id,
            ),
            agent_artifacts=sorted(
                self.state.agent_artifacts.values(),
                key=lambda item: item.artifact_id,
            ),
            proposals=sorted(self.state.proposals.values(), key=lambda item: item.id),
            approvals=sorted(self.state.approvals.values(), key=lambda item: item.id),
            executed_actions=sorted(
                self.state.executed_actions.values(),
                key=lambda item: item.id,
            ),
            reports=sorted(self.state.reports.values(), key=lambda item: item.report_id),
            audit_events=sorted(self.state.audit_events, key=lambda item: item.sequence),
            state_digest="pending",
            provenance=provenance,
        )
        digest = compute_state_digest(state)
        return state.model_copy(update={"state_digest": digest})

    def _build_graph_snapshot(self) -> GraphSnapshotV1 | None:
        if not self.state.graph_nodes and not self.state.graph_edges:
            return None
        captured = self.state.last_sim_time or _utc_now()
        nodes = sorted(self.state.graph_nodes.values(), key=lambda item: item.id)
        return GraphSnapshotV1.model_validate(
            {
                "schemaVersion": GRAPH_SNAPSHOT_SCHEMA_VERSION,
                "runId": self.state.run_id,
                "sequence": self.state.last_sequence,
                "capturedAt": captured.isoformat().replace("+00:00", "Z"),
                "nodes": [node.model_dump(mode="json", by_alias=True) for node in nodes],
                "edges": self.state.graph_edges,
                "clusters": [],
                "revision": self.state.graph_revision,
            }
        )

    def _ensure_graph_node(
        self,
        asset_id: str,
        *,
        label: str | None = None,
        status: NodeStatus = NodeStatus.NORMAL,
        asset_type: str = AssetType.SERVICE.value,
    ) -> None:
        if not asset_id.startswith("asset:"):
            return
        existing = self.state.graph_nodes.get(asset_id)
        if existing is not None:
            return
        self.state.graph_nodes[asset_id] = GraphNodeV1.model_validate(
            {
                "schemaVersion": GRAPH_NODE_SCHEMA_VERSION,
                "id": asset_id,
                "entityType": EntityType.ASSET.value,
                "assetType": asset_type,
                "label": label or asset_id,
                "clusterId": None,
                "riskScore": 0.0,
                "criticality": 0.5,
                "status": status.value,
                "revision": 1,
            }
        )
        self.state.graph_revision += 1

    def _on_telemetry(self, event: DomainEventEnvelopeV1) -> None:
        payload = event.payload
        asset_id = _as_str(payload.get("assetId"), event.subject.id)
        self._ensure_graph_node(asset_id, label=_as_str(payload.get("label"), asset_id))
        source = _as_str(payload.get("sourceAssetId") or payload.get("sourceId"))
        target = _as_str(payload.get("targetAssetId") or payload.get("targetId"))
        if source:
            self._ensure_graph_node(source)
        if target:
            self._ensure_graph_node(target)
        if event.type.endswith("authentication.failed"):
            node = self.state.graph_nodes.get(asset_id)
            if node is not None:
                # A failed auth is a posture signal, so it must not paint over a control:
                # an isolated asset stays contained however noisy its auth log gets.
                status, controls = self._apply_asset_status(
                    asset_id, NodeStatus.SUSPICIOUS.value
                )
                self.state.graph_nodes[asset_id] = node.model_copy(
                    update={
                        "status": NodeStatus(status),
                        "applied_controls": controls,
                        "revision": node.revision + 1,
                    }
                )

    def _on_branch_selected(self, event: DomainEventEnvelopeV1) -> None:
        # Branch selection is audit-relevant; keep run revision advancing.
        if self.state.run is not None:
            self.state.run = self.state.run.model_copy(
                update={
                    "sim_time": event.sim_time,
                    "revision": self.state.run.revision + 1,
                }
            )

    def _on_run_started(self, event: DomainEventEnvelopeV1) -> None:
        payload = event.payload
        self.state.run = RunV1.model_validate(
            {
                "schemaVersion": RUN_SCHEMA_VERSION,
                "id": self.state.run_id,
                "scenarioVersionId": _as_str(
                    payload.get("scenarioVersionId"),
                    "scenario-version:unknown",
                ),
                "seed": _as_int(payload.get("seed"), 0),
                "status": "running",
                "startedAt": event.recorded_at.isoformat().replace("+00:00", "Z"),
                "simTime": event.sim_time.isoformat().replace("+00:00", "Z"),
                "revision": max(1, event.sequence),
            }
        )

    def _on_run_status(self, status: str):
        def handler(event: DomainEventEnvelopeV1) -> None:
            if self.state.run is None:
                self._on_run_started(event)
            assert self.state.run is not None
            self.state.run = self.state.run.model_copy(
                update={
                    "status": status,
                    "sim_time": event.sim_time,
                    "revision": self.state.run.revision + 1,
                }
            )

        return handler

    def _apply_asset_status(self, asset_id: str, applied: str) -> tuple[str, list[str]]:
        """Route one applied status into the projection's posture/control split.

        Mirrors ``AssetState.apply_status``: a control accumulates, anything else replaces
        the posture. Reconstructing the split here — rather than reading it off the event —
        means runs persisted before the split replay into the same composed projection as
        runs recorded after it, because the event has always carried the applied value.
        """
        node = self.state.graph_nodes.get(asset_id)
        controls = list(node.applied_controls) if node is not None else []
        if is_control_status(applied):
            if applied not in controls:
                controls.append(applied)
        else:
            self.state.asset_postures[asset_id] = applied
        posture = self.state.asset_postures.get(asset_id, NodeStatus.NORMAL.value)
        return project_effective_status(posture, controls).value, controls

    def _on_asset_status_changed(self, event: DomainEventEnvelopeV1) -> None:
        payload = event.payload
        asset_id = _as_str(payload.get("assetId"), event.subject.id)
        # The event carries one value from either vocabulary — a posture the attacker
        # drove the asset into, or a control the defender applied. Composing the two
        # rather than overwriting is what keeps an observed compromise visibly
        # compromised, and a contained one from reading as an unhandled threat.
        status, controls = self._apply_asset_status(
            asset_id, _as_str(payload.get("status"), "suspicious")
        )
        existing = self.state.graph_nodes.get(asset_id)
        if existing is None:
            node = GraphNodeV1.model_validate(
                {
                    "schemaVersion": GRAPH_NODE_SCHEMA_VERSION,
                    "id": asset_id,
                    "entityType": EntityType.ASSET.value,
                    "assetType": _as_str(payload.get("assetType"), AssetType.SERVICE.value),
                    "label": _as_str(payload.get("label"), asset_id),
                    "clusterId": payload.get("clusterId"),
                    "riskScore": _as_float(payload.get("riskScore"), 0.0),
                    "criticality": _as_float(payload.get("criticality"), 0.5),
                    "status": status,
                    "appliedControls": controls,
                    "revision": 1,
                }
            )
        else:
            node = existing.model_copy(
                update={
                    "status": NodeStatus(status),
                    "applied_controls": controls,
                    "revision": existing.revision + 1,
                }
            )
        self.state.graph_nodes[asset_id] = node
        self.state.graph_revision += 1

    def _on_graph_snapshot_created(self, event: DomainEventEnvelopeV1) -> None:
        payload = event.payload
        snapshot_payload = payload.get("snapshot") or payload.get("graphSnapshot") or payload
        if not isinstance(snapshot_payload, dict):
            return
        try:
            snapshot = GraphSnapshotV1.model_validate(snapshot_payload)
        except Exception:
            return
        self.state.graph_nodes = {node.id: node for node in snapshot.nodes}
        # A persisted snapshot is authoritative for the nodes it carries; reseed posture
        # from it so status changes after this point compose against the right baseline.
        self.state.asset_postures.update(
            {node.id: node.status.value for node in snapshot.nodes}
        )
        self.state.graph_edges = [
            edge.model_dump(mode="json", by_alias=True) for edge in snapshot.edges
        ]
        self.state.graph_revision = snapshot.revision

    def _on_alert_created(self, event: DomainEventEnvelopeV1) -> None:
        # Alerts feed evidence; incident correlation may arrive later.
        self._maybe_project_evidence(event)

    def _on_incident_created(self, event: DomainEventEnvelopeV1) -> None:
        payload = event.payload
        incident_id = _as_str(payload.get("id") or payload.get("incidentId"), event.subject.id)
        alert_ids = payload.get("alertIds")
        if not isinstance(alert_ids, list):
            alert_ids = []
        self.state.incidents[incident_id] = IncidentV1.model_validate(
            {
                "schemaVersion": INCIDENT_SCHEMA_VERSION,
                "id": incident_id,
                "runId": self.state.run_id,
                "title": _as_str(payload.get("title"), "Incident"),
                "state": _as_str(payload.get("state"), IncidentState.OPEN.value),
                "alertIds": [item for item in alert_ids if isinstance(item, str)],
                "createdAt": event.recorded_at.isoformat().replace("+00:00", "Z"),
                "updatedAt": event.recorded_at.isoformat().replace("+00:00", "Z"),
                "revision": 1,
            }
        )

    def _on_incident_state_changed(self, event: DomainEventEnvelopeV1) -> None:
        payload = event.payload
        incident_id = _as_str(payload.get("incidentId") or payload.get("id"), event.subject.id)
        existing = self.state.incidents.get(incident_id)
        if existing is None:
            self._on_incident_created(event)
            existing = self.state.incidents.get(incident_id)
        if existing is None:
            return
        state_raw = _as_str(payload.get("state"), existing.state.value)
        try:
            state = IncidentState(state_raw)
        except ValueError:
            state = existing.state
        # The detection engine also emits this event when a follow-on alert joins an open
        # case (the registry has no alert-attachment type), so the payload's alert ids are
        # merged, not ignored — otherwise a replayed incident keeps only the alerts it was
        # opened with and the case-file timeline diverges from the live run.
        payload_alert_ids = payload.get("alertIds")
        alert_ids = sorted(
            {
                *existing.alert_ids,
                *(
                    item
                    for item in (payload_alert_ids if isinstance(payload_alert_ids, list) else [])
                    if isinstance(item, str)
                ),
            }
        )
        self.state.incidents[incident_id] = existing.model_copy(
            update={
                "state": state,
                "alert_ids": alert_ids,
                "title": _as_str(payload.get("title"), existing.title),
                "updated_at": event.recorded_at,
                "revision": existing.revision + 1,
            }
        )

    def _on_risk_score(self, event: DomainEventEnvelopeV1) -> None:
        payload = event.payload
        asset_id = _as_str(payload.get("assetId"), event.subject.id)
        score = _as_float(payload.get("score") or payload.get("riskScore"), 0.0)
        revision = _as_int(payload.get("revision"), 1)
        self.state.risk_scores[asset_id] = ReplayRiskScoreV1(
            asset_id=asset_id,
            score=max(0.0, min(1.0, score)),
            revision=revision,
        )
        node = self.state.graph_nodes.get(asset_id)
        if node is not None:
            self.state.graph_nodes[asset_id] = node.model_copy(
                update={"risk_score": max(0.0, min(1.0, score)), "revision": node.revision + 1}
            )

    def _on_risk_projection(self, event: DomainEventEnvelopeV1) -> None:
        payload = event.payload
        updates = payload.get("nodeUpdates")
        if not isinstance(updates, list):
            return
        for update in updates:
            if not isinstance(update, dict):
                continue
            asset_id = _as_str(update.get("assetId"))
            if not asset_id:
                continue
            score = _as_float(update.get("riskScore"), 0.0)
            revision = _as_int(update.get("revision"), 1)
            self.state.risk_scores[asset_id] = ReplayRiskScoreV1(
                asset_id=asset_id,
                score=max(0.0, min(1.0, score)),
                revision=revision,
            )
            node = self.state.graph_nodes.get(asset_id)
            if node is not None:
                self.state.graph_nodes[asset_id] = node.model_copy(
                    update={
                        "risk_score": max(0.0, min(1.0, score)),
                        "revision": max(node.revision + 1, revision),
                    }
                )

    def _agent_session_id(self, event: DomainEventEnvelopeV1) -> str:
        payload = event.payload
        return _as_str(
            payload.get("sessionId") or payload.get("agentSessionId") or payload.get("id"),
            event.subject.id,
        )

    def _on_agent_session_started(self, event: DomainEventEnvelopeV1) -> None:
        payload = event.payload
        session_id = self._agent_session_id(event)
        role_raw = _as_str(payload.get("role"), AgentRole.TRACE.value)
        try:
            role = AgentRole(role_raw)
        except ValueError:
            role = AgentRole.TRACE
        # The run is authoritative on the envelope, and the incident is genuinely absent
        # for run-scoped copilot threads (ADR 0035) — neither is repeated in the payload.
        incident_id = payload.get("incidentId")
        self.state.agent_sessions[session_id] = AgentSessionV1.model_validate(
            {
                "schemaVersion": AGENT_SESSION_SCHEMA_VERSION,
                "id": session_id,
                "runId": self.state.run_id,
                "incidentId": incident_id if isinstance(incident_id, str) else None,
                "role": role.value,
                "state": self._agent_session_state(payload, AgentSessionState.GATHERING),
                "traceId": _as_str(payload.get("traceId"), event.trace_id),
                "createdAt": event.recorded_at.isoformat().replace("+00:00", "Z"),
                "updatedAt": event.recorded_at.isoformat().replace("+00:00", "Z"),
            }
        )
        artifact_id = _as_str(payload.get("artifactId"))
        if artifact_id:
            self.state.agent_artifacts[artifact_id] = ReplayAgentArtifactRefV1(
                artifact_id=artifact_id,
                agent_session_id=session_id,
                artifact_type=_as_str(payload.get("artifactType"), "session_start"),
                object_key=_as_str(payload.get("objectKey")) or None,
                checksum=_as_str(payload.get("checksum")) or None,
            )

    @staticmethod
    def _agent_session_state(
        payload: dict[str, Any],
        fallback: AgentSessionState,
    ) -> str:
        """Resolve a session state from a payload that names it ``toState`` or ``state``."""
        raw = payload.get("toState") or payload.get("state")
        if isinstance(raw, str):
            try:
                return AgentSessionState(raw).value
            except ValueError:
                pass
        return fallback.value

    def _on_agent_session_state(self, event: DomainEventEnvelopeV1) -> None:
        payload = event.payload
        session_id = self._agent_session_id(event)
        existing = self.state.agent_sessions.get(session_id)
        if existing is None:
            # A state change can be the first event in range when reconstruction starts
            # mid-run; seed the session from it so the transition is not dropped.
            self._on_agent_session_started(event)
            existing = self.state.agent_sessions.get(session_id)
            if existing is None:
                return
        state = AgentSessionState(self._agent_session_state(payload, existing.state))
        self.state.agent_sessions[session_id] = existing.model_copy(
            update={"state": state, "updated_at": event.recorded_at}
        )

    def _on_agent_session_completed(self, event: DomainEventEnvelopeV1) -> None:
        payload = dict(event.payload)
        payload["toState"] = AgentSessionState.COMPLETED.value
        payload["state"] = AgentSessionState.COMPLETED.value
        event = event.model_copy(update={"payload": payload})
        self._on_agent_session_state(event)

    def _on_proposal_created(self, event: DomainEventEnvelopeV1) -> None:
        payload = event.payload
        proposal_id = _as_str(payload.get("id") or payload.get("proposalId"), event.subject.id)
        action_class = _as_str(payload.get("actionClass"), ActionClass.OPERATIONAL.value)
        self.state.proposals[proposal_id] = ActionProposalV1.model_validate(
            {
                "schemaVersion": ACTION_PROPOSAL_SCHEMA_VERSION,
                "id": proposal_id,
                "incidentId": _as_str(payload.get("incidentId"), "incident:inc_unknown"),
                "agentSessionId": _as_str(
                    payload.get("agentSessionId"),
                    "agent-session:ags_unknown",
                ),
                "actionClass": action_class,
                "targetAssetId": _as_str(payload.get("targetAssetId"), "asset:unknown"),
                "command": _as_str(payload.get("command"), "unknown"),
                "scenarioCommand": payload.get("scenarioCommand"),
                "currentRevisionId": payload.get("currentRevisionId"),
                "status": ProposalStatus.PENDING.value,
                "rationale": _as_str(payload.get("rationale"), ""),
                "revision": _as_int(payload.get("revision"), 1),
                "createdAt": event.recorded_at.isoformat().replace("+00:00", "Z"),
            }
        )

    def _on_proposal_status(self, status: ProposalStatus):
        def handler(event: DomainEventEnvelopeV1) -> None:
            payload = event.payload
            proposal_id = _as_str(
                payload.get("proposalId") or payload.get("id"),
                event.subject.id,
            )
            existing = self.state.proposals.get(proposal_id)
            if existing is None:
                self._on_proposal_created(event)
                existing = self.state.proposals[proposal_id]
            self.state.proposals[proposal_id] = existing.model_copy(update={"status": status})
            if status == ProposalStatus.APPROVED:
                approval_id = _as_str(payload.get("approvalId"), f"apr_{event.event_id[4:]}")
                # approval ids must match runtime pattern; derive from event when missing
                if not approval_id.startswith("apr_"):
                    approval_id = "apr_" + event.event_id.split("_", 1)[-1]
                with contextlib.suppress(Exception):
                    # Skip malformed approval projection; event remains in audit trail.
                    self.state.approvals[approval_id] = ApprovalV1.model_validate(
                        {
                            "schemaVersion": APPROVAL_SCHEMA_VERSION,
                            "id": approval_id,
                            "proposalId": proposal_id,
                            "decision": ApprovalDecision.APPROVED.value,
                            "approverId": _as_str(payload.get("approverId"), event.actor.id),
                            "proposalRevision": _as_int(
                                payload.get("proposalRevision"),
                                existing.revision,
                            ),
                            "decidedAt": event.recorded_at.isoformat().replace("+00:00", "Z"),
                        }
                    )
            if status == ProposalStatus.REJECTED:
                approval_id = _as_str(payload.get("approvalId"), "")
                if approval_id.startswith("apr_"):
                    with contextlib.suppress(Exception):
                        self.state.approvals[approval_id] = ApprovalV1.model_validate(
                            {
                                "schemaVersion": APPROVAL_SCHEMA_VERSION,
                                "id": approval_id,
                                "proposalId": proposal_id,
                                "decision": ApprovalDecision.REJECTED.value,
                                "approverId": _as_str(payload.get("approverId"), event.actor.id),
                                "proposalRevision": _as_int(
                                    payload.get("proposalRevision"),
                                    existing.revision,
                                ),
                                "decidedAt": event.recorded_at.isoformat().replace(
                                    "+00:00",
                                    "Z",
                                ),
                            }
                        )

        return handler

    def _on_proposal_modified(self, event: DomainEventEnvelopeV1) -> None:
        payload = event.payload
        proposal_id = _as_str(payload.get("proposalId") or payload.get("id"), event.subject.id)
        existing = self.state.proposals.get(proposal_id)
        if existing is None:
            self._on_proposal_created(event)
            existing = self.state.proposals[proposal_id]
        self.state.proposals[proposal_id] = existing.model_copy(
            update={
                "status": ProposalStatus.PENDING,
                "revision": existing.revision + 1,
                "current_revision_id": _as_str(
                    payload.get("newRevisionId") or payload.get("currentRevisionId"),
                    existing.current_revision_id or "",
                )
                or existing.current_revision_id,
                "rationale": _as_str(payload.get("rationale"), existing.rationale),
            }
        )

    def _on_action_executed(self, event: DomainEventEnvelopeV1) -> None:
        payload = event.payload
        action_id = _as_str(payload.get("id") or payload.get("actionId"), "")
        if not action_id.startswith("act_"):
            action_id = "act_" + event.event_id.split("_", 1)[-1]
        proposal_id = _as_str(payload.get("proposalId"), "prp_" + event.event_id.split("_", 1)[-1])
        try:
            self.state.executed_actions[action_id] = ExecutedActionV1.model_validate(
                {
                    "schemaVersion": EXECUTED_ACTION_SCHEMA_VERSION,
                    "id": action_id,
                    "proposalId": proposal_id,
                    "runId": self.state.run_id,
                    "resultEventId": event.event_id,
                    "idempotencyKey": _as_str(
                        payload.get("idempotencyKey"),
                        f"idem_{event.event_id}",
                    ),
                    "executedAt": event.recorded_at.isoformat().replace("+00:00", "Z"),
                }
            )
        except Exception:
            return
        proposal = self.state.proposals.get(proposal_id)
        if proposal is not None:
            self.state.proposals[proposal_id] = proposal.model_copy(
                update={"status": ProposalStatus.EXECUTED}
            )

    def _on_report_version(self, event: DomainEventEnvelopeV1) -> None:
        payload = event.payload
        report_id = _as_str(payload.get("reportId") or payload.get("id"), f"aar_{event.sequence}")
        version_id = _as_str(
            payload.get("reportVersionId") or payload.get("versionId"),
            f"rpv_{event.sequence}",
        )
        incident_raw = payload.get("incidentId")
        incident_id = incident_raw if isinstance(incident_raw, str) else None
        self.state.reports[report_id] = ReplayReportRefV1(
            report_id=report_id,
            report_version_id=version_id,
            incident_id=incident_id,  # type: ignore[arg-type]
            status=_as_str(payload.get("status"), "created"),
            checksum=_as_str(payload.get("checksum")) or None,
        )

    def _on_report_completed(self, event: DomainEventEnvelopeV1) -> None:
        payload = event.payload
        report_id = _as_str(payload.get("reportId"), "")
        if not report_id:
            return
        existing = self.state.reports.get(report_id)
        if existing is None:
            self._on_report_version(event)
            existing = self.state.reports.get(report_id)
        if existing is None:
            return
        self.state.reports[report_id] = existing.model_copy(update={"status": "completed"})

    def _on_report_failed(self, event: DomainEventEnvelopeV1) -> None:
        payload = event.payload
        report_id = _as_str(payload.get("reportId"), "")
        if not report_id:
            return
        existing = self.state.reports.get(report_id)
        if existing is None:
            self._on_report_version(event)
            existing = self.state.reports.get(report_id)
        if existing is None:
            return
        self.state.reports[report_id] = existing.model_copy(update={"status": "failed"})

    def _maybe_project_evidence(self, event: DomainEventEnvelopeV1) -> None:
        payload = event.payload
        evidence_id: object
        summary: object
        if event.type == "alert.created":
            # ``evidenceId`` names evidence; the alert's ``id`` names the alert
            # (``alert:...``). Falling back to ``id`` meant the "evidence:" guard below
            # rejected every real alert, so replay reconstructed an empty evidence list
            # for every run — the historical inspector had nothing to show.
            explicit = payload.get("evidenceId")
            evidence_id = (
                explicit if isinstance(explicit, str) else f"evidence:evd_alert_{event.sequence}"
            )
            summary = _as_str(payload.get("summary")) or _as_str(
                payload.get("title"),
                "Alert evidence",
            )
        else:
            evidence_id = payload.get("evidenceId") or payload.get("id")
            summary = payload.get("summary")
        if not isinstance(evidence_id, str) or not evidence_id.startswith("evidence:"):
            return
        if not isinstance(summary, str) or not summary:
            return
        asset_id = payload.get("assetId")
        self.state.evidence[evidence_id] = EvidenceV1.model_validate(
            {
                "schemaVersion": EVIDENCE_SCHEMA_VERSION,
                "id": evidence_id,
                "runId": self.state.run_id,
                "sourceEventId": event.event_id,
                "summary": summary,
                "assetId": asset_id if isinstance(asset_id, str) else None,
                "createdAt": event.recorded_at.isoformat().replace("+00:00", "Z"),
            }
        )

    def _audit_summary(self, event: DomainEventEnvelopeV1) -> str:
        payload = event.payload
        title = payload.get("title") or payload.get("command") or payload.get("status")
        if isinstance(title, str) and title:
            return f"{event.type}: {title}"[:512]
        return event.type[:512]


def empty_provenance(
    *,
    run_id: str,
    mode: ReplayModeV1,
    applied_from: int,
    applied_to: int,
    applied_count: int,
    snapshot_id: str | None = None,
    snapshot_sequence: int | None = None,
    fallback_reason: str | None = None,
) -> ReplayProvenanceV1:
    return ReplayProvenanceV1(
        schema_version=REPLAY_PROVENANCE_SCHEMA_VERSION,
        run_id=run_id,  # type: ignore[arg-type]
        mode=mode,
        snapshot_id=snapshot_id,  # type: ignore[arg-type]
        snapshot_sequence=snapshot_sequence,
        applied_from_sequence=applied_from,
        applied_to_sequence=applied_to,
        applied_event_count=applied_count,
        fallback_reason=fallback_reason,
        reconstructed_at=_utc_now(),
    )
