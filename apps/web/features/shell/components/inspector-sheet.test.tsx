import { act, cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/features/shell/components/inspector-panel', () => ({
  InspectorPanel: () => <p>inspector body</p>,
}));

import { InspectorSheet } from './inspector-sheet';
import { defaultOperatorWorkspaceState } from '@/features/shell/contracts/operator-workspace-state';
import { useCockpitUiStore } from '@/stores/cockpit-ui-store';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

const RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

beforeEach(() => {
  useCockpitUiStore.getState().resetCockpitUi();
  useWorkspaceUiStore.setState({ workspace: { ...defaultOperatorWorkspaceState } });
});

afterEach(() => {
  cleanup();
  useCockpitUiStore.getState().resetCockpitUi();
});

describe('InspectorSheet', () => {
  it('stays away until summoned', () => {
    render(<InspectorSheet runId={RUN_ID} />);
    expect(screen.queryByTestId('inspector-sheet')).not.toBeInTheDocument();
  });

  it('opens as a right-side dialog around the inspector, named for its subject', () => {
    act(() => {
      useWorkspaceUiStore.getState().setSelectedEntityId('asset:web-01');
      useCockpitUiStore.getState().setInspectorSheetOpen(true);
    });
    render(<InspectorSheet runId={RUN_ID} />);

    const sheet = screen.getByRole('dialog', { name: 'Inspector' });
    expect(sheet).toHaveAttribute('data-side', 'right');
    expect(sheet).toHaveAttribute('data-budget', 'solo');
    expect(screen.getByText('asset:web-01')).toBeInTheDocument();
    expect(screen.getByText('inspector body')).toBeInTheDocument();
  });

  it('shares the space budget when the copilot sheet holds the other side', () => {
    act(() => {
      useCockpitUiStore.getState().setInspectorSheetOpen(true);
      useCockpitUiStore.getState().setCopilotSheetOpen(true);
    });
    render(<InspectorSheet runId={RUN_ID} />);
    expect(screen.getByTestId('inspector-sheet')).toHaveAttribute('data-budget', 'shared');
  });

  it('dismisses through its close control', async () => {
    const user = userEvent.setup();
    act(() => {
      useCockpitUiStore.getState().setInspectorSheetOpen(true);
    });
    render(<InspectorSheet runId={RUN_ID} />);

    await user.click(screen.getByTestId('inspector-sheet-close'));
    expect(useCockpitUiStore.getState().inspectorSheetOpen).toBe(false);
  });
});
