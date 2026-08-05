import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { useLiveRun } = vi.hoisted(() => ({
  useLiveRun: vi.fn(),
}));

vi.mock('@/features/live-run', () => ({
  LiveRunControls: () => <div data-testid="live-run-controls" />,
  useLiveRun,
}));
vi.mock('@/features/operator-actions', async () => {
  const slot = await import('@/features/operator-actions/action-result-slot');
  return {
    AssetCommandBar: ({ chrome }: { chrome?: string }) => (
      <div data-testid="asset-command-bar" data-chrome={chrome} />
    ),
    ActionResultSlot: slot.ActionResultSlot,
  };
});
vi.mock('@/features/timeline', () => ({
  RunTape: ({ chrome }: { chrome?: string }) => <div data-testid="run-tape" data-chrome={chrome} />,
}));
vi.mock('./copilot-chip', () => ({
  CopilotChip: () => <button type="button" data-testid="copilot-chip" />,
}));

import { Console } from './console';
import { useCockpitUiStore } from '@/stores/cockpit-ui-store';

const RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

function liveRunWithStatus(runStatus: string) {
  return {
    isLiveMode: true,
    state: { runStatus },
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  useLiveRun.mockReturnValue(null);
  useCockpitUiStore.getState().resetCockpitUi();
});

afterEach(() => {
  cleanup();
  useCockpitUiStore.getState().resetCockpitUi();
});

describe('Console band', () => {
  it('fuses transport, asset commands and the tape into one band', () => {
    render(<Console runId={RUN_ID} />);
    const console = screen.getByTestId('cockpit-console');
    const controls = screen.getByTestId('live-run-controls');
    const commandBar = screen.getByTestId('asset-command-bar');
    const tape = screen.getByTestId('run-tape');
    expect(console).toContainElement(controls);
    expect(console).toContainElement(commandBar);
    expect(console).toContainElement(tape);
    // Reading order is the doc's order: transport, then commands, then time.
    expect(
      controls.compareDocumentPosition(commandBar) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      commandBar.compareDocumentPosition(tape) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it('hands its clusters the console chrome so the band owns the frame', () => {
    render(<Console runId={RUN_ID} />);
    expect(screen.getByTestId('asset-command-bar')).toHaveAttribute('data-chrome', 'console');
    expect(screen.getByTestId('run-tape')).toHaveAttribute('data-chrome', 'console');
  });

  it('carries the copilot presence chip', () => {
    render(<Console runId={RUN_ID} />);
    expect(screen.getByTestId('cockpit-console')).toContainElement(
      screen.getByTestId('copilot-chip'),
    );
  });
});

describe('Console as a command line to the agents', () => {
  it('routes a printable keystroke into the copilot composer', () => {
    render(<Console runId={RUN_ID} />);
    const band = screen.getByRole('toolbar', { name: 'Console' });
    fireEvent.keyDown(band, { key: 'w' });

    const state = useCockpitUiStore.getState();
    expect(state.copilotSheetOpen).toBe(true);
    expect(state.copilotSeed).toMatchObject({ text: 'w' });
  });

  it('leaves space, modifier chords and typing contexts alone', () => {
    render(<Console runId={RUN_ID} />);
    const band = screen.getByRole('toolbar', { name: 'Console' });
    fireEvent.keyDown(band, { key: ' ' });
    fireEvent.keyDown(band, { key: 'k', ctrlKey: true });
    expect(useCockpitUiStore.getState().copilotSheetOpen).toBe(false);
  });

  // The console is the cockpit's single Tab stop, so seeding *every* letter from here made
  // the cockpit's own vocabulary unreachable from the only place a keyboard operator stands.
  it.each([['a'], ['i'], ['c'], ['t'], ['T']])(
    'lets the bound shortcut %s through instead of composing with it',
    (key) => {
      render(<Console runId={RUN_ID} />);
      const band = screen.getByRole('toolbar', { name: 'Console' });
      const event = fireEvent.keyDown(band, { key });

      // Not consumed by the band: it reaches the window handlers that own the shortcut.
      expect(event).toBe(true);
      expect(useCockpitUiStore.getState().copilotSeed).toBeNull();
    },
  );

  it('still composes with printable keys that are not shortcuts', () => {
    render(<Console runId={RUN_ID} />);
    const band = screen.getByRole('toolbar', { name: 'Console' });
    fireEvent.keyDown(band, { key: 'h' });
    expect(useCockpitUiStore.getState().copilotSeed).toMatchObject({ text: 'h' });
  });
});

describe('Console result rail', () => {
  it('gives action results a laid-out row above the band, not a floating card over it', () => {
    render(<Console runId={RUN_ID} />);
    const slot = screen.getByTestId('action-result-slot');
    const band = screen.getByRole('toolbar', { name: 'Console' });

    expect(screen.getByTestId('cockpit-console')).toContainElement(slot);
    expect(slot).not.toContainElement(band);
    // Above the band in reading order, so a result can never sit over its own controls.
    expect(slot.compareDocumentPosition(band) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});

describe('Console execution-semantics notice (BUG-012)', () => {
  it('says nothing about the timeline while the sim is running', () => {
    useLiveRun.mockReturnValue(liveRunWithStatus('running'));
    render(<Console runId={RUN_ID} />);
    expect(screen.queryByTestId('frozen-timeline-notice')).not.toBeInTheDocument();
    expect(screen.queryByTestId('run-ended-notice')).not.toBeInTheDocument();
  });

  it('states frozen-timeline execution semantics while paused, above the band', () => {
    useLiveRun.mockReturnValue(liveRunWithStatus('paused'));
    render(<Console runId={RUN_ID} />);
    const notice = screen.getByTestId('frozen-timeline-notice');
    expect(notice).toHaveTextContent(/frozen timeline/i);
    expect(
      notice.compareDocumentPosition(screen.getByTestId('live-run-controls')) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it('states read-only semantics once the run has ended', () => {
    useLiveRun.mockReturnValue(liveRunWithStatus('stopped'));
    render(<Console runId={RUN_ID} />);
    expect(screen.getByTestId('run-ended-notice')).toHaveTextContent(/read-only/i);
  });
});
