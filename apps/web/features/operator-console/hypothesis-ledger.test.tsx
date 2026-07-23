import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';

import { HypothesisLedger } from './hypothesis-ledger';
import type { HypothesisLedger as Ledger } from './ledger-model';

let ledgerState: { ledger: Ledger; isLoading: boolean; isError: boolean };
const createMutate = vi.fn();

vi.mock('./use-hypothesis-ledger', () => ({
  useHypothesisLedger: () => ledgerState,
  useCreateHypothesis: () => ({
    mutate: createMutate,
    isPending: false,
    isError: false,
    error: null,
  }),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('HypothesisLedger', () => {
  it('badges a challenged hypothesis and expands its rationale', () => {
    ledgerState = {
      ledger: {
        cards: [
          {
            id: 'hyp:1',
            statement: 'Logistics API is patient zero.',
            confidence: 0.6,
            origin: 'operator',
            evidenceIds: ['evidence:ev_1'],
            challenged: true,
            challengeRationale: 'New auth failures contradict this.',
          },
        ],
        collapsedNoChangeCount: 2,
      },
      isLoading: false,
      isError: false,
    };
    render(<HypothesisLedger runId="run_x" />);
    expect(screen.getByTestId('hypothesis-card-challenged')).toBeInTheDocument();
    expect(screen.getByTestId('hypothesis-challenge-badge')).toHaveTextContent('Challenged');
    expect(screen.getByTestId('hypothesis-nochange')).toHaveTextContent('2 bias checks');
  });

  it('renders an empty state when there are no hypotheses', () => {
    ledgerState = {
      ledger: { cards: [], collapsedNoChangeCount: 0 },
      isLoading: false,
      isError: false,
    };
    render(<HypothesisLedger runId="run_x" />);
    expect(screen.getByText(/No hypotheses yet/i)).toBeInTheDocument();
  });

  it('has no accessibility violations', async () => {
    ledgerState = {
      ledger: {
        cards: [
          {
            id: 'hyp:1',
            statement: 'Credentials were compromised.',
            confidence: 0.7,
            origin: 'agent',
            evidenceIds: [],
            challenged: false,
            challengeRationale: null,
          },
        ],
        collapsedNoChangeCount: 0,
      },
      isLoading: false,
      isError: false,
    };
    const { container } = render(<HypothesisLedger runId="run_x" />);
    expect((await axe(container)).violations).toHaveLength(0);
  });
});
