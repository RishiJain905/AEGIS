import type { ReactNode } from 'react';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

const mutate = vi.fn();
vi.mock('@/features/command-surface', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/command-surface')>();
  return {
    ...actual,
    useSubmitOperatorAction: () => ({ mutate, isPending: false }),
  };
});

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

import { AssetContextMenu, type AssetContextTarget } from './asset-context-menu';

beforeAll(() => {
  Element.prototype.hasPointerCapture = vi.fn(() => false);
  Element.prototype.setPointerCapture = vi.fn();
  Element.prototype.releasePointerCapture = vi.fn();
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function renderMenu(target: Partial<AssetContextTarget>) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AssetContextMenu
        runId="run_x"
        target={{
          nodeId: 'asset:node',
          label: 'Node',
          assetType: 'service',
          x: 10,
          y: 20,
          ...target,
        }}
        onDismiss={vi.fn()}
      />
    </QueryClientProvider>,
  );
}

describe('AssetContextMenu', () => {
  it('follows the same per-asset-class catalogue as the other action surfaces', () => {
    const { unmount } = renderMenu({
      nodeId: 'asset:database-customer-pii',
      label: 'Customer PII Database',
      assetType: 'database',
    });

    expect(screen.getByTestId('action-item-restrict_access')).toBeInTheDocument();
    expect(screen.queryByTestId('action-item-rollback_deployment')).not.toBeInTheDocument();
    unmount();

    renderMenu({
      nodeId: 'asset:svc-logistics-api',
      label: 'Logistics Routing API',
      assetType: 'service',
    });

    expect(screen.getByTestId('action-item-rollback_deployment')).toBeInTheDocument();
    expect(screen.getByTestId('action-item-isolate')).toHaveTextContent('Isolate service');
  });
});
