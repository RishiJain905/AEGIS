"""Deterministic timeline synthesis from persisted domain events."""

from __future__ import annotations

from aegis_contracts.events import DomainEventEnvelopeV1
from aegis_contracts.investigation import InvestigationDetailV1
from aegis_contracts.reports import ReportTimelineEntryV1
from aegis_contracts.versioning import REPORT_TIMELINE_ENTRY_SCHEMA_VERSION

_TIMELINE_EVENT_PREFIXES = (
    "telemetry.",
    "alert.",
    "model.score.",
    "risk.",
    "incident.",
    "sim.asset.",
    "sim.branch.",
    "sim.hidden_condition.",
    "investigation.",
    "action.proposal.",
    "agent.",
    "report.",
)


def _format_payload_string(value: object, fallback: str) -> str:
    return value if isinstance(value, str) else fallback


def timeline_label_for_event(event: DomainEventEnvelopeV1) -> str:
    payload = event.payload
    subject_id = event.subject.id
    match event.type:
        case "sim.run.started":
            return "Run started"
        case "sim.run.paused":
            return "Run paused"
        case "sim.run.resumed":
            return "Run resumed"
        case "sim.run.stopped":
            return "Run stopped"
        case "sim.asset.status_changed":
            asset_id = _format_payload_string(payload.get("assetId"), subject_id)
            status = _format_payload_string(payload.get("status"), "updated")
            return f"Asset {asset_id} → {status}"
        case "telemetry.authentication.failed":
            asset_id = _format_payload_string(payload.get("assetId"), subject_id)
            return f"Authentication failed on {asset_id}"
        case "telemetry.authentication.succeeded":
            asset_id = _format_payload_string(payload.get("assetId"), subject_id)
            return f"Authentication succeeded on {asset_id}"
        case "telemetry.api.request":
            asset_id = _format_payload_string(payload.get("assetId"), subject_id)
            return f"API request on {asset_id}"
        case "alert.created":
            return f"Alert: {_format_payload_string(payload.get('title'), 'created')}"
        case "risk.score.computed":
            asset_id = _format_payload_string(payload.get("assetId"), subject_id)
            return f"Graph risk updated on {asset_id}"
        case "risk.projection.updated":
            return "Graph risk projection updated"
        case "incident.created":
            return f"Incident: {_format_payload_string(payload.get('title'), 'created')}"
        case "report.version.created":
            return "After-action report version created"
        case "report.generation.completed":
            return "Report generation completed"
        case _:
            return event.type


def timeline_status_for_event(event_type: str, payload: dict[str, object]) -> str:
    if event_type == "sim.asset.status_changed":
        status = payload.get("status")
        return status if isinstance(status, str) else "suspicious"
    if event_type.startswith("alert."):
        return "suspicious"
    if event_type.startswith("incident."):
        return "under_investigation"
    if "failed" in event_type:
        return "suspicious"
    return "normal"


def _evidence_for_event(
    event: DomainEventEnvelopeV1,
    investigation: InvestigationDetailV1,
) -> list[str]:
    evidence_ids: list[str] = []
    for attachment in investigation.evidence_attachments:
        provenance = attachment.provenance
        if (
            provenance.source_type.value == "event"
            and provenance.source_id == event.event_id
            and attachment.evidence_id
        ):
            evidence_ids.append(attachment.evidence_id)
    return evidence_ids


def synthesize_timeline(
    events: list[DomainEventEnvelopeV1],
    investigation: InvestigationDetailV1,
) -> list[ReportTimelineEntryV1]:
    timeline: list[ReportTimelineEntryV1] = []
    for event in sorted(events, key=lambda item: item.sequence):
        if not any(event.type.startswith(prefix) for prefix in _TIMELINE_EVENT_PREFIXES):
            continue
        timeline.append(
            ReportTimelineEntryV1(
                schema_version=REPORT_TIMELINE_ENTRY_SCHEMA_VERSION,
                sequence=event.sequence,
                event_id=event.event_id,
                event_type=event.type,
                label=timeline_label_for_event(event),
                timestamp=event.sim_time,
                status=timeline_status_for_event(event.type, event.payload),
                related_evidence_ids=_evidence_for_event(event, investigation),
                related_hypothesis_ids=[],
            )
        )
    return timeline
