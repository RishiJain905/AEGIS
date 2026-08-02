import type { AlertV1, GraphSnapshotV1, IncidentV1 } from '@aegis/contracts-ts';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';

import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

import { AlertsPanel } from './alerts-panel';

/**
 * Open a `<details>` the way the browser does — jsdom does not toggle it from a summary
 * click, so the open state and the `toggle` event are set explicitly.
 */
function toggleDisclosure(summaryTestId: string, open: boolean) {
  const details = screen.getByTestId(summaryTestId).closest('details');
  if (!details) {
    throw new Error(`No <details> around ${summaryTestId}`);
  }
  details.open = open;
  fireEvent(details, new Event('toggle'));
}

const ASSET = 'asset:svc-comms-gateway';
const OTHER_ASSET = 'asset:svc-identity-broker';

const focusAsset = vi.fn();
vi.mock('@/features/operational-graph', () => ({
  useFocusAsset: () => focusAsset,
}));

const activity = vi.fn();
vi.mock('@/features/live-run', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/live-run')>();
  return { ...actual, useRunActivity: () => activity() as unknown };
});

function quietActivity() {
  return {
    level: 'quiet' as const,
    score: 0,
    count: 0,
    buckets: Array.from({ length: 12 }, () => 0),
    windowSeconds: 90,
    lastSimTime: null,
  };
}

/**
 * A real-shaped rule alert. `deduplicationKey` carries the server's window epoch, exactly
 * as `aegis_incidents.rules.dedup` builds it — repeats differ in it, so a fixture that
 * held it constant could never catch the collapsing bug QA found.
 */
function alert(
  overrides: Partial<AlertV1> & { id: string },
  window?: { sequence: number; simTime: string; windowStartEpoch: number },
): AlertV1 {
  const sequence = window?.sequence ?? 14;
  const simTime = window?.simTime ?? '2026-01-01T00:00:24.000Z';
  const epoch = window?.windowStartEpoch ?? 1767225600;
  return {
    schemaVersion: 1,
    runId: 'run_x',
    title: 'Unseen device or source activity',
    severity: 'medium',
    sourceEventId: `evt-${overrides.id}`,
    assetId: ASSET,
    createdAt: simTime,
    confidence: 0.75,
    ruleId: 'rule-unseen-source',
    ruleVersion: '1.0.0',
    detectorId: 'rule-unseen-source',
    detectorVersion: '1.0.0',
    deduplicationKey: `run_x:rule-unseen-source:${ASSET}:${String(epoch)}`,
    evidence: {
      featureSchemaVersion: 1,
      featureValues: {},
      sourceEventIds: [`evt-${overrides.id}`],
      windowKey: `run_x:${ASSET}:${String(epoch)}`,
      sequenceStart: sequence,
      sequenceEnd: sequence,
      simTimeStart: simTime,
      simTimeEnd: simTime,
    },
    ...overrides,
  } as AlertV1;
}

function snapshot(status = 'normal'): GraphSnapshotV1 {
  return {
    schemaVersion: 1,
    runId: 'run_x',
    revision: 1,
    sequence: 1,
    capturedAt: '2026-01-01T00:00:00.000Z',
    nodes: [
      {
        schemaVersion: 1,
        id: ASSET,
        entityType: 'asset',
        assetType: 'service',
        label: 'Communications Gateway',
        riskScore: 0.4,
        criticality: 0.8,
        status,
        revision: 1,
      },
      {
        schemaVersion: 1,
        id: OTHER_ASSET,
        entityType: 'asset',
        assetType: 'service',
        label: 'Identity Broker',
        riskScore: 0.5,
        criticality: 0.9,
        status: 'normal',
        revision: 1,
      },
    ],
    edges: [],
  } as unknown as GraphSnapshotV1;
}

function incident(alertIds: string[]): IncidentV1 {
  return {
    schemaVersion: 1,
    id: 'incident:inc_1',
    runId: 'run_x',
    title: 'Suspected credential abuse',
    state: 'investigating',
    alertIds,
    createdAt: '2026-01-01T00:01:00.000Z',
    updatedAt: '2026-01-01T00:01:00.000Z',
    revision: 1,
  } as IncidentV1;
}

const explainedAlert = {
  ...alert({ id: 'a1' }),
  explanation: {
    schemaVersion: 1,
    summary: 'A source never seen before contacted this asset.',
    condition: 'first_seen activity',
    featureName: 'first_seen',
    observed: 2,
    threshold: 2,
    comparison: 'first_seen activity 2 >= 2.0',
    windowKey: `run_x:${ASSET}:1767225600`,
    detectorType: 'deterministic',
  },
} as AlertV1;

beforeEach(() => {
  useWorkspaceUiStore.setState({ alertExplanationOpened: false });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('AlertsPanel', () => {
  it('names the target asset by display name and never prints the raw id or the window key', () => {
    activity.mockReturnValue(quietActivity());
    render(<AlertsPanel alerts={[alert({ id: 'a1' })]} incidents={[]} snapshot={snapshot()} />);

    expect(screen.getByTestId('alert-asset-a1')).toHaveTextContent('Communications Gateway');
    expect(screen.queryByText(/Window:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/1767225600/)).not.toBeInTheDocument();
  });

  it('selects and focuses the node when the asset name is clicked', () => {
    activity.mockReturnValue(quietActivity());
    render(<AlertsPanel alerts={[alert({ id: 'a1' })]} incidents={[]} snapshot={snapshot()} />);

    fireEvent.click(screen.getByTestId('alert-asset-a1'));
    expect(focusAsset).toHaveBeenCalledWith(ASSET);
  });

  it('folds repeats of one rule on one asset into a single counted card', () => {
    // Regression for the live defect: Identity Broker and Comms Gateway each showed two
    // identical uncollapsed cards, because every repeat carried its own server dedup key.
    activity.mockReturnValue(quietActivity());
    render(
      <AlertsPanel
        alerts={[
          alert(
            { id: 'a1' },
            { sequence: 14, simTime: '2026-01-01T00:00:24.000Z', windowStartEpoch: 1767225600 },
          ),
          alert(
            { id: 'a2' },
            { sequence: 27, simTime: '2026-01-01T00:00:40.000Z', windowStartEpoch: 1767225660 },
          ),
          alert(
            { id: 'a3' },
            { sequence: 72, simTime: '2026-01-01T00:02:30.000Z', windowStartEpoch: 1767225720 },
          ),
        ]}
        incidents={[]}
        snapshot={snapshot()}
      />,
    );

    expect(screen.getAllByTestId(/^alert-item-/)).toHaveLength(1);
    const badge = screen.getByTestId('alert-repeat-a3');
    expect(badge).toHaveTextContent('×3');
    expect(badge).toHaveAttribute('title', 'Seen 3 times, last at 00:02:30');
  });

  it('keeps one rule on two different assets as two cards', () => {
    // The other half of the same judgement: identical wording about different assets is
    // not a repeat, and collapsing it would hide an asset from the operator.
    activity.mockReturnValue(quietActivity());
    render(
      <AlertsPanel
        alerts={[alert({ id: 'a1' }), alert({ id: 'b1', assetId: OTHER_ASSET })]}
        incidents={[]}
        snapshot={snapshot()}
      />,
    );

    expect(screen.getAllByTestId(/^alert-item-/)).toHaveLength(2);
    expect(screen.queryByTestId(/^alert-repeat-/)).not.toBeInTheDocument();
  });

  it('shows the status transition the alert preceded', () => {
    activity.mockReturnValue(quietActivity());
    render(
      <AlertsPanel
        alerts={[alert({ id: 'a1' })]}
        incidents={[]}
        snapshot={snapshot('compromised')}
        timelineEntries={[
          {
            eventType: 'sim.asset.status_changed',
            label: `Asset ${ASSET} → compromised`,
            sequence: 316,
            timestamp: '2026-01-01T00:06:15.000Z',
          },
        ]}
      />,
    );

    expect(screen.getByTestId('alert-outcome-a1')).toHaveTextContent('compromised');
    expect(screen.getByTestId('alert-outcome-a1')).toHaveTextContent('SEQ 316');
    expect(screen.getByTestId('alert-item-a1')).toHaveTextContent(
      'Communications Gateway was confirmed compromised at 00:06:15',
    );
  });

  it('marks an escalated alert and offers its case', () => {
    activity.mockReturnValue(quietActivity());
    render(
      <AlertsPanel
        alerts={[alert({ id: 'a1' })]}
        incidents={[incident(['a1'])]}
        snapshot={snapshot()}
      />,
    );

    expect(screen.getByTestId('alert-item-a1')).toHaveAttribute('data-lifecycle', 'escalated');
    expect(screen.getByTestId('alert-incident-a1')).toHaveTextContent('Suspected credential abuse');
  });

  it('leads the explanation with plain language and demotes the rule text under it', () => {
    activity.mockReturnValue(quietActivity());
    render(<AlertsPanel alerts={[explainedAlert]} incidents={[]} snapshot={snapshot()} />);

    // The stakes line is unconditional; the rule arithmetic is a disclosure down.
    expect(screen.getByTestId('alert-item-a1')).toHaveTextContent('First sighting on');
    expect(screen.getByTestId('alert-explanation-a1')).toHaveTextContent('Explanation');
    expect(screen.getByText('Detector detail')).toBeInTheDocument();
    expect(screen.getByText(/first_seen activity 2 >= 2\.0/)).toBeInTheDocument();
  });

  it('reports to the walkthrough when the operator opens an explanation', () => {
    activity.mockReturnValue(quietActivity());
    render(<AlertsPanel alerts={[explainedAlert]} incidents={[]} snapshot={snapshot()} />);

    expect(useWorkspaceUiStore.getState().alertExplanationOpened).toBe(false);

    toggleDisclosure('alert-explanation-a1', true);
    expect(useWorkspaceUiStore.getState().alertExplanationOpened).toBe(true);
    expect(screen.getByTestId('alert-item-a1')).toHaveAttribute('data-lifecycle', 'investigated');
  });

  it('keeps the explanation read once it has been read, even after collapsing', () => {
    activity.mockReturnValue(quietActivity());
    render(<AlertsPanel alerts={[explainedAlert]} incidents={[]} snapshot={snapshot()} />);

    toggleDisclosure('alert-explanation-a1', true);
    toggleDisclosure('alert-explanation-a1', false);

    expect(useWorkspaceUiStore.getState().alertExplanationOpened).toBe(true);
  });

  it('gives an anomaly alert its own model disclosure, and it also counts as read', () => {
    activity.mockReturnValue(quietActivity());
    render(
      <AlertsPanel
        alerts={[
          {
            ...alert({ id: 'a1' }),
            detectorId: 'isolation-forest',
            anomalyExplanation: {
              summary: 'Authentication volume sits far outside this asset’s baseline.',
              observedScore: 0.91,
              threshold: 0.7,
              topFeatures: ['auth_failures', 'distinct_sources'],
              modelVersionId: 'model:isoforest_v3',
            },
          } as AlertV1,
        ]}
        incidents={[]}
        snapshot={snapshot()}
      />,
    );

    const anomaly = screen.getByTestId('alert-anomaly-a1');
    expect(anomaly).toHaveTextContent('Anomaly model');
    expect(screen.getByText(/Score 0\.91 · threshold 0\.70/)).toBeInTheDocument();
    expect(screen.getByText(/auth_failures, distinct_sources/)).toBeInTheDocument();

    toggleDisclosure('alert-anomaly-a1', true);
    expect(useWorkspaceUiStore.getState().alertExplanationOpened).toBe(true);
  });

  it('renders a hidden-cause reveal as its own prominent entry', () => {
    activity.mockReturnValue(quietActivity());
    render(
      <AlertsPanel
        alerts={[alert({ id: 'a1' })]}
        incidents={[]}
        snapshot={snapshot()}
        timelineEntries={[
          {
            eventType: 'sim.hidden_condition.revealed',
            label: 'Underlying cause revealed: Vendor key reuse',
            sequence: 247,
            timestamp: '2026-01-01T00:05:00.000Z',
          },
        ]}
      />,
    );

    const reveal = screen.getByTestId('alert-reveal-247');
    expect(reveal).toHaveTextContent('Cause revealed');
    expect(reveal).toHaveTextContent('Vendor key reuse');
    expect(reveal).not.toHaveTextContent('hidden_condition');
  });

  it('reports the run cadence so a fogged operator can tell idle from active', () => {
    activity.mockReturnValue({
      level: 'active' as const,
      score: 20,
      count: 9,
      buckets: [0, 1, 3, 4, 2, 0, 5, 1, 2, 0, 1, 1],
      windowSeconds: 90,
      lastSimTime: '2026-01-01T00:02:30.000Z',
    });
    render(<AlertsPanel alerts={[alert({ id: 'a1' })]} incidents={[]} snapshot={snapshot()} />);

    const strip = screen.getByTestId('activity-strip');
    expect(strip).toHaveAttribute('data-level', 'active');
    expect(strip).toHaveTextContent('Active');
    expect(screen.getByLabelText(/Run activity: active\. 9 events/)).toBeInTheDocument();
  });

  it('renders nothing when the run has neither alerts nor reveals', () => {
    activity.mockReturnValue(quietActivity());
    const { container } = render(<AlertsPanel alerts={[]} incidents={[]} snapshot={snapshot()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('has no accessibility violations', async () => {
    activity.mockReturnValue(quietActivity());
    const { container } = render(
      <AlertsPanel
        alerts={[alert({ id: 'a1' })]}
        incidents={[incident(['a1'])]}
        snapshot={snapshot('compromised')}
        timelineEntries={[
          {
            eventType: 'sim.hidden_condition.revealed',
            label: 'Underlying cause revealed: Vendor key reuse',
            sequence: 247,
            timestamp: '2026-01-01T00:05:00.000Z',
          },
        ]}
      />,
    );
    // Colour contrast is disabled: jsdom cannot resolve the design tokens' computed
    // colours, so the rule reports against a transparent default rather than the theme.
    const results = await axe(container, { rules: { 'color-contrast': { enabled: false } } });
    expect(results.violations).toHaveLength(0);
  });
});
