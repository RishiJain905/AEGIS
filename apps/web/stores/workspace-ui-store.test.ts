import { beforeEach, describe, expect, it } from 'vitest';

import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

describe('workspace ui store', () => {
  beforeEach(() => {
    useWorkspaceUiStore.setState({
      workspace: {
        schemaVersion: 1,
        selectedEntityId: null,
        selectedIncidentId: null,
        commandPaletteOpen: false,
        timelineCursorSequence: null,
        presentationMode: 'live',
        focusRestorationToken: null,
      },
      panelPreferences: {
        schemaVersion: 1,
        regions: {
          operationsRail: { docked: true, collapsed: false, width: null },
          inspector: { docked: true, collapsed: false, width: 360 },
          timeline: { docked: true, collapsed: false, width: null },
          visualization: { docked: true, collapsed: false, width: null },
        },
      },
      activeRunId: null,
      mobileRailOpen: false,
    });
  });

  it('toggles inspector collapse', () => {
    useWorkspaceUiStore.getState().togglePanelCollapsed('inspector');
    expect(useWorkspaceUiStore.getState().panelPreferences.regions.inspector?.collapsed).toBe(true);
  });

  it('resets workspace state when run changes', () => {
    useWorkspaceUiStore.getState().setSelectedEntityId('asset:test');
    useWorkspaceUiStore.getState().resetForRun('run_a');
    expect(useWorkspaceUiStore.getState().workspace.selectedEntityId).toBeNull();
    expect(useWorkspaceUiStore.getState().activeRunId).toBe('run_a');
  });

  it('resets graph visual state when run changes', async () => {
    const { useGraphVisualStore } = await import(
      '@/features/operational-graph/stores/graph-visual-store'
    );
    useGraphVisualStore.getState().setSearchQuery('test-query');
    useWorkspaceUiStore.getState().resetForRun('run_b');
    expect(useGraphVisualStore.getState().visualState.searchQuery).toBe('');
  });

  it('opens command palette', () => {
    useWorkspaceUiStore.getState().setCommandPaletteOpen(true);
    expect(useWorkspaceUiStore.getState().workspace.commandPaletteOpen).toBe(true);
  });
});
