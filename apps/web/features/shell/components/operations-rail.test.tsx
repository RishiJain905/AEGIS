import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { setTheme, useTheme } = vi.hoisted(() => {
  const setThemeFn = vi.fn();
  return {
    setTheme: setThemeFn,
    useTheme: vi.fn(() => ({ theme: 'dark', resolvedTheme: 'dark', setTheme: setThemeFn })),
  };
});

vi.mock('@/features/shell/hooks/use-theme', () => ({ useTheme }));

vi.mock('next/navigation', () => ({ usePathname: () => '/scenarios' }));

// The rail's nav links resolve their run through `useActiveRunId`, which now confirms the
// run still exists before offering it as a destination. Nothing here is about a run, but the
// rail cannot render without the data layer that lookup goes through.
vi.mock('@/lib/api/api-client-provider', () => ({
  useApiClient: () => ({ getRun: vi.fn((runId: string) => Promise.resolve({ id: runId })) }),
}));

vi.mock('next/link', () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

import { OperationsRail } from '@/features/shell/components/operations-rail';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

function renderRail() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <OperationsRail />
    </QueryClientProvider>,
  );
}

describe('OperationsRail theme toggle', () => {
  beforeEach(() => {
    setTheme.mockReset();
    useTheme.mockReturnValue({ theme: 'dark', resolvedTheme: 'dark', setTheme });
    useWorkspaceUiStore.getState().setPanelCollapsed('operationsRail', false);
  });
  afterEach(() => {
    cleanup();
  });

  it('renders the theme toggle with an accessible name when expanded', () => {
    renderRail();
    const toggle = screen.getByTestId('toggle-theme');
    expect(toggle).toBeInTheDocument();
    expect(toggle).toHaveAccessibleName(/theme/i);
  });

  it('flips the explicit preference to light when the resolved theme is dark', () => {
    renderRail();
    fireEvent.click(screen.getByTestId('toggle-theme'));
    expect(setTheme).toHaveBeenCalledWith('light');
  });

  it('flips the explicit preference to dark when the resolved theme is light', () => {
    useTheme.mockReturnValue({ theme: 'light', resolvedTheme: 'light', setTheme });
    renderRail();
    fireEvent.click(screen.getByTestId('toggle-theme'));
    expect(setTheme).toHaveBeenCalledWith('dark');
  });

  it('keeps an accessible name on the toggle when the rail is collapsed', () => {
    useWorkspaceUiStore.getState().setPanelCollapsed('operationsRail', true);
    renderRail();
    const toggle = screen.getByTestId('toggle-theme');
    expect(toggle).toHaveAccessibleName(/switch to (light|dark) theme/i);
  });
});
