import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { ConsoleEvent } from '@/features/command-surface';

import { EventSearch } from './event-search';

const search = vi.fn();
const loadMore = vi.fn();
const reset = vi.fn();
let consoleState: {
  events: ConsoleEvent[];
  hasMore: boolean;
  hasSearched: boolean;
  isPending: boolean;
  isError: boolean;
  error: Error | null;
};

vi.mock('@/features/command-surface', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/command-surface')>();
  return {
    ...actual,
    useConsoleSearch: () => ({ ...consoleState, search, loadMore, reset }),
  };
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function baseState(overrides: Partial<typeof consoleState> = {}) {
  return {
    events: [],
    hasMore: false,
    hasSearched: false,
    isPending: false,
    isError: false,
    error: null,
    ...overrides,
  };
}

describe('EventSearch', () => {
  it('submits typed filters, omitting blanks as null', async () => {
    consoleState = baseState();
    const user = userEvent.setup();
    render(<EventSearch runId="run_x" />);
    await user.type(screen.getByLabelText(/Search text/i), 'lateral');
    await user.type(screen.getByLabelText(/^Asset$/i), 'asset:vpn-gw');
    await user.click(screen.getByRole('button', { name: /Search evidence/i }));
    expect(search).toHaveBeenCalledTimes(1);
    expect(search.mock.calls[0]?.[0]).toEqual({
      text: 'lateral',
      assetId: 'asset:vpn-gw',
      eventTypePrefix: null,
      fromSimTime: null,
      toSimTime: null,
    });
  });

  it('renders results and loads more via the cursor', async () => {
    consoleState = baseState({
      hasSearched: true,
      hasMore: true,
      events: [
        {
          eventId: 'evt-1',
          sequence: 1,
          type: 'telemetry.auth.failed',
          simTime: '2026-07-22T00:00:00.000Z',
          assetId: 'asset:vpn-gw',
          payload: { count: 3 },
        },
      ],
    });
    const user = userEvent.setup();
    render(<EventSearch runId="run_x" />);
    expect(screen.getByText('telemetry.auth.failed')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Load more/i }));
    expect(loadMore).toHaveBeenCalledTimes(1);
  });

  it('shows an empty state after a search with no matches', () => {
    consoleState = baseState({ hasSearched: true, events: [] });
    render(<EventSearch runId="run_x" />);
    expect(screen.getByText(/No matching events/i)).toBeInTheDocument();
  });
});
