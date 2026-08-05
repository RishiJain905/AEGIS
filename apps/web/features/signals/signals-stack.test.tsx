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

  // Docked *against* the sheet's leading edge, not floating over its header — where it used
  // to cover the subject line as soon as the sheet narrowed.
  it('steps clear of the sheet it docks to, and of both sheets when they share', () => {
    render(<SignalsStack runId={RUN_ID} />);
    const dock = () =>
      screen.getByTestId('signals-capsule').style.getPropertyValue('--aegis-signals-dock');

    expect(dock()).toBe('0.75rem');

    act(() => {
      useCockpitUiStore.getState().setInspectorSheetOpen(true);
    });
    // The inspector's own solo width, so the capsule sits beside it rather than on it.
    expect(dock()).toBe('calc(min(30rem, 42%) + 0.75rem)');

    act(() => {
      useCockpitUiStore.getState().setCopilotSheetOpen(true);
    });
    expect(dock()).toBe('calc(min(26rem, 32%) + 0.75rem)');
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

/**
 * The stage's top edge is shared with the graph's own chrome row — search on the left, View
 * options and the +/−/Reset zoom cluster on the right. Signals rested at a fixed 6rem, which
 * clears that row only while nothing wraps; the stage header and the chrome row both do, and
 * when they did the capsule rendered on top of the zoom buttons and swallowed their clicks.
 *
 * jsdom has no layout, so the stage and the chrome row are given real rectangles here and the
 * assertion is the geometry contract itself: signals starts at or below the row's bottom edge.
 */
describe('SignalsStack × graph chrome collision', () => {
  const STAGE_TOP = 200;

  /**
   * The stage as the cockpit builds it: the graph's chrome row floating over it, and the
   * signals furniture beside that. Signals mounts into its own child so the React root does
   * not take the chrome row with it.
   */
  function stageWithChromeRow(rowBottom: number) {
    const stage = document.createElement('div');
    stage.setAttribute('data-testid', 'cockpit-stage');
    const row = document.createElement('div');
    row.setAttribute('data-testid', 'graph-chrome-row');
    const mount = document.createElement('div');
    stage.append(row, mount);
    document.body.append(stage);

    stage.getBoundingClientRect = () => ({ top: STAGE_TOP, bottom: STAGE_TOP + 800 }) as DOMRect;
    row.getBoundingClientRect = () => ({ top: STAGE_TOP + 40, bottom: rowBottom }) as DOMRect;
    return { stage, row, mount };
  }

  function topOf(element: HTMLElement): number {
    return Number.parseFloat(element.style.top);
  }

  afterEach(() => {
    document.querySelectorAll('[data-testid="cockpit-stage"]').forEach((node) => {
      node.remove();
    });
  });

  it('starts below a chrome row that has wrapped past its resting place', () => {
    // A wrapped row whose zoom cluster ends 140px into the stage — past the old 6rem.
    const { mount } = stageWithChromeRow(STAGE_TOP + 140);
    render(<SignalsStack runId={RUN_ID} />, { container: mount, baseElement: document.body });

    const capsule = screen.getByTestId('signals-capsule');
    expect(topOf(capsule)).toBeGreaterThanOrEqual(140);
  });

  it('clears the chrome row in the docked state too, where a sheet holds the right side', () => {
    const { mount } = stageWithChromeRow(STAGE_TOP + 140);
    act(() => {
      useCockpitUiStore.getState().setInspectorSheetOpen(true);
    });
    render(<SignalsStack runId={RUN_ID} />, { container: mount, baseElement: document.body });

    const capsule = screen.getByTestId('signals-capsule');
    expect(capsule).toHaveAttribute('data-docked', 'sheet');
    expect(topOf(capsule)).toBeGreaterThanOrEqual(140);
  });

  it('keeps the expanded stack clear of the chrome row as well', () => {
    const { mount } = stageWithChromeRow(STAGE_TOP + 140);
    useRunAlerts.mockReturnValue(alertsOf(['critical']));
    render(<SignalsStack runId={RUN_ID} />, { container: mount, baseElement: document.body });

    expect(topOf(screen.getByTestId('signals-stack'))).toBeGreaterThanOrEqual(140);
  });

  it('never floats above its resting place when the row measures short or not at all', () => {
    const { mount } = stageWithChromeRow(STAGE_TOP + 10);
    render(<SignalsStack runId={RUN_ID} />, { container: mount, baseElement: document.body });
    // A short (or unlaid-out) row must not pull signals up into the chrome it clears.
    expect(topOf(screen.getByTestId('signals-capsule'))).toBe(96);
  });
});
