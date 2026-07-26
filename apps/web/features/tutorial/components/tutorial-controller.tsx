'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { usePathname, useRouter } from 'next/navigation';

import { useRunCommands } from '@/features/live-run/use-run-commands';

import {
  applyEvidence,
  clampProgress,
  flattenChapters,
  goBack,
  goNext,
  isObjectiveSatisfied,
  isWalkthroughComplete,
  jumpToChapter,
  pendingObjectiveKeys,
  resolveCurrentBeat,
  setDismissed,
  setMinimized,
  skipChapter,
} from '../tutorial-machine';
import { TUTORIAL_CHAPTERS } from '../tutorial-content';
import type { TutorialEvidence, TutorialEvidenceKey, TutorialProgress } from '../tutorial-contract';
import {
  clearActiveTutorialRunId,
  getActiveTutorialRunId,
  getArmToken,
  loadProgress,
  saveProgress,
  setActiveTutorialRunId,
  TUTORIAL_ARMED_EVENT,
} from '../tutorial-storage';
import {
  runClockNotice,
  setClockHeld,
  shouldHoldRunClock,
  shouldWatchRunClock,
  walkthroughNeedsLiveRun,
  withRunClockNotice,
} from '../tutorial-run-clock';
import { useTutorialEvidence } from '../use-tutorial-evidence';
import { CoachMarkOverlay } from './coach-mark-overlay';

// A run belongs to the guided tutorial when its scenario-version id carries this marker
// (e.g. `scenario-version:1.0.0-synthetic-training`). Matching the marker rather than a
// literal id keeps activation stable across scenario version bumps.
const TRAINING_SCENARIO_MARKER = 'synthetic-training';

// Shell surfaces the walkthrough is allowed to appear on — one per `TutorialSurface` the
// content points a beat at. The cockpit chapters live on the run surfaces; the tour chapters
// walk the operator through reports, admin and the catalogue, so the overlay has to survive
// the trip. Anywhere else (the design system, sign-in) it stays hidden even while armed.
// Note the final beat's launch-next dismisses before routing to `/scenarios`, so ending the
// tour still leaves the catalogue clean.
const TUTORIAL_SURFACE_PATTERN =
  /^\/(runs|incidents|after-action|replay|reports|admin|scenarios)(\/|$)/;

const NO_PENDING_KEYS: readonly TutorialEvidenceKey[] = [];

/**
 * Progress paired with the walkthrough it was loaded for. The pairing is the whole point.
 *
 * The identity is `(runId, armToken)`, not the run id alone. Restarting the training run
 * rebuilds it under the same id — run ids derive from seed plus scenario version — so the id
 * cannot distinguish "still the walkthrough I am showing" from "a fresh one was just armed".
 */
interface ScopedProgress {
  runId: string;
  armToken: number;
  progress: TutorialProgress;
}

/** Which walkthrough the storage layer currently says is armed. */
interface ArmState {
  runId: string | null;
  token: number;
}

const UNARMED: ArmState = { runId: null, token: 0 };

function extractRunId(pathname: string | null): string | null {
  if (!pathname) {
    return null;
  }
  const match = /\/runs\/([^/?#]+)/.exec(pathname);
  const captured = match?.[1];
  return captured ? decodeURIComponent(captured) : null;
}

/**
 * Top-level driver for the guided walkthrough. Mounted once at the shell layout: it resolves
 * the active run, confirms it is the training scenario, loads and persists progress, derives
 * evidence from the live run, and renders the coach mark.
 *
 * **Progress is scoped by construction.** Stored progress is held together with the
 * `(runId, armToken)` it was loaded for, and every read and write goes through that pair.
 * Until the pair matches the walkthrough currently on screen there is no progress to compute
 * from and nothing is written. That covers both ways in-memory state can go stale:
 *
 *  - the run id changes (a different run), where a monotonic `reached` would otherwise leak
 *    into the new run's storage while the load effect catches up with the route change;
 *  - the run id *doesn't* change but the walkthrough was re-armed. Restarting the training
 *    run rebuilds it under the same id, so an id-keyed effect never re-runs and the overlay
 *    keeps showing the pre-restart cursor while storage says beat one.
 */
export function TutorialController() {
  const pathname = usePathname();
  const router = useRouter();

  const beats = useMemo(() => flattenChapters(TUTORIAL_CHAPTERS), []);

  const [arm, setArm] = useState<ArmState>(UNARMED);
  const [scoped, setScoped] = useState<ScopedProgress | null>(null);
  const [trainingRunId, setTrainingRunId] = useState<string | null>(null);

  // Track what the storage layer says is armed: the pointer, so the overlay survives
  // navigation to surfaces with no run id in the URL (an incident route, reports, admin), and
  // the token, so re-arming the run already on screen re-initialises rather than sticking.
  useEffect(() => {
    const sync = () => {
      const runId = getActiveTutorialRunId();
      const token = getArmToken();
      setArm((prev) => (prev.runId === runId && prev.token === token ? prev : { runId, token }));
    };
    sync();
    window.addEventListener(TUTORIAL_ARMED_EVENT, sync);
    return () => {
      window.removeEventListener(TUTORIAL_ARMED_EVENT, sync);
    };
  }, []);

  const routeRunId = extractRunId(pathname);
  const runId = routeRunId ?? arm.runId;
  const armToken = arm.token;

  // Load persisted progress for the resolved walkthrough. The record is stamped with the
  // `(runId, armToken)` it was loaded for, so a route change or a re-arm that outruns this
  // effect leaves `progress` null rather than exposing the previous walkthrough's cursor.
  useEffect(() => {
    if (!runId) {
      setScoped(null);
      return;
    }
    setScoped((prev) =>
      prev?.runId === runId && prev.armToken === armToken
        ? prev
        : { runId, armToken, progress: clampProgress(loadProgress(runId), beats) },
    );
  }, [runId, armToken, beats]);

  const progress =
    scoped && scoped.runId === runId && scoped.armToken === armToken ? scoped.progress : null;
  const isTraining = trainingRunId != null && trainingRunId === runId;

  const pendingKeys = useMemo(
    () => (progress ? pendingObjectiveKeys(progress, beats) : NO_PENDING_KEYS),
    [progress, beats],
  );

  // Poll only for a confirmed training run whose walkthrough is still in flight: dismissed or
  // finished stands every query down, and `pendingKeys` narrows it further to the objectives
  // the operator is actually waiting on.
  const observing =
    progress != null &&
    isTraining &&
    !progress.dismissed &&
    !isWalkthroughComplete(progress, beats);

  // Whether the walkthrough still needs the world moving, and whether that means keeping an eye
  // on the run's clock. Both are pure reads of progress against the content — see
  // `tutorial-run-clock.ts`.
  const needsLiveRun = progress != null && walkthroughNeedsLiveRun(progress, beats);
  const clockHeld = progress?.clockHeld ?? false;
  const watchRunClock = shouldWatchRunClock({
    walkthroughActive: observing,
    needsLiveRun,
    clockHeld,
    pendingKeys,
  });

  const observation = useTutorialEvidence(runId, {
    enabled: observing,
    pendingKeys,
    watchRunClock,
  });

  // Confirm the scenario once the run detail resolves. Held as run-scoped state so the flag
  // can never be read against a different run than the one it was derived from.
  const scenarioVersionId = observation.scenarioVersionId;
  useEffect(() => {
    if (runId && scenarioVersionId?.includes(TRAINING_SCENARIO_MARKER)) {
      setTrainingRunId(runId);
    }
  }, [runId, scenarioVersionId]);

  // Point the pointer at a confirmed training run visited directly. This is bookkeeping, not
  // an arm: it must not bump the token, or every visit would restart the walkthrough.
  useEffect(() => {
    if (routeRunId && trainingRunId === routeRunId) {
      setActiveTutorialRunId(routeRunId);
      setArm((prev) => (prev.runId === routeRunId ? prev : { ...prev, runId: routeRunId }));
    }
  }, [routeRunId, trainingRunId]);

  /** Apply a machine transition to the walkthrough on screen, and only that one. */
  const commit = useCallback(
    (updater: (prev: TutorialProgress) => TutorialProgress) => {
      setScoped((prev) => {
        if (!prev || prev.runId !== runId || prev.armToken !== armToken) {
          return prev;
        }
        const next = updater(prev.progress);
        if (next === prev.progress) {
          return prev;
        }
        return { ...prev, progress: next };
      });
    },
    [runId, armToken],
  );

  // Persist against the run the record belongs to, never against whatever run is on screen.
  useEffect(() => {
    if (!scoped) {
      return;
    }
    saveProgress(scoped.runId, scoped.progress);
  }, [scoped]);

  // --- The one hold on the run clock -------------------------------------------------------
  //
  // A training run finalizes at its horizon after roughly eleven minutes of wall clock, which
  // is nowhere near long enough to read forty-two beats. Rather than let the run die under the
  // operator mid-chapter — stranding every hands-on beat behind evidence that will never
  // arrive — the walkthrough presses Pause sim for them once, near the end, and says so on the
  // card. `shouldHoldRunClock` owns every clause of that decision; this is only the wiring.
  const { pause } = useRunCommands(runId ?? '');
  const pauseRun = pause.mutate;
  // Which walkthrough the hold was issued for, so a restart (same run id, new arm token) gets
  // its own hold and a re-render never issues a second one.
  const holdIssuedFor = useRef<string | null>(null);
  const walkthroughKey = runId ? `${runId}#${String(armToken)}` : null;

  const wantsHold = shouldHoldRunClock({
    walkthroughActive: observing,
    needsLiveRun,
    clockHeld,
    runStatus: observation.runStatus,
    simTime: observation.simTime,
  });

  useEffect(() => {
    if (!wantsHold || !walkthroughKey || holdIssuedFor.current === walkthroughKey) {
      return;
    }
    // Spend the hold before the request goes out, and never retry it. A pause that fails leaves
    // the run to reach its horizon, where the run-ended copy takes over — worse than a hold,
    // far better than a mutation that fires again on every poll for the rest of the run.
    holdIssuedFor.current = walkthroughKey;
    commit((prev) => setClockHeld(prev, true));
    pauseRun();
  }, [wantsHold, walkthroughKey, commit, pauseRun]);

  const evidence: TutorialEvidence = useMemo(
    () => ({
      ...observation.evidence,
      // Beat one is acknowledged the moment the operator moves off it.
      welcomeAcknowledged: (progress?.reached ?? 0) > 0,
    }),
    [observation.evidence, progress?.reached],
  );

  // Fold evidence in: record satisfied objectives and honour `advanceOnSatisfied`.
  useEffect(() => {
    if (!observing) {
      return;
    }
    commit((prev) => applyEvidence(prev, evidence, beats));
  }, [observing, evidence, beats, commit]);

  const handleNext = useCallback(() => {
    commit((prev) => goNext(prev, beats));
  }, [commit, beats]);

  const handleBack = useCallback(() => {
    commit(goBack);
  }, [commit]);

  const handleSkipChapter = useCallback(() => {
    commit((prev) => skipChapter(prev, beats));
  }, [commit, beats]);

  const handleJumpToChapter = useCallback(
    (chapterId: string) => {
      commit((prev) => jumpToChapter(prev, chapterId, beats));
    },
    [commit, beats],
  );

  const handleMinimize = useCallback(() => {
    commit((prev) => setMinimized(prev, true));
  }, [commit]);

  const handleRestore = useCallback(() => {
    commit((prev) => setMinimized(prev, false));
  }, [commit]);

  // Dismissing hides the walkthrough and stands the polling down. It keeps both the stored
  // progress and the active pointer, so re-arming is a matter of clearing one flag rather
  // than starting the tour over.
  const handleDismiss = useCallback(() => {
    commit((prev) => setDismissed(prev, true));
  }, [commit]);

  const handleLaunchNext = useCallback(() => {
    commit((prev) => setDismissed(prev, true));
    clearActiveTutorialRunId();
    setArm((prev) => ({ ...prev, runId: null }));
    router.push('/scenarios');
  }, [commit, router]);

  const onTutorialSurface = pathname ? TUTORIAL_SURFACE_PATTERN.test(pathname) : false;
  const resolved = progress ? resolveCurrentBeat(progress, beats) : null;

  // The run's lifecycle, told in the walkthrough's own voice: why it is paused, or why a
  // finished run has stranded the step the operator is on. Folded into the beat rather than
  // handed to the overlay as a new state, so the notice inherits the card's layout, spotlight
  // and screen reader announcement and the overlay stays a pure function of its beat.
  const notice = isTraining
    ? runClockNotice({ runStatus: observation.runStatus, clockHeld, pendingKeys })
    : null;
  const displayed = useMemo(
    () => (resolved ? withRunClockNotice(resolved, notice) : null),
    [resolved, notice],
  );

  if (
    !progress ||
    !resolved ||
    !displayed ||
    !isTraining ||
    progress.dismissed ||
    !onTutorialSurface
  ) {
    return null;
  }

  const objectiveSatisfied =
    progress.completedBeatIds.includes(resolved.beat.id) ||
    isObjectiveSatisfied(resolved.beat, evidence);

  return (
    <CoachMarkOverlay
      resolved={displayed}
      chapters={TUTORIAL_CHAPTERS}
      evidence={evidence}
      progress={progress}
      objectiveSatisfied={objectiveSatisfied}
      onNext={handleNext}
      onBack={handleBack}
      onSkipChapter={handleSkipChapter}
      onJumpToChapter={handleJumpToChapter}
      onMinimize={handleMinimize}
      onRestore={handleRestore}
      onDismiss={handleDismiss}
      onBegin={handleNext}
      onLaunchNext={handleLaunchNext}
    />
  );
}
