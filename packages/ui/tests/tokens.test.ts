import { describe, expect, it } from 'vitest';

import {
  ALL_NODE_STATUSES,
  ALL_OPERATIONAL_STATUSES,
  uiStatusTokens,
} from '../src/tokens/status-tokens';
import { densityTokens, focusTokens, riskTokens, surfaceTokens } from '../src/tokens/tokens';
import { motionDurations, motionEasings } from '../src/tokens/motion-tokens';

describe('design tokens', () => {
  it('defines all surface tokens', () => {
    expect(Object.keys(surfaceTokens)).toEqual(['base', 'elevated', 'panel', 'rail', 'overlay']);
  });

  it('defines all risk tokens', () => {
    expect(Object.keys(riskTokens)).toEqual(['low', 'medium', 'high', 'critical']);
  });

  it('defines density variants', () => {
    expect(Object.keys(densityTokens)).toEqual(['compact', 'comfortable', 'spacious']);
  });

  it('includes focus ring token that is never empty', () => {
    expect(focusTokens.ring.length).toBeGreaterThan(0);
  });

  it('maps every NodeStatus to a ui token', () => {
    for (const status of ALL_NODE_STATUSES) {
      expect(uiStatusTokens[status]).toBeDefined();
    }
  });

  it('defines operational status tokens', () => {
    for (const status of ALL_OPERATIONAL_STATUSES) {
      expect(status).toMatch(/^(loading|error|disconnected|empty)$/);
    }
  });

  it('defines motion durations and easings', () => {
    expect(Object.keys(motionDurations)).toEqual(['instant', 'fast', 'normal', 'slow']);
    expect(Object.keys(motionEasings)).toEqual(['standard', 'emphasis', 'decelerate']);
  });
});
