import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { useCopilotPresence } = vi.hoisted(() => ({
  useCopilotPresence: vi.fn(),
}));

vi.mock('./use-copilot-presence', () => ({
  PREVIEW_VISIBLE_MS: 8_000,
  useCopilotPresence,
}));

import { CopilotChip } from './copilot-chip';
import { useCockpitUiStore } from '@/stores/cockpit-ui-store';

const RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

function presence(overrides: Record<string, unknown> = {}) {
  return {
    phase: 'idle',
    workingRoles: [],
    unreadCount: 0,
    preview: null,
    previewRole: null,
    hasFailure: false,
    lastEventAt: null,
    announcement: null,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  useCockpitUiStore.getState().resetCockpitUi();
  useCopilotPresence.mockReturnValue(presence());
});

afterEach(() => {
  cleanup();
  useCockpitUiStore.getState().resetCockpitUi();
});

describe('CopilotChip', () => {
  it('rests quiet and opens the copilot sheet on click', async () => {
    const user = userEvent.setup();
    render(<CopilotChip runId={RUN_ID} />);
    const chip = screen.getByTestId('copilot-chip');
    expect(chip).toHaveAttribute('data-phase', 'idle');

    await user.click(chip);
    expect(useCockpitUiStore.getState().copilotSheetOpen).toBe(true);
  });

  it('looks alive for the whole working turn', () => {
    useCopilotPresence.mockReturnValue(
      presence({ phase: 'working', workingRoles: ['WATCHTOWER'] }),
    );
    render(<CopilotChip runId={RUN_ID} />);
    const chip = screen.getByTestId('copilot-chip');
    expect(chip).toHaveAttribute('data-phase', 'working');
    expect(chip).toHaveTextContent('WATCHTOWER');
    expect(screen.getByTestId('copilot-chip-ring')).toBeInTheDocument();
  });

  it('flips to an unmissable unread state with badge, preview and announcement', () => {
    useCopilotPresence.mockReturnValue(
      presence({
        phase: 'unread',
        unreadCount: 2,
        preview: 'The identity provider shows anomalous auth.',
        previewRole: 'WATCHTOWER',
        lastEventAt: Date.now(),
        announcement: 'WATCHTOWER replied',
      }),
    );
    render(<CopilotChip runId={RUN_ID} />);
    expect(screen.getByTestId('copilot-chip-unread')).toHaveTextContent('2');
    expect(screen.getByTestId('copilot-chip-preview')).toHaveTextContent(
      'WATCHTOWER: The identity provider shows anomalous auth.',
    );
    expect(screen.getByRole('status')).toHaveTextContent('WATCHTOWER replied');
  });

  it('carries the risk tint and needs-attention copy on failure', () => {
    useCopilotPresence.mockReturnValue(
      presence({
        phase: 'failed',
        unreadCount: 1,
        hasFailure: true,
        preview: 'Model timed out',
        previewRole: 'TRACE',
        lastEventAt: Date.now(),
        announcement: 'TRACE needs attention',
      }),
    );
    render(<CopilotChip runId={RUN_ID} />);
    const chip = screen.getByTestId('copilot-chip');
    expect(chip).toHaveAttribute('data-phase', 'failed');
    expect(chip).toHaveTextContent('Needs attention');
    expect(screen.getByRole('status')).toHaveTextContent('TRACE needs attention');
  });
});
