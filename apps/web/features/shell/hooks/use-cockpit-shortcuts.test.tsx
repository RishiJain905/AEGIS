import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/features/live-run', () => ({
  LiveRunControls: () => <div data-testid="live-run-controls" />,
  useLiveRun: () => null,
}));
vi.mock('@/features/operator-actions', async () => {
  const slot = await import('@/features/operator-actions/action-result-slot');
  return {
    AssetCommandBar: () => (
      <button type="button" data-testid="isolate">
        Isolate
      </button>
    ),
    ActionResultSlot: slot.ActionResultSlot,
  };
});
vi.mock('@/features/timeline', () => ({
  RunTape: () => <div data-testid="run-tape" />,
}));
vi.mock('@/features/console/copilot-chip', () => ({
  CopilotChip: () => <button type="button" data-testid="copilot-chip" />,
}));

import { Console } from '@/features/console/console';
import { useCockpitShortcuts } from '@/features/shell/hooks/use-cockpit-shortcuts';
import { useCockpitUiStore } from '@/stores/cockpit-ui-store';

const RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

/** The cockpit as a keyboard operator meets it: the console is the only Tab stop. */
function Cockpit() {
  useCockpitShortcuts();
  return <Console runId={RUN_ID} />;
}

beforeEach(() => {
  useCockpitUiStore.getState().resetCockpitUi();
});

afterEach(() => {
  cleanup();
  useCockpitUiStore.getState().resetCockpitUi();
});

describe('cockpit shortcuts from the console', () => {
  // The console band swallowed every printable key to seed the copilot composer, which made
  // the cockpit's own vocabulary unreachable from the one place a keyboard operator stands.
  it.each([
    ['i', 'inspectorSheetOpen'],
    ['c', 'copilotSheetOpen'],
    ['t', 'chronicleOpen'],
  ] as const)('reaches %s with focus on the console', (key, flag) => {
    render(<Cockpit />);
    fireEvent.keyDown(screen.getByTestId('isolate'), { key });

    expect(useCockpitUiStore.getState()[flag]).toBe(true);
    // ...and it composed nothing: a shortcut is not a character.
    expect(useCockpitUiStore.getState().copilotSeed).toBeNull();
  });

  it('composes with a letter the cockpit has not bound', () => {
    render(<Cockpit />);
    fireEvent.keyDown(screen.getByTestId('isolate'), { key: 'h' });

    const state = useCockpitUiStore.getState();
    expect(state.copilotSheetOpen).toBe(true);
    expect(state.copilotSeed).toMatchObject({ text: 'h' });
    expect(state.chronicleOpen).toBe(false);
  });

  it('keeps every key a character once the operator is typing', () => {
    render(
      <>
        <Cockpit />
        <textarea aria-label="Ask the copilot" />
      </>,
    );
    const composer = screen.getByLabelText('Ask the copilot');
    fireEvent.keyDown(composer, { key: 't' });
    fireEvent.keyDown(composer, { key: 'i' });

    const state = useCockpitUiStore.getState();
    expect(state.chronicleOpen).toBe(false);
    expect(state.inspectorSheetOpen).toBe(false);
  });
});
