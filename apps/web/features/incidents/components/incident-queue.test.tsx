import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { useIncidentQueue } = vi.hoisted(() => ({ useIncidentQueue: vi.fn() }));

vi.mock('@/features/incidents/hooks/use-incident-queries', () => ({
  useIncidentQueue,
}));

vi.mock('@/features/incidents/components/incident-workspace', () => ({
  IncidentWorkspace: ({ children, title }: { children: React.ReactNode; title: string }) => (
    <div data-testid="workspace-mock">
      <h1>{title}</h1>
      {children}
    </div>
  ),
}));

vi.mock('next/link', () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

import { IncidentQueue } from '@/features/incidents/components/incident-queue';
import { ApiClientError } from '@/lib/api/types';

function row(id: string, state: string, alertIds: string[]) {
  return {
    incident: {
      id,
      runId: 'run_1',
      title: `Incident ${id}`,
      state,
      alertIds,
      createdAt: '2026-06-30T02:00:00.000Z',
      updatedAt: '2026-06-30T02:05:00.000Z',
    },
    run: { id: 'run_1' },
    severity: 'high',
    linkedAlertCount: alertIds.length,
    presentation: {
      phase: 'triage',
      label: 'Open',
      nodeStatus: 'suspicious',
      isResolved: false,
    },
  };
}

describe('IncidentQueue', () => {
  beforeEach(() => {
    useIncidentQueue.mockReset();
  });
  afterEach(() => {
    cleanup();
  });

  it('shows a loading state while fetching', () => {
    useIncidentQueue.mockReturnValue({
      isPending: true,
      isError: false,
      data: undefined,
    });
    render(<IncidentQueue />);
    expect(screen.getByTestId('incident-queue-loading')).toBeInTheDocument();
  });

  it('shows an error state on failure', () => {
    useIncidentQueue.mockReturnValue({
      isPending: false,
      isError: true,
      data: undefined,
      error: new Error('boom'),
      refetch: vi.fn(),
    });
    render(<IncidentQueue />);
    expect(screen.getByTestId('incident-queue-error')).toBeInTheDocument();
  });

  it('distinguishes an expired session from a transport failure, and hides a useless retry', () => {
    useIncidentQueue.mockReturnValue({
      isPending: false,
      isError: true,
      data: undefined,
      error: new ApiClientError({ code: 'UNAUTHENTICATED', message: 'expired', status: 401 }),
      refetch: vi.fn(),
    });
    render(<IncidentQueue />);
    const state = screen.getByTestId('incident-queue-error');
    expect(state).toHaveAttribute('data-failure-kind', 'auth');
    expect(screen.getByText(/session has expired/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument();
  });

  it('offers a retry when the API is unreachable', () => {
    useIncidentQueue.mockReturnValue({
      isPending: false,
      isError: true,
      data: undefined,
      error: new TypeError('Failed to fetch'),
      refetch: vi.fn(),
    });
    render(<IncidentQueue />);
    expect(screen.getByTestId('incident-queue-error')).toHaveAttribute(
      'data-failure-kind',
      'connectivity',
    );
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });

  it('shows an empty state when no incidents exist', () => {
    useIncidentQueue.mockReturnValue({
      isPending: false,
      isError: false,
      data: [],
    });
    render(<IncidentQueue />);
    expect(screen.getByTestId('incident-queue-empty')).toBeInTheDocument();
  });

  it('renders queue rows and a summary when incidents exist', () => {
    useIncidentQueue.mockReturnValue({
      isPending: false,
      isError: false,
      data: [row('incident:a', 'open', ['alert:1', 'alert:2'])],
    });
    render(<IncidentQueue />);
    expect(screen.getByTestId('incident-queue-summary')).toBeInTheDocument();
    expect(screen.getByTestId('queue-row-incident:a')).toBeInTheDocument();
    expect(screen.getByText('Incident incident:a')).toBeInTheDocument();
  });
});
