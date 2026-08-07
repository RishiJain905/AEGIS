import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';

import { RestartRunControl } from './restart-run-control';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

let runData: unknown = undefined;
vi.mock('@/features/shell/hooks/use-shell-queries', () => ({
  useRun: () => ({ data: runData }),
}));

vi.mock('./use-run-commands', () => ({
  useCreateRun: () => ({
    mutateAsync: vi.fn().mockResolvedValue({ run: { id: 'run_x' } }),
    isPending: false,
  }),
}));

vi.mock('./live-run-provider', () => ({
  useLiveRun: () => ({ state: { runStatus: 'stopped' } }),
}));

vi.mock('@/features/tutorial/tutorial-storage', () => ({
  armTutorial: vi.fn(),
}));

function Wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

beforeAll(() => {
  Element.prototype.hasPointerCapture = vi.fn(() => false);
  Element.prototype.setPointerCapture = vi.fn();
  Element.prototype.releasePointerCapture = vi.fn();
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  runData = undefined;
});

describe('RestartRunControl accessibility', () => {
  it('renders the terminal-cockpit control without axe violations', async () => {
    runData = {
      id: 'run_x',
      scenarioVersionId: 'scenario-version:1.0.0-silent-relay',
      seed: 424242,
      status: 'stopped',
    };
    const { container } = render(
      <Wrapper>
        <RestartRunControl runId="run_x" />
      </Wrapper>,
    );

    expect(screen.getByTestId('live-restart')).toBeInTheDocument();
    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });

  it('renders the open confirm dialog without axe violations', async () => {
    const user = userEvent.setup();
    runData = {
      id: 'run_x',
      scenarioVersionId: 'scenario-version:1.0.0-silent-relay',
      seed: 424242,
      status: 'stopped',
    };
    render(
      <Wrapper>
        <RestartRunControl runId="run_x" />
      </Wrapper>,
    );

    await user.click(screen.getByTestId('live-restart'));
    expect(await screen.findByTestId('restart-run-dialog')).toBeInTheDocument();

    // The dialog renders through a Radix portal, so the axe pass must cover the document
    // rather than the render container.
    const results = await axe(document.body);
    expect(results.violations).toHaveLength(0);
  });
});
