import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';

import type { IntentReviewResult } from './use-intent-review';
import { IntentReview } from './intent-review';

const useIntentReview = vi.fn();
vi.mock('./use-intent-review', () => ({
  useIntentReview: (runId: string) => useIntentReview(runId) as unknown,
}));

function result(overrides: Partial<IntentReviewResult>): IntentReviewResult {
  return {
    sealed: true,
    intent: 'protect student records; preserve evidence',
    isLoading: false,
    isError: false,
    error: null,
    assessment: null,
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('IntentReview', () => {
  it('shows an empty state when no intent was set', () => {
    useIntentReview.mockReturnValue(result({ intent: null }));
    render(<IntentReview runId="run_x" />);
    expect(screen.getByText(/No commander's intent was set/i)).toBeInTheDocument();
  });

  it('shows a locked note before the run ends', () => {
    useIntentReview.mockReturnValue(result({ sealed: false }));
    render(<IntentReview runId="run_x" />);
    expect(screen.getByText(/unlocks once the run ends/i)).toBeInTheDocument();
  });

  it('renders the intent quote and held/tension/violated findings', () => {
    useIntentReview.mockReturnValue(
      result({
        assessment: {
          intent: 'protect student records; preserve evidence',
          hasIntent: true,
          keywords: ['student', 'records', 'evidence'],
          namedAssets: [
            { id: 'asset:records', label: 'Student Records Database', kind: 'database' },
          ],
          findings: [
            {
              id: 'intent-protect-asset:records',
              status: 'violated',
              title: 'Protect Student Records Database',
              detail: 'Attacker reached it and no containment ran.',
              supportingEventIds: ['evt:1', 'evt:2'],
            },
            {
              id: 'intent-evidence',
              status: 'held',
              title: 'Preserve evidence',
              detail: 'No destructive actions ran.',
              supportingEventIds: [],
            },
          ],
        },
      }),
    );
    render(<IntentReview runId="run_x" />);
    expect(screen.getByText(/records; preserve evidence/i)).toBeInTheDocument();
    expect(screen.getByText('Protect Student Records Database')).toBeInTheDocument();
    expect(screen.getByText('Violated')).toBeInTheDocument();
    expect(screen.getByText('Held')).toBeInTheDocument();
    expect(screen.getByText('Student Records Database')).toBeInTheDocument();
  });

  it('has no axe violations in light and dark themes', async () => {
    useIntentReview.mockReturnValue(
      result({
        assessment: {
          intent: 'protect student records',
          hasIntent: true,
          keywords: ['student', 'records'],
          namedAssets: [],
          findings: [
            {
              id: 'intent-containment-timing',
              status: 'tension',
              title: 'Stop exfiltration',
              detail: 'Containment landed after exfiltration began.',
              supportingEventIds: ['evt:1'],
            },
          ],
        },
      }),
    );
    for (const theme of ['light', 'dark'] as const) {
      document.documentElement.setAttribute('data-theme', theme);
      try {
        const { container } = render(<IntentReview runId="run_x" />);
        expect((await axe(container)).violations).toHaveLength(0);
        cleanup();
      } finally {
        document.documentElement.removeAttribute('data-theme');
      }
    }
  });
});
