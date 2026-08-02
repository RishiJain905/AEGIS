import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/features/console', () => ({
  Chronicle: () => <div data-testid="chronicle-stub" />,
  Console: () => <div data-testid="cockpit-console" />,
  CopilotSheet: () => <div data-testid="copilot-sheet-stub" />,
}));
vi.mock('@/features/shell/components/inspector-sheet', () => ({
  InspectorSheet: () => <div data-testid="inspector-sheet-stub" />,
}));
vi.mock('@/features/shell/components/visualization-slot', () => ({
  VisualizationSlot: () => <div data-testid="visualization-slot" />,
}));
vi.mock('@/features/signals', () => ({
  SignalsStack: () => <div data-testid="signals-stack-stub" />,
}));

import { RunWorkspace } from '@/features/shell/components/run-workspace';
import { defaultOperatorWorkspaceState } from '@/features/shell/contracts/operator-workspace-state';
import { useCockpitUiStore } from '@/stores/cockpit-ui-store';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

const RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

beforeEach(() => {
  vi.clearAllMocks();
  useWorkspaceUiStore.setState({
    workspace: { ...defaultOperatorWorkspaceState },
    activeRunId: RUN_ID,
  });
  useWorkspaceUiStore.getState().setPanelCollapsed('rightDock', false);
  useCockpitUiStore.getState().resetCockpitUi();
});

afterEach(() => {
  cleanup();
  useCockpitUiStore.getState().resetCockpitUi();
});

describe('RunWorkspace stage', () => {
  it('mounts signals, both context sheets and the chronicle over the stage, console at its foot', () => {
    render(<RunWorkspace runId={RUN_ID} />);
    const stage = screen.getByTestId('cockpit-stage');
    expect(stage).toContainElement(screen.getByTestId('visualization-slot'));
    expect(stage).toContainElement(screen.getByTestId('signals-stack-stub'));
    expect(stage).toContainElement(screen.getByTestId('inspector-sheet-stub'));
    expect(stage).toContainElement(screen.getByTestId('copilot-sheet-stub'));
    expect(stage).toContainElement(screen.getByTestId('chronicle-stub'));
    expect(screen.getByTestId('cockpit-console')).toBeInTheDocument();
  });

  it('has no docks left — one stage, no walls', () => {
    render(<RunWorkspace runId={RUN_ID} />);
    expect(screen.queryByTestId('left-dock')).not.toBeInTheDocument();
    expect(screen.queryByTestId('right-dock')).not.toBeInTheDocument();
  });
});

describe('RunWorkspace inspector sheet summoning', () => {
  it('summons the sheet when the operator names a node', () => {
    render(<RunWorkspace runId={RUN_ID} />);
    expect(useCockpitUiStore.getState().inspectorSheetOpen).toBe(false);

    act(() => {
      useWorkspaceUiStore.getState().setSelectedEntityId('asset:web-01');
    });
    expect(useCockpitUiStore.getState().inspectorSheetOpen).toBe(true);
  });

  it('summons the sheet when a case opens', () => {
    render(<RunWorkspace runId={RUN_ID} />);
    act(() => {
      useWorkspaceUiStore.getState().setSelectedIncidentId('incident:inc_1');
    });
    expect(useCockpitUiStore.getState().inspectorSheetOpen).toBe(true);
  });

  it('retracts the sheet when its subject deselects', () => {
    render(<RunWorkspace runId={RUN_ID} />);
    act(() => {
      useWorkspaceUiStore.getState().setSelectedEntityId('asset:web-01');
    });
    expect(useCockpitUiStore.getState().inspectorSheetOpen).toBe(true);

    act(() => {
      useWorkspaceUiStore.getState().setSelectedEntityId(null);
    });
    expect(useCockpitUiStore.getState().inspectorSheetOpen).toBe(false);
  });

  it('lets a dismissal stick until the operator names something again', () => {
    render(<RunWorkspace runId={RUN_ID} />);
    act(() => {
      useWorkspaceUiStore.getState().setSelectedEntityId('asset:web-01');
    });
    act(() => {
      useCockpitUiStore.getState().setInspectorSheetOpen(false);
    });
    expect(useCockpitUiStore.getState().inspectorSheetOpen).toBe(false);

    act(() => {
      useWorkspaceUiStore.getState().setSelectedEntityId('asset:db-02');
    });
    expect(useCockpitUiStore.getState().inspectorSheetOpen).toBe(true);
  });
});

describe('RunWorkspace keyboard vocabulary', () => {
  it('toggles the inspector sheet on I and the copilot sheet on C', () => {
    render(<RunWorkspace runId={RUN_ID} />);

    fireEvent.keyDown(window, { key: 'i' });
    expect(useCockpitUiStore.getState().inspectorSheetOpen).toBe(true);
    fireEvent.keyDown(window, { key: 'i' });
    expect(useCockpitUiStore.getState().inspectorSheetOpen).toBe(false);

    fireEvent.keyDown(window, { key: 'c' });
    expect(useCockpitUiStore.getState().copilotSheetOpen).toBe(true);
  });

  it('toggles the chronicle on T', () => {
    render(<RunWorkspace runId={RUN_ID} />);
    fireEvent.keyDown(window, { key: 't' });
    expect(useCockpitUiStore.getState().chronicleOpen).toBe(true);
    fireEvent.keyDown(window, { key: 'T' });
    expect(useCockpitUiStore.getState().chronicleOpen).toBe(false);
  });

  it('Escape closes the topmost summoned surface, then deselects', () => {
    render(<RunWorkspace runId={RUN_ID} />);
    act(() => {
      useWorkspaceUiStore.getState().setSelectedEntityId('asset:web-01');
      useCockpitUiStore.getState().setCopilotSheetOpen(true);
    });
    expect(useCockpitUiStore.getState().inspectorSheetOpen).toBe(true);

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(useCockpitUiStore.getState().inspectorSheetOpen).toBe(false);
    expect(useCockpitUiStore.getState().copilotSheetOpen).toBe(true);

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(useCockpitUiStore.getState().copilotSheetOpen).toBe(false);

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(useWorkspaceUiStore.getState().workspace.selectedEntityId).toBeNull();
  });

  it('stays quiet inside typing contexts', () => {
    render(
      <div>
        <input aria-label="scratch" />
        <RunWorkspace runId={RUN_ID} />
      </div>,
    );
    const input = screen.getByLabelText('scratch');
    input.focus();
    fireEvent.keyDown(input, { key: 'i' });
    expect(useCockpitUiStore.getState().inspectorSheetOpen).toBe(false);
  });
});
