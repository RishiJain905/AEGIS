import { describe, expect, it } from 'vitest';

import {
  ACTION_CLASS_LABEL,
  COMMAND_CATALOGUE,
  commandMeta,
  DEFAULT_LOADOUT,
  requiresConfirmation,
  ROE_DOCTRINE,
  RULES_OF_ENGAGEMENT,
} from './contracts';

describe('command-surface contracts', () => {
  it('maps every command to the policy engine action class', () => {
    // Mirrors packages/policy/src/aegis_policy/commands.py — the confirm gate depends on it.
    expect(commandMeta('observe').actionClass).toBe('class_0');
    expect(commandMeta('increase_monitoring').actionClass).toBe('class_1');
    expect(commandMeta('isolate').actionClass).toBe('class_2');
    expect(commandMeta('restrict_access').actionClass).toBe('class_2');
    expect(commandMeta('revoke_credentials').actionClass).toBe('class_2');
    expect(commandMeta('restart_service').actionClass).toBe('class_3');
    expect(commandMeta('rollback_deployment').actionClass).toBe('class_3');
  });

  it('requires confirmation only for Class 2 and Class 3', () => {
    expect(requiresConfirmation('class_0')).toBe(false);
    expect(requiresConfirmation('class_1')).toBe(false);
    expect(requiresConfirmation('class_2')).toBe(true);
    expect(requiresConfirmation('class_3')).toBe(true);
  });

  it('flags irreversible commands as not reversible', () => {
    expect(commandMeta('rollback_deployment').reversible).toBe(false);
    expect(commandMeta('restart_service').reversible).toBe(false);
    expect(commandMeta('isolate').reversible).toBe(true);
  });

  it('catalogue and labels are complete', () => {
    expect(COMMAND_CATALOGUE).toHaveLength(7);
    for (const cls of ['class_0', 'class_1', 'class_2', 'class_3'] as const) {
      expect(ACTION_CLASS_LABEL[cls]).toBeTruthy();
    }
  });

  it('exposes a doctrine line for every rule of engagement, defaulting to investigate', () => {
    expect(DEFAULT_LOADOUT.roe).toBe('investigate');
    for (const roe of RULES_OF_ENGAGEMENT) {
      expect(ROE_DOCTRINE[roe].doctrine.length).toBeGreaterThan(0);
    }
  });
});
