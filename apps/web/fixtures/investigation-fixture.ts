import {
  agentSessionDetailSchema,
  investigationDetailSchema,
  parseContract,
  type AgentSessionDetailV1,
  type InvestigationDetailV1,
} from '@aegis/contracts-ts';

const SYNTHETIC_INCIDENT_ID = 'incident:inc_synthetic_001';
const SYNTHETIC_RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';
const WATCHTOWER_SESSION_ID = 'agent-session:ags_watchtower_001';
const TRACE_SESSION_ID = 'agent-session:ags_synthetic_001';
const WATCHTOWER_TASK_ID = 'atk_01ARZ3NDEKTSV4RRFFQ69G5FB0';
const TRACE_TASK_ID = 'atk_01ARZ3NDEKTSV4RRFFQ69G5FAV';

const syntheticInvestigationDetail = parseContract(investigationDetailSchema, {
  schemaVersion: 1,
  incidentId: SYNTHETIC_INCIDENT_ID,
  runId: SYNTHETIC_RUN_ID,
  triageResults: [
    {
      schemaVersion: 1,
      id: 'wtri_synthetic_001',
      incidentId: SYNTHETIC_INCIDENT_ID,
      runId: SYNTHETIC_RUN_ID,
      sessionId: WATCHTOWER_SESSION_ID,
      taskId: WATCHTOWER_TASK_ID,
      alertSummaries: [
        {
          alertId: 'alert:alt_synthetic_001',
          title: 'Suspicious authentication burst',
          severity: 'high',
        },
      ],
      groupedAlertIds: ['alert:alt_synthetic_001'],
      separatedAlertIds: [],
      correlationDecisions: [
        {
          alertIds: ['alert:alt_synthetic_001'],
          decision: 'group',
          rationale: 'Shared source asset and overlapping authentication window.',
          factors: ['shared_asset', 'temporal_overlap'],
        },
      ],
      escalation: 'investigate',
      escalationRationale:
        'High-confidence authentication anomaly on API gateway warrants bounded TRACE expansion.',
      confidence: 0.86,
      evidenceIds: ['evidence:evd_synthetic_001'],
      idempotencyKey: 'watchtower:synthetic:001',
      createdAt: '2026-06-30T02:01:00.000Z',
    },
  ],
  plans: [
    {
      schemaVersion: 1,
      id: 'tplan_synthetic_001',
      incidentId: SYNTHETIC_INCIDENT_ID,
      runId: SYNTHETIC_RUN_ID,
      sessionId: TRACE_SESSION_ID,
      taskId: TRACE_TASK_ID,
      seedAssetIds: ['asset:svc-api-gateway'],
      timeWindowStartSequence: 0,
      timeWindowEndSequence: 300,
      maxHops: 2,
      maxToolCalls: 12,
      maxTokens: 8000,
      searchSteps: [
        {
          toolName: 'list_alerts_for_asset',
          arguments: { assetId: 'asset:svc-api-gateway' },
          purpose: 'Collect alert context around the gateway seed.',
        },
        {
          toolName: 'query_graph_paths',
          arguments: {
            sourceId: 'asset:svc-api-gateway',
            targetId: 'asset:svc-auth-service',
            maxHops: 2,
          },
          purpose: 'Trace authentication dependency paths.',
        },
      ],
      rationale: 'Expand from API gateway with bounded hops toward auth dependencies.',
      createdAt: '2026-06-30T02:02:00.000Z',
    },
  ],
  evidenceAttachments: [
    {
      schemaVersion: 1,
      id: 'eatt_synthetic_001',
      incidentId: SYNTHETIC_INCIDENT_ID,
      sessionId: TRACE_SESSION_ID,
      taskId: TRACE_TASK_ID,
      provenance: {
        sourceType: 'alert',
        sourceId: 'alert:alt_synthetic_001',
        summary: 'Gateway authentication burst exceeded baseline by 4.2σ.',
        collectedByTool: 'list_alerts_for_asset',
        collectedAtSequence: 42,
      },
      evidenceId: 'evidence:evd_synthetic_001',
      assetId: 'asset:svc-api-gateway',
      isContradiction: false,
      confidence: 0.91,
      rationale: 'Alert confidence and graph centrality support gateway involvement.',
      createdAt: '2026-06-30T02:03:00.000Z',
    },
    {
      schemaVersion: 1,
      id: 'eatt_synthetic_002',
      incidentId: SYNTHETIC_INCIDENT_ID,
      sessionId: TRACE_SESSION_ID,
      taskId: TRACE_TASK_ID,
      provenance: {
        sourceType: 'asset',
        sourceId: 'asset:svc-notification',
        summary: 'Notification service shows normal outbound volume during the window.',
        collectedByTool: 'get_asset_timeline',
        collectedAtSequence: 55,
      },
      assetId: 'asset:svc-notification',
      isContradiction: true,
      confidence: 0.72,
      rationale: 'Contradicts lateral movement hypothesis via notification fan-out.',
      createdAt: '2026-06-30T02:04:00.000Z',
    },
  ],
  notes: [
    {
      schemaVersion: 1,
      id: 'inote_synthetic_001',
      incidentId: SYNTHETIC_INCIDENT_ID,
      sessionId: TRACE_SESSION_ID,
      taskId: TRACE_TASK_ID,
      note: 'Gateway remains primary seed; notification traffic does not corroborate lateral spread.',
      evidenceIds: ['evidence:evd_synthetic_001'],
      createdAt: '2026-06-30T02:05:00.000Z',
    },
  ],
  candidateAssets: [
    {
      schemaVersion: 1,
      id: 'cand_synthetic_001',
      incidentId: SYNTHETIC_INCIDENT_ID,
      assetId: 'asset:svc-api-gateway',
      confidence: 0.88,
      evidenceIds: ['evidence:evd_synthetic_001'],
      rationale: 'Highest combined alert and graph-risk contribution.',
      createdAt: '2026-06-30T02:05:30.000Z',
    },
  ],
  overlays: [
    {
      schemaVersion: 1,
      id: 'golv_synthetic_001',
      incidentId: SYNTHETIC_INCIDENT_ID,
      runId: SYNTHETIC_RUN_ID,
      sessionId: TRACE_SESSION_ID,
      taskId: TRACE_TASK_ID,
      highlights: [
        {
          entityId: 'asset:svc-api-gateway',
          entityType: 'asset',
          highlightKind: 'seed',
          label: 'TRACE seed',
        },
        {
          entityId: 'asset:svc-auth-service',
          entityType: 'asset',
          highlightKind: 'expanded',
          label: 'Auth dependency',
        },
        {
          entityId: 'asset:device-workstation-01',
          entityType: 'asset',
          highlightKind: 'expanded',
          label: 'Inbound workstation',
        },
      ],
      edgeHighlights: [
        {
          entityId: 'edge:edge_conn_001',
          entityType: 'edge',
          highlightKind: 'traversed',
          label: '',
        },
        {
          entityId: 'edge:edge_dep_001',
          entityType: 'edge',
          highlightKind: 'traversed',
          label: '',
        },
      ],
      rationale: 'Bounded 2-hop expansion from API gateway seed.',
      createdAt: '2026-06-30T02:06:00.000Z',
    },
  ],
});

const watchtowerSessionDetail = parseContract(agentSessionDetailSchema, {
  schemaVersion: 1,
  session: {
    schemaVersion: 1,
    id: WATCHTOWER_SESSION_ID,
    incidentId: SYNTHETIC_INCIDENT_ID,
    role: 'WATCHTOWER',
    state: 'completed',
    traceId: 'trc_01ARZ3NDEKTSV4RRFFQ69G5FAV',
    createdAt: '2026-06-30T02:00:30.000Z',
    updatedAt: '2026-06-30T02:01:30.000Z',
  },
  tasks: [
    {
      schemaVersion: 1,
      id: WATCHTOWER_TASK_ID,
      sessionId: WATCHTOWER_SESSION_ID,
      incidentId: SYNTHETIC_INCIDENT_ID,
      status: 'completed',
      attempt: 1,
      idempotencyKey: 'initial-watchtower-synthetic',
      traceId: 'trc_01ARZ3NDEKTSV4RRFFQ69G5FAV',
      providerId: 'mock',
      createdAt: '2026-06-30T02:00:35.000Z',
      updatedAt: '2026-06-30T02:01:20.000Z',
      startedAt: '2026-06-30T02:00:40.000Z',
      completedAt: '2026-06-30T02:01:20.000Z',
    },
  ],
  transitions: [
    {
      schemaVersion: 1,
      id: 'transition:watchtower_001',
      sessionId: WATCHTOWER_SESSION_ID,
      taskId: WATCHTOWER_TASK_ID,
      fromState: 'queued',
      toState: 'gathering',
      reason: 'Task execution started',
      createdAt: '2026-06-30T02:00:40.000Z',
    },
    {
      schemaVersion: 1,
      id: 'transition:watchtower_002',
      sessionId: WATCHTOWER_SESSION_ID,
      taskId: WATCHTOWER_TASK_ID,
      fromState: 'gathering',
      toState: 'completed',
      reason: 'Triage result persisted',
      createdAt: '2026-06-30T02:01:20.000Z',
    },
  ],
  toolInvocations: [],
  artifacts: [],
});

const traceSessionDetail = parseContract(agentSessionDetailSchema, {
  schemaVersion: 1,
  session: {
    schemaVersion: 1,
    id: TRACE_SESSION_ID,
    incidentId: SYNTHETIC_INCIDENT_ID,
    role: 'TRACE',
    state: 'completed',
    traceId: 'trc_01ARZ3NDEKTSV4RRFFQ69G5FAV',
    createdAt: '2026-06-30T02:01:40.000Z',
    updatedAt: '2026-06-30T02:06:10.000Z',
  },
  tasks: [
    {
      schemaVersion: 1,
      id: TRACE_TASK_ID,
      sessionId: TRACE_SESSION_ID,
      incidentId: SYNTHETIC_INCIDENT_ID,
      status: 'completed',
      attempt: 1,
      idempotencyKey: 'initial-trace-synthetic',
      traceId: 'trc_01ARZ3NDEKTSV4RRFFQ69G5FAV',
      providerId: 'mock',
      createdAt: '2026-06-30T02:01:45.000Z',
      updatedAt: '2026-06-30T02:06:00.000Z',
      startedAt: '2026-06-30T02:01:50.000Z',
      completedAt: '2026-06-30T02:06:00.000Z',
    },
  ],
  transitions: [
    {
      schemaVersion: 1,
      id: 'transition:trace_001',
      sessionId: TRACE_SESSION_ID,
      taskId: TRACE_TASK_ID,
      fromState: 'queued',
      toState: 'gathering',
      reason: 'TRACE plan created',
      createdAt: '2026-06-30T02:01:50.000Z',
    },
    {
      schemaVersion: 1,
      id: 'transition:trace_002',
      sessionId: TRACE_SESSION_ID,
      taskId: TRACE_TASK_ID,
      fromState: 'gathering',
      toState: 'verifying',
      reason: 'Evidence collection in progress',
      createdAt: '2026-06-30T02:03:30.000Z',
    },
    {
      schemaVersion: 1,
      id: 'transition:trace_003',
      sessionId: TRACE_SESSION_ID,
      taskId: TRACE_TASK_ID,
      fromState: 'verifying',
      toState: 'completed',
      reason: 'Graph overlay and candidates persisted',
      createdAt: '2026-06-30T02:06:00.000Z',
    },
  ],
  toolInvocations: [
    {
      schemaVersion: 1,
      id: 'tiv_01ARZ3NDEKTSV4RRFFQ69G5FB1',
      taskId: TRACE_TASK_ID,
      sessionId: TRACE_SESSION_ID,
      toolName: 'list_alerts_for_asset',
      toolClass: 'read',
      status: 'success',
      durationMs: 42,
      createdAt: '2026-06-30T02:02:10.000Z',
    },
    {
      schemaVersion: 1,
      id: 'tiv_01ARZ3NDEKTSV4RRFFQ69G5FB2',
      taskId: TRACE_TASK_ID,
      sessionId: TRACE_SESSION_ID,
      toolName: 'attach_evidence',
      toolClass: 'analysis_write',
      status: 'success',
      durationMs: 18,
      createdAt: '2026-06-30T02:03:45.000Z',
    },
  ],
  artifacts: [],
});

const INVESTIGATION_DETAILS: Record<string, InvestigationDetailV1> = {
  [SYNTHETIC_INCIDENT_ID]: syntheticInvestigationDetail,
};

const AGENT_SESSION_DETAILS: Record<string, AgentSessionDetailV1> = {
  [WATCHTOWER_SESSION_ID]: watchtowerSessionDetail,
  [TRACE_SESSION_ID]: traceSessionDetail,
};

export function getInvestigationDetailFixture(incidentId: string): InvestigationDetailV1 | null {
  return INVESTIGATION_DETAILS[incidentId] ?? null;
}

export function getAgentSessionFixture(sessionId: string): AgentSessionDetailV1 | null {
  return AGENT_SESSION_DETAILS[sessionId] ?? null;
}

export function listInvestigationSessionIds(incidentId: string): string[] {
  const detail = INVESTIGATION_DETAILS[incidentId];
  if (!detail) {
    return [];
  }
  const sessionIds = new Set<string>();
  for (const triage of detail.triageResults) {
    sessionIds.add(triage.sessionId);
  }
  for (const plan of detail.plans) {
    sessionIds.add(plan.sessionId);
  }
  for (const attachment of detail.evidenceAttachments) {
    sessionIds.add(attachment.sessionId);
  }
  for (const note of detail.notes) {
    sessionIds.add(note.sessionId);
  }
  for (const overlay of detail.overlays) {
    sessionIds.add(overlay.sessionId);
  }
  return [...sessionIds];
}
