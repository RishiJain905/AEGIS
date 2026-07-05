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

const ORACLE_SESSION_ID = 'agent-session:ags_oracle_001';
const ORACLE_TASK_ID = 'atk_01ARZ3NDEKTSV4RRFFQ69G5FB1';
const HYPOTHESIS_ONE_ID = 'hyp_01ARZ3NDEKTSV4RRFFQ69G5FB2';
const HYPOTHESIS_TWO_ID = 'hyp_01ARZ3NDEKTSV4RRFFQ69G5FB3';
const REVISION_ONE_ID = 'hrev_01ARZ3NDEKTSV4RRFFQ69G5FB4';
const REVISION_TWO_ID = 'hrev_01ARZ3NDEKTSV4RRFFQ69G5FB5';
const REVISION_THREE_ID = 'hrev_01ARZ3NDEKTSV4RRFFQ69G5FB6';

const syntheticInvestigationDetail = parseContract(investigationDetailSchema, {
  schemaVersion: 2,
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
  hypotheses: [
    {
      schemaVersion: 2,
      id: HYPOTHESIS_ONE_ID,
      incidentId: SYNTHETIC_INCIDENT_ID,
      currentRevisionId: REVISION_ONE_ID,
      family: 'credential_abuse',
      status: 'active',
      createdAt: '2026-06-30T02:07:00.000Z',
    },
    {
      schemaVersion: 2,
      id: HYPOTHESIS_TWO_ID,
      incidentId: SYNTHETIC_INCIDENT_ID,
      currentRevisionId: REVISION_THREE_ID,
      family: 'benign_anomaly',
      status: 'active',
      createdAt: '2026-06-30T02:07:10.000Z',
    },
  ],
  hypothesisRevisions: [
    {
      schemaVersion: 1,
      id: REVISION_ONE_ID,
      hypothesisId: HYPOTHESIS_ONE_ID,
      incidentId: SYNTHETIC_INCIDENT_ID,
      sessionId: ORACLE_SESSION_ID,
      taskId: ORACLE_TASK_ID,
      revisionNumber: 1,
      claim: 'Compromised gateway credentials enabled relay authentication bursts.',
      family: 'credential_abuse',
      confidence: {
        schemaVersion: 1,
        point: 0.74,
        min: 0.6,
        max: 0.84,
        coverage: 0.68,
        contradictionPenalty: 0.14,
        explanation: 'Grounded in authentication alert and gateway evidence attachments.',
      },
      claims: [
        {
          schemaVersion: 1,
          kind: 'observed_fact',
          text: 'Authentication burst exceeded baseline on API gateway.',
          evidenceIds: ['evidence:evd_synthetic_001'],
          attachmentIds: ['eatt_synthetic_001'],
          isAssumption: false,
        },
      ],
      assumptions: [],
      supportingEvidenceIds: ['evidence:evd_synthetic_001'],
      contradictingEvidenceIds: [],
      unknowns: ['Whether MFA bypass occurred'],
      predictions: ['Additional relay hops if credential reuse continues'],
      contradictionLinks: [],
      status: 'active',
      rationale: 'Primary competing explanation for gateway authentication anomaly.',
      createdAt: '2026-06-30T02:07:00.000Z',
    },
    {
      schemaVersion: 1,
      id: REVISION_TWO_ID,
      hypothesisId: HYPOTHESIS_TWO_ID,
      incidentId: SYNTHETIC_INCIDENT_ID,
      sessionId: ORACLE_SESSION_ID,
      taskId: ORACLE_TASK_ID,
      revisionNumber: 1,
      claim: 'Notification fan-out may explain elevated gateway traffic.',
      family: 'benign_anomaly',
      confidence: {
        schemaVersion: 1,
        point: 0.36,
        min: 0.22,
        max: 0.5,
        coverage: 0.28,
        contradictionPenalty: 0.32,
        explanation: 'Lower coverage with contradictory notification timing evidence.',
      },
      claims: [
        {
          schemaVersion: 1,
          kind: 'agent_inference',
          text: 'Maintenance overlap is possible but unverified.',
          evidenceIds: [],
          attachmentIds: [],
          isAssumption: true,
        },
      ],
      assumptions: ['Scheduled maintenance window overlap'],
      supportingEvidenceIds: [],
      contradictingEvidenceIds: ['evidence:evd_synthetic_001'],
      unknowns: ['Maintenance schedule confirmation'],
      predictions: ['Traffic normalization without containment'],
      contradictionLinks: [
        {
          schemaVersion: 1,
          supportingEvidenceIds: [],
          contradictingEvidenceIds: ['evidence:evd_synthetic_001'],
          supportingAttachmentIds: [],
          contradictingAttachmentIds: ['eatt_synthetic_002'],
          rationale: 'Normal notification volume contradicts lateral movement theory.',
        },
      ],
      status: 'superseded',
      rationale: 'Initial benign explanation before contradiction review.',
      createdAt: '2026-06-30T02:07:05.000Z',
    },
    {
      schemaVersion: 1,
      id: REVISION_THREE_ID,
      hypothesisId: HYPOTHESIS_TWO_ID,
      incidentId: SYNTHETIC_INCIDENT_ID,
      sessionId: ORACLE_SESSION_ID,
      taskId: ORACLE_TASK_ID,
      revisionNumber: 2,
      claim: 'Benign maintenance remains possible but weakened by contradictory timing.',
      family: 'benign_anomaly',
      confidence: {
        schemaVersion: 1,
        point: 0.29,
        min: 0.18,
        max: 0.42,
        coverage: 0.22,
        contradictionPenalty: 0.38,
        explanation: 'Revised downward after contradictory notification evidence.',
      },
      claims: [
        {
          schemaVersion: 1,
          kind: 'unsupported_claim',
          text: 'Maintenance was definitely scheduled at incident time.',
          evidenceIds: [],
          attachmentIds: [],
          isAssumption: false,
        },
      ],
      assumptions: ['Maintenance schedule not yet confirmed'],
      supportingEvidenceIds: [],
      contradictingEvidenceIds: ['evidence:evd_synthetic_001'],
      unknowns: ['Maintenance schedule confirmation'],
      predictions: ['Traffic normalization if maintenance confirmed'],
      contradictionLinks: [
        {
          schemaVersion: 1,
          supportingEvidenceIds: [],
          contradictingEvidenceIds: ['evidence:evd_synthetic_001'],
          supportingAttachmentIds: [],
          contradictingAttachmentIds: ['eatt_synthetic_002'],
          rationale: 'Contradictory notification evidence remains visible after revision.',
        },
      ],
      status: 'active',
      rationale: 'Revised hypothesis after new contradictory evidence arrived.',
      createdAt: '2026-06-30T02:08:00.000Z',
    },
  ],
  hypothesisComparisons: [
    {
      schemaVersion: 1,
      id: 'hcmp_synthetic_001',
      incidentId: SYNTHETIC_INCIDENT_ID,
      sessionId: ORACLE_SESSION_ID,
      taskId: ORACLE_TASK_ID,
      entries: [
        {
          hypothesisId: HYPOTHESIS_ONE_ID,
          revisionId: REVISION_ONE_ID,
          sharedEvidenceIds: [],
          uniqueEvidenceIds: ['evidence:evd_synthetic_001'],
          contradictingEvidenceIds: [],
          confidencePoint: 0.74,
        },
        {
          hypothesisId: HYPOTHESIS_TWO_ID,
          revisionId: REVISION_THREE_ID,
          sharedEvidenceIds: [],
          uniqueEvidenceIds: [],
          contradictingEvidenceIds: ['evidence:evd_synthetic_001'],
          confidencePoint: 0.29,
        },
      ],
      summary:
        'Credential abuse has stronger grounded support; benign maintenance remains visible but contradicted.',
      matrix: {
        sharedEvidence: [],
        competingFamilies: ['credential_abuse', 'benign_anomaly'],
      },
      createdAt: '2026-06-30T02:07:30.000Z',
    },
  ],
  verificationRequests: [
    {
      schemaVersion: 1,
      id: 'vreq_synthetic_001',
      incidentId: SYNTHETIC_INCIDENT_ID,
      hypothesisId: HYPOTHESIS_ONE_ID,
      sessionId: ORACLE_SESSION_ID,
      taskId: ORACLE_TASK_ID,
      purpose: 'Confirm credential reuse across relay hops',
      targetEvidenceIds: ['evidence:evd_synthetic_001'],
      idempotencyKey: 'oracle:synthetic:verify:001',
      createdAt: '2026-06-30T02:07:40.000Z',
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

const oracleSessionDetail = parseContract(agentSessionDetailSchema, {
  schemaVersion: 1,
  session: {
    schemaVersion: 1,
    id: ORACLE_SESSION_ID,
    incidentId: SYNTHETIC_INCIDENT_ID,
    role: 'ORACLE',
    state: 'completed',
    traceId: 'trc_01ARZ3NDEKTSV4RRFFQ69G5FAV',
    createdAt: '2026-06-30T02:06:30.000Z',
    updatedAt: '2026-06-30T02:08:10.000Z',
  },
  tasks: [
    {
      schemaVersion: 1,
      id: ORACLE_TASK_ID,
      sessionId: ORACLE_SESSION_ID,
      incidentId: SYNTHETIC_INCIDENT_ID,
      status: 'completed',
      attempt: 1,
      idempotencyKey: 'oracle:synthetic:001',
      traceId: 'trc_01ARZ3NDEKTSV4RRFFQ69G5FAV',
      providerId: 'mock',
      createdAt: '2026-06-30T02:06:35.000Z',
      updatedAt: '2026-06-30T02:08:00.000Z',
      startedAt: '2026-06-30T02:06:40.000Z',
      completedAt: '2026-06-30T02:08:00.000Z',
    },
  ],
  transitions: [
    {
      schemaVersion: 1,
      id: 'transition:oracle_001',
      sessionId: ORACLE_SESSION_ID,
      taskId: ORACLE_TASK_ID,
      fromState: 'queued',
      toState: 'hypothesizing',
      reason: 'model_step_received',
      createdAt: '2026-06-30T02:07:00.000Z',
    },
    {
      schemaVersion: 1,
      id: 'transition:oracle_002',
      sessionId: ORACLE_SESSION_ID,
      taskId: ORACLE_TASK_ID,
      fromState: 'hypothesizing',
      toState: 'verifying',
      reason: 'grounding_validated',
      createdAt: '2026-06-30T02:07:20.000Z',
    },
    {
      schemaVersion: 1,
      id: 'transition:oracle_003',
      sessionId: ORACLE_SESSION_ID,
      taskId: ORACLE_TASK_ID,
      fromState: 'verifying',
      toState: 'completed',
      reason: 'Hypothesis artifacts persisted',
      createdAt: '2026-06-30T02:08:00.000Z',
    },
  ],
  toolInvocations: [
    {
      schemaVersion: 1,
      id: 'tiv_01ARZ3NDEKTSV4RRFFQ69G5FB3',
      taskId: ORACLE_TASK_ID,
      sessionId: ORACLE_SESSION_ID,
      toolName: 'list_existing_evidence',
      toolClass: 'read',
      status: 'success',
      durationMs: 12,
      createdAt: '2026-06-30T02:07:05.000Z',
    },
    {
      schemaVersion: 1,
      id: 'tiv_01ARZ3NDEKTSV4RRFFQ69G5FB4',
      taskId: ORACLE_TASK_ID,
      sessionId: ORACLE_SESSION_ID,
      toolName: 'list_hypotheses',
      toolClass: 'read',
      status: 'success',
      durationMs: 9,
      createdAt: '2026-06-30T02:07:10.000Z',
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
  [ORACLE_SESSION_ID]: oracleSessionDetail,
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
  for (const revision of detail.hypothesisRevisions) {
    sessionIds.add(revision.sessionId);
  }
  return [...sessionIds];
}
