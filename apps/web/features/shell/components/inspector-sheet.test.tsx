import { act, cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { useInspectorGraph } = vi.hoisted(() => ({
  useInspectorGraph: vi.fn(),
}));

vi.mock('@/features/shell/components/inspector-panel', () => ({
  InspectorPanel: () => <p>inspector body</p>,
}));
vi.mock('@/features/inspector', () => ({
  useInspectorGraph,
}));

import { InspectorSheet } from './inspector-sheet';
import { defaultOperatorWorkspaceState } from '@/features/shell/contracts/operator-workspace-state';
import { useCockpitUiStore } from '@/stores/cockpit-ui-store';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

const RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

function graphWith(nodes: { id: string; label: string }[]) {
  return { snapshot: { nodes }, isPending: false, isError: false, refetch: vi.fn() };
}

beforeEach(() => {
  vi.clearAllMocks();
  useInspectorGraph.mockReturnValue(graphWith([]));
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

  it('opens as a right-side dialog around the inspector', () => {
    act(() => {
      useWorkspaceUiStore.getState().setSelectedEntityId('asset:device-analyst-01');
      useCockpitUiStore.getState().setInspectorSheetOpen(true);
    });
    render(<InspectorSheet runId={RUN_ID} />);

    const sheet = screen.getByRole('dialog', { name: 'Inspector' });
    expect(sheet).toHaveAttribute('data-side', 'right');
    expect(sheet).toHaveAttribute('data-budget', 'solo');
    expect(screen.getByText('inspector body')).toBeInTheDocument();
  });

  // The subject is a thing in the estate, not a row key.
  it('names its subject by display name, keeping the id underneath', () => {
    useInspectorGraph.mockReturnValue(
      graphWith([{ id: 'asset:device-analyst-01', label: 'Analyst workstation' }]),
    );
    act(() => {
      useWorkspaceUiStore.getState().setSelectedEntityId('asset:device-analyst-01');
      useCockpitUiStore.getState().setInspectorSheetOpen(true);
    });
    render(<InspectorSheet runId={RUN_ID} />);

    expect(screen.getByTestId('inspector-sheet-subject')).toHaveTextContent('Analyst workstation');
    expect(screen.getByTestId('inspector-sheet-subject-detail')).toHaveTextContent(
      'asset:device-analyst-01',
    );
  });

  it('falls back to the id when the graph does not know the subject', () => {
    act(() => {
      useWorkspaceUiStore.getState().setSelectedEntityId('incident:inc_a');
      useCockpitUiStore.getState().setInspectorSheetOpen(true);
    });
    render(<InspectorSheet runId={RUN_ID} />);

    expect(screen.getByTestId('inspector-sheet-subject')).toHaveTextContent('incident:inc_a');
    expect(screen.queryByTestId('inspector-sheet-subject-detail')).not.toBeInTheDocument();
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

  // Summoning the sheet folds the signals stack the invoker lived on, so the sheet has no
  // connected element to hand focus back to. Without a fallback, focus lands on <body> and
  // the keyboard operator loses the room.
  it('hands focus to the signals capsule when the invoker folded away', async () => {
    const user = userEvent.setup();
    const capsule = document.createElement('button');
    capsule.dataset.testid = 'signals-capsule';
    capsule.setAttribute('data-testid', 'signals-capsule');
    document.body.append(capsule);

    const invoker = document.createElement('button');
    document.body.append(invoker);
    invoker.focus();

    const { rerender } = render(<InspectorSheet runId={RUN_ID} />);
    act(() => {
      useCockpitUiStore.getState().setInspectorSheetOpen(true);
    });
    rerender(<InspectorSheet runId={RUN_ID} />);
    // The card that summoned the sheet is gone the moment the sheet claims the right side.
    invoker.remove();

    await user.click(screen.getByTestId('inspector-sheet-close'));
    expect(capsule).toHaveFocus();

    capsule.remove();
  });
});
