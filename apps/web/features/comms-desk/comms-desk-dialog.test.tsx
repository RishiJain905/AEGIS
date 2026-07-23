import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';

import { CommsDeskDialog } from './comms-desk-dialog';
import type { Sitrep } from './use-comms-desk';

const mutate = vi.fn();
let historyState: { sitreps: Sitrep[]; isLoading: boolean; isError: boolean };
let requestState: {
  mutate: typeof mutate;
  isPending: boolean;
  isError: boolean;
  error: Error | null;
  submittedAt: number;
};

vi.mock('./use-comms-desk', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./use-comms-desk')>();
  return {
    ...actual,
    useSitrepHistory: () => historyState,
    useRequestSitrep: () => requestState,
  };
});

function sitrep(overrides: Partial<Sitrep> & { taskId: string }): Sitrep {
  return {
    sessionId: 'agent-session:sess_scribe',
    status: 'completed',
    createdAt: '2026-07-22T00:00:00.000Z',
    completedAt: '2026-07-22T00:01:00.000Z',
    brief: '',
    evidenceIds: [],
    confidence: null,
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function baseRequest(overrides: Partial<typeof requestState> = {}) {
  return { mutate, isPending: false, isError: false, error: null, submittedAt: 0, ...overrides };
}

describe('CommsDeskDialog', () => {
  it('renders a finished sitrep brief with evidence chips', () => {
    historyState = {
      sitreps: [
        sitrep({
          taskId: 'agent-task:t1',
          brief: 'Logistics API shows elevated auth failures; contained at 00:14.',
          evidenceIds: ['evidence:ev_1'],
          confidence: 0.7,
        }),
      ],
      isLoading: false,
      isError: false,
    };
    requestState = baseRequest();
    render(<CommsDeskDialog runId="run_x" open onOpenChange={vi.fn()} />);
    expect(screen.getByTestId('sitrep-brief')).toHaveTextContent('elevated auth failures');
    expect(screen.getByTestId('sitrep-evidence')).toHaveTextContent('evidence:ev_1');
  });

  it('requests a sitrep on click', async () => {
    historyState = { sitreps: [], isLoading: false, isError: false };
    requestState = baseRequest();
    const user = userEvent.setup();
    render(<CommsDeskDialog runId="run_x" open onOpenChange={vi.fn()} />);
    await user.click(screen.getByTestId('sitrep-request'));
    expect(mutate).toHaveBeenCalledTimes(1);
  });

  it('shows an honest compiling state while the turn runs', () => {
    historyState = {
      sitreps: [sitrep({ taskId: 'agent-task:t1', status: 'running' })],
      isLoading: false,
      isError: false,
    };
    requestState = baseRequest({ isPending: true, submittedAt: Date.now() });
    render(<CommsDeskDialog runId="run_x" open onOpenChange={vi.fn()} />);
    expect(screen.getByTestId('sitrep-compiling')).toHaveTextContent('Compiling sitrep');
  });

  it('has no accessibility violations with a rendered brief', async () => {
    historyState = {
      sitreps: [sitrep({ taskId: 'agent-task:t1', brief: 'All quiet. No active incidents.' })],
      isLoading: false,
      isError: false,
    };
    requestState = baseRequest();
    const { container } = render(<CommsDeskDialog runId="run_x" open onOpenChange={vi.fn()} />);
    expect((await axe(container)).violations).toHaveLength(0);
  });
});
