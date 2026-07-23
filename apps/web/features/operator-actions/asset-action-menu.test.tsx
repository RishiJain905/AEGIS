import type { ReactNode } from 'react';

import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import { AssetActionMenu } from './asset-action-menu';

// Capture operator-action submissions without a live network layer.
const mutate = vi.fn();
vi.mock('@/features/command-surface', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/command-surface')>();
  return {
    ...actual,
    useSubmitOperatorAction: () => ({ mutate, isPending: false }),
  };
});

// Render the dropdown primitives inline so the confirm-gating logic is exercised without
// Radix's pointer-capture portal (unavailable in jsdom). Items become plain buttons that
// fire onSelect on click — the behaviour AssetActionMenu depends on.
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
    }: {
      children: ReactNode;
      onSelect?: () => void;
    } & Record<string, unknown>) => (
      <button type="button" onClick={onSelect} {...rest}>
        {children}
      </button>
    ),
  };
});

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
});

function renderMenu() {
  return render(
    <AssetActionMenu runId="run_x" assetId="asset:vpn-gw" assetLabel="VPN Gateway" />,
  );
}

describe('AssetActionMenu confirm gating', () => {
  it('auto-executes a Class 0 action without a confirmation dialog', async () => {
    const user = userEvent.setup();
    renderMenu();
    await user.click(screen.getByTestId('action-item-observe'));
    expect(screen.queryByTestId('action-consequences-dialog')).not.toBeInTheDocument();
    expect(mutate).toHaveBeenCalledTimes(1);
    expect(mutate.mock.calls[0]?.[0]).toMatchObject({ command: 'observe', confirm: false });
  });

  it('requires confirmation before submitting a Class 2 action', async () => {
    const user = userEvent.setup();
    renderMenu();
    await user.click(screen.getByTestId('action-item-isolate'));
    // Dialog opens; nothing submitted yet.
    expect(await screen.findByTestId('action-consequences-dialog')).toBeInTheDocument();
    expect(mutate).not.toHaveBeenCalled();

    await user.type(screen.getByLabelText(/Justification/i), 'Contain lateral movement');
    await user.click(screen.getByTestId('action-confirm-execute'));
    await waitFor(() => {
      expect(mutate).toHaveBeenCalledTimes(1);
    });
    expect(mutate.mock.calls[0]?.[0]).toMatchObject({ command: 'isolate', confirm: true });
  });

  it('requires confirmation before submitting a Class 3 action', async () => {
    const user = userEvent.setup();
    renderMenu();
    await user.click(screen.getByTestId('action-item-restart_service'));
    expect(await screen.findByTestId('action-consequences-dialog')).toBeInTheDocument();
    expect(mutate).not.toHaveBeenCalled();
  });
});
