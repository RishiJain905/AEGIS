import type { AfterActionReportV1, ReportVersionV1 } from '@aegis/contracts-ts';
import { afterActionReportSchema, parseContract, reportVersionSchema } from '@aegis/contracts-ts';

const SYNTHETIC_RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';
const SYNTHETIC_INCIDENT_ID = 'incident:inc_synthetic_001';

export const syntheticAfterActionReport: AfterActionReportV1 = parseContract(afterActionReportSchema, {
  schemaVersion: 1,
  id: 'aar_01ARZ3NDEKTSV4RRFFQ69G5FBW',
  runId: SYNTHETIC_RUN_ID,
  incidentId: SYNTHETIC_INCIDENT_ID,
  versionNumber: 1,
  title: 'Operation Silent Relay — After-action report',
  executiveSummary:
    'Deterministic after-action report summarizing WATCHTOWER triage, TRACE evidence collection, ORACLE hypotheses, BASTION proposals, and WARDEN policy outcomes.',
  chronologySummary:
    'Timeline synthesized from persisted domain events sequences 1–42 with investigation artifact cross-links.',
  claims: [
    {
      schemaVersion: 1,
      claimId: 'claim_001',
      category: 'observed_fact',
      text: 'Repeated authentication failures were observed on the logistics workstation asset.',
      confidence: 0.91,
      citations: [
        {
          schemaVersion: 1,
          kind: 'event',
          referenceId: 'evt_01ARZ3NDEKTSV4RRFFQ69G5FAW',
          label: 'Authentication failure telemetry',
          sequence: 12,
        },
      ],
      grounded: true,
    },
    {
      schemaVersion: 1,
      claimId: 'claim_002',
      category: 'investigation_evidence',
      text: 'TRACE attached authentication failure evidence with visible provenance.',
      citations: [
        {
          schemaVersion: 1,
          kind: 'evidence',
          referenceId: 'evidence:evt_auth_fail_001',
          label: 'Authentication failure evidence',
        },
      ],
      grounded: true,
    },
    {
      schemaVersion: 1,
      claimId: 'claim_003',
      category: 'oracle_hypothesis',
      text: 'ORACLE proposed credential misuse competing with benign admin activity.',
      confidence: 0.74,
      uncertainty: 'Competing hypotheses remain active.',
      citations: [
        {
          schemaVersion: 1,
          kind: 'hypothesis',
          referenceId: 'hyp_01ARZ3NDEKTSV4RRFFQ69G5FBW',
          label: 'Credential misuse',
        },
      ],
      grounded: true,
    },
    {
      schemaVersion: 1,
      claimId: 'claim_004',
      category: 'bastion_proposal',
      text: 'BASTION proposed increased monitoring on the logistics API service.',
      citations: [
        {
          schemaVersion: 1,
          kind: 'proposal',
          referenceId: 'prp_01ARZ3NDEKTSV4RRFFQ69G5FB9',
          label: 'Increase monitoring proposal',
        },
      ],
      grounded: true,
    },
    {
      schemaVersion: 1,
      claimId: 'claim_005',
      category: 'warden_policy_decision',
      text: 'WARDEN required human approval for the operational isolation proposal.',
      citations: [
        {
          schemaVersion: 1,
          kind: 'policy_decision',
          referenceId: 'pdc_01ARZ3NDEKTSV4RRFFQ69G5FBA',
          label: 'approval_required',
        },
      ],
      grounded: true,
    },
    {
      schemaVersion: 1,
      claimId: 'claim_006',
      category: 'agent_inference',
      text: 'Inference suggests staged access using valid credentials before API abuse.',
      confidence: 0.63,
      uncertainty: 'Inference only; not an observed fact.',
      citations: [],
      grounded: true,
    },
    {
      schemaVersion: 1,
      claimId: 'claim_007',
      category: 'unsupported',
      text: 'Rejected narrative claim referenced non-existent evidence.',
      citations: [],
      grounded: false,
      rejectionReason: 'Hallucinated evidence reference rejected during grounding validation.',
    },
  ],
  timeline: [
    {
      schemaVersion: 1,
      sequence: 1,
      eventId: 'evt_01ARZ3NDEKTSV4RRFFQ69G5FAW',
      eventType: 'sim.run.started',
      label: 'Run started',
      timestamp: '2026-06-30T02:00:00.000Z',
      status: 'normal',
      relatedEvidenceIds: [],
      relatedHypothesisIds: [],
    },
    {
      schemaVersion: 1,
      sequence: 12,
      eventId: 'evt_01ARZ3NDEKTSV4RRFFQ69G5FB0',
      eventType: 'telemetry.authentication.failed',
      label: 'Authentication failed on asset:device-workstation-01',
      timestamp: '2026-06-30T02:04:10.000Z',
      status: 'suspicious',
      relatedEvidenceIds: ['evidence:evt_auth_fail_001'],
      relatedHypothesisIds: [],
    },
    {
      schemaVersion: 1,
      sequence: 40,
      eventId: 'evt_01ARZ3NDEKTSV4RRFFQ69G5FC0',
      eventType: 'report.generation.completed',
      label: 'After-action report generation completed',
      timestamp: '2026-06-30T02:30:00.000Z',
      status: 'normal',
      relatedEvidenceIds: [],
      relatedHypothesisIds: [],
    },
  ],
  lessons: [
    'Preserve contradictory hypotheses during after-action review.',
    'Policy-gated proposals require explicit human approval before execution.',
  ],
  contradictions: ['Competing ORACLE hypotheses disagree on whether admin activity is benign.'],
  uncertainties: ['Credential misuse confidence remains below verification threshold.'],
  source: {
    schemaVersion: 1,
    runId: SYNTHETIC_RUN_ID,
    incidentId: SYNTHETIC_INCIDENT_ID,
    sourceSequenceFrom: 1,
    sourceSequenceTo: 42,
    eventIds: ['evt_01ARZ3NDEKTSV4RRFFQ69G5FAW'],
    evidenceIds: ['evidence:evt_auth_fail_001'],
    hypothesisIds: ['hyp_01ARZ3NDEKTSV4RRFFQ69G5FBW'],
    proposalIds: ['prp_01ARZ3NDEKTSV4RRFFQ69G5FB9'],
    policyDecisionIds: ['pdc_01ARZ3NDEKTSV4RRFFQ69G5FBA'],
    affectedAssetIds: ['asset:device-workstation-01'],
    alertIds: ['alert:alt_synthetic_001'],
    agentSessionIds: ['agent-session:ags_scribe_001'],
    timeline: [],
    investigationSummary: {
      incidentTitle: 'Operation Silent Relay — After-action report',
      incidentState: 'approval_pending',
    },
  },
  groundingFallback: false,
  narrativeProviderId: 'mock',
  narrativePromptVersion: 'phase23-scribe-v1',
  sessionId: 'agent-session:ags_scribe_001',
  taskId: 'atk_01ARZ3NDEKTSV4RRFFQ69G5FBD',
  checksum: 'a'.repeat(64),
  createdAt: '2026-06-30T02:30:00.000Z',
});

export const syntheticReportVersions: ReportVersionV1[] = [
  parseContract(reportVersionSchema, {
    schemaVersion: 1,
    id: 'rpv_01ARZ3NDEKTSV4RRFFQ69G5FBE',
    runId: SYNTHETIC_RUN_ID,
    incidentId: SYNTHETIC_INCIDENT_ID,
    versionNumber: 1,
    reportId: syntheticAfterActionReport.id,
    status: 'completed',
    sourceSequenceFrom: 1,
    sourceSequenceTo: 42,
    providerId: 'mock',
    promptVersion: 'phase23-scribe-v1',
    sessionId: 'agent-session:ags_scribe_001',
    taskId: 'atk_01ARZ3NDEKTSV4RRFFQ69G5FBD',
    checksum: syntheticAfterActionReport.checksum,
    groundingFallback: false,
    createdAt: '2026-06-30T02:30:00.000Z',
  }),
];

export function getAfterActionReportFixture(runId: string): AfterActionReportV1 | null {
  if (runId === SYNTHETIC_RUN_ID || runId.includes('synthetic')) {
    return syntheticAfterActionReport;
  }
  return null;
}

export function getReportVersionsFixture(runId: string): ReportVersionV1[] {
  if (runId === SYNTHETIC_RUN_ID || runId.includes('synthetic')) {
    return syntheticReportVersions;
  }
  return [];
}
