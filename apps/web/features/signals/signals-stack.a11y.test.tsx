import { act, cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';

const { useRunAlerts, useRunActivity } = vi.hoisted(() => ({
  useRunAlerts: vi.fn(),
  useRunActivity: vi.fn(),
}));

vi.mock('@/features/shell/hooks/use-shell-queries', () => ({ useRunAlerts }));
vi.mock('@/features/live-run', () => ({ useRunActivity }));
vi.mock('@/features/shell/components/alerts-tab', () => ({
  AlertsTab: () => (
    <ul aria-label="Alerts">
      <li>Anomalous VPN session</li>
    </ul>
  ),
}));

import { SignalsStack } from './signals-stack';
import { useCockpitUiStore } from '@/stores/cockpit-ui-store';

const RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

beforeEach(() => {
  vi.clearAllMocks();
  useCockpitUiStore.getState().resetCockpitUi();
  useRunActivity.mockReturnValue({
    level: 'elevated',
    count: 4,
    windowSeconds: 90,
    buckets: [0, 1, 2, 1],
  });
});

afterEach(() => {
  cleanup();
  useCockpitUiStore.getState().resetCockpitUi();
});

describe('SignalsStack accessibility', () => {
  it('renders the expanded stack without axe violations', async () => {
    useRunAlerts.mockReturnValue({ data: [{ id: 'a1', severity: 'high' }] });
    const { container } = render(<SignalsStack runId={RUN_ID} />);
    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });

  it('renders the capsule without axe violations', async () => {
    useRunAlerts.mockReturnValue({ data: [{ id: 'a1', severity: 'critical' }] });
    act(() => {
      useCockpitUiStore.getState().setSignalsPreference('capsule');
    });
    const { container } = render(<SignalsStack runId={RUN_ID} />);
    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });
});
