"""Bounded snapshot of the run state an agent is grounded on.

Run-scoped agent turns (the operator copilot and the autonomy lanes) are
single-shot: the model answers once, and any ``toolRequests`` it returns are
executed *after* generation, with their results never fed back into a second
call. Injected context is therefore the only grounding an agent has for the
turn it is answering, so the request must carry the run's observable state
rather than expecting the model to go fetch it.

The snapshot is deliberately bounded on both cardinality and per-string length
so it always fits the delimited-data byte ceiling, and it reports the true
totals alongside the truncated lists so an agent can tell "there are none" from
"there are more than I was shown".
"""

from __future__ import annotations

from typing import Any

from aegis_contracts.entities import AlertV1, EvidenceV1, IncidentV1

MAX_RUN_STATE_ALERTS = 40
MAX_RUN_STATE_INCIDENTS = 15
MAX_RUN_STATE_EVIDENCE = 30
MAX_RUN_STATE_TEXT_CHARS = 160


def _clip(text: str | None) -> str:
    return (text or "")[:MAX_RUN_STATE_TEXT_CHARS]


def _serialize_alert(alert: AlertV1) -> dict[str, Any]:
    return {
        "alertId": alert.id,
        "title": _clip(alert.title),
        "severity": alert.severity,
        "assetId": alert.asset_id,
        "confidence": alert.confidence,
        "createdAt": alert.created_at.isoformat(),
    }


def _serialize_incident(incident: IncidentV1) -> dict[str, Any]:
    return {
        "incidentId": incident.id,
        "title": _clip(incident.title),
        "state": incident.state.value,
        "alertIds": incident.alert_ids[:MAX_RUN_STATE_ALERTS],
        "createdAt": incident.created_at.isoformat(),
    }


def _serialize_evidence(evidence: EvidenceV1) -> dict[str, Any]:
    return {
        "evidenceId": evidence.id,
        "summary": _clip(evidence.summary),
        "assetId": evidence.asset_id,
        "createdAt": evidence.created_at.isoformat(),
    }


def _section(items: list[Any], *, limit: int, serialize: Any) -> dict[str, Any]:
    """Serialize the ``limit`` most recent items, keeping the true total.

    Repository listings are ordered oldest-first, so the tail is the most
    recent — which is what matters for triage.
    """
    shown = items[-limit:] if limit < len(items) else list(items)
    return {
        "total": len(items),
        "shown": len(shown),
        "truncated": len(shown) < len(items),
        "items": [serialize(item) for item in shown],
    }


def summarize_run_state(
    *,
    run_id: str,
    alerts: list[AlertV1],
    incidents: list[IncidentV1],
    evidence: list[EvidenceV1],
) -> dict[str, Any]:
    """Build the run-state snapshot injected into a run-scoped agent request.

    Everything here is already visible to the operator in the command centre —
    detection output and declared incidents, not attacker ground truth — so the
    snapshot discloses nothing the human asking the question cannot see.
    """
    return {
        "runId": run_id,
        "alerts": _section(alerts, limit=MAX_RUN_STATE_ALERTS, serialize=_serialize_alert),
        "incidents": _section(
            incidents, limit=MAX_RUN_STATE_INCIDENTS, serialize=_serialize_incident
        ),
        "evidence": _section(evidence, limit=MAX_RUN_STATE_EVIDENCE, serialize=_serialize_evidence),
    }
