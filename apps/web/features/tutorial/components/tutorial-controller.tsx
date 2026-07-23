'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

import { usePathname, useRouter } from 'next/navigation';

import {
  STEP_COUNT,
  advanceProgress,
  computeActiveStep,
  INITIAL_PROGRESS,
  type TutorialEvidence,
  type TutorialProgress,
} from '../tutorial-machine';
import { TUTORIAL_STEPS } from '../tutorial-steps';
import {
  clearActiveTutorialRunId,
  getActiveTutorialRunId,
  loadProgress,
  saveProgress,
  setActiveTutorialRunId,
} from '../tutorial-storage';
import { useTutorialEvidence } from '../use-tutorial-evidence';
import { CoachMarkOverlay } from './coach-mark-overlay';

// A run belongs to the guided tutorial when its scenario-version id carries this marker
// (e.g. `scenario-version:1.0.0-synthetic-training`). Matching the marker rather than a
// literal id keeps activation stable across scenario version bumps.
const TRAINING_SCENARIO_MARKER = 'synthetic-training';

// Shell surfaces where a run-scoped walkthrough should be visible. On the catalogue,
// admin, or design-system pages the overlay stays hidden even while a tutorial is armed.
const RUN_SURFACE_PATTERN = /^\/(runs|incidents|after-action|replay)(\/|$)/;

function extractRunId(pathname: string | null): string | null {
  if (!pathname) {
    return null;
  }
  const match = /\/runs\/([^/?#]+)/.exec(pathname);
  const captured = match?.[1];
  return captured ? decodeURIComponent(captured) : null;
}

/**
 * Top-level driver for the Synthetic Training guided walkthrough. Mounted once at the
 * shell layout: it resolves the active run, confirms it is the training scenario, derives
 * the active step from live evidence, persists progress, and renders the coach mark.
 *
 * It sits outside the per-run LiveRunProvider, so evidence is collected by self-polling
 * the same TanStack queries the live surfaces use rather than by websocket subscription.
 */
export function TutorialController() {
  const pathname = usePathname();
  const router = useRouter();

  const [armedRunId, setArmedRunId] = useState<string | null>(null);
  const [progress, setProgress] = useState<TutorialProgress>(INITIAL_PROGRESS);
  const [enabled, setEnabled] = useState(false);

  // Read the armed-tutorial pointer once on mount so the overlay survives navigation to
  // run surfaces that do not carry the runId in the URL (e.g. an incident route).
  useEffect(() => {
    setArmedRunId(getActiveTutorialRunId());
  }, []);

  const routeRunId = extractRunId(pathname);
  const runId = routeRunId ?? armedRunId;

  const observation = useTutorialEvidence(runId, enabled);
  const isTraining = observation.scenarioVersionId
    ? observation.scenarioVersionId.includes(TRAINING_SCENARIO_MARKER)
    : false;

  // Arm the pointer whenever a confirmed training run is visited directly.
  useEffect(() => {
    if (routeRunId && isTraining) {
      setActiveTutorialRunId(routeRunId);
      setArmedRunId(routeRunId);
    }
  }, [routeRunId, isTraining]);

  // Load persisted progress when the resolved run changes.
  useEffect(() => {
    if (!runId) {
      setProgress(INITIAL_PROGRESS);
      return;
    }
    setProgress(loadProgress(runId));
  }, [runId]);

  // Enable heavy evidence polling only for a confirmed, in-progress training run.
  useEffect(() => {
    setEnabled(Boolean(runId) && isTraining && !progress.dismissed);
  }, [runId, isTraining, progress.dismissed]);

  const onRunSurface = pathname ? RUN_SURFACE_PATTERN.test(pathname) : false;
  const active = Boolean(runId) && isTraining && !progress.dismissed && onRunSurface;

  const evidence: TutorialEvidence = useMemo(
    () => ({ ...observation.evidence, welcomeAcknowledged: progress.welcomeAcknowledged }),
    [observation.evidence, progress.welcomeAcknowledged],
  );

  const activeStep = active ? computeActiveStep(evidence, progress.reached) : -1;

  // Persist forward progress (monotonic) as evidence advances the walkthrough.
  useEffect(() => {
    if (activeStep < 0 || !runId) {
      return;
    }
    setProgress((prev) => {
      const next = advanceProgress(prev, activeStep);
      if (next !== prev) {
        saveProgress(runId, next);
      }
      return next;
    });
  }, [activeStep, runId]);

  const persist = useCallback(
    (updater: (prev: TutorialProgress) => TutorialProgress) => {
      setProgress((prev) => {
        const next = updater(prev);
        if (runId) {
          saveProgress(runId, next);
        }
        return next;
      });
    },
    [runId],
  );

  const handleBegin = useCallback(() => {
    persist((prev) => ({ ...prev, welcomeAcknowledged: true, reached: Math.max(prev.reached, 1) }));
  }, [persist]);

  const handleSkipStep = useCallback(() => {
    const target = Math.min(activeStep + 1, STEP_COUNT - 1);
    persist((prev) => ({
      ...prev,
      welcomeAcknowledged: prev.welcomeAcknowledged || activeStep === 0,
      reached: Math.max(prev.reached, target),
    }));
  }, [persist, activeStep]);

  const handleSkipTutorial = useCallback(() => {
    persist((prev) => ({ ...prev, dismissed: true }));
    clearActiveTutorialRunId();
    setArmedRunId(null);
  }, [persist]);

  const handleLaunchNext = useCallback(() => {
    persist((prev) => ({ ...prev, dismissed: true }));
    clearActiveTutorialRunId();
    setArmedRunId(null);
    router.push('/scenarios');
  }, [persist, router]);

  if (activeStep < 0) {
    return null;
  }
  const step = TUTORIAL_STEPS[activeStep];
  if (!step) {
    return null;
  }

  return (
    <CoachMarkOverlay
      step={step}
      onBegin={handleBegin}
      onSkipStep={handleSkipStep}
      onSkipTutorial={handleSkipTutorial}
      onLaunchNext={handleLaunchNext}
    />
  );
}
