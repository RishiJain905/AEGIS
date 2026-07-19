import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { IncidentAgentRoster } from '@/features/incidents/components/incident-agent-roster';
import type { AgentActivity } from '@/features/incidents/lib/incident-model';

const ROSTER: AgentActivity[] = [
  {
    role: 'WATCHTOWER',
    present: true,
    headline: 'Correlated alerts and set escalation.',
    metricLabel: 'Triage results',
    metricValue: 3,
  },
  {
    role: 'WARDEN',
    present: false,
    headline: 'No policy evaluation yet.',
    metricLabel: 'Policy decisions',
    metricValue: 0,
  },
  {
    role: 'SCRIBE',
    present: false,
    headline: 'No report yet.',
    metricLabel: 'Reports',
    metricValue: 0,
  },
];

describe('IncidentAgentRoster', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders a fixed glyph badge per role while keeping the role name as accessible text', () => {
    render(<IncidentAgentRoster roster={ROSTER} />);

    // Role name remains present as readable text (the glyph itself is decorative).
    const watchtower = screen.getByTestId('agent-role-WATCHTOWER');
    expect(within(watchtower).getByText('WATCHTOWER')).toBeInTheDocument();
    // Distinct glyphs avoid a duplicate single letter for WATCHTOWER vs WARDEN.
    expect(within(watchtower).getByText('W')).toBeInTheDocument();

    const warden = screen.getByTestId('agent-role-WARDEN');
    expect(within(warden).getByText('WARDEN')).toBeInTheDocument();
    expect(within(warden).getByText('WD')).toBeInTheDocument();

    const scribe = screen.getByTestId('agent-role-SCRIBE');
    expect(within(scribe).getByText('S')).toBeInTheDocument();
  });
});
