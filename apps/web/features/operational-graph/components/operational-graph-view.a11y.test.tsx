import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';

import { graphSnapshotSchema, parseContract } from '@aegis/contracts-ts';

vi.mock('sigma', () => ({
  default: class MockSigma {
    kill = vi.fn();
    refresh = vi.fn();
    on = vi.fn();
    off = vi.fn();
    setSetting = vi.fn();
    scheduleRender = vi.fn();
    resize = vi.fn();
    getCamera() {
      return {
        animate: vi.fn(),
        animatedReset: vi.fn(),
        ratio: 1,
      };
    }
  },
}));

// The investigation query stack (react-query + ApiClientProvider + Next
// router) is irrelevant to the a11y surface under test.
vi.mock('@/features/investigation', () => ({
  useInvestigationDetail: () => ({ data: undefined }),
}));

import { OperationalGraphView } from '@/features/operational-graph/components/operational-graph-view';
import shellDataset from '@/fixtures/shell-dataset.json';

describe('OperationalGraphView accessibility', () => {
  it('renders the graph surface without axe violations', async () => {
    const snapshot = parseContract(graphSnapshotSchema, shellDataset.graphSnapshots[0]);

    const { container } = render(
      <OperationalGraphView snapshot={snapshot} runId={snapshot.runId} />,
    );

    expect(screen.getByTestId('operational-graph-view')).toBeInTheDocument();
    expect(screen.getByTestId('graph-entity-list')).toBeInTheDocument();

    const results = await axe(container);
    expect(results.violations).toHaveLength(0);

    cleanup();
  });
});
