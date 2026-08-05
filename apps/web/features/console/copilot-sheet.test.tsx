import { act, cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useEffect, useRef } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const seenSeeds: unknown[] = [];

// Mirrors the real panel's seed contract: a new token appends the character and hands the
// composer focus. Faithful on that point on purpose — the sheet's own focus move used to
// land after this one and take it straight back.
vi.mock('@/features/agent-chat', () => ({
  AgentChatPanel: ({ composerSeed }: { composerSeed?: { text: string; token: number } | null }) => {
    seenSeeds.push(composerSeed);
    const draftRef = useRef<HTMLTextAreaElement>(null);
    const token = composerSeed?.token ?? 0;
    useEffect(() => {
      if (token > 0) {
        draftRef.current?.focus();
      }
    }, [token]);
    return (
      <div>
        <p>copilot body</p>
        <textarea ref={draftRef} aria-label="Ask the copilot" />
      </div>
    );
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

  // Seeding without focus is worse than not seeding at all: the character lands in a
  // composer nobody is typing into, and every key after it fires a cockpit shortcut instead.
  it('leaves focus in the composer it just seeded, not on the sheet', () => {
    act(() => {
      useCockpitUiStore.getState().seedCopilotComposer('h');
    });
    render(<CopilotSheet runId={RUN_ID} />);

    expect(screen.getByLabelText('Ask the copilot')).toHaveFocus();
  });

  it('takes focus itself when it was summoned without a keystroke', () => {
    act(() => {
      useCockpitUiStore.getState().setCopilotSheetOpen(true);
    });
    render(<CopilotSheet runId={RUN_ID} />);

    expect(screen.getByRole('dialog', { name: 'Copilot' })).toHaveFocus();
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
