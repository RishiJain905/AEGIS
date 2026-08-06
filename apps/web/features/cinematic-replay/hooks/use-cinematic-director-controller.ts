'use client';

import { useEffect, useRef } from 'react';

import { useReducedMotion } from '@aegis/ui';

import { GraphViewMode } from '@/features/cinematic-graph/contracts';
import { useCinematicGraphStore } from '@/features/cinematic-graph/stores/cinematic-graph-store';
import { planCinematicBeats } from '@/features/cinematic-replay/lib/beat-planner';
import { speedToBeatIntervalMs } from '@/features/cinematic-replay/lib/camera-director';
import { presentationHintsForRun } from '@/features/cinematic-replay/lib/silent-relay-hints';
import { useCinematicReplayStore } from '@/features/cinematic-replay/stores/cinematic-replay-store';
import { useReplayStore } from '@/stores/replay-store';
import { useWorkspaceUiStore } from '@/stores/workspace-ui-store';

/**
 * Orchestrates cinematic director ↔ Phase 26 replay cursor ↔ Phase 27 camera.
 * Presentation only — never mutates authoritative replay/live domain state beyond cursor seeks.
 */
export function useCinematicDirectorController(runId: string): void {
  const reducedMotion = useReducedMotion();
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const plannedForRef = useRef<string | null>(null);
  const applyingRef = useRef(false);

  const reconstructedState = useReplayStore((state) => state.reconstructedState);
  const loadStatus = useReplayStore((state) => state.loadStatus);
  const maxSequence = useReplayStore((state) => state.maxSequence);
  const setCursorSequence = useReplayStore((state) => state.setCursorSequence);
  const cursor = useReplayStore((state) => state.cursor);

  const mode = useCinematicReplayStore((state) => state.mode);
  const status = useCinematicReplayStore((state) => state.status);
  const speed = useCinematicReplayStore((state) => state.speed);
  const plan = useCinematicReplayStore((state) => state.plan);
  const setPlan = useCinematicReplayStore((state) => state.setPlan);
  const setReducedMotion = useCinematicReplayStore((state) => state.setReducedMotion);
  const setError = useCinematicReplayStore((state) => state.setError);
  const goToBeat = useCinematicReplayStore((state) => state.goToBeat);
  const nextBeat = useCinematicReplayStore((state) => state.nextBeat);
  const setStatus = useCinematicReplayStore((state) => state.setStatus);
  const clear = useCinematicReplayStore((state) => state.clear);
  const lastApplied = useCinematicReplayStore((state) => state.lastApplied);

  const setCamera = useCinematicGraphStore((state) => state.setCamera);
  const setViewMode = useCinematicGraphStore((state) => state.setViewMode);
  const setSelectedEntityId = useWorkspaceUiStore((state) => state.setSelectedEntityId);

  useEffect(() => {
    setReducedMotion(reducedMotion);
  }, [reducedMotion, setReducedMotion]);

  // Reset plan cache when leaving cinematic mode
  useEffect(() => {
    if (mode !== 'cinematic') {
      plannedForRef.current = null;
    }
  }, [mode]);

  // Build plan once per cinematic session from the fullest reconstructed state available.
  // Prefer planning when cursor is at/near maxSequence so entity surfaces are complete.
  useEffect(() => {
    if (mode !== 'cinematic') {
      return;
    }
    if (loadStatus === 'unavailable' || loadStatus === 'error') {
      setPlan(null);
      setError({
        code: 'CINEMATIC_REPLAY_UNAVAILABLE',
        message:
          'Cinematic replay cannot start: replay data is unavailable, malformed, or incompatible.',
      });
      plannedForRef.current = null;
      return;
    }
    if (!reconstructedState || reconstructedState.runId !== runId) {
      return;
    }

    const planKey = `${runId}:${String(maxSequence)}`;
    if (plannedForRef.current === planKey && plan) {
      return;
    }

    // Wait until we have a late-enough reconstruction for coherent chapters when possible
    const sequence = reconstructedState.cursor.sequence;
    const readyEnough = sequence >= Math.min(maxSequence, 120) || maxSequence < 120;
    if (!readyEnough && plannedForRef.current === null) {
      // Seek once to max so the plan can include the run's full set of chapters
      if (cursor && cursor.sequence !== maxSequence) {
        setCursorSequence(maxSequence);
      }
      return;
    }

    try {
      const planned = planCinematicBeats({
        state: reconstructedState,
        // Only the hints authored for this run's own scenario; every other run plans
        // from its replay state alone.
        hints: presentationHintsForRun(reconstructedState.run?.scenarioVersionId),
      });
      setPlan(planned);
      setError(null);
      plannedForRef.current = planKey;
    } catch (error) {
      setPlan(null);
      plannedForRef.current = null;
      setError({
        code: 'CINEMATIC_VALIDATION_FAILED',
        message:
          error instanceof Error
            ? error.message
            : 'Failed to build cinematic plan from replay state.',
      });
    }
  }, [
    mode,
    loadStatus,
    reconstructedState,
    runId,
    maxSequence,
    plan,
    cursor,
    setCursorSequence,
    setPlan,
    setError,
  ]);

  // Apply camera/selection/cursor when director advances a beat.
  // Do not force 3D here — entering cinematic mode selects 3D once; Open-in-2D must stick.
  useEffect(() => {
    if (mode !== 'cinematic' || !lastApplied || applyingRef.current) {
      return;
    }
    applyingRef.current = true;
    try {
      setCamera(lastApplied.camera);
      if (lastApplied.focusEntityId) {
        setSelectedEntityId(lastApplied.focusEntityId);
      }
      if (cursor && cursor.sequence !== lastApplied.sequence) {
        setCursorSequence(lastApplied.sequence, lastApplied.beat.provenance.incidentId ?? null);
      }
    } finally {
      applyingRef.current = false;
    }
  }, [mode, lastApplied, setCamera, setSelectedEntityId, setCursorSequence, cursor]);

  // Prefer 3D once when entering cinematic mode (unless reduced motion).
  useEffect(() => {
    if (mode !== 'cinematic') {
      return;
    }
    if (!reducedMotion) {
      setViewMode(GraphViewMode.THREE_D);
    }
  }, [mode, reducedMotion, setViewMode]);

  // Auto-advance beats while playing (disabled under reduced motion)
  useEffect(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (mode !== 'cinematic' || status !== 'playing' || !plan) {
      return;
    }
    if (reducedMotion) {
      return;
    }
    timerRef.current = setInterval(() => {
      const { beatIndex, plan: currentPlan } = useCinematicReplayStore.getState();
      if (!currentPlan || beatIndex >= currentPlan.beats.length - 1) {
        setStatus('paused');
        return;
      }
      nextBeat();
    }, speedToBeatIntervalMs(speed));
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [mode, status, plan, speed, reducedMotion, nextBeat, setStatus]);

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      clear();
    };
  }, [clear]);

  useEffect(() => {
    if (mode === 'cinematic' && plan && !lastApplied) {
      goToBeat(0);
    }
  }, [mode, plan, lastApplied, goToBeat]);
}
