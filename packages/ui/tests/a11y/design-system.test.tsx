/**
 * @vitest-environment jsdom
 */
import { NodeStatus } from '@aegis/contracts-ts';
import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';

import {
  Alert,
  Badge,
  Button,
  Card,
  DisconnectedState,
  EmptyState,
  ErrorState,
  LoadingState,
  MetricTile,
  Panel,
} from '../../src';

function DesignSystemTree() {
  return (
    <main>
      <h1>Design system</h1>
      <DisconnectedState />
      <Panel title="Status">
        <Badge nodeStatus={NodeStatus.NORMAL} />
        <Badge nodeStatus={NodeStatus.SUSPICIOUS} />
      </Panel>
      <MetricTile label="Alerts" value={5} riskBand="medium" />
      <Alert variant="warning" title="Warning">
        Elevated watch
      </Alert>
      <Card title="States">
        <LoadingState message="Loading" />
        <EmptyState />
        <ErrorState />
      </Card>
      <Button>Primary action</Button>
    </main>
  );
}

// The redesign added a light theme (via `data-theme` on the document root)
// alongside the dark default. Every a11y suite now runs against BOTH themes so
// no theme-specific markup/ARIA regression slips through. (Colour-contrast is
// verified deterministically against the token source in contrast.test.ts —
// axe cannot measure CSS-custom-property pairings under jsdom.)
describe.each(['dark', 'light'] as const)('design system accessibility (%s theme)', (theme) => {
  beforeEach(() => {
    document.documentElement.setAttribute('data-theme', theme);
  });

  afterEach(() => {
    document.documentElement.removeAttribute('data-theme');
  });

  it('has no axe violations on representative component tree', async () => {
    const { container } = render(<DesignSystemTree />);
    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });

  it('renders status text not color-only', () => {
    render(<Badge nodeStatus={NodeStatus.COMPROMISED} />);
    expect(screen.getByText('Compromised')).toBeInTheDocument();
  });

  it('preserves essential information in loading state', () => {
    const { container } = render(<LoadingState message="Loading incidents" />);
    expect(screen.getByText('Loading incidents')).toBeInTheDocument();
    expect(container.querySelector('[role="status"]')).toHaveAttribute(
      'aria-label',
      'Status: Loading — data in progress',
    );
  });
});
