import { describe, expect, it } from 'vitest';

import {
  assessIntent,
  type IntentAssessmentInput,
  type IntentFindingStatus,
} from './assess-intent';

function baseInput(overrides: Partial<IntentAssessmentInput> = {}): IntentAssessmentInput {
  return {
    intent: '',
    assets: [
      { id: 'asset:records-db', label: 'Student Records Database', kind: 'database' },
      { id: 'asset:mail', label: 'Mail Relay', kind: 'service' },
    ],
    actions: [],
    threatEvents: [],
    ...overrides,
  };
}

function statusFor(
  input: IntentAssessmentInput,
  findingId: string,
): IntentFindingStatus | undefined {
  return assessIntent(input).findings.find((f) => f.id === findingId)?.status;
}

describe('assessIntent', () => {
  it('returns no findings and hasIntent=false for an empty intent', () => {
    const result = assessIntent(baseInput({ intent: '   ' }));
    expect(result.hasIntent).toBe(false);
    expect(result.findings).toHaveLength(0);
  });

  it('fuzzy-matches the intent to the named asset by label keyword', () => {
    const result = assessIntent(baseInput({ intent: 'priority: protect student records' }));
    expect(result.namedAssets.map((a) => a.id)).toContain('asset:records-db');
    expect(result.namedAssets.map((a) => a.id)).not.toContain('asset:mail');
  });

  it('HELD: named asset contained before attacker activity reaches it', () => {
    const input = baseInput({
      intent: 'protect student records above all',
      actions: [
        {
          id: 'act:1',
          targetAssetId: 'asset:records-db',
          actionClass: 'class_2',
          command: 'isolate host',
          sequence: 5,
        },
      ],
      threatEvents: [
        {
          id: 'evt:t1',
          assetId: 'asset:records-db',
          sequence: 9,
          kind: 'attacker',
          label: 'lateral move',
        },
      ],
    });
    expect(statusFor(input, 'intent-protect-asset:records-db')).toBe('held');
  });

  it('TENSION: named asset contained only after attacker activity reaches it', () => {
    const input = baseInput({
      intent: 'protect student records',
      actions: [
        {
          id: 'act:1',
          targetAssetId: 'asset:records-db',
          actionClass: 'class_3',
          command: 'isolate host',
          sequence: 20,
        },
      ],
      threatEvents: [
        {
          id: 'evt:t1',
          assetId: 'asset:records-db',
          sequence: 8,
          kind: 'attacker',
          label: 'access',
        },
      ],
    });
    expect(statusFor(input, 'intent-protect-asset:records-db')).toBe('tension');
  });

  it('VIOLATED: attacker reaches named asset and no containment ever runs on it', () => {
    const input = baseInput({
      intent: 'protect student records',
      actions: [
        {
          id: 'act:1',
          targetAssetId: 'asset:mail',
          actionClass: 'class_2',
          command: 'isolate host',
          sequence: 12,
        },
      ],
      threatEvents: [
        {
          id: 'evt:t1',
          assetId: 'asset:records-db',
          sequence: 8,
          kind: 'exfil',
          label: 'data theft',
        },
      ],
    });
    expect(statusFor(input, 'intent-protect-asset:records-db')).toBe('violated');
  });

  it('VIOLATED evidence: destructive command executed against an evidence-preservation intent', () => {
    const input = baseInput({
      intent: 'preserve forensic evidence; keep chain of custody intact',
      actions: [
        {
          id: 'act:1',
          targetAssetId: 'asset:records-db',
          actionClass: 'class_3',
          command: 'rollback snapshot',
          sequence: 12,
        },
      ],
    });
    expect(statusFor(input, 'intent-evidence')).toBe('violated');
  });

  it('HELD evidence: no aggressive or destructive actions under an evidence intent', () => {
    const input = baseInput({
      intent: 'preserve forensic evidence first',
      actions: [
        {
          id: 'act:1',
          targetAssetId: 'asset:records-db',
          actionClass: 'class_1',
          command: 'collect logs',
          sequence: 3,
        },
      ],
    });
    expect(statusFor(input, 'intent-evidence')).toBe('held');
  });

  it('containment timing: HELD when containment precedes first exfil', () => {
    const input = baseInput({
      intent: 'stop the attacker and prevent exfiltration',
      actions: [
        {
          id: 'act:1',
          targetAssetId: 'asset:records-db',
          actionClass: 'class_2',
          command: 'revoke credentials',
          sequence: 4,
        },
      ],
      threatEvents: [
        { id: 'evt:x1', assetId: 'asset:records-db', sequence: 10, kind: 'exfil', label: 'exfil' },
      ],
    });
    expect(statusFor(input, 'intent-containment-timing')).toBe('held');
  });

  it('containment timing: VIOLATED when exfil occurs and no containment runs', () => {
    const input = baseInput({
      intent: 'stop the attacker, block exfiltration',
      actions: [],
      threatEvents: [
        { id: 'evt:x1', assetId: 'asset:records-db', sequence: 10, kind: 'exfil', label: 'exfil' },
      ],
    });
    expect(statusFor(input, 'intent-containment-timing')).toBe('violated');
  });

  it('is deterministic — same input yields identical findings', () => {
    const input = baseInput({
      intent: 'protect student records; preserve evidence',
      actions: [
        {
          id: 'act:1',
          targetAssetId: 'asset:records-db',
          actionClass: 'class_2',
          command: 'isolate',
          sequence: 5,
        },
      ],
      threatEvents: [
        { id: 'evt:t1', assetId: 'asset:records-db', sequence: 9, kind: 'attacker', label: 'move' },
      ],
    });
    expect(assessIntent(input)).toEqual(assessIntent(input));
  });
});
