import {
  parseContract,
  replayCursorSchema,
  replayStateSchema,
  snapshotManifestSchema,
  stateDiffSchema,
  type ReplayCursorV1,
  type ReplayStateV1,
  type SnapshotManifestV1,
  type StateDiffV1,
} from '@aegis/contracts-ts';

import shellDataset from '@/fixtures/shell-dataset.json';

const DEFAULT_RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

const BASE_AUDIT = [
  {
    eventId: 'evt_01ARZ3NDEKTSV4RRFFQ69G5FA1',
    sequence: 0,
    eventType: 'run.started',
    summary: 'Operation Silent Relay started',
  },
  {
    eventId: 'evt_01ARZ3NDEKTSV4RRFFQ69G5FA2',
    sequence: 40,
    eventType: 'telemetry.observed',
    summary: 'Baseline telemetry observed',
  },
  {
    eventId: 'evt_01ARZ3NDEKTSV4RRFFQ69G5FA3',
    sequence: 120,
    eventType: 'incident.opened',
    summary: 'Suspicious authentication activity detected',
  },
  {
    eventId: 'evt_01ARZ3NDEKTSV4RRFFQ69G5FA4',
    sequence: 180,
    eventType: 'evidence.attached',
    summary: 'Failed login evidence attached',
  },
  {
    eventId: 'evt_01ARZ3NDEKTSV4RRFFQ69G5FA5',
    sequence: 250,
    eventType: 'agent.session.started',
    summary: 'TRACE investigation session started',
  },
  {
    eventId: 'evt_01ARZ3NDEKTSV4RRFFQ69G5FA6',
    sequence: 320,
    eventType: 'proposal.submitted',
    summary: 'BASTION isolation proposal submitted',
  },
  {
    eventId: 'evt_01ARZ3NDEKTSV4RRFFQ69G5FA7',
    sequence: 400,
    eventType: 'approval.decided',
    summary: 'Operator approved isolation proposal',
  },
  {
    eventId: 'evt_01ARZ3NDEKTSV4RRFFQ69G5FA8',
    sequence: 500,
    eventType: 'action.executed',
    summary: 'Isolation command executed',
  },
] as const;

function cloneGraphAtSequence(runId: string, sequence: number) {
  const snapshot = (
    shellDataset as { graphSnapshots: Array<Record<string, unknown>> }
  ).graphSnapshots.find((item) => item.runId === runId);
  if (!snapshot) {
    return null;
  }
  const nodes = Array.isArray(snapshot.nodes)
    ? snapshot.nodes.map((node) => {
        const record = node as Record<string, unknown>;
        const riskScore = typeof record.riskScore === 'number' ? record.riskScore : 0.2;
        const scaled = Math.min(1, Math.max(0, riskScore * (0.4 + sequence / 500)));
        return {
          ...record,
          riskScore: Number(scaled.toFixed(2)),
          status:
            sequence >= 400 ? 'contained' : sequence >= 120 ? 'under_investigation' : 'normal',
          revision: Math.max(1, sequence),
        };
      })
    : [];
  return {
    ...snapshot,
    sequence,
    revision: Math.max(1, Math.floor(sequence / 40)),
    nodes,
  };
}

function simTimeForSequence(sequence: number): string {
  const totalSeconds = Math.max(0, sequence) * 6;
  const hours = 18 + Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return `2026-01-01T${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}.000Z`;
}

function buildReplayState(
  runId: string,
  sequence: number,
  incidentId?: string | null,
): ReplayStateV1 {
  const clamped = Math.max(0, Math.min(500, sequence));
  const simTime = simTimeForSequence(clamped);
  const auditEvents = BASE_AUDIT.filter((event) => event.sequence <= clamped).map((event) => ({
    ...event,
  }));
  const includeIncident = clamped >= 120;
  const includeEvidence = clamped >= 180;
  const includeAgent = clamped >= 250;
  const includeProposal = clamped >= 320;
  const includeApproval = clamped >= 400;
  const includeAction = clamped >= 500;

  const raw = {
    schemaVersion: 1,
    runId,
    cursor: {
      schemaVersion: 1,
      runId,
      sequence: clamped,
      simTime,
      incidentId: incidentId ?? null,
    },
    run: {
      schemaVersion: 1,
      id: runId,
      scenarioVersionId: 'scenario-version:v1.0.0-synthetic',
      seed: 424242,
      status: clamped >= 500 ? 'completed' : 'running',
      startedAt: '2026-06-30T02:00:00.000Z',
      simTime,
      revision: Math.max(1, Math.floor(clamped / 50)),
    },
    graph: cloneGraphAtSequence(runId, clamped),
    incidents: includeIncident
      ? [
          {
            schemaVersion: 1,
            id: 'incident:inc_synthetic_001',
            runId,
            title: 'Suspicious authentication activity',
            state: includeApproval ? 'containing' : includeAgent ? 'investigating' : 'open',
            alertIds: ['alert:alt_synthetic_001'],
            createdAt: '2026-06-30T02:00:01.102Z',
            updatedAt: '2026-06-30T02:05:00.000Z',
            revision: includeApproval ? 3 : 2,
          },
        ].filter((incident) => !incidentId || incident.id === incidentId)
      : [],
    evidence: includeEvidence
      ? [
          {
            schemaVersion: 1,
            id: 'evidence:evd_synthetic_001',
            runId,
            sourceEventId: 'evt_01ARZ3NDEKTSV4RRFFQ69G5FA3',
            summary: 'Failed login attempt from workstation',
            assetId: 'asset:device-workstation-01',
            createdAt: '2026-06-30T02:00:01.102Z',
          },
        ]
      : [],
    riskScores:
      clamped >= 40
        ? [
            {
              assetId: 'asset:svc-api-gateway',
              score: Number(Math.min(0.95, 0.2 + clamped / 700).toFixed(2)),
              revision: Math.max(1, Math.floor(clamped / 100)),
            },
          ]
        : [],
    agentSessions: includeAgent
      ? [
          {
            schemaVersion: 1,
            id: 'agent-session:ags_synthetic_001',
            incidentId: 'incident:inc_synthetic_001',
            role: 'TRACE',
            state: 'gathering',
            traceId: 'trc_01ARZ3NDEKTSV4RRFFQ69G5FAX',
            createdAt: '2026-06-30T02:15:00.000Z',
            updatedAt: '2026-06-30T02:15:00.000Z',
          },
        ]
      : [],
    agentArtifacts: includeAgent
      ? [
          {
            artifactId: 'aaf_01ARZ3NDEKTSV4RRFFQ69G5FB1',
            agentSessionId: 'agent-session:ags_synthetic_001',
            artifactType: 'investigation_note',
            objectKey: 'artifacts/agent/aaf_01ARZ3NDEKTSV4RRFFQ69G5FB1.json',
            checksum: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
          },
        ]
      : [],
    proposals: includeProposal
      ? [
          {
            schemaVersion: 2,
            id: 'prp_01ARZ3NDEKTSV4RRFFQ69G5FAY',
            incidentId: 'incident:inc_synthetic_001',
            agentSessionId: 'agent-session:ags_synthetic_001',
            actionClass: 'class_2',
            targetAssetId: 'asset:device-workstation-01',
            command: 'isolate',
            scenarioCommand: 'isolate',
            currentRevisionId: 'prv_01ARZ3NDEKTSV4RRFFQ69G5FB0',
            status: includeApproval ? 'approved' : 'pending',
            rationale: 'Contain suspected compromised workstation',
            revision: 1,
            createdAt: '2026-06-30T02:20:00.000Z',
          },
        ]
      : [],
    approvals: includeApproval
      ? [
          {
            schemaVersion: 1,
            id: 'apr_01ARZ3NDEKTSV4RRFFQ69G5FAZ',
            proposalId: 'prp_01ARZ3NDEKTSV4RRFFQ69G5FAY',
            decision: 'approved',
            approverId: 'operator:synthetic-001',
            proposalRevision: 1,
            decidedAt: '2026-06-30T02:25:00.000Z',
          },
        ]
      : [],
    executedActions: includeAction
      ? [
          {
            schemaVersion: 1,
            id: 'act_01ARZ3NDEKTSV4RRFFQ69G5FB0',
            proposalId: 'prp_01ARZ3NDEKTSV4RRFFQ69G5FAY',
            runId,
            resultEventId: 'evt_01ARZ3NDEKTSV4RRFFQ69G5FA8',
            idempotencyKey: 'replay:fixture:execute:isolate:001',
            executedAt: '2026-06-30T02:30:00.000Z',
          },
        ]
      : [],
    reports: includeAction
      ? [
          {
            reportId: 'aar_01ARZ3NDEKTSV4RRFFQ69G5FBD',
            reportVersionId: 'rpv_01ARZ3NDEKTSV4RRFFQ69G5FBE',
            incidentId: 'incident:inc_synthetic_001',
            status: 'completed',
            checksum: 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
          },
        ]
      : [],
    auditEvents,
    stateDigest: `sha256:fixture${String(clamped).padStart(58, '0')}`,
    provenance: {
      schemaVersion: 1,
      runId,
      mode: clamped >= 200 ? 'from_snapshot_plus_events' : 'from_events',
      snapshotId: clamped >= 200 ? 'rps_01ARZ3NDEKTSV4RRFFQ69G5FC0' : null,
      snapshotSequence: clamped >= 200 ? 200 : null,
      appliedFromSequence: clamped >= 200 ? 201 : 0,
      appliedToSequence: clamped,
      appliedEventCount: auditEvents.length,
      fallbackReason: null,
      reconstructedAt: '2026-06-30T03:00:00.000Z',
    },
  };

  return parseContract(replayStateSchema, raw);
}

export function getReplayStateFixture(
  runId: string,
  params?: { sequence?: number; simTime?: string; incidentId?: string | null },
): ReplayStateV1 {
  if (runId === 'run_01ARZ3NDEKTSV4RRFFQ69G5FZ0') {
    throw Object.assign(new Error('Replay data unavailable'), {
      code: 'REPLAY_NOT_FOUND',
      status: 404,
    });
  }
  if (runId === 'run_01ARZ3NDEKTSV4RRFFQ69G5FZ1') {
    throw Object.assign(new Error('Snapshot checksum mismatch'), {
      code: 'SNAPSHOT_CHECKSUM_MISMATCH',
      status: 409,
    });
  }
  if (runId === 'run_01ARZ3NDEKTSV4RRFFQ69G5FZ2') {
    throw Object.assign(new Error('Snapshot incompatible with projector'), {
      code: 'SNAPSHOT_INCOMPATIBLE',
      status: 409,
    });
  }
  const sequence = params?.sequence ?? 500;
  return buildReplayState(runId || DEFAULT_RUN_ID, sequence, params?.incidentId);
}

export function getReplayCursorFixture(
  runId: string,
  params?: { sequence?: number; simTime?: string; incidentId?: string | null },
): ReplayCursorV1 {
  const state = getReplayStateFixture(runId, params);
  return parseContract(replayCursorSchema, state.cursor);
}

export function getReplayDiffFixture(
  runId: string,
  fromSequence: number,
  toSequence: number,
): StateDiffV1 {
  const fromState = getReplayStateFixture(runId, { sequence: fromSequence });
  const toState = getReplayStateFixture(runId, { sequence: toSequence });
  const entries = [];
  if ((fromState.incidents[0]?.state ?? null) !== (toState.incidents[0]?.state ?? null)) {
    entries.push({
      path: 'incidents[0].state',
      changeType: 'updated',
      before: fromState.incidents[0]?.state ?? null,
      after: toState.incidents[0]?.state ?? null,
    });
  }
  if ((fromState.graph?.nodes.length ?? 0) !== (toState.graph?.nodes.length ?? 0)) {
    entries.push({
      path: 'graph.nodes.length',
      changeType: 'updated',
      before: fromState.graph?.nodes.length ?? 0,
      after: toState.graph?.nodes.length ?? 0,
    });
  }
  if ((fromState.riskScores[0]?.score ?? null) !== (toState.riskScores[0]?.score ?? null)) {
    entries.push({
      path: 'riskScores[0].score',
      changeType: 'updated',
      before: fromState.riskScores[0]?.score ?? null,
      after: toState.riskScores[0]?.score ?? null,
    });
  }
  return parseContract(stateDiffSchema, {
    schemaVersion: 1,
    runId,
    fromCursor: fromState.cursor,
    toCursor: toState.cursor,
    entries,
    fromDigest: fromState.stateDigest,
    toDigest: toState.stateDigest,
    equivalent: fromState.stateDigest === toState.stateDigest,
  });
}

export function listReplaySnapshotsFixture(runId: string): SnapshotManifestV1[] {
  return [
    parseContract(snapshotManifestSchema, {
      schemaVersion: 1,
      snapshotId: 'rps_01ARZ3NDEKTSV4RRFFQ69G5FC0',
      runId,
      sequence: 200,
      simTime: '2026-01-01T18:20:00.000Z',
      scenarioVersionId: 'scenario-version:v1.0.0-synthetic',
      engineVersion: '0.0.0-phase10',
      projectorVersion: 'replay-projector-v1',
      workspaceVersion: '0.0.0-phase26',
      eventRangeFrom: 0,
      eventRangeTo: 200,
      checksum: 'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd',
      compression: 'gzip',
      contentType: 'application/json',
      sizeBytes: 2048,
      objectKey: `snapshots/${runId}/200/rps_01ARZ3NDEKTSV4RRFFQ69G5FC0.json.gz`,
      stateDigest: 'sha256:fixture00000000000000000000000000000000000000000000000000000200',
      triggerReason: 'sequence_interval',
      retentionClass: 'standard',
      createdAt: '2026-06-30T02:10:00.000Z',
      compatible: true,
    }),
    parseContract(snapshotManifestSchema, {
      schemaVersion: 1,
      snapshotId: 'rps_01ARZ3NDEKTSV4RRFFQ69G5FC1',
      runId,
      sequence: 400,
      simTime: '2026-01-01T18:40:00.000Z',
      scenarioVersionId: 'scenario-version:v1.0.0-synthetic',
      engineVersion: '0.0.0-phase10',
      projectorVersion: 'replay-projector-v1',
      workspaceVersion: '0.0.0-phase26',
      eventRangeFrom: 0,
      eventRangeTo: 400,
      checksum: 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
      compression: 'gzip',
      contentType: 'application/json',
      sizeBytes: 4096,
      objectKey: `snapshots/${runId}/400/rps_01ARZ3NDEKTSV4RRFFQ69G5FC1.json.gz`,
      stateDigest: 'sha256:fixture00000000000000000000000000000000000000000000000000000400',
      triggerReason: 'sequence_interval',
      retentionClass: 'standard',
      createdAt: '2026-06-30T02:20:00.000Z',
      compatible: true,
    }),
  ];
}

export const REPLAY_FIXTURE_MAX_SEQUENCE = 500;
export const REPLAY_FIXTURE_MIN_SEQUENCE = 0;
