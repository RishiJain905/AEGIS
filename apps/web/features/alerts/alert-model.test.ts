import type { AlertV1, IncidentV1 } from '@aegis/contracts-ts';
import { describe, expect, it } from 'vitest';

import {
  alertGroupKey,
  buildAlertCards,
  readAnomalyDetail,
  readReveals,
  readStatusTransitions,
  simClock,
  type AssetFacts,
} from './alert-model';

const ASSET = 'asset:svc-comms-gateway';

function alert(overrides: Partial<AlertV1> & { id: string }): AlertV1 {
  return {
    schemaVersion: 1,
    runId: 'run_x',
    title: 'Unseen source activity detected',
    severity: 'medium',
    sourceEventId: `evt-${overrides.id}`,
    assetId: ASSET,
    createdAt: '2026-01-01T00:00:24.000Z',
    confidence: 0.75,
    detectorId: 'first-seen',
    detectorVersion: '1.0.0',
    deduplicationKey: `${ASSET}:first-seen`,
    ...overrides,
  } as AlertV1;
}

function withEvidence(base: AlertV1, sequence: number, simTime: string): AlertV1 {
  return {
    ...base,
    evidence: {
      featureSchemaVersion: 1,
      featureValues: {},
      sourceEventIds: [base.sourceEventId],
      windowKey: `run_x:${ASSET}:1767225600`,
      sequenceStart: sequence,
      sequenceEnd: sequence,
      simTimeStart: simTime,
      simTimeEnd: simTime,
    },
  };
}

function incident(overrides: Partial<IncidentV1> & { id: string }): IncidentV1 {
  return {
    schemaVersion: 1,
    runId: 'run_x',
    title: 'Suspected credential abuse',
    state: 'investigating',
    alertIds: [],
    createdAt: '2026-01-01T00:01:00.000Z',
    updatedAt: '2026-01-01T00:01:00.000Z',
    revision: 1,
    ...overrides,
  } as IncidentV1;
}

const assets = new Map<string, AssetFacts>([
  [ASSET, { label: 'Communications Gateway', status: 'normal' }],
]);

describe('alertGroupKey', () => {
  it('prefers the detector dedup key and falls back to asset + title + detector', () => {
    expect(alertGroupKey(alert({ id: 'a1' }))).toBe(`${ASSET}:first-seen`);
    const undeduped = { ...alert({ id: 'a2' }), deduplicationKey: undefined };
    expect(alertGroupKey(undeduped)).toBe(`${ASSET}|Unseen source activity detected|first-seen`);
  });
});

describe('simClock', () => {
  it('reduces an ISO sim timestamp to its clock and passes anything else through', () => {
    expect(simClock('2026-01-01T00:02:30.000Z')).toBe('00:02:30');
    expect(simClock(null)).toBe('—');
  });
});

describe('buildAlertCards', () => {
  it('collapses exact duplicates into one card carrying the count and sequence range', () => {
    const cards = buildAlertCards({
      alerts: [
        withEvidence(alert({ id: 'a1' }), 14, '2026-01-01T00:00:24.000Z'),
        withEvidence(alert({ id: 'a2' }), 27, '2026-01-01T00:00:40.000Z'),
        withEvidence(alert({ id: 'a3' }), 72, '2026-01-01T00:01:30.000Z'),
      ],
      incidents: [],
      assets,
    });

    expect(cards).toHaveLength(1);
    expect(cards[0]?.count).toBe(3);
    expect(cards[0]?.firstSequence).toBe(14);
    expect(cards[0]?.lastSequence).toBe(72);
    expect(cards[0]?.assetLabel).toBe('Communications Gateway');
    expect(cards[0]?.whyItMatters).toContain('3 sightings on Communications Gateway');
  });

  it('names the asset by display label and keeps the raw id off the card copy', () => {
    const cards = buildAlertCards({
      alerts: [withEvidence(alert({ id: 'a1' }), 14, '2026-01-01T00:00:24.000Z')],
      incidents: [],
      assets,
    });
    expect(cards[0]?.assetLabel).toBe('Communications Gateway');
    expect(cards[0]?.whyItMatters).not.toContain('asset:');
  });

  it('falls back to the asset id when the graph has no node for it', () => {
    const cards = buildAlertCards({
      alerts: [alert({ id: 'a1' })],
      incidents: [],
      assets: new Map(),
    });
    expect(cards[0]?.assetLabel).toBe(ASSET);
    expect(cards[0]?.assetStatus).toBeNull();
  });

  it('marks a card escalated and links its incident', () => {
    const cards = buildAlertCards({
      alerts: [alert({ id: 'a1' })],
      incidents: [incident({ id: 'incident:inc_1', alertIds: ['a1'] })],
      assets,
    });
    expect(cards[0]?.lifecycle).toBe('escalated');
    expect(cards[0]?.incident).toEqual({
      id: 'incident:inc_1',
      title: 'Suspected credential abuse',
      state: 'investigating',
    });
    expect(cards[0]?.whyItMatters).toContain('Suspected credential abuse');
  });

  it('marks a card investigated once the operator has opened it', () => {
    const cards = buildAlertCards({
      alerts: [alert({ id: 'a1' })],
      incidents: [],
      assets,
      openedKeys: new Set([`${ASSET}:first-seen`]),
    });
    expect(cards[0]?.lifecycle).toBe('investigated');
  });

  it('marks a card investigated when the asset is already under investigation', () => {
    const cards = buildAlertCards({
      alerts: [alert({ id: 'a1' })],
      incidents: [],
      assets: new Map([
        [ASSET, { label: 'Communications Gateway', status: 'under_investigation' }],
      ]),
    });
    expect(cards[0]?.lifecycle).toBe('investigated');
  });

  it('marks the older card superseded when a different alert lands later on the same asset', () => {
    const cards = buildAlertCards({
      alerts: [
        withEvidence(alert({ id: 'a1' }), 14, '2026-01-01T00:00:24.000Z'),
        withEvidence(
          alert({
            id: 'b1',
            title: 'Authentication failure burst',
            deduplicationKey: `${ASSET}:auth-burst`,
          }),
          130,
          '2026-01-01T00:02:24.000Z',
        ),
      ],
      incidents: [],
      assets,
    });

    expect(cards[0]?.alert.id).toBe('b1');
    expect(cards[0]?.lifecycle).toBe('new');
    expect(cards[1]?.alert.id).toBe('a1');
    expect(cards[1]?.lifecycle).toBe('superseded');
  });

  it('attaches the status transition the alert preceded and leads with its consequence', () => {
    const cards = buildAlertCards({
      alerts: [withEvidence(alert({ id: 'a1' }), 14, '2026-01-01T00:00:24.000Z')],
      incidents: [],
      assets: new Map([[ASSET, { label: 'Communications Gateway', status: 'compromised' }]]),
      transitions: [
        {
          assetId: ASSET,
          status: 'compromised',
          sequence: 316,
          simTime: '2026-01-01T00:06:15.000Z',
        },
      ],
    });

    expect(cards[0]?.outcome).toEqual({
      status: 'compromised',
      sequence: 316,
      simTime: '2026-01-01T00:06:15.000Z',
    });
    expect(cards[0]?.whyItMatters).toBe(
      'Communications Gateway was confirmed compromised at 00:06:15. This alert saw it first.',
    );
  });

  it('ignores a status transition that happened before the alert fired', () => {
    const cards = buildAlertCards({
      alerts: [withEvidence(alert({ id: 'a1' }), 200, '2026-01-01T00:04:00.000Z')],
      incidents: [],
      assets,
      transitions: [
        {
          assetId: ASSET,
          status: 'compromised',
          sequence: 20,
          simTime: '2026-01-01T00:00:30.000Z',
        },
      ],
    });
    expect(cards[0]?.outcome).toBeNull();
  });

  it('keeps the detector rule text available but out of the plain-language line', () => {
    const cards = buildAlertCards({
      alerts: [
        {
          ...alert({ id: 'a1' }),
          explanation: {
            schemaVersion: 1,
            summary: 'A source never seen before contacted this asset.',
            condition: 'first_seen activity',
            featureName: 'first_seen',
            observed: 2,
            threshold: 2,
            comparison: 'first_seen activity 2 >= 2.0',
            windowKey: `run_x:${ASSET}:1767225600`,
            detectorType: 'deterministic',
          },
        } as AlertV1,
      ],
      incidents: [],
      assets,
    });
    expect(cards[0]?.detectorDetail).toBe('first_seen activity — first_seen activity 2 >= 2.0');
    expect(cards[0]?.whyItMatters).not.toContain('>=');
  });
});

describe('readStatusTransitions', () => {
  it('reads asset id and status out of the projector-authored label', () => {
    expect(
      readStatusTransitions([
        {
          eventType: 'sim.asset.status_changed',
          label: `Asset ${ASSET} → compromised`,
          sequence: 316,
          timestamp: '2026-01-01T00:06:15.000Z',
        },
        {
          eventType: 'telemetry.api.request',
          label: 'API request',
          sequence: 130,
          timestamp: '2026-01-01T00:02:24.000Z',
        },
      ]),
    ).toEqual([
      { assetId: ASSET, status: 'compromised', sequence: 316, simTime: '2026-01-01T00:06:15.000Z' },
    ]);
  });

  it('drops a status entry whose label no longer matches rather than guessing', () => {
    expect(
      readStatusTransitions([
        {
          eventType: 'sim.asset.status_changed',
          label: 'something else entirely',
          sequence: 5,
          timestamp: '2026-01-01T00:00:05.000Z',
        },
      ]),
    ).toEqual([]);
  });
});

describe('readReveals', () => {
  it('reports the revealed cause in operator language with the assets it moved', () => {
    const notes = readReveals(
      [
        {
          eventType: 'sim.hidden_condition.revealed',
          label: 'Underlying cause revealed: Vendor key reuse',
          sequence: 247,
          timestamp: '2026-01-01T00:05:00.000Z',
        },
        {
          eventType: 'sim.asset.status_changed',
          label: `Asset ${ASSET} → compromised`,
          sequence: 250,
          timestamp: '2026-01-01T00:05:00.000Z',
        },
      ],
      assets,
    );

    expect(notes).toHaveLength(1);
    expect(notes[0]?.cause).toBe('Vendor key reuse');
    expect(notes[0]?.assetLabels).toEqual(['Communications Gateway']);
    expect(notes[0]?.sequence).toBe(247);
  });

  it('leaves the asset list empty when nothing moved near the reveal', () => {
    const notes = readReveals(
      [
        {
          eventType: 'sim.hidden_condition.revealed',
          label: 'Underlying cause revealed: Vendor key reuse',
          sequence: 247,
          timestamp: '2026-01-01T00:05:00.000Z',
        },
        {
          eventType: 'sim.asset.status_changed',
          label: `Asset ${ASSET} → compromised`,
          sequence: 400,
          timestamp: '2026-01-01T00:08:00.000Z',
        },
      ],
      assets,
    );
    expect(notes[0]?.assetLabels).toEqual([]);
  });
});

describe('readAnomalyDetail', () => {
  it('returns null for a rule alert that carries no model account', () => {
    expect(readAnomalyDetail(alert({ id: 'a1' }))).toBeNull();
  });

  it('reads the model’s score, threshold, features and version', () => {
    const detail = readAnomalyDetail(
      alert({
        id: 'a1',
        anomalyExplanation: {
          summary: 'Authentication volume sits far outside baseline.',
          observedScore: 0.91,
          threshold: 0.7,
          topFeatures: ['auth_failures', 'distinct_sources'],
          modelVersionId: 'model:isoforest_v3',
        },
      } as Partial<AlertV1> & { id: string }),
    );

    expect(detail).toEqual({
      summary: 'Authentication volume sits far outside baseline.',
      observedScore: 0.91,
      threshold: 0.7,
      topFeatures: ['auth_failures', 'distinct_sources'],
      modelVersionId: 'model:isoforest_v3',
    });
  });

  it('degrades field by field when the model ships an unexpected payload', () => {
    // The contract types this as an open record, so a shape change must cost lines of the
    // disclosure rather than the whole card.
    const detail = readAnomalyDetail(
      alert({
        id: 'a1',
        confidence: 0.62,
        anomalyExplanation: { summary: 42, topFeatures: ['auth_failures', 7] },
      } as unknown as Partial<AlertV1> & { id: string }),
    );

    expect(detail).toEqual({
      summary: null,
      // Falls back to the alert's own confidence — the same number by another name.
      observedScore: 0.62,
      threshold: null,
      topFeatures: ['auth_failures'],
      modelVersionId: null,
    });
  });
});
