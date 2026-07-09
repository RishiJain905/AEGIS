import { beforeEach, describe, expect, it } from 'vitest';

import { useReplayStore } from '@/stores/replay-store';

describe('replay-store isolation and cursor controls', () => {
  beforeEach(() => {
    useReplayStore.getState().clear();
  });

  it('enters historical mode with a sequence-primary cursor', () => {
    useReplayStore.getState().enterHistorical('run_01ARZ3NDEKTSV4RRFFQ69G5FAV', {
      sequence: 250,
      maxSequence: 500,
    });
    const state = useReplayStore.getState();
    expect(state.mode).toBe('historical');
    expect(state.cursor?.sequence).toBe(250);
    expect(state.maxSequence).toBe(500);
    expect(state.loadStatus).toBe('loading');
  });

  it('clamps scrubbing and steps deterministically', () => {
    useReplayStore.getState().enterHistorical('run_01ARZ3NDEKTSV4RRFFQ69G5FAV', {
      sequence: 10,
      maxSequence: 20,
    });
    useReplayStore.getState().setCursorSequence(999);
    expect(useReplayStore.getState().cursor?.sequence).toBe(20);
    useReplayStore.getState().step(-5);
    expect(useReplayStore.getState().cursor?.sequence).toBe(15);
    useReplayStore.getState().jumpToMin();
    expect(useReplayStore.getState().cursor?.sequence).toBe(0);
  });

  it('cancels stale reconstruction generations', () => {
    useReplayStore.getState().enterHistorical('run_01ARZ3NDEKTSV4RRFFQ69G5FAV', {
      sequence: 100,
      maxSequence: 500,
    });
    const first = useReplayStore.getState().beginReconstruction();
    const second = useReplayStore.getState().beginReconstruction();
    expect(second).toBeGreaterThan(first);

    useReplayStore.getState().applyReconstructedState(
      first,
      {
        schemaVersion: 1,
        runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
        cursor: {
          schemaVersion: 1,
          runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
          sequence: 50,
          simTime: null,
          incidentId: null,
        },
        incidents: [],
        evidence: [],
        riskScores: [],
        agentSessions: [],
        agentArtifacts: [],
        proposals: [],
        approvals: [],
        executedActions: [],
        reports: [],
        auditEvents: [],
        stateDigest: 'stale',
        provenance: {
          schemaVersion: 1,
          runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
          mode: 'from_events',
          snapshotId: null,
          snapshotSequence: null,
          appliedFromSequence: 0,
          appliedToSequence: 50,
          appliedEventCount: 1,
          fallbackReason: null,
          reconstructedAt: '2026-06-30T03:00:00.000Z',
        },
      },
      null,
    );

    expect(useReplayStore.getState().reconstructedState).toBeNull();
  });

  it('return-to-live clears the historical store and requires authoritative resync', () => {
    useReplayStore.getState().enterHistorical('run_01ARZ3NDEKTSV4RRFFQ69G5FAV', {
      sequence: 400,
      maxSequence: 500,
    });
    const result = useReplayStore.getState().returnToLive();
    expect(result).toEqual(
      expect.objectContaining({
        runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
        fromSequence: 400,
        liveRoute: '/runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
        authoritativeResyncRequired: true,
        replayStoreCleared: true,
      }),
    );
    expect(useReplayStore.getState().runId).toBeNull();
    expect(useReplayStore.getState().reconstructedState).toBeNull();
  });

  it('selects bookmarks and comparison ranges without mutating live APIs', () => {
    useReplayStore.getState().enterHistorical('run_01ARZ3NDEKTSV4RRFFQ69G5FAV', {
      sequence: 100,
      maxSequence: 500,
    });
    useReplayStore.getState().setBookmarks([
      {
        schemaVersion: 1,
        id: 'bm_test',
        runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
        label: 'Detection',
        kind: 'incident',
        sequence: 120,
        toSequence: 180,
        incidentId: 'incident:inc_synthetic_001',
        description: null,
      },
    ]);
    useReplayStore.getState().selectBookmark('bm_test');
    expect(useReplayStore.getState().cursor?.sequence).toBe(120);
    expect(useReplayStore.getState().cursor?.incidentId).toBe('incident:inc_synthetic_001');
    useReplayStore.getState().setComparisonRange(100, 200);
    expect(useReplayStore.getState().comparison).toEqual(
      expect.objectContaining({
        leftSequence: 100,
        rightSequence: 200,
        loading: true,
      }),
    );
  });
});
