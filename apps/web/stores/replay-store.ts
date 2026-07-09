import { create } from 'zustand';

import type {
  HistoricalGraphAdapterV1,
  ReplayBookmarkV1,
  ReplayComparisonV1,
  ReplayCursorV1,
  ReplayLoadStatus,
  ReplayPlaybackSpeed,
  ReplayPlaybackStatus,
  ReplayProvenanceV1,
  ReplayStateV1,
  ReplayViewMode,
  ReplayViewStateV1,
  ReturnToLiveResultV1,
  SnapshotManifestV1,
  StateDiffV1,
  TimelineFilterV1,
} from '@aegis/contracts-ts';

import { clampSequence } from '@/features/replay/lib/playback';
import { buildReturnToLiveResult } from '@/features/replay/lib/return-to-live';

export interface ReplayStoreState {
  runId: string | null;
  mode: ReplayViewMode;
  cursor: ReplayCursorV1 | null;
  minSequence: number;
  maxSequence: number;
  playbackStatus: ReplayPlaybackStatus;
  speed: ReplayPlaybackSpeed;
  loadStatus: ReplayLoadStatus;
  reducedMotion: boolean;
  selectedBookmarkId: string | null;
  timelineFilter: TimelineFilterV1 | null;
  comparison: ReplayComparisonV1 | null;
  historicalGraph: HistoricalGraphAdapterV1 | null;
  provenance: ReplayProvenanceV1 | null;
  stateDigest: string | null;
  errorCode: string | null;
  errorMessage: string | null;
  lastReconstructedAt: string | null;
  reconstructedState: ReplayStateV1 | null;
  bookmarks: ReplayBookmarkV1[];
  snapshots: SnapshotManifestV1[];
  requestGeneration: number;
  enterHistorical: (runId: string, options?: { sequence?: number; maxSequence?: number }) => void;
  setCursorSequence: (sequence: number, incidentId?: string | null) => void;
  setPlaybackStatus: (status: ReplayPlaybackStatus) => void;
  setSpeed: (speed: ReplayPlaybackSpeed) => void;
  setReducedMotion: (reducedMotion: boolean) => void;
  setLoadStatus: (status: ReplayLoadStatus) => void;
  setError: (code: string | null, message: string | null) => void;
  beginReconstruction: () => number;
  applyReconstructedState: (
    generation: number,
    state: ReplayStateV1,
    historicalGraph: HistoricalGraphAdapterV1 | null,
  ) => void;
  setBookmarks: (bookmarks: ReplayBookmarkV1[]) => void;
  setSnapshots: (snapshots: SnapshotManifestV1[]) => void;
  selectBookmark: (bookmarkId: string | null) => void;
  setTimelineFilter: (filter: TimelineFilterV1 | null) => void;
  setComparisonRange: (leftSequence: number, rightSequence: number) => void;
  applyComparisonDiff: (
    diff: StateDiffV1 | null,
    errorCode?: string | null,
    errorMessage?: string | null,
  ) => void;
  step: (delta: number) => void;
  jumpToMin: () => void;
  jumpToMax: () => void;
  clear: () => void;
  returnToLive: () => ReturnToLiveResultV1 | null;
  toViewState: () => ReplayViewStateV1 | null;
}

const initialState = {
  runId: null as string | null,
  mode: 'historical' as ReplayViewMode,
  cursor: null as ReplayCursorV1 | null,
  minSequence: 0,
  maxSequence: 0,
  playbackStatus: 'idle' as ReplayPlaybackStatus,
  speed: '1x' as ReplayPlaybackSpeed,
  loadStatus: 'idle' as ReplayLoadStatus,
  reducedMotion: false,
  selectedBookmarkId: null as string | null,
  timelineFilter: null as TimelineFilterV1 | null,
  comparison: null as ReplayComparisonV1 | null,
  historicalGraph: null as HistoricalGraphAdapterV1 | null,
  provenance: null as ReplayProvenanceV1 | null,
  stateDigest: null as string | null,
  errorCode: null as string | null,
  errorMessage: null as string | null,
  lastReconstructedAt: null as string | null,
  reconstructedState: null as ReplayStateV1 | null,
  bookmarks: [] as ReplayBookmarkV1[],
  snapshots: [] as SnapshotManifestV1[],
  requestGeneration: 0,
};

export const useReplayStore = create<ReplayStoreState>((set, get) => ({
  ...initialState,

  enterHistorical: (runId, options) => {
    const maxSequence = options?.maxSequence ?? 0;
    const sequence = clampSequence(options?.sequence ?? maxSequence, 0, maxSequence);
    set({
      ...initialState,
      runId,
      mode: 'historical',
      minSequence: 0,
      maxSequence,
      loadStatus: 'loading',
      cursor: {
        schemaVersion: 1,
        runId,
        sequence,
        simTime: null,
        incidentId: null,
      },
    });
  },

  setCursorSequence: (sequence, incidentId) => {
    const state = get();
    if (!state.runId || !state.cursor) {
      return;
    }
    const nextSequence = clampSequence(sequence, state.minSequence, state.maxSequence);
    set({
      cursor: {
        ...state.cursor,
        sequence: nextSequence,
        incidentId: incidentId === undefined ? state.cursor.incidentId : incidentId,
      },
      mode: state.playbackStatus === 'playing' ? 'playback' : 'historical',
      errorCode: null,
      errorMessage: null,
    });
  },

  setPlaybackStatus: (status) => {
    set({
      playbackStatus: status,
      mode: status === 'playing' ? 'playback' : 'historical',
    });
  },

  setSpeed: (speed) => {
    set({ speed });
  },

  setReducedMotion: (reducedMotion) => {
    set((state) => ({
      reducedMotion,
      playbackStatus:
        reducedMotion && state.playbackStatus === 'playing' ? 'paused' : state.playbackStatus,
    }));
  },

  setLoadStatus: (status) => {
    set({ loadStatus: status });
  },

  setError: (code, message) => {
    set({
      errorCode: code,
      errorMessage: message,
      loadStatus: code ? 'error' : get().loadStatus,
      playbackStatus: 'paused',
    });
  },

  beginReconstruction: () => {
    const generation = get().requestGeneration + 1;
    set({ requestGeneration: generation, loadStatus: 'loading' });
    return generation;
  },

  applyReconstructedState: (generation, state, historicalGraph) => {
    if (generation !== get().requestGeneration) {
      return;
    }
    set({
      reconstructedState: state,
      cursor: state.cursor,
      maxSequence: Math.max(get().maxSequence, state.cursor.sequence),
      provenance: state.provenance,
      stateDigest: state.stateDigest,
      historicalGraph,
      lastReconstructedAt: state.provenance.reconstructedAt,
      loadStatus: 'ready',
      errorCode: null,
      errorMessage: null,
    });
  },

  setBookmarks: (bookmarks) => {
    set({ bookmarks });
  },

  setSnapshots: (snapshots) => {
    set({ snapshots });
  },

  selectBookmark: (bookmarkId) => {
    const bookmark = get().bookmarks.find((item) => item.id === bookmarkId) ?? null;
    if (!bookmark) {
      set({ selectedBookmarkId: null });
      return;
    }
    get().setCursorSequence(bookmark.sequence, bookmark.incidentId ?? null);
    set({ selectedBookmarkId: bookmark.id, playbackStatus: 'paused', mode: 'historical' });
  },

  setTimelineFilter: (filter) => {
    set({ timelineFilter: filter });
  },

  setComparisonRange: (leftSequence, rightSequence) => {
    const runId = get().runId;
    if (!runId) {
      return;
    }
    const left = clampSequence(leftSequence, get().minSequence, get().maxSequence);
    const right = clampSequence(rightSequence, get().minSequence, get().maxSequence);
    set({
      comparison: {
        schemaVersion: 1,
        runId,
        leftSequence: Math.min(left, right),
        rightSequence: Math.max(left, right),
        leftLabel: `Seq ${String(Math.min(left, right))}`,
        rightLabel: `Seq ${String(Math.max(left, right))}`,
        diff: null,
        loading: true,
        errorCode: null,
        errorMessage: null,
      },
    });
  },

  applyComparisonDiff: (diff, errorCode = null, errorMessage = null) => {
    const comparison = get().comparison;
    if (!comparison) {
      return;
    }
    set({
      comparison: {
        ...comparison,
        diff,
        loading: false,
        errorCode: errorCode as ReplayComparisonV1['errorCode'],
        errorMessage,
      },
    });
  },

  step: (delta) => {
    const state = get();
    if (!state.cursor) {
      return;
    }
    get().setCursorSequence(state.cursor.sequence + delta);
    set({ playbackStatus: 'paused', mode: 'historical' });
  },

  jumpToMin: () => {
    get().setCursorSequence(get().minSequence);
    set({ playbackStatus: 'paused', mode: 'historical' });
  },

  jumpToMax: () => {
    get().setCursorSequence(get().maxSequence);
    set({ playbackStatus: 'paused', mode: 'historical' });
  },

  clear: () => {
    set({ ...initialState });
  },

  returnToLive: () => {
    const state = get();
    if (!state.runId || !state.cursor) {
      return null;
    }
    const result = buildReturnToLiveResult(state.runId, state.cursor.sequence);
    set({ ...initialState });
    return result;
  },

  toViewState: () => {
    const state = get();
    if (!state.runId || !state.cursor) {
      return null;
    }
    return {
      schemaVersion: 1,
      runId: state.runId,
      mode: state.mode,
      cursor: state.cursor,
      minSequence: state.minSequence,
      maxSequence: state.maxSequence,
      playbackStatus: state.playbackStatus,
      speed: state.speed,
      loadStatus: state.loadStatus,
      reducedMotion: state.reducedMotion,
      selectedBookmarkId: state.selectedBookmarkId,
      timelineFilter: state.timelineFilter,
      comparison: state.comparison,
      historicalGraph: state.historicalGraph,
      provenance: state.provenance,
      stateDigest: state.stateDigest,
      errorCode: state.errorCode as ReplayViewStateV1['errorCode'],
      errorMessage: state.errorMessage,
      lastReconstructedAt: state.lastReconstructedAt,
    };
  },
}));
