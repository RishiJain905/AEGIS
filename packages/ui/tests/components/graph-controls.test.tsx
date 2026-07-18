/**
 * @vitest-environment jsdom
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { GraphLegend } from '../../src';

describe('GraphLegend', () => {
  it('exposes the promised visual encoding with text and shape metadata', () => {
    render(
      <GraphLegend
        items={[
          { label: 'Device', color: '#8999ff', shape: 'diamond' },
          {
            label: 'High risk',
            color: '#ef5b66',
            shape: 'ring',
            description: 'Elevated or critical risk',
          },
        ]}
      />,
    );

    expect(screen.getByTestId('graph-legend-symbol-device')).toHaveAttribute(
      'data-shape',
      'diamond',
    );
    expect(screen.getByTestId('graph-legend-symbol-high-risk')).toHaveAttribute(
      'data-shape',
      'ring',
    );
    expect(screen.getByText('Elevated or critical risk')).toBeInTheDocument();
  });
});
