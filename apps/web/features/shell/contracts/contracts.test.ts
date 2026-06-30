import { describe, expect, it } from 'vitest';

import {
  defaultOperatorWorkspaceState,
  operatorWorkspaceStateSchema,
} from '@/features/shell/contracts/operator-workspace-state';
import {
  defaultPanelPreferences,
  parsePanelPreferences,
} from '@/features/shell/contracts/panel-preferences';

describe('operator workspace state', () => {
  it('parses valid default state', () => {
    const parsed = operatorWorkspaceStateSchema.parse(defaultOperatorWorkspaceState);
    expect(parsed.schemaVersion).toBe(1);
    expect(parsed.commandPaletteOpen).toBe(false);
  });

  it('rejects authoritative status fields', () => {
    const result = operatorWorkspaceStateSchema.safeParse({
      ...defaultOperatorWorkspaceState,
      incidentStatus: 'open',
    });
    expect(result.success).toBe(false);
  });
});

describe('panel preferences', () => {
  it('returns defaults for invalid persisted data', () => {
    expect(parsePanelPreferences({ invalid: true })).toEqual(defaultPanelPreferences);
  });

  it('preserves valid region preferences', () => {
    const parsed = parsePanelPreferences({
      schemaVersion: 1,
      regions: {
        ...defaultPanelPreferences.regions,
        inspector: { docked: true, collapsed: true, width: 320 },
      },
    });
    expect(parsed.regions.inspector?.collapsed).toBe(true);
    expect(parsed.regions.inspector?.width).toBe(320);
  });
});
