/**
 * BUG-022: replay was reachable only by typing a run's URL. `/replay` now has a
 * run-selection state, so the rail item has somewhere to go with no run in context.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

const { useRuns, listScenarios, listScenarioVersions } = vi.hoisted(() => ({
  useRuns: vi.fn(),
  listScenarios: vi.fn(),
  listScenarioVersions: vi.fn(),
}));

vi.mock('@/features/shell/hooks/use-shell-queries', () => ({ useRuns }));
vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    useApiClient: () => ({ listScenarios, listScenarioVersions }),
  };
});

vi.mock('next/link', () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

import { ReplayRunPicker } from '@/features/replay/components/replay-run-picker';

const SILENT_RELAY = 'run_8024W2GZ4PMQ02P8FXTH840AY6';
const TUTORIAL = 'run_E02AHM3GRDCYE9CDMM1PBTD3D1';

function run(id: string, overrides: Record<string, unknown> = {}) {
  return {
    schemaVersion: 1,
    id,
    scenarioVersionId: 'scenario-version:1.0.0',
    seed: 1725850860,
    status: 'stopped',
    startedAt: '2026-01-01T00:00:00.000Z',
    simTime: '2026-01-01T00:06:24.000Z',
    revision: 327,
    ...overrides,
  };
}

function renderPicker() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ReplayRunPicker />
    </QueryClientProvider>,
  );
}

describe('ReplayRunPicker', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('lists the operator’s runs with an open-replay action', async () => {
    useRuns.mockReturnValue({ isPending: false, isError: false, data: [run(SILENT_RELAY)] });
    listScenarios.mockResolvedValue([
      { id: 'scenario:operation-silent-relay', name: 'Operation Silent Relay' },
    ]);
    listScenarioVersions.mockResolvedValue([{ id: 'scenario-version:1.0.0' }]);

    renderPicker();

    const option = screen.getByTestId('replay-run-option');
    expect(option).toHaveAttribute('data-run-id', SILENT_RELAY);
    expect(screen.getByTestId('replay-run-status').textContent).toBe('stopped');
    expect(option.textContent).toContain('1725850860');
    expect(option.textContent).toContain('00:06:24');
    expect(screen.getByTestId('replay-run-open')).toHaveAttribute(
      'href',
      `/replay/${SILENT_RELAY}`,
    );

    // The scenario name resolves through the catalogue: a run carries only its version id.
    await waitFor(() => {
      expect(option.textContent).toContain('Operation Silent Relay');
    });
  });

  it('puts a still-running run ahead of finished ones', () => {
    useRuns.mockReturnValue({
      isPending: false,
      isError: false,
      data: [run(SILENT_RELAY, { status: 'stopped' }), run(TUTORIAL, { status: 'running' })],
    });
    listScenarios.mockResolvedValue([]);

    renderPicker();

    const ids = screen
      .getAllByTestId('replay-run-option')
      .map((node) => node.getAttribute('data-run-id'));
    expect(ids).toEqual([TUTORIAL, SILENT_RELAY]);
  });

  it('explains an empty history instead of rendering a bare list', () => {
    useRuns.mockReturnValue({ isPending: false, isError: false, data: [] });
    listScenarios.mockResolvedValue([]);

    renderPicker();

    expect(screen.getByTestId('replay-runs-empty')).toBeInTheDocument();
    expect(screen.queryByTestId('replay-run-option')).toBeNull();
  });

  it('offers a retry when the run history cannot be read', () => {
    const refetch = vi.fn();
    useRuns.mockReturnValue({ isPending: false, isError: true, data: undefined, refetch });
    listScenarios.mockResolvedValue([]);

    renderPicker();

    expect(screen.getByTestId('replay-runs-error')).toBeInTheDocument();
    screen.getByRole('button', { name: 'Retry' }).click();
    expect(refetch).toHaveBeenCalled();
  });
});
