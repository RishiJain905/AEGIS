import type { ReactNode } from 'react';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  EMPTY_EVIDENCE,
  TUTORIAL_PROGRESS_VERSION,
  type TutorialChapter,
  type TutorialEvidence,
} from '../tutorial-contract';
import type { CoachMarkOverlayProps } from './coach-mark-overlay';
import { armTutorial, resumeTutorial } from '../tutorial-storage';
import {
  HOLD_AT_ELAPSED_SIM_SECONDS,
  RUN_HELD_NOTICE,
  SIM_INITIAL_TIME_ISO,
} from '../tutorial-run-clock';
import { TutorialController } from './tutorial-controller';

const TRAINING_SCENARIO = 'scenario-version:1.0.0-synthetic-training';
const LIVE_SCENARIO = 'scenario-version:1.0.0-silent-relay';

/**
 * Everything the mocks need lives here: `vi.mock` factories are hoisted above the imports, so
 * they can only close over hoisted state. The walkthrough content, the overlay and the
 * evidence hook are all stubbed — this suite is about the controller's own job (resolving the
 * run, scoping progress to it, and wiring the machine to the overlay).
 */
const hoisted = vi.hoisted(() => ({
  overlayProps: [] as unknown[],
  route: { pathname: '/runs/run_a', push: (() => undefined) as (href: string) => void },
  observation: {
    scenarioVersionId: undefined as string | undefined,
    evidence: {} as Record<string, boolean>,
    runStatus: null as string | null,
    simTime: null as string | null,
  },
  observationCalls: [] as {
    runId: string | null;
    enabled: boolean;
    pendingKeys: string[];
    watchRunClock: boolean;
  }[],
  /** Every run command the controller issues. It may only ever issue `pause`, and only once. */
  runCommands: [] as string[],
  chapters: [
    {
      id: 'ch-one',
      title: 'One',
      summary: 'First',
      section: 'cockpit',
      beats: [
        {
          id: 'welcome',
          kind: 'learn',
          title: 'Welcome',
          body: [],
          anchors: [],
          pointerLabel: 'shell',
          primaryAction: 'begin',
        },
        {
          id: 'select-asset',
          kind: 'do',
          title: 'Select an asset',
          body: [],
          anchors: [],
          pointerLabel: 'graph',
          objective: {
            evidence: 'assetSelected',
            pending: 'Select an asset',
            done: 'Asset selected',
            advanceOnSatisfied: true,
          },
        },
      ],
    },
    {
      id: 'ch-two',
      title: 'Two',
      summary: 'Second',
      section: 'tour',
      beats: [
        {
          id: 'report',
          kind: 'do',
          title: 'Report',
          body: [],
          anchors: [],
          pointerLabel: 'reports',
          objective: { evidence: 'reportReady', pending: 'Wait', done: 'Ready' },
        },
      ],
    },
  ] satisfies TutorialChapter[],
}));

vi.mock('next/navigation', () => ({
  usePathname: () => hoisted.route.pathname,
  useRouter: () => ({ push: hoisted.route.push }),
}));

vi.mock('../tutorial-content', () => ({ TUTORIAL_CHAPTERS: hoisted.chapters }));

vi.mock('./coach-mark-overlay', () => ({
  CoachMarkOverlay: (props: unknown) => {
    hoisted.overlayProps.push(props);
    return null;
  },
}));

vi.mock('../use-tutorial-evidence', () => ({
  useTutorialEvidence: (
    runId: string | null,
    input: { enabled: boolean; pendingKeys: readonly string[]; watchRunClock: boolean },
  ) => {
    hoisted.observationCalls.push({
      runId,
      enabled: input.enabled,
      pendingKeys: [...input.pendingKeys],
      watchRunClock: input.watchRunClock,
    });
    return {
      scenarioVersionId: hoisted.observation.scenarioVersionId,
      runStatus: hoisted.observation.runStatus,
      simTime: hoisted.observation.simTime,
      runReady: true,
      evidence: hoisted.observation.evidence,
      activeIncidentId: null,
    };
  },
}));

// Stubbed at the boundary: the controller's job is to decide *whether* to pause, not to own the
// request. A real `useRunCommands` would also drag a QueryClientProvider into every test here.
vi.mock('@/features/live-run/use-run-commands', () => ({
  useRunCommands: () => ({
    pause: {
      mutate: () => {
        hoisted.runCommands.push('pause');
      },
    },
    resume: { mutate: () => undefined },
    stop: { mutate: () => undefined },
    step: { mutate: () => undefined },
  }),
}));

function latestProps(): CoachMarkOverlayProps | null {
  return (hoisted.overlayProps.at(-1) as CoachMarkOverlayProps | undefined) ?? null;
}

function storedProgress(runId: string): Record<string, unknown> | null {
  const raw = window.localStorage.getItem(`aegis:tutorial:progress:${runId}`);
  return raw ? (JSON.parse(raw) as Record<string, unknown>) : null;
}

function setEvidence(overrides: Partial<TutorialEvidence>): void {
  hoisted.observation.evidence = { ...EMPTY_EVIDENCE, ...overrides } as unknown as Record<
    string,
    boolean
  >;
}

/**
 * Render the controller inside a query client. The controller reaches for `useRunCommands`,
 * which is stubbed above but still sits behind TanStack's context in the real tree — wrapping
 * here keeps the harness honest about where the controller actually lives.
 */
function renderController(): { unmount: () => void; rerender: () => void } {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  const view = render(<TutorialController />, { wrapper: Wrapper });
  return {
    unmount: () => {
      view.unmount();
    },
    // Re-rendering the same element through the same wrapper is how these tests simulate a
    // route change or fresh evidence landing, so callers never pass the element themselves.
    rerender: () => {
      view.rerender(<TutorialController />);
    },
  };
}

beforeEach(() => {
  window.localStorage.clear();
  hoisted.overlayProps.length = 0;
  hoisted.observationCalls.length = 0;
  hoisted.runCommands.length = 0;
  hoisted.route.pathname = '/runs/run_a';
  hoisted.route.push = () => undefined;
  hoisted.observation.scenarioVersionId = TRAINING_SCENARIO;
  hoisted.observation.runStatus = null;
  hoisted.observation.simTime = null;
  setEvidence({});
});

afterEach(() => {
  cleanup();
});

describe('TutorialController · activation', () => {
  it('renders the first beat of a training run', () => {
    renderController();
    expect(latestProps()?.resolved.beat.id).toBe('welcome');
    expect(latestProps()?.chapters).toBe(hoisted.chapters);
    expect(storedProgress('run_a')).toMatchObject({
      version: TUTORIAL_PROGRESS_VERSION,
      cursor: 0,
    });
  });

  it('stays out of the way on a run that is not the training scenario', () => {
    hoisted.observation.scenarioVersionId = LIVE_SCENARIO;
    renderController();
    expect(latestProps()).toBeNull();
    expect(hoisted.observationCalls.every((call) => !call.enabled)).toBe(true);
  });

  it('stays hidden on surfaces the walkthrough does not cover', () => {
    window.localStorage.setItem('aegis:tutorial:active', 'run_a');
    hoisted.route.pathname = '/sign-in';
    renderController();
    expect(latestProps()).toBeNull();
  });

  it.each(['/reports', '/admin', '/scenarios', '/incidents/incident:inc_1'])(
    'follows the armed run onto %s, which carries no run id',
    (pathname) => {
      window.localStorage.setItem('aegis:tutorial:active', 'run_a');
      hoisted.route.pathname = pathname;
      renderController();
      expect(latestProps()?.resolved.beat.id).toBe('welcome');
    },
  );
});

describe('TutorialController · navigation', () => {
  it('advances, steps back and jumps chapters, persisting each move', () => {
    renderController();

    act(() => {
      latestProps()?.onNext();
    });
    expect(latestProps()?.resolved.beat.id).toBe('select-asset');
    expect(storedProgress('run_a')).toMatchObject({ cursor: 1, reached: 1 });

    act(() => {
      latestProps()?.onBack();
    });
    // Back moves the operator without giving up the ground they covered.
    expect(latestProps()?.resolved.beat.id).toBe('welcome');
    expect(storedProgress('run_a')).toMatchObject({ cursor: 0, reached: 1 });

    act(() => {
      latestProps()?.onJumpToChapter('ch-two');
    });
    expect(latestProps()?.resolved.beat.id).toBe('report');
    expect(storedProgress('run_a')).toMatchObject({ cursor: 2, reached: 2 });
  });

  it('resumes where the operator left off after a reload', () => {
    const { unmount } = renderController();
    act(() => {
      latestProps()?.onNext();
    });
    unmount();
    hoisted.overlayProps.length = 0;

    renderController();
    expect(latestProps()?.resolved.beat.id).toBe('select-asset');
  });

  it('minimises and restores without touching progress', () => {
    renderController();
    act(() => {
      latestProps()?.onNext();
    });

    act(() => {
      latestProps()?.onMinimize();
    });
    expect(latestProps()?.progress.minimized).toBe(true);
    expect(storedProgress('run_a')).toMatchObject({ minimized: true, cursor: 1 });

    act(() => {
      latestProps()?.onRestore();
    });
    expect(latestProps()?.progress.minimized).toBe(false);
  });
});

describe('TutorialController · evidence', () => {
  it('checks an objective off and pulls the walkthrough forward', () => {
    const { rerender } = renderController();
    act(() => {
      latestProps()?.onNext();
    });
    expect(latestProps()?.objectiveSatisfied).toBe(false);

    setEvidence({ assetSelected: true });
    rerender();

    // `select-asset` opted into auto-advance, so satisfying it moves on and records it.
    expect(latestProps()?.resolved.beat.id).toBe('report');
    expect(storedProgress('run_a')).toMatchObject({ completedBeatIds: ['select-asset'] });
  });

  it('keeps the done copy after the transient evidence goes away', () => {
    const { rerender } = renderController();
    act(() => {
      latestProps()?.onNext();
    });
    setEvidence({ assetSelected: true });
    rerender();

    act(() => {
      latestProps()?.onBack();
    });
    setEvidence({});
    rerender();

    // Back on `select-asset` with the selection cleared: the objective stays checked off.
    expect(latestProps()?.resolved.beat.id).toBe('select-asset');
    expect(latestProps()?.objectiveSatisfied).toBe(true);
  });

  it('only asks for the evidence the reached beats are waiting on', () => {
    const { rerender } = renderController();
    // Beat one is a `learn` beat — nothing to observe, so nothing to poll.
    expect(hoisted.observationCalls.at(-1)?.pendingKeys).toEqual([]);

    act(() => {
      latestProps()?.onNext();
    });
    expect(hoisted.observationCalls.at(-1)?.pendingKeys).toEqual(['assetSelected']);

    setEvidence({ assetSelected: true });
    rerender();
    // Satisfied, and the next beat's objective takes over the budget.
    expect(hoisted.observationCalls.at(-1)?.pendingKeys).toEqual(['reportReady']);
  });

  it('stands the polling down once the walkthrough is finished', () => {
    const { rerender } = renderController();
    act(() => {
      latestProps()?.onJumpToChapter('ch-two');
    });
    setEvidence({ assetSelected: true, reportReady: true });
    rerender();

    expect(hoisted.observationCalls.at(-1)?.enabled).toBe(false);
    expect(hoisted.observationCalls.at(-1)?.pendingKeys).toEqual([]);
  });
});

describe('TutorialController · dismissal', () => {
  it('hides the walkthrough and stops observing, but keeps the progress', () => {
    renderController();
    act(() => {
      latestProps()?.onNext();
    });

    const rendersBefore = hoisted.overlayProps.length;
    act(() => {
      latestProps()?.onDismiss();
    });

    expect(hoisted.overlayProps.length).toBe(rendersBefore);
    expect(storedProgress('run_a')).toMatchObject({ dismissed: true, cursor: 1, reached: 1 });
    expect(hoisted.observationCalls.at(-1)?.enabled).toBe(false);

    // Nothing renders on a later visit, but the record is still there to resume from.
    cleanup();
    hoisted.overlayProps.length = 0;
    renderController();
    expect(latestProps()).toBeNull();
    expect(storedProgress('run_a')).toMatchObject({ cursor: 1, completedBeatIds: [] });
  });

  it('routes to the catalogue on launch-next and disarms the pointer', () => {
    const push = vi.fn();
    hoisted.route.push = push;
    window.localStorage.setItem('aegis:tutorial:active', 'run_a');
    renderController();

    act(() => {
      latestProps()?.onLaunchNext();
    });

    expect(push).toHaveBeenCalledWith('/scenarios');
    expect(window.localStorage.getItem('aegis:tutorial:active')).toBeNull();
    expect(storedProgress('run_a')).toMatchObject({ dismissed: true });
  });
});

describe('TutorialController · run scoping', () => {
  it('never writes one run’s progress into another run’s storage', () => {
    const { rerender } = renderController();
    act(() => {
      latestProps()?.onNext();
    });
    act(() => {
      latestProps()?.onJumpToChapter('ch-two');
    });
    expect(storedProgress('run_a')).toMatchObject({ cursor: 2, reached: 2 });

    // The operator opens a different run. The loaded record still belongs to run_a for the
    // first render at the new route; nothing may be computed from it or written under run_b.
    hoisted.route.pathname = '/runs/run_b';
    rerender();

    expect(storedProgress('run_b')).toMatchObject({ cursor: 0, reached: 0 });
    expect(storedProgress('run_a')).toMatchObject({ cursor: 2, reached: 2 });
    expect(latestProps()?.resolved.beat.id).toBe('welcome');
  });

  it('does not inherit a previously viewed run’s cursor', () => {
    hoisted.route.pathname = '/runs/run_b';
    window.localStorage.setItem(
      'aegis:tutorial:progress:run_a',
      JSON.stringify({
        version: TUTORIAL_PROGRESS_VERSION,
        cursor: 2,
        reached: 2,
        completedBeatIds: [],
        minimized: false,
        dismissed: false,
      }),
    );

    renderController();

    expect(latestProps()?.resolved.beat.id).toBe('welcome');
    expect(storedProgress('run_a')).toMatchObject({ cursor: 2 });
  });

  it('re-initialises when the same run id is re-armed, without a reload', () => {
    // The training run's id derives from seed + scenario version, so restarting it from the
    // catalogue rebuilds it under the *same* id. Nothing in the route or the pointer moves —
    // only the arm token — and the overlay has to drop what it was showing anyway.
    renderController();
    act(() => {
      latestProps()?.onNext();
    });
    act(() => {
      latestProps()?.onJumpToChapter('ch-two');
    });
    expect(latestProps()?.resolved.beat.id).toBe('report');
    expect(storedProgress('run_a')).toMatchObject({ cursor: 2, reached: 2 });

    act(() => {
      armTutorial('run_a');
    });

    expect(latestProps()?.resolved.beat.id).toBe('welcome');
    expect(latestProps()?.progress).toMatchObject({ cursor: 0, reached: 0, completedBeatIds: [] });
    // Re-read from storage, not kept in memory: the stale cursor must not be written back.
    expect(storedProgress('run_a')).toMatchObject({ cursor: 0, reached: 0 });
  });

  it('drives the re-armed walkthrough, not the one it replaced', () => {
    renderController();
    act(() => {
      latestProps()?.onJumpToChapter('ch-two');
    });
    act(() => {
      armTutorial('run_a');
    });

    act(() => {
      latestProps()?.onNext();
    });

    expect(latestProps()?.resolved.beat.id).toBe('select-asset');
    expect(storedProgress('run_a')).toMatchObject({ cursor: 1, reached: 1 });
  });

  it('re-arming after a dismissal reopens where the operator left off', () => {
    renderController();
    act(() => {
      latestProps()?.onNext();
    });
    act(() => {
      latestProps()?.onDismiss();
    });
    hoisted.overlayProps.length = 0;

    act(() => {
      resumeTutorial('run_a');
    });

    // Resume is not restart: the in-memory `dismissed` is dropped, the cursor is not.
    expect(latestProps()?.resolved.beat.id).toBe('select-asset');
    expect(latestProps()?.progress).toMatchObject({ cursor: 1, dismissed: false });
  });

  it('does not restart a walkthrough merely because the operator navigated away and back', () => {
    const { rerender } = renderController();
    act(() => {
      latestProps()?.onJumpToChapter('ch-two');
    });

    hoisted.route.pathname = '/incidents/incident:inc_1';
    rerender();
    expect(latestProps()?.resolved.beat.id).toBe('report');

    hoisted.route.pathname = '/runs/run_a';
    rerender();
    expect(latestProps()?.resolved.beat.id).toBe('report');
    expect(storedProgress('run_a')).toMatchObject({ cursor: 2, reached: 2 });
  });

  it('takes the run id from the route over a stale armed pointer', () => {
    window.localStorage.setItem('aegis:tutorial:active', 'run_a');
    hoisted.route.pathname = '/runs/run_b';
    renderController();

    act(() => {
      latestProps()?.onNext();
    });

    expect(storedProgress('run_b')).toMatchObject({ cursor: 1 });
    expect(storedProgress('run_a')).toBeNull();
    expect(window.localStorage.getItem('aegis:tutorial:active')).toBe('run_b');
  });
});

describe('TutorialController · holding the run clock', () => {
  /** An absolute sim clock `seconds` into the run, the way the API reports it. */
  function simTimeAt(seconds: number): string {
    return new Date(Date.parse(SIM_INITIAL_TIME_ISO) + seconds * 1000).toISOString();
  }

  /** Put a walkthrough already part-way through into storage, without arming a fresh one. */
  function seedProgress(runId: string, overrides: Record<string, unknown>): void {
    window.localStorage.setItem('aegis:tutorial:active', runId);
    window.localStorage.setItem(
      `aegis:tutorial:progress:${runId}`,
      JSON.stringify({
        version: TUTORIAL_PROGRESS_VERSION,
        cursor: 0,
        reached: 0,
        completedBeatIds: [],
        minimized: false,
        dismissed: false,
        clockHeld: false,
        ...overrides,
      }),
    );
  }

  function nearHorizon(): void {
    hoisted.observation.runStatus = 'running';
    hoisted.observation.simTime = simTimeAt(HOLD_AT_ELAPSED_SIM_SECONDS);
  }

  it('pauses the run once as it closes on the horizon, and remembers doing it', () => {
    nearHorizon();
    const view = renderController();

    expect(hoisted.runCommands).toEqual(['pause']);
    expect(storedProgress('run_a')).toMatchObject({ clockHeld: true });

    // The stubbed mutation hands back a fresh identity on every render; the hold must still be
    // spent exactly once, or the operator gets re-paused for the rest of the run.
    act(() => {
      view.rerender();
    });
    expect(hoisted.runCommands).toEqual(['pause']);
  });

  it('leaves a run alone until it is near the horizon', () => {
    hoisted.observation.runStatus = 'running';
    hoisted.observation.simTime = simTimeAt(60);
    renderController();
    expect(hoisted.runCommands).toEqual([]);
    expect(storedProgress('run_a')).toMatchObject({ clockHeld: false });
  });

  it('never touches a run that is not the training scenario', () => {
    hoisted.observation.scenarioVersionId = LIVE_SCENARIO;
    nearHorizon();
    renderController();
    expect(hoisted.runCommands).toEqual([]);
  });

  it('does not re-pause a run the operator resumed by hand', () => {
    seedProgress('run_a', { clockHeld: true });
    nearHorizon();
    renderController();
    expect(hoisted.runCommands).toEqual([]);
  });

  it('explains the hold on the card, and stops once the operator resumes', () => {
    seedProgress('run_a', { clockHeld: true });
    hoisted.observation.runStatus = 'paused';
    const view = renderController();
    expect(latestProps()?.resolved.beat.body).toContain(RUN_HELD_NOTICE);
    // Same beat id, so progress, keys and test hooks all still line up.
    expect(latestProps()?.resolved.beat.id).toBe('welcome');

    hoisted.observation.runStatus = 'running';
    act(() => {
      view.rerender();
    });
    expect(latestProps()?.resolved.beat.body).not.toContain(RUN_HELD_NOTICE);
  });

  it('watches the run clock while the hold is still available, and stands down after', () => {
    nearHorizon();
    renderController();
    // Not on the very first render — the scenario is not confirmed yet — but once it is.
    expect(hoisted.observationCalls.some((call) => call.watchRunClock)).toBe(true);
    // The hold has been spent and no reached objective feeds off the simulation.
    expect(hoisted.observationCalls.at(-1)?.watchRunClock).toBe(false);
  });
});
