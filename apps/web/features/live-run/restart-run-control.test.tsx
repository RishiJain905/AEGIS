import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import { RestartRunControl } from './restart-run-control';

const push = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push }),
}));

// The control resolves the run's scenario from the run detail query; the query stack itself
// is not under test, so the hook is stubbed to the fixture the case needs.
let runData: unknown = undefined;
vi.mock('@/features/shell/hooks/use-shell-queries', () => ({
  useRun: () => ({ data: runData }),
}));

const mutateAsync = vi.fn();
vi.mock('./use-run-commands', () => ({
  useCreateRun: () => ({ mutateAsync, isPending: false }),
}));

// The control reads the run's lifecycle from the live provider; `null` stands for "no live
// run context", which is what every case except the terminal-run ones renders under.
let liveRunStatus: string | null = null;
vi.mock('./live-run-provider', () => ({
  useLiveRun: () => (liveRunStatus === null ? null : { state: { runStatus: liveRunStatus } }),
}));

// Hoisted: the mock factory below runs before the module body, so the spy must exist first.
const { armTutorial } = vi.hoisted(() => ({ armTutorial: vi.fn() }));
vi.mock('@/features/tutorial/tutorial-storage', () => ({
  armTutorial,
}));

// `readRunLoadout` (command-surface) and the scenario-launch config (loadout) are pure and
// stay real; only the network-touching hooks above are stubbed.

interface RunFixture {
  id: string;
  scenarioVersionId: string;
  seed: number;
  status: string;
  loadout?: unknown;
  commanderIntent?: string | null;
}

const SILENT_RELAY_RUN: RunFixture = {
  id: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
  scenarioVersionId: 'scenario-version:1.0.0-silent-relay',
  seed: 424242,
  status: 'stopped',
  loadout: {
    schemaVersion: 1,
    biasGuard: true,
    threatTempo: false,
    roe: 'investigate',
    providerId: 'openai',
    modelId: 'gpt-4o',
  },
  commanderIntent: 'Contain the exfil before it spreads.',
};

const TUTORIAL_RUN: RunFixture = {
  id: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
  scenarioVersionId: 'scenario-version:1.0.0-synthetic-training',
  seed: 1000,
  status: 'completed',
};

function Wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function renderControl(runId = 'run_x') {
  return render(
    <Wrapper>
      <RestartRunControl runId={runId} />
    </Wrapper>,
  );
}

beforeAll(() => {
  // Radix Dialog reads these; jsdom omits them.
  Element.prototype.hasPointerCapture = vi.fn(() => false);
  Element.prototype.setPointerCapture = vi.fn();
  Element.prototype.releasePointerCapture = vi.fn();
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  runData = undefined;
  liveRunStatus = null;
});

describe('RestartRunControl gating', () => {
  it('renders nothing while the run detail is still loading', () => {
    liveRunStatus = 'stopped';
    renderControl();
    expect(screen.queryByTestId('live-restart')).not.toBeInTheDocument();
  });

  it('renders nothing while the run is live — restarting mid-run would destroy it', () => {
    runData = SILENT_RELAY_RUN;
    liveRunStatus = 'running';
    renderControl();
    expect(screen.queryByTestId('live-restart')).not.toBeInTheDocument();
  });

  it('renders nothing for a scenario version this deployment cannot relaunch', () => {
    runData = { ...SILENT_RELAY_RUN, scenarioVersionId: 'scenario-version:9.9.9-future' };
    liveRunStatus = 'stopped';
    renderControl();
    expect(screen.queryByTestId('live-restart')).not.toBeInTheDocument();
  });

  it.each(['stopped', 'completed', 'failed', 'aborted'])(
    'offers the way back once the run is %s',
    (runStatus) => {
      runData = SILENT_RELAY_RUN;
      liveRunStatus = runStatus;
      renderControl();
      expect(screen.getByTestId('live-restart')).toBeInTheDocument();
    },
  );
});

describe('RestartRunControl confirm flow', () => {
  beforeEach(() => {
    runData = SILENT_RELAY_RUN;
    liveRunStatus = 'stopped';
  });

  it('states the consequences before asking for the confirmation', async () => {
    const user = userEvent.setup();
    renderControl();

    await user.click(screen.getByTestId('live-restart'));

    const dialog = await screen.findByTestId('restart-run-dialog');
    expect(dialog).toHaveTextContent('Restart this run?');
    // The destructive part is said out loud, not buried in a tooltip.
    expect(dialog).toHaveTextContent(/timeline, after-action report and replay are discarded/i);
    expect(dialog).toHaveTextContent('Seed 424242');
    expect(mutateAsync).not.toHaveBeenCalled();
  });

  it('cancels without launching anything', async () => {
    const user = userEvent.setup();
    renderControl();

    await user.click(screen.getByTestId('live-restart'));
    await user.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(screen.queryByTestId('restart-run-dialog')).not.toBeInTheDocument();
    expect(mutateAsync).not.toHaveBeenCalled();
  });

  it('relaunches the run with its own scenario, seed, loadout and intent', async () => {
    const user = userEvent.setup();
    mutateAsync.mockResolvedValue({ run: { id: SILENT_RELAY_RUN.id } });
    renderControl();

    await user.click(screen.getByTestId('live-restart'));
    await user.click(screen.getByTestId('restart-run-confirm'));

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledTimes(1);
    });
    expect(mutateAsync.mock.calls[0]?.[0]).toEqual({
      scenarioPackagePath: 'scenarios/operation-silent-relay',
      seed: 424242,
      loadout: {
        schemaVersion: 1,
        biasGuard: true,
        threatTempo: false,
        roe: 'investigate',
        providerId: 'openai',
        modelId: 'gpt-4o',
      },
      commanderIntent: 'Contain the exfil before it spreads.',
      restartExisting: true,
    });
  });

  it('omits the loadout and intent on a legacy run that never had them', async () => {
    const user = userEvent.setup();
    mutateAsync.mockResolvedValue({ run: { id: TUTORIAL_RUN.id } });
    runData = { ...TUTORIAL_RUN, loadout: null, commanderIntent: null };
    renderControl();

    await user.click(screen.getByTestId('live-restart'));
    await user.click(screen.getByTestId('restart-run-confirm'));

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledTimes(1);
    });
    expect(mutateAsync.mock.calls[0]?.[0]).toEqual({
      scenarioPackagePath: 'scenarios/synthetic-training',
      seed: 1000,
      restartExisting: true,
    });
  });

  it('navigates back into the rebuilt run with an epoch key so the shell remounts', async () => {
    const user = userEvent.setup();
    mutateAsync.mockResolvedValue({ run: { id: SILENT_RELAY_RUN.id } });
    renderControl();

    await user.click(screen.getByTestId('live-restart'));
    await user.click(screen.getByTestId('restart-run-confirm'));

    await waitFor(() => {
      expect(push).toHaveBeenCalledTimes(1);
    });
    // Same run id, so the route alone would not remount the cockpit — the epoch query
    // param is what forces a fresh bootstrap of the rebuilt run.
    const [path] = push.mock.calls[0] as [string];
    expect(path).toMatch(new RegExp(`^/runs/${SILENT_RELAY_RUN.id}\\?restart=\\d+$`));
    expect(screen.queryByTestId('restart-run-dialog')).not.toBeInTheDocument();
  });

  it('re-arms the guided walkthrough when the restarted scenario is the tutorial', async () => {
    const user = userEvent.setup();
    mutateAsync.mockResolvedValue({ run: { id: TUTORIAL_RUN.id } });
    runData = TUTORIAL_RUN;
    renderControl();

    await user.click(screen.getByTestId('live-restart'));
    // The tutorial's confirm copy says the walkthrough restarts from the top.
    expect(await screen.findByTestId('restart-run-dialog')).toHaveTextContent(
      /guided walkthrough restarts from the top/i,
    );
    await user.click(screen.getByTestId('restart-run-confirm'));

    await waitFor(() => {
      expect(armTutorial).toHaveBeenCalledWith(TUTORIAL_RUN.id);
    });
  });

  it('keeps the dialog open and says why when the relaunch fails', async () => {
    const user = userEvent.setup();
    mutateAsync.mockRejectedValue(
      new Error('RUN_OWNED_BY_ANOTHER_USER: run belongs to another operator'),
    );
    renderControl();

    await user.click(screen.getByTestId('live-restart'));
    await user.click(screen.getByTestId('restart-run-confirm'));

    const error = await screen.findByTestId('restart-run-error');
    expect(error).toHaveTextContent('RUN_OWNED_BY_ANOTHER_USER');
    expect(screen.getByTestId('restart-run-dialog')).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });
});
