import type { GraphSnapshotV1 } from '@aegis/contracts-ts';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import {
  PENDING_CONTROL_TTL_MS,
  usePendingControlStore,
} from '@/features/operator-actions/pending-control-store';

import { GraphEntityInspector } from './graph-entity-inspector';

const ASSET = 'asset:svc-comms-gateway';

function snapshot(appliedControls: string[] = [], status = 'normal'): GraphSnapshotV1 {
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
        appliedControls,
      },
    ],
    edges: [],
  } as unknown as GraphSnapshotV1;
}

beforeEach(() => {
  usePendingControlStore.setState({ runId: null, pending: {} });
});

afterEach(() => {
  cleanup();
});

describe('GraphEntityInspector observation acknowledgment', () => {
  it('acknowledges an accepted order before the control reaches the node', () => {
    usePendingControlStore.getState().note('run_x', ASSET, 'Observe');
    render(<GraphEntityInspector snapshot={snapshot()} selectedEntityId={ASSET} />);

    expect(screen.getByTestId('pending-control-badge')).toHaveTextContent('Observe · applying');
  });

  it('drops the acknowledgment once the durable control lands on the node', () => {
    usePendingControlStore.getState().note('run_x', ASSET, 'Observe');
    render(<GraphEntityInspector snapshot={snapshot(['observed'])} selectedEntityId={ASSET} />);

    expect(screen.queryByTestId('pending-control-badge')).not.toBeInTheDocument();
    // Named the way an operator would say it, not the way the world stores it.
    expect(screen.getByTestId('applied-control-badge')).toHaveTextContent('Under observation');
    expect(usePendingControlStore.getState().pending[ASSET]).toBeUndefined();
  });

  it('names a containment control and keeps it beside the composed status', () => {
    render(
      <GraphEntityInspector
        snapshot={snapshot(['isolated'], 'contained')}
        selectedEntityId={ASSET}
      />,
    );

    expect(screen.getByTestId('applied-control-badge')).toHaveTextContent('Isolated');
    expect(screen.getByText('contained')).toBeInTheDocument();
  });

  it('drops an acknowledgment that was never answered', () => {
    usePendingControlStore.setState({
      runId: 'run_x',
      pending: {
        [ASSET]: { assetId: ASSET, label: 'Observe', at: Date.now() - PENDING_CONTROL_TTL_MS - 1 },
      },
    });
    render(<GraphEntityInspector snapshot={snapshot()} selectedEntityId={ASSET} />);

    expect(screen.queryByTestId('pending-control-badge')).not.toBeInTheDocument();
  });

  it('does not acknowledge an order made against a different asset', () => {
    usePendingControlStore.getState().note('run_x', 'asset:other', 'Observe');
    render(<GraphEntityInspector snapshot={snapshot()} selectedEntityId={ASSET} />);

    expect(screen.queryByTestId('pending-control-badge')).not.toBeInTheDocument();
  });

  it('forgets acknowledgments from a previous run', () => {
    const store = usePendingControlStore.getState();
    store.note('run_a', ASSET, 'Observe');
    store.note('run_b', 'asset:other', 'Isolate');

    expect(usePendingControlStore.getState().pending[ASSET]).toBeUndefined();
    expect(usePendingControlStore.getState().pending['asset:other']?.label).toBe('Isolate');
  });
});
