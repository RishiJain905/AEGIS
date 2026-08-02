import type { ReactNode } from 'react';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import type { SelectedAsset } from './use-selected-asset';

const mutate = vi.fn();
vi.mock('@/features/command-surface', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/command-surface')>();
  return {
    ...actual,
    useSubmitOperatorAction: () => ({ mutate, isPending: false }),
  };
});

// The command bar resolves its asset from the authoritative graph projection; the layout
// and dispatch behaviour under test do not need the query stack behind it.
let selected: SelectedAsset | null = null;
vi.mock('./use-selected-asset', () => ({
  useSelectedAsset: () => selected,
}));

// The deep-dive drawer pulls asset detail; it is closed in every case here.
vi.mock('./asset-detail-drawer', () => ({
  AssetDetailDrawer: () => null,
}));

// The bar reads the run's lifecycle to decide whether commands can execute at all. `null`
// stands for "no live run context", which is what every case below except the terminal-run
// ones renders under.
let liveRunStatus: string | null = null;
vi.mock('@/features/live-run', () => ({
  useLiveRun: () => (liveRunStatus === null ? null : { state: { runStatus: liveRunStatus } }),
}));

vi.mock('@aegis/ui', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@aegis/ui')>();
  return {
    ...actual,
    DropdownMenu: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DropdownMenuTrigger: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DropdownMenuContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DropdownMenuLabel: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DropdownMenuSeparator: () => <hr />,
    DropdownMenuItem: ({
      children,
      onSelect,
      ...rest
    }: { children: ReactNode; onSelect?: () => void } & Record<string, unknown>) => (
      <button type="button" onClick={onSelect} {...rest}>
        {children}
      </button>
    ),
  };
});

import { AssetCommandBar } from './asset-command-bar';

beforeAll(() => {
  Element.prototype.hasPointerCapture = vi.fn(() => false);
  Element.prototype.setPointerCapture = vi.fn();
  Element.prototype.releasePointerCapture = vi.fn();
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  selected = null;
  liveRunStatus = null;
});

function renderBar() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AssetCommandBar runId="run_x" />
    </QueryClientProvider>,
  );
}

function asset(overrides: Partial<SelectedAsset['node']>): SelectedAsset {
  return {
    node: {
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
      ...overrides,
    },
    disclosed: true,
  };
}

const VPN_GATEWAY = asset({});
const CUSTOMER_DATABASE = asset({
  id: 'asset:database-customer-pii',
  assetType: 'database',
  label: 'Customer PII Database',
});

describe('AssetCommandBar', () => {
  it('prompts for a selection instead of disappearing when nothing is selected', () => {
    renderBar();
    const bar = screen.getByTestId('asset-command-bar');
    expect(bar).toHaveAttribute('data-state', 'empty');
    expect(bar).toHaveTextContent(/right-click a node/i);
  });

  it('dispatches a quick action on the selected asset in a single click', async () => {
    const user = userEvent.setup();
    selected = VPN_GATEWAY;
    renderBar();

    expect(screen.getByTestId('command-bar-asset-label')).toHaveTextContent('VPN Gateway');

    await user.click(screen.getByTestId('command-bar-action-observe'));

    expect(screen.queryByTestId('action-consequences-dialog')).not.toBeInTheDocument();
    expect(mutate).toHaveBeenCalledTimes(1);
    expect(mutate.mock.calls[0]?.[0]).toMatchObject({
      command: 'observe',
      targetAssetId: 'asset:vpn-gw',
      confirm: false,
    });
  });

  it('gates a confirm-required quick action behind the consequences dialog', async () => {
    const user = userEvent.setup();
    selected = VPN_GATEWAY;
    renderBar();

    await user.click(screen.getByTestId('command-bar-action-isolate'));

    expect(await screen.findByTestId('action-consequences-dialog')).toBeInTheDocument();
    expect(mutate).not.toHaveBeenCalled();
  });

  it('keeps every remaining command reachable from the overflow menu', () => {
    selected = VPN_GATEWAY;
    renderBar();

    // Quick buttons cover the head of the catalogue; the menu still lists all of it,
    // including the commands that did not fit.
    expect(screen.getByTestId('command-bar-all-actions')).toBeInTheDocument();
    expect(screen.getByTestId('action-item-restart_service')).toBeInTheDocument();
  });

  it('offers the verbs that fit the selected asset class, not one list for everything', () => {
    selected = VPN_GATEWAY;
    const { unmount } = renderBar();

    // An endpoint: isolate the host, kill the process on it.
    expect(screen.getByTestId('command-bar-action-isolate')).toHaveTextContent('Isolate host');
    expect(screen.getByTestId('action-item-restart_service')).toHaveTextContent(
      'Kill malicious process',
    );
    expect(screen.queryByTestId('action-item-rollback_deployment')).not.toBeInTheDocument();
    unmount();

    // A datastore: lock it down and rotate its logins. It is not a deployment, so nothing
    // in the critical tier applies and the tier's heading drops out with it.
    selected = CUSTOMER_DATABASE;
    renderBar();

    expect(screen.getByTestId('command-bar-action-restrict_access')).toBeInTheDocument();
    expect(screen.getByTestId('action-item-revoke_credentials')).toHaveTextContent(
      'Rotate database credentials',
    );
    expect(screen.queryByTestId('action-item-restart_service')).not.toBeInTheDocument();
    expect(screen.queryByTestId('action-item-rollback_deployment')).not.toBeInTheDocument();
    expect(screen.queryByText(/Critical · needs confirm/)).not.toBeInTheDocument();
  });

  it('confirms the action under the same name the operator clicked', async () => {
    const user = userEvent.setup();
    selected = VPN_GATEWAY;
    renderBar();

    await user.click(screen.getByTestId('action-item-restart_service'));

    const dialog = await screen.findByTestId('action-consequences-dialog');
    expect(dialog).toHaveTextContent('Kill malicious process');
    expect(dialog).not.toHaveTextContent('Restart service');
  });

  describe('once the run is over', () => {
    // The workspace already shows "RUN ENDED — commands can no longer execute" directly above
    // this bar. Saying that while every button still invites a click teaches the operator the
    // sentence is decoration; the controls have to agree with the ribbon.
    it.each(['stopped', 'completed', 'failed', 'aborted'])(
      'disables the command controls when the run is %s',
      (runStatus) => {
        selected = CUSTOMER_DATABASE;
        liveRunStatus = runStatus;
        renderBar();

        expect(screen.getByTestId('command-bar-action-restrict_access')).toBeDisabled();
        expect(screen.getByTestId('command-bar-all-actions')).toBeDisabled();
      },
    );

    it('leaves the read-only deep dive reachable', () => {
      // Examining what happened is most of what an ended run is for.
      selected = VPN_GATEWAY;
      liveRunStatus = 'stopped';
      renderBar();

      expect(screen.getByTestId('open-asset-deep-dive')).toBeEnabled();
    });

    it.each(['running', 'paused'])('keeps commands live while the run is %s', (runStatus) => {
      selected = VPN_GATEWAY;
      liveRunStatus = runStatus;
      renderBar();

      expect(screen.getByTestId('command-bar-action-observe')).toBeEnabled();
    });
  });
});
