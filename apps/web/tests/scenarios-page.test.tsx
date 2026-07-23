import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { push, mutateAsync, resumeRun, useScenarios, useRuns } = vi.hoisted(() => ({
  push: vi.fn(),
  mutateAsync: vi.fn(),
  resumeRun: vi.fn(),
  useScenarios: vi.fn(),
  useRuns: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push }),
}));

vi.mock('@/features/shell/components/command-centre-shell', () => ({
  CommandCentreShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock('@/features/live-run', () => ({
  useCreateRun: () => ({ isPending: false, mutateAsync }),
  resumeRun,
}));

vi.mock('@/features/shell/hooks/use-shell-queries', () => ({
  useScenarios,
  useRuns,
}));

import ScenariosPage from '@/app/(shell)/scenarios/page';

const SILENT_RELAY = {
  id: 'scenario:operation-silent-relay',
  name: 'Operation Silent Relay',
};

function scenariosSuccess() {
  return {
    isPending: false,
    isError: false,
    isSuccess: true,
    data: [SILENT_RELAY],
    refetch: vi.fn(),
  };
}

function runsResult(data: unknown[]) {
  return { isPending: false, isError: false, isSuccess: true, data };
}

describe('ScenariosPage run entry UX (AEGIS-BUG-010)', () => {
  beforeEach(() => {
    push.mockReset();
    mutateAsync.mockReset();
    resumeRun.mockReset();
    resumeRun.mockResolvedValue(undefined);
    useScenarios.mockReturnValue(scenariosSuccess());
  });

  afterEach(() => {
    cleanup();
  });

  it('starts a new run and navigates to it when the account owns no run', async () => {
    useRuns.mockReturnValue(runsResult([]));
    mutateAsync.mockResolvedValue({ run: { id: 'run_newly_created' } });

    render(<ScenariosPage />);

    // No hardcoded fallback: with no owned runs there is no resume affordance.
    expect(
      screen.queryByTestId('resume-run-scenario:operation-silent-relay'),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('start-run-scenario:operation-silent-relay'));

    await waitFor(() => {
      // Seedless launch: no seed is sent, so the server draws a random one.
      expect(mutateAsync).toHaveBeenCalledWith({
        scenarioPackagePath: 'scenarios/operation-silent-relay',
        seed: undefined,
      });
    });
    await waitFor(() => {
      expect(push).toHaveBeenCalledWith('/runs/run_newly_created');
    });
  });

  it('offers resume only for a run the account owns for that scenario', () => {
    useRuns.mockReturnValue(
      runsResult([
        {
          id: 'run_owned_1',
          scenarioVersionId: 'scenario-version:1.0.0-silent-relay',
          status: 'running',
          startedAt: '2026-06-30T02:00:00.000Z',
          ownerUserId: 'user:operator-alpha',
        },
      ]),
    );

    render(<ScenariosPage />);

    const resume = screen.getByTestId('resume-run-scenario:operation-silent-relay');
    expect(resume).toBeInTheDocument();
    fireEvent.click(resume);
    // A running run needs no resume call — navigate straight in.
    expect(resumeRun).not.toHaveBeenCalled();
    expect(push).toHaveBeenCalledWith('/runs/run_owned_1');
  });

  it('resumes a paused run before navigating into it', async () => {
    useRuns.mockReturnValue(
      runsResult([
        {
          id: 'run_paused_1',
          scenarioVersionId: 'scenario-version:1.0.0-silent-relay',
          status: 'paused',
          startedAt: '2026-06-30T02:00:00.000Z',
          ownerUserId: 'user:operator-alpha',
        },
      ]),
    );

    render(<ScenariosPage />);

    fireEvent.click(screen.getByTestId('resume-run-scenario:operation-silent-relay'));

    await waitFor(() => {
      expect(resumeRun).toHaveBeenCalledWith('run_paused_1');
    });
    await waitFor(() => {
      expect(push).toHaveBeenCalledWith('/runs/run_paused_1');
    });
  });
});
