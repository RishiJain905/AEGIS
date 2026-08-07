import type { ReactNode } from 'react';

import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import type { GraphNodeV1 } from '@aegis/contracts-ts';

import { AssetDetailDrawer } from './asset-detail-drawer';

// The drawer reads the run's lifecycle to decide whether its action menu may execute.
// `null` stands for "no live run context", which is what every case except the terminal-run
// one renders under.
let liveRunStatus: string | null = null;
vi.mock('@/features/live-run', () => ({
  useLiveRun: () => (liveRunStatus === null ? null : { state: { runStatus: liveRunStatus } }),
}));

// Render the drawer primitives inline so the gating logic is exercised without Radix's
// pointer-capture portal (unavailable in jsdom).
vi.mock('@aegis/ui', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@aegis/ui')>();
  return {
    ...actual,
    Drawer: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DrawerContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DrawerHeader: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DrawerTitle: ({ children }: { children: ReactNode }) => <h2>{children}</h2>,
    DrawerDescription: ({ children }: { children: ReactNode }) => <p>{children}</p>,
  };
});

// The action menu's own confirm-gating is covered in asset-action-menu.test.tsx; here it is
// stubbed to a button that reflects the `disabled` prop the drawer threads through.
vi.mock('./asset-action-menu', () => ({
  AssetActionMenu: ({ disabled }: { disabled?: boolean }) => (
    <button type="button" disabled={disabled} data-testid="drawer-action-menu">
      Operator actions
    </button>
  ),
}));

const NODE: GraphNodeV1 = {
  schemaVersion: 1,
  id: 'asset:vpn-gw',
  entityType: 'asset',
  assetType: 'device',
  label: 'VPN Gateway',
  riskScore: 0.4,
  criticality: 0.8,
  status: 'suspicious',
  revision: 1,
  disclosed: true,
};

beforeAll(() => {
  Element.prototype.hasPointerCapture = vi.fn(() => false);
  Element.prototype.setPointerCapture = vi.fn();
  Element.prototype.releasePointerCapture = vi.fn();
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  liveRunStatus = null;
});

function renderDrawer() {
  return render(
    <AssetDetailDrawer
      runId="run_x"
      node={NODE}
      disclosed
      open
      onOpenChange={vi.fn()}
    />,
  );
}

describe('AssetDetailDrawer ended-run gating', () => {
  it('keeps the action menu live and explains the policy pipeline while the run is live', () => {
    liveRunStatus = 'running';
    renderDrawer();

    expect(screen.getByTestId('drawer-action-menu')).toBeEnabled();
    expect(screen.queryByTestId('drawer-run-ended-hint')).not.toBeInTheDocument();
    expect(screen.getByText(/routed through the same policy pipeline/i)).toBeInTheDocument();
  });

  it('disables the action menu and says why once the run is over', () => {
    // The deep dive read as buggy because its actions were the only dead ones left
    // reachable (P1, owner-reported 2026-08-07) — the hint has to be in the drawer.
    liveRunStatus = 'stopped';
    renderDrawer();

    expect(screen.getByTestId('drawer-action-menu')).toBeDisabled();
    expect(screen.getByTestId('drawer-run-ended-hint')).toHaveTextContent(
      'The run has ended — commands can no longer execute. The record stays readable.',
    );
    expect(screen.queryByText(/routed through the same policy pipeline/i)).not.toBeInTheDocument();
  });
});
