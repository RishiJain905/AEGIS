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
});

function renderBar() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AssetCommandBar runId="run_x" />
    </QueryClientProvider>,
  );
}

const VPN_GATEWAY: SelectedAsset = {
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
  },
  disclosed: true,
};

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
    expect(screen.getByTestId('action-item-rollback_deployment')).toBeInTheDocument();
  });
});
