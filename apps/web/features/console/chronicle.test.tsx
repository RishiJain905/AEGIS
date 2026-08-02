import { act, cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/features/ops-feed', () => ({
  OpsFeedPanel: () => <p>feed body</p>,
}));

import { Chronicle } from './chronicle';
import { useCockpitUiStore } from '@/stores/cockpit-ui-store';

const RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

beforeEach(() => {
  useCockpitUiStore.getState().resetCockpitUi();
});

afterEach(() => {
  cleanup();
  useCockpitUiStore.getState().resetCockpitUi();
});

describe('Chronicle', () => {
  it('stays collapsed into the tape until summoned', () => {
    render(<Chronicle runId={RUN_ID} />);
    expect(screen.queryByTestId('chronicle')).not.toBeInTheDocument();
  });

  it('rises from the console with the whole ops feed inside', () => {
    act(() => {
      useCockpitUiStore.getState().setChronicleOpen(true);
    });
    render(<Chronicle runId={RUN_ID} />);
    const chronicle = screen.getByRole('dialog', { name: 'Chronicle' });
    expect(chronicle).toHaveAttribute('data-side', 'bottom');
    expect(screen.getByText('feed body')).toBeInTheDocument();
  });

  it('closes on Escape from inside, mirroring the tape affordances', async () => {
    const user = userEvent.setup();
    act(() => {
      useCockpitUiStore.getState().setChronicleOpen(true);
    });
    render(<Chronicle runId={RUN_ID} />);

    await user.keyboard('{Escape}');
    expect(useCockpitUiStore.getState().chronicleOpen).toBe(false);
  });
});
