import { act, cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const seenSeeds: unknown[] = [];

vi.mock('@/features/agent-chat', () => ({
  AgentChatPanel: ({ composerSeed }: { composerSeed?: unknown }) => {
    seenSeeds.push(composerSeed);
    return <p>copilot body</p>;
  },
}));
vi.mock('@/features/operator-console', () => ({
  EventSearch: () => <p>evidence body</p>,
  HypothesisLedger: () => <p>hypotheses body</p>,
}));

import { CopilotSheet } from './copilot-sheet';
import { useCockpitUiStore } from '@/stores/cockpit-ui-store';

const RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

beforeEach(() => {
  seenSeeds.length = 0;
  useCockpitUiStore.getState().resetCockpitUi();
});

afterEach(() => {
  cleanup();
  useCockpitUiStore.getState().resetCockpitUi();
});

describe('CopilotSheet', () => {
  it('stays away until summoned', () => {
    render(<CopilotSheet runId={RUN_ID} />);
    expect(screen.queryByTestId('copilot-sheet')).not.toBeInTheDocument();
  });

  it('opens on the left with the colleague first and its working material as tabs', async () => {
    const user = userEvent.setup();
    act(() => {
      useCockpitUiStore.getState().setCopilotSheetOpen(true);
    });
    render(<CopilotSheet runId={RUN_ID} />);

    const sheet = screen.getByRole('dialog', { name: 'Copilot' });
    expect(sheet).toHaveAttribute('data-side', 'left');
    expect(screen.getByText('copilot body')).toBeInTheDocument();

    await user.click(screen.getByTestId('copilot-sheet-tab-evidence'));
    expect(screen.getByText('evidence body')).toBeInTheDocument();

    await user.click(screen.getByTestId('copilot-sheet-tab-hypotheses'));
    expect(screen.getByText('hypotheses body')).toBeInTheDocument();
  });

  it('hands routed console keystrokes to the composer', () => {
    act(() => {
      useCockpitUiStore.getState().seedCopilotComposer('w');
    });
    render(<CopilotSheet runId={RUN_ID} />);
    // Seeding opened the sheet and the seed reached the chat panel.
    expect(screen.getByTestId('copilot-sheet')).toBeInTheDocument();
    expect(seenSeeds.at(-1)).toMatchObject({ text: 'w', token: 1 });
  });

  it('shares the space budget when the inspector holds the other side', () => {
    act(() => {
      useCockpitUiStore.getState().setCopilotSheetOpen(true);
      useCockpitUiStore.getState().setInspectorSheetOpen(true);
    });
    render(<CopilotSheet runId={RUN_ID} />);
    expect(screen.getByTestId('copilot-sheet')).toHaveAttribute('data-budget', 'shared');
  });
});
