import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

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

const TRAINING = {
  id: 'scenario:synthetic-training',
  name: 'Synthetic Training',
};

function scenariosSuccess(data: { id: string; name: string }[] = [SILENT_RELAY]) {
  return {
    isPending: false,
    isError: false,
    isSuccess: true,
    data,
    refetch: vi.fn(),
  };
}

function trainingRun(status = 'stopped') {
  return {
    id: 'run_training_1',
    scenarioVersionId: 'scenario-version:1.0.0-synthetic-training',
    status,
    startedAt: '2026-06-30T02:00:00.000Z',
    ownerUserId: 'user:operator-alpha',
  };
}

function runsResult(data: unknown[]) {
  return { isPending: false, isError: false, isSuccess: true, data };
}

describe('ScenariosPage run entry UX (AEGIS-BUG-010)', () => {
  beforeAll(() => {
    // The live-scenario launch now opens a Radix dialog (the loadout step); jsdom omits these.
    Element.prototype.hasPointerCapture = vi.fn(() => false);
    Element.prototype.setPointerCapture = vi.fn();
    Element.prototype.releasePointerCapture = vi.fn();
    Element.prototype.scrollIntoView = vi.fn();
  });

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

  it('starts a new run through the loadout step and navigates to it', async () => {
    useRuns.mockReturnValue(runsResult([]));
    mutateAsync.mockResolvedValue({ run: { id: 'run_newly_created' } });

    render(<ScenariosPage />);

    // No hardcoded fallback: with no owned runs there is no resume affordance.
    expect(
      screen.queryByTestId('resume-run-scenario:operation-silent-relay'),
    ).not.toBeInTheDocument();

    // A live operation opens the loadout step before launching (the second variety axis).
    fireEvent.click(screen.getByTestId('start-run-scenario:operation-silent-relay'));
    const launch = await screen.findByTestId('loadout-launch-confirm');
    fireEvent.click(launch);

    await waitFor(() => {
      // Seedless launch (server draws the seed) with the default loadout persisted on the run.
      expect(mutateAsync).toHaveBeenCalledWith({
        scenarioPackagePath: 'scenarios/operation-silent-relay',
        seed: undefined,
        loadout: { schemaVersion: 1, biasGuard: true, threatTempo: true, roe: 'investigate' },
        // Seedless: a fresh run id every launch, so there is never anything to restart.
        restartExisting: false,
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

// The tutorial pins seed 1000, so its run id is derived once and reused forever: relaunching
// replaces the existing training run rather than adding one. The card has to say that, and
// the request has to ask the server for it.
describe('ScenariosPage tutorial relaunch', () => {
  beforeEach(() => {
    push.mockReset();
    mutateAsync.mockReset();
    resumeRun.mockReset();
    resumeRun.mockResolvedValue(undefined);
    useScenarios.mockReturnValue(scenariosSuccess([TRAINING]));
  });

  afterEach(() => {
    cleanup();
  });

  it('offers a plain start with no existing training run', () => {
    useRuns.mockReturnValue(runsResult([]));

    render(<ScenariosPage />);

    expect(screen.getByTestId('start-run-scenario:synthetic-training')).toHaveTextContent(
      'Start new run',
    );
    expect(
      screen.queryByTestId('restart-note-scenario:synthetic-training'),
    ).not.toBeInTheDocument();
  });

  it('reframes the launch as a restart once a training run exists', () => {
    useRuns.mockReturnValue(runsResult([trainingRun()]));

    render(<ScenariosPage />);

    expect(screen.getByTestId('start-run-scenario:synthetic-training')).toHaveTextContent(
      'Restart training run',
    );
    expect(screen.getByTestId('restart-note-scenario:synthetic-training')).toHaveTextContent(
      'Replaces the existing training run',
    );
  });

  it('launches the tutorial directly with restartExisting set', async () => {
    useRuns.mockReturnValue(runsResult([trainingRun()]));
    mutateAsync.mockResolvedValue({ run: { id: 'run_training_1' } });

    render(<ScenariosPage />);

    // The tutorial skips the loadout step and launches straight into the walkthrough.
    fireEvent.click(screen.getByTestId('start-run-scenario:synthetic-training'));

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith({
        scenarioPackagePath: 'scenarios/synthetic-training',
        seed: 1000,
        loadout: undefined,
        commanderIntent: undefined,
        restartExisting: true,
      });
    });
    await waitFor(() => {
      expect(push).toHaveBeenCalledWith('/runs/run_training_1');
    });
  });
});
