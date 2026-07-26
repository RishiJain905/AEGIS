import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';

import {
  CoachMarkOverlay,
  computeCardPosition,
  intersectionArea,
  spotlightRect,
} from './coach-mark-overlay';
import {
  EMPTY_EVIDENCE,
  INITIAL_PROGRESS,
  type ResolvedBeat,
  type TutorialChapter,
  type TutorialProgress,
} from '../tutorial-contract';

const CHAPTERS: TutorialChapter[] = [
  {
    id: 'chapter:orientation',
    title: 'Orientation',
    summary: 'What the command centre is showing you.',
    section: 'cockpit',
    beats: [
      {
        id: 'beat:welcome',
        kind: 'learn',
        title: 'Welcome to the command centre',
        body: ['A synthetic org is under attack. You have the console.'],
        anchors: [],
        pointerLabel: 'the run workspace',
        primaryAction: 'begin',
      },
      {
        id: 'beat:select-asset',
        kind: 'do',
        title: 'Pick an asset off the map',
        body: ['Every node is a real host in the synthetic estate.'],
        anchors: ['[data-tutorial-id="graph-stage"]'],
        pointerLabel: 'the operational graph',
        objective: {
          evidence: 'assetSelected',
          pending: 'Select any asset on the graph.',
          done: 'Asset selected — the inspector is now live.',
        },
      },
    ],
  },
  {
    id: 'chapter:containment',
    title: 'Containment',
    summary: 'Approving the response the agents propose.',
    section: 'cockpit',
    beats: [
      {
        id: 'beat:proposal',
        kind: 'do',
        title: 'Read the proposal',
        body: ['BASTION never executes; it proposes.'],
        anchors: ['[data-tutorial-id="proposal-panel"]'],
        pointerLabel: 'the proposal panel',
        objective: {
          evidence: 'proposalRaised',
          pending: 'Wait for a response proposal to land.',
          done: 'A proposal is waiting on your decision.',
        },
      },
    ],
  },
  {
    id: 'chapter:reports',
    title: 'Reports',
    summary: 'Where the run is written up afterwards.',
    section: 'tour',
    beats: [
      {
        id: 'beat:after-action',
        kind: 'learn',
        title: 'The after-action report',
        body: ['Every decision you made, scored.'],
        anchors: [],
        pointerLabel: 'the after-action report',
        primaryAction: 'launch-next',
      },
    ],
  },
];

const FLAT = CHAPTERS.flatMap((chapter) => chapter.beats);

function resolve(beatId: string): ResolvedBeat {
  const chapterIndex = CHAPTERS.findIndex((chapter) =>
    chapter.beats.some((beat) => beat.id === beatId),
  );
  const chapter = CHAPTERS[chapterIndex];
  if (!chapter) {
    throw new Error(`No chapter holds beat ${beatId}`);
  }
  const beatIndex = chapter.beats.findIndex((beat) => beat.id === beatId);
  const beat = chapter.beats[beatIndex];
  if (!beat) {
    throw new Error(`No beat ${beatId}`);
  }
  return {
    beat,
    chapter,
    index: FLAT.findIndex((candidate) => candidate.id === beatId),
    beatNumber: beatIndex + 1,
    beatCount: chapter.beats.length,
    chapterNumber: chapterIndex + 1,
    chapterCount: CHAPTERS.length,
  };
}

function renderOverlay(
  options: {
    beatId?: string;
    objectiveSatisfied?: boolean;
    progress?: Partial<TutorialProgress>;
  } = {},
) {
  const handlers = {
    onNext: vi.fn(),
    onBack: vi.fn(),
    onSkipChapter: vi.fn(),
    onJumpToChapter: vi.fn(),
    onMinimize: vi.fn(),
    onRestore: vi.fn(),
    onDismiss: vi.fn(),
    onBegin: vi.fn(),
    onLaunchNext: vi.fn(),
  };
  render(
    <CoachMarkOverlay
      resolved={resolve(options.beatId ?? 'beat:welcome')}
      chapters={CHAPTERS}
      evidence={EMPTY_EVIDENCE}
      progress={{ ...INITIAL_PROGRESS, reached: 1, ...options.progress }}
      objectiveSatisfied={options.objectiveSatisfied ?? false}
      {...handlers}
    />,
  );
  return handlers;
}

afterEach(() => {
  cleanup();
  document.body.innerHTML = '';
});

describe('CoachMarkOverlay', () => {
  it('renders an accessible dialog named by the beat title', () => {
    renderOverlay();
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'false');
    expect(dialog).toHaveAccessibleName('Welcome to the command centre');
  });

  it('announces chapter and beat position through a polite live region', () => {
    renderOverlay({ beatId: 'beat:select-asset' });
    const status = screen.getByRole('status');
    expect(status).toHaveAttribute('aria-live', 'polite');
    expect(status).toHaveTextContent('Chapter 1 of 3, Orientation');
    expect(status).toHaveTextContent('Beat 2 of 2: Pick an asset off the map');
    expect(status).toHaveTextContent('Pointing at the operational graph');
  });

  it('reads its position naturally rather than as a global step count', () => {
    renderOverlay({ beatId: 'beat:proposal' });
    expect(screen.getByTestId('tutorial-chapter-menu-trigger')).toHaveTextContent(
      'Chapter 2 of 3 · Beat 1 of 1',
    );
  });

  it('never captures pointer events on the dimming layer, keeping controls clickable', () => {
    renderOverlay();
    expect(screen.getByTestId('tutorial-overlay').className).toContain('pointer-events-none');
    expect(screen.getByTestId('tutorial-coach-mark').className).toContain('pointer-events-auto');
  });

  it('degrades to a centred card when no anchor is present in the DOM', () => {
    renderOverlay({ beatId: 'beat:proposal' });
    const card = screen.getByTestId('tutorial-coach-mark');
    expect(card).toBeInTheDocument();
    expect(card.style.top).toBe('50%');
    expect(card.style.left).toBe('50%');
    expect(card.style.transform).toBe('translate(-50%, -50%)');
  });

  it('anchors the card to the beat selector once the target is in the DOM', () => {
    const anchor = document.createElement('div');
    anchor.setAttribute('data-tutorial-id', 'graph-stage');
    document.body.append(anchor);

    renderOverlay({ beatId: 'beat:select-asset' });
    const card = screen.getByTestId('tutorial-coach-mark');
    // jsdom reports a zero rect, but the card must leave centred mode all the same.
    expect(card.style.transform).toBe('');
    expect(card.style.top).not.toBe('50%');
  });

  it('keeps the rendered card off a tall anchor that fills half the viewport', () => {
    // jsdom's viewport is 1024x768 and it lays nothing out, so the anchor's rect is stubbed
    // and the card falls back to its declared size. Before the placement rewrite this exact
    // geometry clamped the card to (16, 452) — dead centre of the spotlight.
    const anchorRect = { top: 0, left: 0, width: 512, height: 768 };
    const anchor = document.createElement('div');
    anchor.setAttribute('data-tutorial-id', 'graph-stage');
    anchor.getBoundingClientRect = () =>
      ({ ...anchorRect, right: 512, bottom: 768, x: 0, y: 0, toJSON: () => ({}) }) as DOMRect;
    document.body.append(anchor);

    renderOverlay({ beatId: 'beat:select-asset' });
    const card = screen.getByTestId('tutorial-coach-mark');
    const placed = {
      top: Number.parseFloat(card.style.top),
      left: Number.parseFloat(card.style.left),
      width: 384,
      height: 300,
    };

    expect(placed.left).toBeGreaterThan(512);
    expect(intersectionArea(placed, spotlightRect(anchorRect))).toBe(0);
  });

  describe('soft gating', () => {
    it('keeps Next enabled while an objective is outstanding', () => {
      const handlers = renderOverlay({
        beatId: 'beat:select-asset',
        objectiveSatisfied: false,
      });
      const next = screen.getByTestId('tutorial-next');
      expect(next).toBeEnabled();
      expect(screen.getByTestId('tutorial-objective')).toHaveAttribute('data-state', 'pending');
      expect(screen.getByTestId('tutorial-advance-hint')).toHaveTextContent(
        'Select any asset on the graph.',
      );
      fireEvent.click(next);
      expect(handlers.onNext).toHaveBeenCalledTimes(1);
    });

    it('swaps to the completed objective copy once the evidence lands', () => {
      renderOverlay({ beatId: 'beat:select-asset', objectiveSatisfied: true });
      expect(screen.getByTestId('tutorial-objective')).toHaveAttribute('data-state', 'done');
      expect(screen.getByTestId('tutorial-advance-hint')).toHaveTextContent(
        'Asset selected — the inspector is now live.',
      );
      expect(screen.getByRole('status')).toHaveTextContent('Objective met');
    });

    it('disables Back only on the very first beat', () => {
      renderOverlay({ beatId: 'beat:welcome' });
      expect(screen.getByTestId('tutorial-back')).toBeDisabled();
      cleanup();

      const handlers = renderOverlay({ beatId: 'beat:select-asset' });
      const back = screen.getByTestId('tutorial-back');
      expect(back).toBeEnabled();
      fireEvent.click(back);
      expect(handlers.onBack).toHaveBeenCalledTimes(1);
    });
  });

  describe('chapter menu', () => {
    it('lists every chapter grouped by section and marks the current one', () => {
      renderOverlay({ beatId: 'beat:select-asset' });
      fireEvent.click(screen.getByTestId('tutorial-chapter-menu-trigger'));

      const menu = screen.getByTestId('tutorial-chapter-menu');
      expect(menu).toBeInTheDocument();
      expect(screen.getByRole('group', { name: 'Jump to chapter' })).toBe(menu);
      expect(screen.getByRole('heading', { name: 'Cockpit' })).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: 'Tour' })).toBeInTheDocument();

      for (const chapter of CHAPTERS) {
        const option = screen.getByTestId(`tutorial-chapter-option-${chapter.id}`);
        expect(option).toHaveTextContent(chapter.title);
        expect(option).toHaveTextContent(chapter.summary);
      }
      expect(screen.getByTestId('tutorial-chapter-option-chapter:orientation')).toHaveAttribute(
        'aria-current',
        'step',
      );
      expect(screen.getByTestId('tutorial-chapter-option-chapter:reports')).not.toHaveAttribute(
        'aria-current',
      );
    });

    it('jumps to the selected chapter and closes the list', () => {
      const handlers = renderOverlay({ beatId: 'beat:select-asset' });
      fireEvent.click(screen.getByTestId('tutorial-chapter-menu-trigger'));
      fireEvent.click(screen.getByTestId('tutorial-chapter-option-chapter:reports'));

      expect(handlers.onJumpToChapter).toHaveBeenCalledWith('chapter:reports');
      expect(screen.queryByTestId('tutorial-chapter-menu')).not.toBeInTheDocument();
      expect(handlers.onDismiss).not.toHaveBeenCalled();
    });

    it('opens focused on the chapter the operator is in', () => {
      renderOverlay({ beatId: 'beat:select-asset' });
      fireEvent.click(screen.getByTestId('tutorial-chapter-menu-trigger'));
      expect(document.activeElement).toBe(
        screen.getByTestId('tutorial-chapter-option-chapter:orientation'),
      );
    });

    it('roves focus between chapters with the arrow keys', () => {
      renderOverlay({ beatId: 'beat:select-asset' });
      fireEvent.click(screen.getByTestId('tutorial-chapter-menu-trigger'));
      const menu = screen.getByTestId('tutorial-chapter-menu');

      fireEvent.keyDown(menu, { key: 'ArrowDown' });
      expect(document.activeElement).toBe(
        screen.getByTestId('tutorial-chapter-option-chapter:containment'),
      );
      fireEvent.keyDown(menu, { key: 'ArrowUp' });
      expect(document.activeElement).toBe(
        screen.getByTestId('tutorial-chapter-option-chapter:orientation'),
      );
    });

    it('closes on Escape without minimizing or dismissing the walkthrough', () => {
      const handlers = renderOverlay({ beatId: 'beat:select-asset' });
      const trigger = screen.getByTestId('tutorial-chapter-menu-trigger');
      fireEvent.click(trigger);

      fireEvent.keyDown(screen.getByTestId('tutorial-chapter-menu'), {
        key: 'Escape',
      });

      expect(screen.queryByTestId('tutorial-chapter-menu')).not.toBeInTheDocument();
      expect(screen.getByTestId('tutorial-coach-mark')).toBeInTheDocument();
      expect(handlers.onMinimize).not.toHaveBeenCalled();
      expect(handlers.onDismiss).not.toHaveBeenCalled();
      expect(document.activeElement).toBe(trigger);
    });
  });

  describe('minimize', () => {
    it('collapses to a pill that still reports where the operator is', () => {
      renderOverlay({ beatId: 'beat:proposal', progress: { minimized: true } });

      expect(screen.queryByTestId('tutorial-coach-mark')).not.toBeInTheDocument();
      const pill = screen.getByTestId('tutorial-restore');
      expect(pill).toHaveAccessibleName(
        'Reopen the walkthrough. Chapter 2 of 3, Beat 1 of 1, Containment.',
      );
    });

    it('wires the pill back to restore and the card control to minimize', () => {
      const minimizedHandlers = renderOverlay({
        progress: { minimized: true },
      });
      fireEvent.click(screen.getByTestId('tutorial-restore'));
      expect(minimizedHandlers.onRestore).toHaveBeenCalledTimes(1);
      cleanup();

      const handlers = renderOverlay();
      fireEvent.click(screen.getByTestId('tutorial-minimize'));
      expect(handlers.onMinimize).toHaveBeenCalledTimes(1);
      expect(handlers.onDismiss).not.toHaveBeenCalled();
    });
  });

  describe('keyboard', () => {
    it('minimizes on Escape instead of ending the walkthrough', () => {
      const handlers = renderOverlay();
      fireEvent.keyDown(screen.getByTestId('tutorial-coach-mark'), {
        key: 'Escape',
      });
      expect(handlers.onMinimize).toHaveBeenCalledTimes(1);
      expect(handlers.onDismiss).not.toHaveBeenCalled();
    });

    it('advances on ArrowRight and Enter, and steps back on ArrowLeft', () => {
      const handlers = renderOverlay({ beatId: 'beat:select-asset' });
      const card = screen.getByTestId('tutorial-coach-mark');

      fireEvent.keyDown(card, { key: 'ArrowRight' });
      fireEvent.keyDown(card, { key: 'Enter' });
      expect(handlers.onNext).toHaveBeenCalledTimes(2);

      fireEvent.keyDown(card, { key: 'ArrowLeft' });
      expect(handlers.onBack).toHaveBeenCalledTimes(1);
    });

    it('leaves Enter to the control under focus rather than double-advancing', () => {
      const handlers = renderOverlay({ beatId: 'beat:select-asset' });
      fireEvent.keyDown(screen.getByTestId('tutorial-skip-chapter'), {
        key: 'Enter',
      });
      expect(handlers.onNext).not.toHaveBeenCalled();
    });

    it('holds Back at the first beat', () => {
      const handlers = renderOverlay({ beatId: 'beat:welcome' });
      fireEvent.keyDown(screen.getByTestId('tutorial-coach-mark'), {
        key: 'ArrowLeft',
      });
      expect(handlers.onBack).not.toHaveBeenCalled();
    });
  });

  it('wires the beat primary actions', () => {
    const welcome = renderOverlay({ beatId: 'beat:welcome' });
    fireEvent.click(screen.getByTestId('tutorial-begin'));
    expect(welcome.onBegin).toHaveBeenCalledTimes(1);
    cleanup();

    const debrief = renderOverlay({ beatId: 'beat:after-action' });
    fireEvent.click(screen.getByTestId('tutorial-launch-next'));
    expect(debrief.onLaunchNext).toHaveBeenCalledTimes(1);
  });

  it('skips the chapter and dismisses only through their own controls', () => {
    const handlers = renderOverlay({ beatId: 'beat:select-asset' });
    fireEvent.click(screen.getByTestId('tutorial-skip-chapter'));
    expect(handlers.onSkipChapter).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByTestId('tutorial-dismiss'));
    expect(handlers.onDismiss).toHaveBeenCalledTimes(1);
  });

  it.each(['dark', 'light'] as const)(
    'has no detectable accessibility violations (%s theme)',
    async (theme) => {
      document.documentElement.setAttribute('data-theme', theme);
      try {
        renderOverlay({ beatId: 'beat:select-asset' });
        const results = await axe(document.body);
        expect(results.violations).toHaveLength(0);
      } finally {
        document.documentElement.removeAttribute('data-theme');
      }
    },
  );

  it('has no detectable accessibility violations with the chapter list open', async () => {
    renderOverlay({ beatId: 'beat:select-asset' });
    fireEvent.click(screen.getByTestId('tutorial-chapter-menu-trigger'));
    const results = await axe(document.body);
    expect(results.violations).toHaveLength(0);
  });
});

interface Box {
  top: number;
  left: number;
  width: number;
  height: number;
}

const VIEWPORTS = [
  { name: '1600x1000', width: 1600, height: 1000 },
  { name: '1920x1200', width: 1920, height: 1200 },
];

const CARD = { width: 384, height: 300 };
/** The card grows well past its resting height once the chapter list is open. */
const TALL_CARD = { width: 384, height: 560 };

function placedCard(anchor: Box, viewport: { width: number; height: number }, card = CARD): Box {
  return { ...computeCardPosition(anchor, card, viewport), ...card };
}

function occlusion(anchor: Box, viewport: { width: number; height: number }, card = CARD): number {
  const spot = spotlightRect(anchor);
  return intersectionArea(placedCard(anchor, viewport, card), spot) / (spot.width * spot.height);
}

/**
 * Brute-force oracle: is there *any* on-screen position where the card clears the
 * spotlight? Derived independently of the placement algorithm, so it can catch the
 * algorithm giving up while a clear position existed.
 */
function clearPositionExists(
  anchor: Box,
  viewport: { width: number; height: number },
  card = CARD,
): boolean {
  const spot = spotlightRect(anchor);
  for (let top = 16; top <= viewport.height - card.height - 16; top += 8) {
    for (let left = 16; left <= viewport.width - card.width - 16; left += 8) {
      if (intersectionArea({ top, left, ...card }, spot) === 0) {
        return true;
      }
    }
  }
  return false;
}

/** The smallest overlap any viewport corner can achieve — the fallback's quality bar. */
function bestCornerOverlap(
  anchor: Box,
  viewport: { width: number; height: number },
  card = CARD,
): number {
  const spot = spotlightRect(anchor);
  const maxLeft = Math.max(16, viewport.width - card.width - 16);
  const maxTop = Math.max(16, viewport.height - card.height - 16);
  return Math.min(
    ...[
      { top: 16, left: 16 },
      { top: 16, left: maxLeft },
      { top: maxTop, left: 16 },
      { top: maxTop, left: maxLeft },
    ].map((corner) => intersectionArea({ ...corner, ...card }, spot)),
  );
}

/**
 * The placement contract, in full: clear of the spotlight whenever any on-screen position
 * is, and otherwise the least-occluding corner available — never a silent burial.
 *
 * Both halves matter. Some real anchors (the graph stage flanked by two docks that are
 * each narrower than the card) genuinely admit no clear position at any viewport size, and
 * asserting only the happy path would either fail on them or quietly skip them.
 */
function expectBestPlacement(
  anchor: Box,
  viewport: { width: number; height: number },
  card = CARD,
): void {
  const spot = spotlightRect(anchor);
  const overlap = intersectionArea(placedCard(anchor, viewport, card), spot);

  if (clearPositionExists(anchor, viewport, card)) {
    expect(overlap).toBe(0);
    return;
  }
  expect(overlap).toBe(bestCornerOverlap(anchor, viewport, card));
  // The defect this replaces buried 62-97% of the spotlight. A corner never gets close.
  expect(overlap / (spot.width * spot.height)).toBeLessThan(0.2);
}

describe('computeCardPosition', () => {
  describe.each(VIEWPORTS)('at $name', (viewport) => {
    const geometries: { name: string; anchor: Box }[] = [
      {
        name: 'a small control in the top-left',
        anchor: { top: 24, left: 24, width: 180, height: 40 },
      },
      {
        name: 'a small control in the bottom-right',
        anchor: { top: viewport.height - 64, left: viewport.width - 204, width: 180, height: 40 },
      },
      {
        name: 'a tall dock filling the left half',
        anchor: { top: 0, left: 0, width: Math.round(viewport.width / 2), height: viewport.height },
      },
      {
        name: 'the graph stage between two docks',
        anchor: { top: 96, left: 320, width: viewport.width - 640, height: viewport.height - 260 },
      },
      {
        name: 'a full-width status strip across the top',
        anchor: { top: 0, left: 0, width: viewport.width, height: 72 },
      },
      {
        name: 'a panel pinned to the right edge',
        anchor: { top: 120, left: viewport.width - 360, width: 360, height: viewport.height - 240 },
      },
    ];

    it.each(geometries)('keeps the card off the spotlight for $name', ({ anchor }) => {
      expectBestPlacement(anchor, viewport);
    });

    it.each(geometries)(
      'keeps a chapter-list-sized card off the spotlight for $name',
      ({ anchor }) => {
        expectBestPlacement(anchor, viewport, TALL_CARD);
      },
    );

    // Pins which shapes are geometrically solvable, so a change that makes a solvable
    // anchor unsolvable (a wider card, a bigger gap) shows up here rather than silently
    // downgrading that beat to the fallback corner.
    it('can clear every sampled anchor except the dock-flanked graph stage', () => {
      const solvable = geometries
        .filter(({ anchor }) => clearPositionExists(anchor, viewport))
        .map(({ name }) => name);
      expect(solvable).toEqual([
        'a small control in the top-left',
        'a small control in the bottom-right',
        'a tall dock filling the left half',
        'a full-width status strip across the top',
        'a panel pinned to the right edge',
      ]);
    });

    it('stays inside the viewport margins', () => {
      for (const { anchor } of geometries) {
        const card = placedCard(anchor, viewport);
        expect(card.left).toBeGreaterThanOrEqual(16);
        expect(card.top).toBeGreaterThanOrEqual(16);
        expect(card.left + card.width).toBeLessThanOrEqual(viewport.width - 16);
        expect(card.top + card.height).toBeLessThanOrEqual(viewport.height - 16);
      }
    });

    it('prefers below the anchor when there is room, because that is where a callout reads', () => {
      const anchor: Box = { top: 24, left: 24, width: 180, height: 40 };
      const card = placedCard(anchor, viewport);
      expect(card.top).toBe(anchor.top + anchor.height + 8 + 14);
    });

    it('sits beside a tall anchor rather than clamping back over it', () => {
      const anchor: Box = {
        top: 0,
        left: 0,
        width: Math.round(viewport.width / 2),
        height: viewport.height,
      };
      const card = placedCard(anchor, viewport);
      expect(card.left).toBeGreaterThan(anchor.left + anchor.width);
    });

    it('degrades to the least-occluding corner when no placement can clear the anchor', () => {
      // ~90% of the viewport: every band is narrower than the card, so some overlap is
      // geometrically unavoidable. The fallback must still be the best available corner.
      const anchor: Box = {
        top: Math.round(viewport.height * 0.05),
        left: Math.round(viewport.width * 0.05),
        width: Math.round(viewport.width * 0.9),
        height: Math.round(viewport.height * 0.9),
      };
      expect(clearPositionExists(anchor, viewport)).toBe(false);

      const spot = spotlightRect(anchor);
      const corners = [
        { top: 16, left: 16 },
        { top: 16, left: viewport.width - CARD.width - 16 },
        { top: viewport.height - CARD.height - 16, left: 16 },
        { top: viewport.height - CARD.height - 16, left: viewport.width - CARD.width - 16 },
      ];
      const bestPossible = Math.min(
        ...corners.map((corner) => intersectionArea({ ...corner, ...CARD }, spot)),
      );

      const card = placedCard(anchor, viewport);
      expect(intersectionArea(card, spot)).toBe(bestPossible);
      // The regression this replaces buried 97% of the spotlight; a corner never does.
      expect(occlusion(anchor, viewport)).toBeLessThan(0.1);
    });
  });

  it('never overlaps the spotlight across a sweep of anchor geometries', () => {
    const viewport = { width: 1600, height: 1000 };
    let checked = 0;
    for (let left = 0; left <= 1200; left += 200) {
      for (let top = 0; top <= 800; top += 200) {
        for (const width of [120, 480, 900, 1400]) {
          for (const height of [60, 300, 700, 960]) {
            const anchor: Box = { top, left, width, height };
            if (!clearPositionExists(anchor, viewport)) {
              continue;
            }
            checked += 1;
            expect(intersectionArea(placedCard(anchor, viewport), spotlightRect(anchor))).toBe(0);
          }
        }
      }
    }
    expect(checked).toBeGreaterThan(100);
  });
});
