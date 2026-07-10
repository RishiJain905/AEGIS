import { create } from 'zustand';

import type {
  CinematicDirectorStatus,
  CinematicPlanV1,
  CinematicPlaybackSpeed,
  CinematicPlaybackStateV1,
  CinematicSessionMode,
} from '@aegis/contracts-ts';

import {
  applyBeatCamera,
  beatIndexForSequence,
  chapterIndexForBeat,
  type CameraDirectorApplyResult,
} from '../lib/camera-director';

export interface CinematicReplayUiState {
  mode: CinematicSessionMode;
  status: CinematicDirectorStatus;
  plan: CinematicPlanV1 | null;
  chapterIndex: number;
  beatIndex: number;
  speed: CinematicPlaybackSpeed;
  reducedMotion: boolean;
  captionsEnabled: boolean;
  lastApplied: CameraDirectorApplyResult | null;
  lastError: { code: string; message: string } | null;
  planWarnings: string[];
  setMode: (mode: CinematicSessionMode) => void;
  setPlan: (plan: CinematicPlanV1 | null) => void;
  setStatus: (status: CinematicDirectorStatus) => void;
  setSpeed: (speed: CinematicPlaybackSpeed) => void;
  setReducedMotion: (reducedMotion: boolean) => void;
  setCaptionsEnabled: (enabled: boolean) => void;
  setError: (error: { code: string; message: string } | null) => void;
  goToBeat: (beatIndex: number) => CameraDirectorApplyResult | null;
  nextBeat: () => CameraDirectorApplyResult | null;
  previousBeat: () => CameraDirectorApplyResult | null;
  goToChapter: (chapterIndex: number) => CameraDirectorApplyResult | null;
  syncFromReplaySequence: (sequence: number) => CameraDirectorApplyResult | null;
  takeFreeCamera: () => void;
  resumeCinematic: () => void;
  clear: () => void;
  toPlaybackState: (runId: string) => CinematicPlaybackStateV1 | null;
}

const initialState = {
  mode: 'normal' as CinematicSessionMode,
  status: 'idle' as CinematicDirectorStatus,
  plan: null as CinematicPlanV1 | null,
  chapterIndex: 0,
  beatIndex: 0,
  speed: '1x' as CinematicPlaybackSpeed,
  reducedMotion: false,
  captionsEnabled: true,
  lastApplied: null as CameraDirectorApplyResult | null,
  lastError: null as { code: string; message: string } | null,
  planWarnings: [] as string[],
};

export const useCinematicReplayStore = create<CinematicReplayUiState>((set, get) => ({
  ...initialState,
  setMode: (mode) => {
    set({ mode, status: mode === 'cinematic' ? get().status : 'idle' });
  },
  setPlan: (plan) => {
    set({
      plan,
      planWarnings: plan?.warnings ?? [],
      chapterIndex: 0,
      beatIndex: 0,
      lastApplied: plan ? applyBeatCamera(plan, 0) : null,
      lastError: null,
    });
  },
  setStatus: (status) => {
    set({ status });
  },
  setSpeed: (speed) => {
    set({ speed });
  },
  setReducedMotion: (reducedMotion) => {
    set({ reducedMotion });
  },
  setCaptionsEnabled: (captionsEnabled) => {
    set({ captionsEnabled });
  },
  setError: (lastError) => {
    set({ lastError });
  },
  goToBeat: (beatIndex) => {
    const { plan } = get();
    if (!plan || plan.beats.length === 0) {
      return null;
    }
    const clamped = Math.max(0, Math.min(plan.beats.length - 1, beatIndex));
    const applied = applyBeatCamera(plan, clamped);
    if (!applied) {
      return null;
    }
    set({
      beatIndex: clamped,
      chapterIndex: chapterIndexForBeat(plan, applied.beat),
      lastApplied: applied,
      status: get().status === 'free_camera' ? 'paused' : get().status,
    });
    return applied;
  },
  nextBeat: () => {
    return get().goToBeat(get().beatIndex + 1);
  },
  previousBeat: () => {
    return get().goToBeat(get().beatIndex - 1);
  },
  goToChapter: (chapterIndex) => {
    const { plan } = get();
    if (!plan || plan.chapters.length === 0) {
      return null;
    }
    const clamped = Math.max(0, Math.min(plan.chapters.length - 1, chapterIndex));
    const chapter = plan.chapters[clamped];
    if (!chapter) {
      return null;
    }
    const firstBeatId = chapter.beatIds[0];
    const beatIndex = firstBeatId
      ? plan.beats.findIndex((beat) => beat.id === firstBeatId)
      : plan.beats.findIndex((beat) => beat.chapterId === chapter.id);
    if (beatIndex < 0) {
      set({ chapterIndex: clamped });
      return null;
    }
    return get().goToBeat(beatIndex);
  },
  syncFromReplaySequence: (sequence) => {
    const { plan, mode, status } = get();
    if (!plan || mode !== 'cinematic' || status === 'free_camera') {
      return null;
    }
    const beatIndex = beatIndexForSequence(plan, sequence);
    return get().goToBeat(beatIndex);
  },
  takeFreeCamera: () => {
    set({ status: 'free_camera' });
  },
  resumeCinematic: () => {
    set({ status: 'playing' });
  },
  clear: () => {
    set({ ...initialState });
  },
  toPlaybackState: (runId) => {
    const state = get();
    const beat = state.plan?.beats[state.beatIndex];
    const chapter = state.plan?.chapters[state.chapterIndex];
    return {
      schemaVersion: 1,
      runId,
      mode: state.mode,
      status: state.status,
      chapterIndex: state.chapterIndex,
      beatIndex: state.beatIndex,
      speed: state.speed,
      reducedMotion: state.reducedMotion,
      captionsEnabled: state.captionsEnabled,
      activeBeatId: beat?.id ?? null,
      activeChapterId: chapter?.id ?? null,
    };
  },
}));
