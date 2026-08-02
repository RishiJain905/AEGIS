import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { useRunAlerts, useRunActivity } = vi.hoisted(() => ({
  useRunAlerts: vi.fn(),
  useRunActivity: vi.fn(),
}));

vi.mock('@/features/shell/hooks/use-shell-queries', () => ({ useRunAlerts }));
vi.mock('@/features/live-run', () => ({ useRunActivity }));
vi.mock('@/features/shell/components/alerts-tab', () => ({
  AlertsTab: () => <div data-testid="alerts-tab-stub" />,
}));

import { SignalsStack } from './signals-stack';
import { useCockpitUiStore } from '@/stores/cockpit-ui-store';

const RUN_ID = 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV';

function alertsOf(severities: string[]) {
  return { data: severities.map((severity, index) => ({ id: `a${String(index)}`, severity })) };
}

beforeEach(() => {
  vi.clearAllMocks();
  useCockpitUiStore.getState().resetCockpitUi();
  useRunAlerts.mockReturnValue({ data: [] });
  useRunActivity.mockReturnValue({
    level: 'quiet',
    count: 0,
    windowSeconds: 90,
    buckets: [0, 0, 0, 0],
  });
});

afterEach(() => {
  cleanup();
  useCockpitUiStore.getState().resetCockpitUi();
});

describe('SignalsStack resolution', () => {
  it('rests as a capsule while the floor is quiet', () => {
    render(<SignalsStack runId={RUN_ID} />);
    const capsule = screen.getByTestId('signals-capsule');
    expect(capsule).toHaveAttribute('aria-expanded', 'false');
    expect(capsule).toHaveAttribute('data-severity', 'none');
    expect(screen.getByTestId('signals-count')).toHaveTextContent('0');
  });

  it('expands on its own the moment alerts exist', () => {
    useRunAlerts.mockReturnValue(alertsOf(['high']));
    render(<SignalsStack runId={RUN_ID} />);
    expect(screen.getByTestId('signals-stack')).toBeInTheDocument();
    expect(screen.getByTestId('alerts-tab-stub')).toBeInTheDocument();
    expect(screen.getByTestId('signals-count')).toHaveTextContent('1');
  });

  it('honours an explicit collapse even while alerts exist, and reopens on demand', async () => {
    const user = userEvent.setup();
    useRunAlerts.mockReturnValue(alertsOf(['high', 'critical']));
    render(<SignalsStack runId={RUN_ID} />);

    await user.click(screen.getByTestId('signals-collapse'));
    const capsule = screen.getByTestId('signals-capsule');
    expect(capsule).toBeInTheDocument();
    // The capsule carries the worst live severity as its tint.
    expect(capsule).toHaveAttribute('data-severity', 'critical');

    await user.click(capsule);
    expect(screen.getByTestId('signals-stack')).toBeInTheDocument();
  });
});

describe('SignalsStack keyboard', () => {
  it('toggles on A', () => {
    useRunAlerts.mockReturnValue(alertsOf(['low']));
    render(<SignalsStack runId={RUN_ID} />);
    expect(screen.getByTestId('signals-stack')).toBeInTheDocument();

    fireEvent.keyDown(window, { key: 'a' });
    expect(screen.getByTestId('signals-capsule')).toBeInTheDocument();

    fireEvent.keyDown(window, { key: 'A' });
    expect(screen.getByTestId('signals-stack')).toBeInTheDocument();
  });

  it('never fires from a typing context', () => {
    useRunAlerts.mockReturnValue(alertsOf(['low']));
    render(
      <div>
        <input aria-label="scratch" />
        <SignalsStack runId={RUN_ID} />
      </div>,
    );
    const input = screen.getByLabelText('scratch');
    input.focus();
    fireEvent.keyDown(input, { key: 'a' });
    expect(screen.getByTestId('signals-stack')).toBeInTheDocument();
  });
});

describe('SignalsStack × inspector sheet collision', () => {
  it('force-collapses to a capsule docked on the sheet when the right sheet opens', () => {
    useRunAlerts.mockReturnValue(alertsOf(['critical']));
    render(<SignalsStack runId={RUN_ID} />);
    expect(screen.getByTestId('signals-stack')).toBeInTheDocument();

    act(() => {
      useCockpitUiStore.getState().setInspectorSheetOpen(true);
    });
    const capsule = screen.getByTestId('signals-capsule');
    expect(capsule).toHaveAttribute('data-docked', 'sheet');
  });

  it('expands over the sheet as an overlay, not over the stage', async () => {
    const user = userEvent.setup();
    useRunAlerts.mockReturnValue(alertsOf(['critical']));
    act(() => {
      useCockpitUiStore.getState().setInspectorSheetOpen(true);
    });
    render(<SignalsStack runId={RUN_ID} />);

    await user.click(screen.getByTestId('signals-capsule'));
    expect(screen.getByTestId('signals-stack')).toHaveAttribute('data-mode', 'overlay');
  });

  it('restores its previous expanded state when the sheet closes', () => {
    useRunAlerts.mockReturnValue(alertsOf(['high']));
    render(<SignalsStack runId={RUN_ID} />);
    expect(screen.getByTestId('signals-stack')).toBeInTheDocument();

    act(() => {
      useCockpitUiStore.getState().setInspectorSheetOpen(true);
    });
    expect(screen.getByTestId('signals-capsule')).toBeInTheDocument();

    act(() => {
      useCockpitUiStore.getState().setInspectorSheetOpen(false);
    });
    expect(screen.getByTestId('signals-stack')).toHaveAttribute('data-mode', 'stack');
  });
});
