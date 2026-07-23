import { describe, expect, it } from 'vitest';

import type { RunScoreV1 } from '@aegis/contracts-ts';

import {
  assembleAdversaryDossier,
  formatDwell,
  humanizeAssetId,
  humanizeCauseId,
  intervalUnionSeconds,
  secondsBetween,
  type DossierEvent,
} from './assemble-dossier';

/* ------------------------------------------------------------------ */
/* Fixture — a credentials-branch run                                  */
/* ------------------------------------------------------------------ */

const T0 = Date.parse('2026-01-01T00:00:00.000Z');

function at(minutes: number): string {
  return new Date(T0 + minutes * 60_000).toISOString();
}

function event(
  sequence: number,
  type: string,
  minutes: number,
  payload: Record<string, unknown>,
  overrides: Partial<DossierEvent> = {},
): DossierEvent {
  return {
    sequence,
    type,
    simTime: at(minutes),
    actorType: 'system',
    actorId: 'asset:simulation-engine',
    subjectType: 'asset',
    subjectId: 'asset:simulation-engine',
    payload,
    ...overrides,
  };
}

const CREDENTIALS_ASSET = 'asset:identity-svc-logistics-bot';
const CONDITION = 'hidden-cause-compromised-credentials';

function credentialsRun(): DossierEvent[] {
  return [
    event(1, 'sim.run.started', 0, {}),
    event(2, 'sim.branch.selected', 0, {
      branchGroup: 'root-cause',
      branchId: 'branch-cause-credentials',
    }),
    // covert beats
    event(3, 'sim.hidden_condition.triggered', 5, { conditionId: CONDITION }),
    event(4, 'sim.asset.status_changed', 15, { assetId: CREDENTIALS_ASSET, status: 'compromised' }),
    // detection surfaces the asset at +21m (dwell 6m), reveal fires at +25m (dwell 20m)
    event(5, 'alert.created', 21, {
      assetId: CREDENTIALS_ASSET,
      title: 'Anomalous authentication',
    }),
    event(7, 'incident.created', 22, { title: 'Suspicious logistics bot' }),
    event(6, 'sim.hidden_condition.revealed', 25, { conditionId: CONDITION }),
    // defender response
    event(
      11,
      'run.roe_changed',
      12,
      { newRoe: 'forward-deployed' },
      {
        actorType: 'operator',
        actorId: 'user:op1',
        subjectType: 'operator',
        subjectId: 'user:op1',
      },
    ),
    event(
      8,
      'operator.action.proposed',
      30,
      { scenarioCommand: 'isolate_asset', targetAssetId: CREDENTIALS_ASSET, initiator: 'operator' },
      { actorType: 'operator', actorId: 'user:op1' },
    ),
    event(
      9,
      'action.executed',
      31,
      { proposalId: 'prp_1', incidentId: 'inc_1' },
      { actorType: 'operator', actorId: 'user:op1' },
    ),
    // containment world-note (system actor, benign status) — belongs to neither lane
    event(10, 'sim.asset.status_changed', 32, { assetId: CREDENTIALS_ASSET, status: 'contained' }),
    // noise the dossier must ignore, including a type the TS registry does not enumerate
    event(13, 'telemetry.api.request', 8, { assetId: 'asset:svc-logistics-api' }),
    event(14, 'autonomy.task.enqueued', 20, { role: 'WATCHTOWER', initiator: 'autonomy' }),
    event(12, 'sim.run.stopped', 40, {}),
  ];
}

function scoreFixture(overrides: Partial<RunScoreV1> = {}): RunScoreV1 {
  return {
    schemaVersion: 1,
    scoreId: 'score_1',
    runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
    overallScore: 82,
    maxScore: 100,
    grade: 'B',
    passed: true,
    components: [
      {
        criterionId: 'criterion-detection-speed',
        label: 'Detection speed',
        weight: 0.15,
        rawScore: 0.8,
        weightedContribution: 12,
        explanations: [],
      },
    ],
    provenance: {
      scenarioVersion: 'v1',
      rubricVersion: 'v1',
      gradingEngineVersion: 'v1',
      inputEventSequenceFrom: 1,
      inputEventSequenceTo: 40,
      integrityChecksum: 'abc',
      fingerprint: 'def',
      inputChecksum: 'ghi',
      calculatedAt: at(41),
    },
    decisionReviews: [],
    missedEvidence: [],
    validAlternatives: [],
    coachingAuthoritative: false,
    hiddenCauseId: CONDITION,
    hiddenCauseLabel: 'Compromised service account credentials',
    hiddenCauseRevealed: true,
    ...overrides,
  } as RunScoreV1;
}

/* ------------------------------------------------------------------ */
/* Pure helpers                                                        */
/* ------------------------------------------------------------------ */

describe('dossier helpers', () => {
  it('humanizes asset ids and cause ids', () => {
    expect(humanizeAssetId('asset:identity-svc-logistics-bot')).toBe('Identity Svc Logistics Bot');
    expect(humanizeCauseId('branch-cause-credentials')).toBe('Credentials');
    expect(humanizeCauseId('hidden-cause-compromised-credentials')).toBe('Compromised credentials');
  });

  it('computes seconds between sim times, clamped at zero', () => {
    expect(secondsBetween(at(5), at(11))).toBe(360);
    expect(secondsBetween(at(11), at(5))).toBe(0);
  });

  it('formats dwell durations', () => {
    expect(formatDwell(360)).toBe('6m 00s');
    expect(formatDwell(45)).toBe('45s');
    expect(formatDwell(3720)).toBe('1h 02m');
    expect(formatDwell(0)).toBe('0s');
  });

  it('unions overlapping undetected intervals without double counting', () => {
    // [0,20] and [10,15] overlap -> 20 minutes total, not 25
    const total = intervalUnionSeconds([
      [0, 20 * 60_000],
      [10 * 60_000, 15 * 60_000],
    ]);
    expect(total).toBe(1200);
  });
});

/* ------------------------------------------------------------------ */
/* Assembly                                                            */
/* ------------------------------------------------------------------ */

describe('assembleAdversaryDossier', () => {
  const dossier = assembleAdversaryDossier({
    runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
    events: credentialsRun(),
    score: scoreFixture(),
    assetLabels: { [CREDENTIALS_ASSET]: 'Logistics Service Bot' },
  });

  it('names the root-cause branch that actually ran', () => {
    expect(dossier.rootCauseBranchId).toBe('branch-cause-credentials');
    expect(dossier.rootCauseLabel).toBe('Compromised service account credentials');
    expect(dossier.rootCauseKnown).toBe(true);
  });

  it('attributes covert beats to the attacker lane and ignores unknown/noise events', () => {
    expect(dossier.attackerBeats.map((b) => b.kind)).toEqual([
      'condition_triggered',
      'asset_effect',
    ]);
    // telemetry.* and autonomy.task.enqueued (not in the TS registry) never become beats
    expect(dossier.attackerBeats).toHaveLength(2);
  });

  it('attributes alerts, incidents, operator actions, executions and RoE to the defender lane', () => {
    const kinds = dossier.defenderActions.map((d) => d.kind).sort();
    expect(kinds).toEqual(['alert', 'execution', 'incident', 'operator_action', 'roe_change']);
    // system-actor containment status change is neither lane (no double count with execution)
    expect(dossier.defenderActions).toHaveLength(5);
  });

  it('carries the operator initiator through from the payload', () => {
    const proposal = dossier.defenderActions.find((d) => d.kind === 'operator_action');
    expect(proposal?.initiator).toBe('operator');
    expect(proposal?.label).toContain('Logistics Service Bot');
  });

  it('computes per-beat undetected dwell from trigger to disclosure', () => {
    const triggered = dossier.attackerBeats.find((b) => b.kind === 'condition_triggered');
    const effect = dossier.attackerBeats.find((b) => b.kind === 'asset_effect');
    // condition triggered +5m, revealed +25m -> 20m dwell
    expect(triggered?.detected).toBe(true);
    expect(triggered?.dwellSeconds).toBe(20 * 60);
    // asset compromised +15m, first alert +21m -> 6m dwell
    expect(effect?.detected).toBe(true);
    expect(effect?.dwellSeconds).toBe(6 * 60);
  });

  it('places a detection crossing for every disclosed beat', () => {
    expect(dossier.crossings).toHaveLength(2);
    // the asset-effect crossing links to the alert that disclosed it
    const effect = dossier.attackerBeats.find((b) => b.kind === 'asset_effect');
    const crossing = dossier.crossings.find((c) => c.attackerBeatId === effect?.id);
    expect(crossing?.defenderActionId).toBe('def-5');
  });

  it('summarizes key moments and total undetected dwell as an interval union', () => {
    const km = dossier.keyMoments;
    expect(km.firstBreachSimTime).toBe(at(5));
    expect(km.firstDetectionSimTime).toBe(at(21)); // first alert precedes the reveal
    expect(km.timeToDetectionSeconds).toBe(16 * 60);
    expect(km.containmentSimTime).toBe(at(31));
    // union of [5m,25m] and [15m,21m] = 20 minutes
    expect(km.totalUndetectedDwellSeconds).toBe(20 * 60);
  });

  it('reports a contained breach outcome when revealed and containment executed', () => {
    expect(dossier.exfilOutcome.status).toBe('contained');
  });

  it('reports objectives outcome from the score', () => {
    expect(dossier.objectivesOutcome).toEqual({ passed: true, grade: 'B', overallPct: 82 });
  });

  it('produces a chronologically ordered linear timeline for screen readers', () => {
    const times = dossier.timeline.map((r) => Date.parse(r.simTime));
    const sorted = [...times].sort((a, b) => a - b);
    expect(times).toEqual(sorted);
    expect(dossier.timeline.some((r) => r.side === 'attacker')).toBe(true);
    expect(dossier.timeline.some((r) => r.side === 'defender')).toBe(true);
    expect(dossier.timeline.some((r) => r.side === 'crossing')).toBe(true);
  });
});

describe('assembleAdversaryDossier — never-detected campaign', () => {
  it('marks beats undetected and reports an undetected breach outcome', () => {
    const events: DossierEvent[] = [
      event(1, 'sim.run.started', 0, {}),
      event(2, 'sim.hidden_condition.triggered', 5, { conditionId: CONDITION }),
      event(3, 'sim.asset.status_changed', 15, {
        assetId: CREDENTIALS_ASSET,
        status: 'compromised',
      }),
      event(4, 'sim.run.stopped', 40, {}),
    ];
    const dossier = assembleAdversaryDossier({
      runId: 'run_x',
      events,
      score: scoreFixture({ hiddenCauseRevealed: false }),
    });
    expect(dossier.attackerBeats.every((b) => !b.detected)).toBe(true);
    // both beats dwell until run end (+40m); triggered from +5m = 35m, effect from +15m = 25m
    const triggered = dossier.attackerBeats.find((b) => b.kind === 'condition_triggered');
    expect(triggered?.dwellSeconds).toBe(35 * 60);
    expect(dossier.crossings).toHaveLength(0);
    expect(dossier.exfilOutcome.status).toBe('undetected');
    expect(dossier.keyMoments.timeToDetectionSeconds).toBeUndefined();
  });
});
