import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const {
  fetchIncident,
  useIncident,
  useRun,
  useRunIncidents,
  useRunAlerts,
  useRunRiskScores,
  useRunGraph,
} = vi.hoisted(() => ({
  fetchIncident: vi.fn(),
  useIncident: vi.fn(),
  useRun: vi.fn(),
  useRunIncidents: vi.fn(),
  useRunAlerts: vi.fn(),
  useRunRiskScores: vi.fn(),
  useRunGraph: vi.fn(),
}));

vi.mock('@/features/shell/hooks/use-shell-queries', () => ({
  useIncident,
  useRun,
  useRunIncidents,
  useRunAlerts,
  useRunRiskScores,
  useRunGraph,
}));

// The investigation, proposals and reports panels own query stacks of their own; stub them
// so this stays a wiring assertion — which incident each is mounted for, and whether it is
// mounted at all. What they render for that incident has its own tests.
vi.mock('@/features/investigation', () => ({
  InvestigationPanel: ({ incidentId }: { incidentId: string }) => (
    <div data-testid="investigation-panel-stub">{incidentId}</div>
  ),
}));
vi.mock('@/features/proposals/proposals-panel', () => ({
  ProposalsPanel: ({ incidentId }: { incidentId: string }) => (
    <div data-testid="proposals-panel-stub">{incidentId}</div>
  ),
}));
vi.mock('@/features/reports/reports-panel', () => ({
  ReportsPanel: () => <div data-testid="reports-panel-stub" />,
}));

import { InspectorPanel } from '@/features/shell/components/inspector-panel';
import { defaultOperatorWorkspaceState } from '@/features/shell/contracts/operator-workspace-state';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

const INCIDENT_A = 'incident:inc_a';
const INCIDENT_B = 'incident:inc_b';

const TITLE_A = 'Suspicious authentication activity';
const TITLE_B = 'Lateral movement to finance DB';

const incidents = [
  { id: INCIDENT_A, title: TITLE_A },
  { id: INCIDENT_B, title: TITLE_B },
];

const incidentRecords: Record<string, { id: string; title: string; state: string }> = {
  [INCIDENT_A]: { id: INCIDENT_A, title: TITLE_A, state: 'triage' },
  [INCIDENT_B]: { id: INCIDENT_B, title: TITLE_B, state: 'approval_pending' },
};

function settled(data: unknown) {
  return { isPending: false, isError: false, data, refetch: vi.fn() };
}

describe('InspectorPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useWorkspaceUiStore.setState({
      workspace: { ...defaultOperatorWorkspaceState },
      activeRunId: 'run_1',
    });

    // Mirrors the real hook's `enabled: Boolean(incidentId)` gate, so `fetchIncident` records
    // exactly the requests the panel would put on the wire.
    useIncident.mockImplementation((incidentId: string) => {
      if (!incidentId) {
        return { isPending: false, isError: false, data: undefined, refetch: vi.fn() };
      }
      fetchIncident(incidentId);
      return settled(incidentRecords[incidentId]);
    });
    useRun.mockReturnValue(settled({ id: 'run_1', status: 'running' }));
    useRunIncidents.mockReturnValue(settled(incidents));
    useRunAlerts.mockReturnValue(settled([]));
    useRunRiskScores.mockReturnValue(settled([]));
    useRunGraph.mockReturnValue(settled({ snapshot: null }));
  });

  afterEach(() => {
    cleanup();
  });

  it('fires no incident-scoped query and mounts no case file with nothing selected', () => {
    render(<InspectorPanel runId="run_1" />);

    expect(screen.getByTestId('incidents-panel')).toBeInTheDocument();
    expect(screen.queryByTestId('incident-case-file')).not.toBeInTheDocument();
    expect(screen.queryByTestId('investigation-panel-stub')).not.toBeInTheDocument();
    expect(screen.queryByTestId('proposals-panel-stub')).not.toBeInTheDocument();
    expect(fetchIncident).not.toHaveBeenCalled();
  });

  it('opens the case file inline when an incident is selected in the cockpit', () => {
    render(<InspectorPanel runId="run_1" />);

    fireEvent.click(screen.getByRole('button', { name: TITLE_B }));

    const caseFile = screen.getByTestId('incident-case-file');
    expect(within(caseFile).getByTestId('investigation-panel-stub')).toHaveTextContent(INCIDENT_B);
    expect(within(caseFile).getByTestId('proposals-panel-stub')).toHaveTextContent(INCIDENT_B);
    expect(within(caseFile).getByText(TITLE_B)).toBeInTheDocument();
    expect(within(caseFile).getByText('approval_pending')).toBeInTheDocument();
    expect(fetchIncident).toHaveBeenCalledWith(INCIDENT_B);

    // The case file is the open case, not the graph pointer: selecting it must not write to
    // `selectedEntityId`, which only ever names a graph node.
    expect(useWorkspaceUiStore.getState().workspace.selectedIncidentId).toBe(INCIDENT_B);
    expect(useWorkspaceUiStore.getState().workspace.selectedEntityId).toBeNull();
  });

  it('returns to the run-level view when the case is closed', () => {
    render(<InspectorPanel runId="run_1" />);
    fireEvent.click(screen.getByRole('button', { name: TITLE_A }));
    expect(screen.getByTestId('incident-case-file')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('close-incident-case'));

    expect(screen.queryByTestId('incident-case-file')).not.toBeInTheDocument();
    expect(screen.queryByTestId('proposals-panel-stub')).not.toBeInTheDocument();
    expect(screen.getByTestId('incidents-panel')).toBeInTheDocument();
    expect(useWorkspaceUiStore.getState().workspace.selectedIncidentId).toBeNull();
  });

  it('closes the case when the already-open incident is clicked again', () => {
    render(<InspectorPanel runId="run_1" />);
    const button = screen.getByRole('button', { name: TITLE_A });

    fireEvent.click(button);
    expect(button).toHaveAttribute('aria-pressed', 'true');

    fireEvent.click(button);
    expect(button).toHaveAttribute('aria-pressed', 'false');
    expect(screen.queryByTestId('incident-case-file')).not.toBeInTheDocument();
  });

  it('keeps a route-supplied incident authoritative and not closeable from the dock', () => {
    useWorkspaceUiStore.getState().setSelectedIncidentId(INCIDENT_B);
    render(<InspectorPanel runId="run_1" incidentId={INCIDENT_A} />);

    expect(screen.getByTestId('investigation-panel-stub')).toHaveTextContent(INCIDENT_A);
    expect(screen.getByTestId('proposals-panel-stub')).toHaveTextContent(INCIDENT_A);
    expect(screen.queryByTestId('close-incident-case')).not.toBeInTheDocument();
  });

  it('keeps the run-level inspector usable while the case file loads', () => {
    useIncident.mockImplementation((incidentId: string) => {
      if (!incidentId) {
        return { isPending: false, isError: false, data: undefined, refetch: vi.fn() };
      }
      fetchIncident(incidentId);
      return { isPending: true, isError: false, data: undefined, refetch: vi.fn() };
    });
    useWorkspaceUiStore.getState().setSelectedIncidentId(INCIDENT_A);
    render(<InspectorPanel runId="run_1" />);

    // The incident list stays mounted, so the operator can still switch cases.
    expect(screen.getByTestId('incidents-panel')).toBeInTheDocument();
    expect(screen.getByTestId('incident-case-file')).toBeInTheDocument();
  });

  // The after-action report does not exist until the run is over. Mounting the section on a
  // live run showed an "After-action report not ready" empty state that said nothing, and
  // put a guaranteed 404 on the wire.
  it('mounts no after-action section while the run is live', () => {
    useRun.mockReturnValue(settled({ id: 'run_1', status: 'running' }));
    render(<InspectorPanel runId="run_1" />);
    expect(screen.queryByTestId('reports-panel-stub')).not.toBeInTheDocument();
  });

  it.each(['completed', 'stopped', 'failed', 'aborted'])(
    'mounts the after-action section once the run is %s',
    (status) => {
      useRun.mockReturnValue(settled({ id: 'run_1', status }));
      render(<InspectorPanel runId="run_1" />);
      expect(screen.getByTestId('reports-panel-stub')).toBeInTheDocument();
    },
  );
});
