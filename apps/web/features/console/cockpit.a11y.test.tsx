import { cleanup, render } from '@testing-library/react';
import { act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';

const { useLiveRun, useCopilotPresence } = vi.hoisted(() => ({
  useLiveRun: vi.fn(),
  useCopilotPresence: vi.fn(),
}));

vi.mock('@/features/live-run', () => ({
  LiveRunControls: () => (
    <div role="group" aria-label="Sim controls">
      <button type="button">Pause sim</button>
    </div>
  ),
  useLiveRun,
}));
vi.mock('@/features/operator-actions', () => ({
  AssetCommandBar: () => (
    <div>
      <span>Operator command</span>
      <button type="button">Isolate host</button>
    </div>
  ),
}));
vi.mock('@/features/timeline', () => ({
  RunTape: () => (
    <div role="group" aria-label="Run event tape">
      <button type="button" aria-label="Sequence 4 · Anomalous VPN session" />
    </div>
  ),
}));
vi.mock('./use-copilot-presence', () => ({
  PREVIEW_VISIBLE_MS: 8_000,
  useCopilotPresence,
}));
vi.mock('@/features/ops-feed', () => ({
  OpsFeedPanel: () => <p>feed body</p>,
}));

import { Chronicle } from './chronicle';
import { Console } from './console';
import { useCockpitUiStore } from '@/stores/cockpit-ui-store';

const RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

beforeEach(() => {
  vi.clearAllMocks();
  useLiveRun.mockReturnValue(null);
  useCopilotPresence.mockReturnValue({
    phase: 'unread',
    workingRoles: [],
    unreadCount: 2,
    preview: 'The identity provider shows anomalous auth.',
    previewRole: 'WATCHTOWER',
    hasFailure: false,
    lastEventAt: Date.now(),
    announcement: 'WATCHTOWER replied',
  });
  useCockpitUiStore.getState().resetCockpitUi();
});

afterEach(() => {
  cleanup();
  useCockpitUiStore.getState().resetCockpitUi();
});

describe('Cockpit console accessibility', () => {
  it('renders the console band (with an unread copilot chip) without axe violations', async () => {
    const { container } = render(<Console runId={RUN_ID} />);
    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });

  it('renders the open chronicle without axe violations', async () => {
    act(() => {
      useCockpitUiStore.getState().setChronicleOpen(true);
    });
    const { container } = render(<Chronicle runId={RUN_ID} />);
    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });
});
