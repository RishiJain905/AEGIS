import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';

import type { BlastRadiusPreviewV1 } from '@aegis/contracts-ts';

import { BlastRadiusSummary } from './blast-radius-summary';

const preview: BlastRadiusPreviewV1 = {
  schemaVersion: 1,
  runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
  command: 'isolate',
  targetAssetId: 'asset:svc-logistics-api',
  actionClass: 'class_2',
  severedEdgeCount: 3,
  degradedEdgeCount: 0,
  impactedAssets: [
    {
      assetId: 'asset:svc-comms-gateway',
      label: 'Comms Gateway',
      criticality: 0.9,
      status: 'normal',
      relationshipType: 'DEPENDS_ON',
      impactKind: 'severed',
      edgeId: 'edge:logistics-comms',
    },
  ],
  downstreamAssets: [
    {
      assetId: 'asset:svc-fleet-coordinator',
      label: 'Fleet Coordinator',
      criticality: 0.85,
      hops: 1,
    },
  ],
  warnings: ['Isolation severs all 3 connection(s) to Logistics API.'],
};

afterEach(cleanup);

describe('BlastRadiusSummary', () => {
  it('renders severed/degraded counts, impacted chips, downstream and warnings', () => {
    render(<BlastRadiusSummary preview={preview} loading={false} error={false} />);
    expect(screen.getByTestId('blast-radius-severed')).toHaveTextContent('3 severed');
    expect(screen.getByTestId('blast-radius-impacted')).toHaveTextContent('Comms Gateway');
    expect(screen.getByTestId('blast-radius-downstream')).toHaveTextContent('Fleet Coordinator');
    expect(screen.getByTestId('blast-radius-warnings')).toHaveTextContent('Isolation severs');
  });

  it('shows a loading state while projecting', () => {
    render(<BlastRadiusSummary preview={undefined} loading error={false} />);
    expect(screen.getByTestId('blast-radius-loading')).toBeInTheDocument();
  });

  it('degrades to a quiet note on error so the dialog still works', () => {
    render(<BlastRadiusSummary preview={undefined} loading={false} error />);
    expect(screen.getByTestId('blast-radius-error')).toBeInTheDocument();
  });

  it('has no accessibility violations', async () => {
    const { container } = render(
      <BlastRadiusSummary preview={preview} loading={false} error={false} />,
    );
    expect((await axe(container)).violations).toHaveLength(0);
  });
});
