import { NodeStatus } from '@aegis/contracts-ts';
import { describe, expect, it } from 'vitest';

import { ALL_NODE_STATUSES } from '../src/tokens/status-tokens';
import {
  getNodeStatusPresentation,
  getOperationalStatusPresentation,
} from '../src/semantic/status';

describe('semantic status presentation', () => {
  it('maps every NodeStatus to label, icon, shape, and aria label', () => {
    for (const status of ALL_NODE_STATUSES) {
      const presentation = getNodeStatusPresentation(status);
      expect(presentation.label.length).toBeGreaterThan(0);
      expect(presentation.icon.length).toBeGreaterThan(0);
      expect(presentation.shape.length).toBeGreaterThan(0);
      expect(presentation.tokenClass.length).toBeGreaterThan(0);
      expect(presentation.ariaLabel).toContain('Status:');
    }
  });

  it('does not rely on color alone — each status has distinct icon and shape', () => {
    const presentations = ALL_NODE_STATUSES.map((status) => getNodeStatusPresentation(status));
    const iconShapePairs = presentations.map((p) => `${p.icon}:${p.shape}`);
    expect(new Set(iconShapePairs).size).toBe(presentations.length);
  });

  it('provides operational state presentations', () => {
    const loading = getOperationalStatusPresentation('loading');
    const disconnected = getOperationalStatusPresentation('disconnected');
    expect(loading.label).toBe('Loading');
    expect(disconnected.icon).toBe('wifi-off');
    expect(disconnected.ariaLabel).toContain('Disconnected');
  });

  it('uses canonical NodeStatus constants', () => {
    expect(getNodeStatusPresentation(NodeStatus.COMPROMISED).label).toBe('Compromised');
  });
});
