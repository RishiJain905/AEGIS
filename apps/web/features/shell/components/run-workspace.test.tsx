import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { useLiveRun, useRunAlerts } = vi.hoisted(() => ({
  useLiveRun: vi.fn(),
  useRunAlerts: vi.fn(),
}));

vi.mock('@/features/agent-chat', () => ({ AgentChatPanel: () => <p>copilot stub</p> }));
vi.mock('@/features/live-run', () => ({
  LiveRunControls: () => <div data-testid="live-run-controls" />,
  useLiveRun,
}));
vi.mock('@/features/operator-console', () => ({
  EventSearch: () => null,
  HypothesisLedger: () => null,
}));
vi.mock('@/features/operator-actions', () => ({
  AssetCommandBar: () => <div data-testid="asset-command-bar" />,
}));
vi.mock('@/features/ops-feed', () => ({ OpsFeedPanel: () => <p>feed stub</p> }));
vi.mock('@/features/shell/components/alerts-tab', () => ({
  AlertsTab: () => <p>alerts stub</p>,
}));
vi.mock('@/features/shell/components/inspector-panel', () => ({
  InspectorPanel: () => <p>inspector stub</p>,
}));
vi.mock('@/features/shell/components/visualization-slot', () => ({
  VisualizationSlot: () => <div data-testid="visualization-slot" />,
}));
vi.mock('@/features/shell/hooks/use-shell-queries', () => ({ useRunAlerts }));
vi.mock('@/features/timeline', () => ({ RunTape: () => null }));

import { RunWorkspace } from '@/features/shell/components/run-workspace';
import { defaultOperatorWorkspaceState } from '@/features/shell/contracts/operator-workspace-state';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

const RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

function liveRunWithStatus(runStatus: string) {
  return {
    isLiveMode: true,
    state: { runStatus },
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  useWorkspaceUiStore.setState({
    workspace: { ...defaultOperatorWorkspaceState },
    activeRunId: RUN_ID,
  });
  useWorkspaceUiStore.getState().setPanelCollapsed('rightDock', false);
  useWorkspaceUiStore.getState().setPanelCollapsed('leftDock', false);
  useLiveRun.mockReturnValue(null);
  useRunAlerts.mockReturnValue({ data: [] });
});

afterEach(() => {
  cleanup();
});

describe('RunWorkspace situation channel', () => {
  it('opens on the Alerts tab — attention comes before context', () => {
    render(<RunWorkspace runId={RUN_ID} />);
    expect(screen.getByText('alerts stub')).toBeInTheDocument();
    expect(screen.queryByText('inspector stub')).not.toBeInTheDocument();
  });

  it('shows a live alert count on the Alerts tab', () => {
    useRunAlerts.mockReturnValue({ data: [{ id: 'a1' }, { id: 'a2' }] });
    render(<RunWorkspace runId={RUN_ID} />);
    expect(screen.getByTestId('dock-tab-badge-alerts')).toHaveTextContent('2');
  });

  it('follows a graph selection to the Inspector tab', () => {
    render(<RunWorkspace runId={RUN_ID} />);
    act(() => {
      useWorkspaceUiStore.getState().setSelectedEntityId('asset:web-01');
    });
    expect(screen.getByText('inspector stub')).toBeInTheDocument();
  });

  it('follows an opened case to the Inspector tab', () => {
    render(<RunWorkspace runId={RUN_ID} />);
    act(() => {
      useWorkspaceUiStore.getState().setSelectedIncidentId('incident:inc_1');
    });
    expect(screen.getByText('inspector stub')).toBeInTheDocument();
  });
});

describe('RunWorkspace execution semantics (BUG-012)', () => {
  it('says nothing about the timeline while the sim is running', () => {
    useLiveRun.mockReturnValue(liveRunWithStatus('running'));
    render(<RunWorkspace runId={RUN_ID} />);
    expect(screen.queryByTestId('frozen-timeline-notice')).not.toBeInTheDocument();
    expect(screen.queryByTestId('run-ended-notice')).not.toBeInTheDocument();
  });

  it('states frozen-timeline execution semantics while paused', () => {
    useLiveRun.mockReturnValue(liveRunWithStatus('paused'));
    render(<RunWorkspace runId={RUN_ID} />);
    expect(screen.getByTestId('frozen-timeline-notice')).toHaveTextContent(/frozen timeline/i);
  });

  it('states read-only semantics once the run has ended', () => {
    useLiveRun.mockReturnValue(liveRunWithStatus('stopped'));
    render(<RunWorkspace runId={RUN_ID} />);
    expect(screen.getByTestId('run-ended-notice')).toHaveTextContent(/read-only/i);
  });
});
