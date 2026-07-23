import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';

import type { OperatorProfileV1 } from '@aegis/contracts-ts';

import { OperatorProfilePanelView } from './operator-profile-panel';

function profile(overrides: Partial<OperatorProfileV1> = {}): OperatorProfileV1 {
  return {
    schemaVersion: 1,
    ownerUserId: 'user:op-1',
    generatedAt: '2026-07-23T00:00:00.000Z',
    metrics: {
      runsAnalyzed: 4,
      avgTimeToFirstTriage: 12,
      avgContainmentLatency: 30,
      overContainmentRatio: 0.5,
      falseHypothesisRate: 0.25,
      avgScore: 0.72,
      scoreTrend: [0.5, 0.6, 0.7, 0.72],
    },
    runs: [],
    coaching: [
      {
        id: 'over-containment',
        tone: 'improve',
        message: '2 of your last 4 judged runs over-contained.',
      },
      {
        id: 'score-trend-up',
        tone: 'reinforce',
        message: 'Your scores are trending up (50% to 72%).',
      },
    ],
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
});

describe('OperatorProfilePanel', () => {
  it('renders metrics and coaching from a provided profile', () => {
    render(<OperatorProfilePanelView profile={profile()} />);
    expect(screen.getByText('4 runs analyzed')).toBeInTheDocument();
    expect(screen.getByText('Containment latency')).toBeInTheDocument();
    expect(screen.getByText('72%')).toBeInTheDocument();
    expect(screen.getByText(/trending up/i)).toBeInTheDocument();
  });

  it('shows an empty state when no runs analyzed', () => {
    render(
      <OperatorProfilePanelView
        profile={profile({
          metrics: {
            runsAnalyzed: 0,
            avgTimeToFirstTriage: null,
            avgContainmentLatency: null,
            overContainmentRatio: null,
            falseHypothesisRate: null,
            avgScore: null,
            scoreTrend: [],
          },
          coaching: [],
        })}
      />,
    );
    expect(screen.getByText(/No completed runs yet/i)).toBeInTheDocument();
  });

  it('renders em dashes for undrivable metrics', () => {
    render(
      <OperatorProfilePanelView
        profile={profile({
          metrics: {
            runsAnalyzed: 1,
            avgTimeToFirstTriage: null,
            avgContainmentLatency: null,
            overContainmentRatio: null,
            falseHypothesisRate: null,
            avgScore: null,
            scoreTrend: [],
          },
          coaching: [],
        })}
      />,
    );
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });

  it('has no axe violations in light and dark themes', async () => {
    for (const theme of ['light', 'dark'] as const) {
      document.documentElement.setAttribute('data-theme', theme);
      try {
        const { container } = render(<OperatorProfilePanelView profile={profile()} />);
        expect((await axe(container)).violations).toHaveLength(0);
        cleanup();
      } finally {
        document.documentElement.removeAttribute('data-theme');
      }
    }
  });
});
