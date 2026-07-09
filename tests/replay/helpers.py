"""Helpers for Phase 25 replay unit tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aegis_contracts import ActorRef, ActorType, DomainEventEnvelopeV1

RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"
TRACE_ID = "trc_01ARZ3NDEKTSV4RRFFQ69G5FAX"
BASE_TIME = datetime(2026, 1, 1, 18, 0, 0, tzinfo=UTC)


def event_id(index: int) -> str:
    # Valid Crockford base32 suffix (no I/L/O/U), unique per index.
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    base = alphabet[index % len(alphabet)] * 20
    # Encode index in remaining 6 chars for uniqueness beyond alphabet length.
    n = index
    encoded = []
    for _ in range(6):
        encoded.append(alphabet[n % len(alphabet)])
        n //= len(alphabet)
    suffix = (base + "".join(reversed(encoded)))[:26]
    return f"evt_{suffix}"


def make_event(
    *,
    sequence: int,
    event_type: str,
    payload: dict[str, object] | None = None,
    subject_id: str = "asset:svc-api-gateway",
    event_index: int | None = None,
) -> DomainEventEnvelopeV1:
    idx = event_index if event_index is not None else sequence
    sim = BASE_TIME + timedelta(seconds=sequence)
    return DomainEventEnvelopeV1(
        event_id=event_id(idx),  # type: ignore[arg-type]
        run_id=RUN_ID,  # type: ignore[arg-type]
        sequence=sequence,
        type=event_type,
        schema_version=1,
        sim_time=sim,
        recorded_at=sim,
        actor=ActorRef(type=ActorType.SYSTEM, id="asset:simulation-engine"),
        subject=ActorRef(type=ActorType.ASSET, id=subject_id),  # type: ignore[arg-type]
        payload=payload or {"schemaVersion": 1},
        trace_id=TRACE_ID,  # type: ignore[arg-type]
    )


def sample_history(*, count: int = 20) -> list[DomainEventEnvelopeV1]:
    events: list[DomainEventEnvelopeV1] = []
    events.append(
        make_event(
            sequence=1,
            event_type="sim.run.started",
            payload={
                "schemaVersion": 1,
                "scenarioVersionId": "scenario-version:v1.0.0-synthetic",
                "seed": 42,
            },
            event_index=1,
        )
    )
    for seq in range(2, count + 1):
        if seq == 5:
            events.append(
                make_event(
                    sequence=seq,
                    event_type="sim.asset.status_changed",
                    payload={
                        "schemaVersion": 1,
                        "assetId": "asset:svc-api-gateway",
                        "status": "suspicious",
                        "label": "API Gateway",
                        "assetType": "service",
                        "riskScore": 0.4,
                        "criticality": 0.9,
                    },
                    event_index=seq,
                )
            )
        elif seq == 8:
            events.append(
                make_event(
                    sequence=seq,
                    event_type="alert.created",
                    payload={
                        "schemaVersion": 1,
                        "title": "Suspicious auth",
                        "assetId": "asset:device-workstation-01",
                        "evidenceId": "evidence:evd_synthetic_001",
                        "summary": "Failed login cluster",
                    },
                    subject_id="asset:device-workstation-01",
                    event_index=seq,
                )
            )
        elif seq == 10:
            events.append(
                make_event(
                    sequence=seq,
                    event_type="incident.created",
                    payload={
                        "schemaVersion": 1,
                        "id": "incident:inc_synthetic_001",
                        "title": "Silent Relay probe",
                        "state": "investigating",
                        "alertIds": ["alert:alt_synthetic_001"],
                    },
                    event_index=seq,
                )
            )
        elif seq == 12:
            events.append(
                make_event(
                    sequence=seq,
                    event_type="risk.score.computed",
                    payload={
                        "schemaVersion": 1,
                        "assetId": "asset:svc-api-gateway",
                        "score": 0.77,
                        "revision": 2,
                    },
                    event_index=seq,
                )
            )
        elif seq == 14:
            events.append(
                make_event(
                    sequence=seq,
                    event_type="action.proposal.created",
                    payload={
                        "schemaVersion": 1,
                        "id": "prp_01ARZ3NDEKTSV4RRFFQ69G5FAY",
                        "incidentId": "incident:inc_synthetic_001",
                        "agentSessionId": "agent-session:ags_synthetic_001",
                        "actionClass": "class_2",
                        "targetAssetId": "asset:device-workstation-01",
                        "command": "isolate",
                        "scenarioCommand": "isolate",
                        "currentRevisionId": "prv_01ARZ3NDEKTSV4RRFFQ69G5FB0",
                        "rationale": "Contain workstation",
                        "revision": 1,
                    },
                    event_index=seq,
                )
            )
        elif seq == 16:
            events.append(
                make_event(
                    sequence=seq,
                    event_type="action.proposal.approved",
                    payload={
                        "schemaVersion": 1,
                        "proposalId": "prp_01ARZ3NDEKTSV4RRFFQ69G5FAY",
                        "approvalId": "apr_01ARZ3NDEKTSV4RRFFQ69G5FAZ",
                        "approverId": "asset:operator-console",
                        "proposalRevision": 1,
                    },
                    event_index=seq,
                )
            )
        elif seq == 18:
            events.append(
                make_event(
                    sequence=seq,
                    event_type="action.executed",
                    payload={
                        "schemaVersion": 1,
                        "id": "act_01ARZ3NDEKTSV4RRFFQ69G5FB0",
                        "proposalId": "prp_01ARZ3NDEKTSV4RRFFQ69G5FAY",
                        "idempotencyKey": "idem_replay_fixture_001",
                    },
                    event_index=seq,
                )
            )
        elif seq == count and count >= 19:
            events.append(
                make_event(
                    sequence=seq,
                    event_type="report.version.created",
                    payload={
                        "schemaVersion": 1,
                        "reportId": "aar_fixture_001",
                        "reportVersionId": "rpv_fixture_001",
                        "incidentId": "incident:inc_synthetic_001",
                        "status": "created",
                        "checksum": "sha256:" + ("ab" * 32),
                    },
                    event_index=seq,
                )
            )
        else:
            events.append(
                make_event(
                    sequence=seq,
                    event_type="sim.asset.status_changed",
                    payload={
                        "schemaVersion": 1,
                        "assetId": "asset:svc-api-gateway",
                        "status": "under_investigation" if seq > 5 else "normal",
                        "label": "API Gateway",
                        "assetType": "service",
                    },
                    event_index=seq,
                )
            )
    return events
