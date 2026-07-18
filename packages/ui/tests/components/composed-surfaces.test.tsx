/**
 * @vitest-environment jsdom
 */
import { NodeStatus } from '@aegis/contracts-ts';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Panel, TimelineMark } from '../../src';

describe('composed command-centre surfaces', () => {
  it('separates panel chrome from panel content', () => {
    render(
      <Panel title="Telemetry" description="Current run state">
        <p>Content</p>
      </Panel>,
    );

    expect(screen.getByText('Telemetry').closest('[data-slot="panel-header"]')).not.toBeNull();
    expect(screen.getByText('Content').closest('[data-slot="panel-body"]')).not.toBeNull();
  });

  it('uses mono tabular timestamps on the timeline rail', () => {
    render(
      <ol>
        <TimelineMark
          timestamp="2026-06-30T10:00:00Z"
          label="Signal received"
          nodeStatus={NodeStatus.SUSPICIOUS}
        />
      </ol>,
    );

    const timestamp = screen.getByText('2026-06-30T10:00:00Z');
    expect(timestamp.className).toContain('font-mono');
    expect(timestamp.className).toContain('tabular-nums');
  });
});
