import { describe, expect, it } from 'vitest';

import type { AlertV1, IncidentV1, InvestigationDetailV1, RunV1 } from '@aegis/contracts-ts';

import {
  buildAgentRoster,
  buildIncidentQueue,
  buildProposalViews,
  buildTriageTimeline,
  formatRelativeAge,
  getIncidentStatePresentation,
  maxSeverity,
  summarizeQueue,
  type RunIncidentBundle,
} from './incident-model';

function alert(overrides: Partial<AlertV1>): AlertV1 {
  return {
    schemaVersion: 1,
    id: 'alert:alt_1',
    runId: 'run_1',
    title: 'Test alert',
    severity: 'medium',
    sourceEventId: 'evt_1',
    assetId: 'asset:svc-x',
    createdAt: '2026-06-30T02:00:00.000Z',
    ...overrides,
  } as AlertV1;
}

function incident(overrides: Partial<IncidentV1>): IncidentV1 {
  return {
    schemaVersion: 1,
    id: 'incident:inc_1',
    runId: 'run_1',
    title: 'Test incident',
    state: 'investigating',
    alertIds: ['alert:alt_1'],
    createdAt: '2026-06-30T02:00:01.000Z',
    updatedAt: '2026-06-30T02:05:00.000Z',
    revision: 1,
    ...overrides,
  } as IncidentV1;
}

const run: RunV1 = {
  schemaVersion: 1,
  id: 'run_1',
  scenarioVersionId: 'scenario-version:v1',
  seed: 1,
  status: 'running',
  startedAt: '2026-06-30T02:00:00.000Z',
  simTime: '2026-06-30T02:00:00.000Z',
  revision: 1,
} as RunV1;

describe('maxSeverity', () => {
  it('returns the highest severity among alerts', () => {
    expect(
      maxSeverity([
        alert({ severity: 'low' }),
        alert({ severity: 'critical' }),
        alert({ severity: 'high' }),
      ]),
    ).toBe('critical');
  });

  it('defaults to info for an empty alert list', () => {
    expect(maxSeverity([])).toBe('info');
  });
});

describe('getIncidentStatePresentation', () => {
  it('marks resolved and closed as resolved phase', () => {
    expect(getIncidentStatePresentation('resolved').isResolved).toBe(true);
    expect(getIncidentStatePresentation('closed').isResolved).toBe(true);
  });

  it('keeps active states unresolved', () => {
    expect(getIncidentStatePresentation('approval_pending').isResolved).toBe(false);
    expect(getIncidentStatePresentation('approval_pending').phase).toBe('investigating');
  });
});

describe('buildIncidentQueue', () => {
  it('sorts unresolved before resolved, then by severity', () => {
    const bundles: RunIncidentBundle[] = [
      {
        run,
        alerts: [
          alert({ id: 'alert:low', severity: 'low' }),
          alert({ id: 'alert:crit', severity: 'critical' }),
        ],
        incidents: [
          incident({
            id: 'incident:resolved',
            state: 'resolved',
            alertIds: ['alert:crit'],
          }),
          incident({
            id: 'incident:low',
            state: 'open',
            alertIds: ['alert:low'],
          }),
          incident({
            id: 'incident:crit',
            state: 'open',
            alertIds: ['alert:crit'],
          }),
        ],
      },
    ];

    const rows = buildIncidentQueue(bundles);

    expect(rows.map((r) => r.incident.id)).toEqual([
      'incident:crit',
      'incident:low',
      'incident:resolved',
    ]);
    expect(rows[0]?.severity).toBe('critical');
  });

  it('summarizes active, resolved, and high-severity counts', () => {
    const rows = buildIncidentQueue([
      {
        run,
        alerts: [alert({ id: 'alert:crit', severity: 'critical' })],
        incidents: [
          incident({
            id: 'incident:a',
            state: 'open',
            alertIds: ['alert:crit'],
          }),
          incident({
            id: 'incident:b',
            state: 'resolved',
            alertIds: ['alert:crit'],
          }),
        ],
      },
    ]);
    const summary = summarizeQueue(rows);
    expect(summary).toEqual({
      total: 2,
      active: 1,
      resolved: 1,
      highSeverity: 2,
    });
  });
});

const investigation: InvestigationDetailV1 = {
  schemaVersion: 4,
  incidentId: 'incident:inc_1',
  runId: 'run_1',
  triageResults: [
    {
      schemaVersion: 1,
      id: 'wtri_1',
      incidentId: 'incident:inc_1',
      runId: 'run_1',
      sessionId: 'agent-session:ags_w',
      taskId: 'atk_w',
      alertSummaries: [],
      groupedAlertIds: [],
      separatedAlertIds: [],
      correlationDecisions: [],
      escalation: 'investigate',
      escalationRationale: 'Escalate for bounded expansion.',
      confidence: 0.8,
      evidenceIds: [],
      idempotencyKey: 'k',
      createdAt: '2026-06-30T02:01:00.000Z',
    },
  ],
  plans: [],
  evidenceAttachments: [],
  notes: [],
  candidateAssets: [],
  overlays: [],
  hypotheses: [],
  hypothesisRevisions: [],
  hypothesisComparisons: [],
  verificationRequests: [],
  proposals: [
    {
      schemaVersion: 1,
      id: 'prp_1',
      incidentId: 'incident:inc_1',
      agentSessionId: 'agent-session:ags_b',
      actionClass: 'class_2',
      targetAssetId: 'asset:svc-x',
      command: 'isolate',
      status: 'pending',
      rationale: 'Contain suspected abuse.',
      revision: 1,
      createdAt: '2026-06-30T02:09:00.000Z',
    },
  ],
  proposalRevisions: [],
  policyDecisions: [
    {
      schemaVersion: 1,
      id: 'pdc_1',
      proposalId: 'prp_1',
      proposalRevisionId: 'prv_1',
      incidentId: 'incident:inc_1',
      sessionId: 'agent-session:ags_wd',
      taskId: 'atk_wd',
      outcome: 'approval_required',
      reasonCodes: ['approval_required_operational'],
      approvalRequirement: {
        schemaVersion: 1,
        required: true,
        approverRoles: ['incident_commander'],
        rationale: 'Requires approval.',
      },
      policyInput: {
        schemaVersion: 1,
        proposalId: 'prp_1',
        proposalRevisionId: 'prv_1',
        proposalRevisionNumber: 1,
        currentRevisionId: 'prv_1',
        actionClass: 'class_2',
        scenarioCommand: 'isolate',
        agentRole: 'BASTION',
        targetAssetId: 'asset:svc-x',
        assetCriticality: 0.8,
        reversibility: 'Reversible.',
        incidentState: 'containment_proposed',
        scenarioRestricted: true,
      },
      explanationProse: 'Needs human approval.',
      evaluatedAt: '2026-06-30T02:09:30.000Z',
    },
  ],
  approvals: [],
  executedActions: [],
} as InvestigationDetailV1;

describe('buildTriageTimeline', () => {
  it('assembles a chronological narrative from alert to proposal', () => {
    const events = buildTriageTimeline(
      incident({ state: 'approval_pending' }),
      [alert({ id: 'alert:alt_1', severity: 'high' })],
      investigation,
    );
    const kinds = events.map((e) => e.kind);
    expect(kinds[0]).toBe('alert');
    expect(kinds).toContain('incident_opened');
    expect(kinds).toContain('triage');
    expect(kinds).toContain('proposal');
    expect(kinds).toContain('policy');
    // Sorted ascending by timestamp.
    const times = events.map((e) => e.timestamp);
    expect([...times].sort()).toEqual(times);
  });

  it('still produces the alert/open spine without investigation detail', () => {
    const events = buildTriageTimeline(incident({}), [alert({})], null);
    expect(events.map((e) => e.kind)).toEqual(['alert', 'incident_opened']);
  });
});

describe('buildAgentRoster', () => {
  it('marks roles active based on persisted artifacts', () => {
    const roster = buildAgentRoster(investigation);
    const byRole = Object.fromEntries(roster.map((r) => [r.role, r.present]));
    expect(byRole.WATCHTOWER).toBe(true);
    expect(byRole.BASTION).toBe(true);
    expect(byRole.WARDEN).toBe(true);
    expect(byRole.ORACLE).toBe(false);
  });

  it('treats a missing investigation as an idle roster', () => {
    expect(buildAgentRoster(null).every((r) => !r.present)).toBe(true);
  });
});

describe('buildProposalViews', () => {
  it('joins proposals to their policy decision and pending state', () => {
    const views = buildProposalViews(investigation);
    expect(views).toHaveLength(1);
    expect(views[0]?.policy?.outcome).toBe('approval_required');
    expect(views[0]?.approval).toBeNull();
    expect(views[0]?.proposal.status).toBe('pending');
  });
});

describe('formatRelativeAge', () => {
  const now = Date.parse('2026-06-30T05:00:00.000Z');
  it('formats hours and days', () => {
    expect(formatRelativeAge('2026-06-30T02:00:00.000Z', now)).toBe('3h');
    expect(formatRelativeAge('2026-06-28T05:00:00.000Z', now)).toBe('2d');
  });
  it('handles invalid input', () => {
    expect(formatRelativeAge('not-a-date', now)).toBe('unknown');
  });
});
