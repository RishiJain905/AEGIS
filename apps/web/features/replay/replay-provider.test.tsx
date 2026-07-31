/**
 * BUG-019: the replay transport showed "0–500" for every run and End returned HTTP 400.
 *
 * The range was `max(reconstructed cursor, REPLAY_FIXTURE_MAX_SEQUENCE)` — a 500 borrowed
 * from the demo fixture — so scrubbing to End asked the server for a sequence the run had
 * never reached.
 */
import { cleanup, render, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

const { getReplayState, listReplaySnapshots, push } = vi.hoisted(() => ({
  getReplayState: vi.fn(),
  listReplaySnapshots: vi.fn(),
  push: vi.fn(),
}));

vi.mock('next/navigation', () => ({ useRouter: () => ({ push }) }));
vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  // Stable identity, as the real provider's context value is: the provider's effects key
  // off the client, so a fresh object per render would re-fetch forever.
  const client = { getReplayState, listReplaySnapshots };
  return { ...actual, useApiClient: () => client };
});

import { ReplayProvider } from '@/features/replay/replay-provider';
import { useReplayStore } from '@/stores/replay-store';

const RUN_ID = 'run_8024W2GZ4PMQ02P8FXTH840AY6';
const MAX_SEQUENCE = 327;

function replayState(sequence: number) {
  return {
    schemaVersion: 1,
    runId: RUN_ID,
    cursor: { schemaVersion: 1, runId: RUN_ID, sequence, simTime: null, incidentId: null },
    run: null,
    graph: null,
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
    stateDigest: 'sha256:test',
    provenance: {
      schemaVersion: 1,
      runId: RUN_ID,
      mode: 'from_events',
      snapshotId: null,
      snapshotSequence: null,
      appliedFromSequence: 0,
      appliedToSequence: sequence,
      appliedEventCount: sequence,
      fallbackReason: null,
      reconstructedAt: '2026-07-30T00:00:00.000Z',
    },
  };
}

describe('ReplayProvider timeline range', () => {
  afterEach(() => {
    cleanup();
    useReplayStore.getState().clear();
    vi.clearAllMocks();
  });

  it('derives the range from the run’s own event maximum', async () => {
    getReplayState.mockImplementation((_runId: string, params?: { sequence?: number }) =>
      Promise.resolve(replayState(params?.sequence ?? MAX_SEQUENCE)),
    );
    listReplaySnapshots.mockResolvedValue([]);

    render(<ReplayProvider runId={RUN_ID}>{null}</ReplayProvider>);

    await waitFor(() => {
      expect(useReplayStore.getState().maxSequence).toBe(MAX_SEQUENCE);
    });
    expect(useReplayStore.getState().cursor?.sequence).toBe(MAX_SEQUENCE);
  });

  it('does not invent a range when the run cannot be reconstructed', async () => {
    getReplayState.mockRejectedValue(new Error('boom'));
    listReplaySnapshots.mockResolvedValue([]);

    render(<ReplayProvider runId={RUN_ID}>{null}</ReplayProvider>);

    await waitFor(() => {
      expect(useReplayStore.getState().cursor).not.toBeNull();
    });
    expect(useReplayStore.getState().maxSequence).toBe(0);
  });
});
