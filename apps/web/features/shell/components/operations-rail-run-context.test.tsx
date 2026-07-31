/**
 * BUG-009: "Active run" navigated to /scenarios instead of the run the operator was on.
 *
 * The rail resolved the run from the URL alone, so every non-run surface (Incidents,
 * Reports, the catalogue) answered "no run" and the link silently pointed at the
 * catalogue — which, clicked from the catalogue, went nowhere at all.
 */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { useTheme, usePathname, useOptionalAuth } = vi.hoisted(() => ({
  useTheme: vi.fn(() => ({ theme: 'dark', resolvedTheme: 'dark', setTheme: vi.fn() })),
  usePathname: vi.fn(() => '/scenarios'),
  useOptionalAuth: vi.fn<() => { actor: { userId: string } | null } | null>(() => ({
    actor: { userId: 'user:operator-alpha' },
  })),
}));

vi.mock('@/features/shell/hooks/use-theme', () => ({ useTheme }));
vi.mock('next/navigation', () => ({ usePathname }));
vi.mock('@/features/auth', () => ({ useOptionalAuth }));

vi.mock('next/link', () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

import { OperationsRail } from '@/features/shell/components/operations-rail';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

const RUN_ID = 'run_8024W2GZ4PMQ02P8FXTH840AY6';
const OPERATOR = 'user:operator-alpha';

function activeRunLink(): HTMLElement | null {
  return screen.queryByRole('link', { name: 'Active run' });
}

describe('OperationsRail run-scoped destinations', () => {
  beforeEach(() => {
    usePathname.mockReturnValue('/scenarios');
    useOptionalAuth.mockReturnValue({ actor: { userId: OPERATOR } });
    useWorkspaceUiStore.getState().clearRunContext();
    useWorkspaceUiStore.getState().setPanelCollapsed('operationsRail', false);
  });
  afterEach(() => {
    cleanup();
  });

  it('points at the run named by the route', () => {
    usePathname.mockReturnValue(`/runs/${RUN_ID}`);
    render(<OperationsRail />);

    expect(activeRunLink()).toHaveAttribute('href', `/runs/${RUN_ID}`);
    expect(screen.getByRole('link', { name: 'Replay' })).toHaveAttribute(
      'href',
      `/replay/${RUN_ID}`,
    );
  });

  it('remembers the run after the operator leaves the run surface', () => {
    usePathname.mockReturnValue(`/runs/${RUN_ID}`);
    const { unmount } = render(<OperationsRail />);
    unmount();

    // Incidents is not run-scoped, so the route no longer names the run.
    usePathname.mockReturnValue('/incidents');
    render(<OperationsRail />);

    expect(activeRunLink()).toHaveAttribute('href', `/runs/${RUN_ID}`);
  });

  it('ignores and clears a run remembered for a different identity', () => {
    useWorkspaceUiStore
      .getState()
      .rememberRunContext({ runId: RUN_ID, userId: 'user:admin-alpha' });

    render(<OperationsRail />);

    expect(activeRunLink()).toBeNull();
    expect(screen.getByTestId('rail-pulse-disabled')).toBeInTheDocument();
    expect(useWorkspaceUiStore.getState().runContext).toBeNull();
  });

  it('keeps a remembered run while the session is still resolving', () => {
    useWorkspaceUiStore.getState().rememberRunContext({ runId: RUN_ID, userId: OPERATOR });
    useOptionalAuth.mockReturnValue({ actor: null });

    render(<OperationsRail />);

    // No identity yet is not a mismatched identity: dropping it here would lose the run on
    // every reload, before the session query resolves.
    expect(useWorkspaceUiStore.getState().runContext).toEqual({
      runId: RUN_ID,
      userId: OPERATOR,
    });
  });

  it('disables run-scoped destinations instead of linking to the catalogue', () => {
    render(<OperationsRail />);

    expect(activeRunLink()).toBeNull();
    for (const testId of ['rail-pulse-disabled', 'rail-review-disabled']) {
      const button = screen.getByTestId(testId);
      expect(button).toHaveAttribute('aria-disabled', 'true');
      expect(button).toHaveAttribute('title', expect.stringContaining('No active run'));
    }
    // Destinations that do not depend on a run are unaffected.
    expect(screen.getByRole('link', { name: 'Scenarios' })).toHaveAttribute('href', '/scenarios');
    // Replay is run-scoped but its base renders a run picker, so it stays reachable.
    expect(screen.getByRole('link', { name: 'Replay' })).toHaveAttribute('href', '/replay');
  });
});
