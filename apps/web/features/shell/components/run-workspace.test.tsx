import { act, cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { useLiveRun } = vi.hoisted(() => ({
  useLiveRun: vi.fn(),
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
vi.mock('@/features/shell/components/inspector-panel', () => ({
  InspectorPanel: () => <p>inspector stub</p>,
}));
vi.mock('@/features/shell/components/visualization-slot', () => ({
  VisualizationSlot: () => <div data-testid="visualization-slot" />,
}));
vi.mock('@/features/signals', () => ({
  SignalsStack: () => <div data-testid="signals-stack-stub" />,
}));
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
});

afterEach(() => {
  cleanup();
});

describe('RunWorkspace stage', () => {
  it('mounts the signals stack over the stage, beside the graph', () => {
    render(<RunWorkspace runId={RUN_ID} />);
    const stage = screen.getByTestId('cockpit-stage');
    expect(stage).toContainElement(screen.getByTestId('visualization-slot'));
    expect(stage).toContainElement(screen.getByTestId('signals-stack-stub'));
  });

  it('mounts the console at the foot of the stage', () => {
    render(<RunWorkspace runId={RUN_ID} />);
    expect(screen.getByTestId('cockpit-console')).toBeInTheDocument();
    expect(screen.getByTestId('live-run-controls')).toBeInTheDocument();
    expect(screen.getByTestId('asset-command-bar')).toBeInTheDocument();
  });
});

describe('RunWorkspace situation channel', () => {
  it('opens on the Inspector — alerts live on the stage now', () => {
    render(<RunWorkspace runId={RUN_ID} />);
    expect(screen.getByText('inspector stub')).toBeInTheDocument();
  });

  it('follows a graph selection back to the Inspector tab', async () => {
    const user = userEvent.setup();
    render(<RunWorkspace runId={RUN_ID} />);
    await user.click(screen.getByTestId('dock-tab-feed'));
    expect(screen.queryByText('inspector stub')).not.toBeInTheDocument();

    act(() => {
      useWorkspaceUiStore.getState().setSelectedEntityId('asset:web-01');
    });
    expect(screen.getByText('inspector stub')).toBeInTheDocument();
  });

  it('follows an opened case back to the Inspector tab', async () => {
    const user = userEvent.setup();
    render(<RunWorkspace runId={RUN_ID} />);
    await user.click(screen.getByTestId('dock-tab-feed'));

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
