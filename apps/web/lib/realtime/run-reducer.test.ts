import { describe, expect, it } from 'vitest';

import type { DomainEventEnvelopeV1 } from '@aegis/contracts-ts';
import { ConnectionHealthState } from '@aegis/contracts-ts';

import { projectDomainEventToActions } from '@/lib/realtime/event-projector';
import { createInitialRunReplicatedState, runReplicatedReducer } from '@/lib/realtime/run-reducer';

const baseEvent: DomainEventEnvelopeV1 = {
  eventId: 'evt_test_001',
  runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
  sequence: 1,
  type: 'sim.run.started',
  schemaVersion: 1,
  simTime: '2026-01-01T00:00:00.000Z',
  recordedAt: '2026-01-01T00:00:00.000Z',
  actor: { type: 'system', id: 'asset:simulation-engine' },
  subject: { type: 'system', id: 'asset:simulation-engine' },
  payload: { schemaVersion: 1 },
  traceId: 'trc_test_001',
};

describe('runReplicatedReducer', () => {
  it('shares sequence across run status and timeline updates', () => {
    let state = createInitialRunReplicatedState(baseEvent.runId);
    const runAction = projectDomainEventToActions(baseEvent, {
      lastAppliedSequence: state.lastAppliedSequence,
      seenEventIds: new Set(state.seenEventIds),
      knownNodes: new Map(),
    });
    for (const action of runAction) {
      state = runReplicatedReducer(state, action);
    }

    const telemetryEvent: DomainEventEnvelopeV1 = {
      ...baseEvent,
      eventId: 'evt_test_002',
      sequence: 2,
      type: 'telemetry.authentication.failed',
      subject: { type: 'asset', id: 'asset:svc-api-gateway' },
      payload: {
        schemaVersion: 1,
        assetId: 'asset:svc-api-gateway',
        outcome: 'failed',
      },
    };
    const timelineActions = projectDomainEventToActions(telemetryEvent, {
      lastAppliedSequence: state.lastAppliedSequence,
      seenEventIds: new Set(state.seenEventIds),
      knownNodes: new Map(),
    });
    for (const action of timelineActions) {
      state = runReplicatedReducer(state, action);
    }

    expect(state.lastAppliedSequence).toBe(2);
    expect(state.timelineEntries).toHaveLength(1);
    expect(state.runStatus).toBe('running');
  });

  it('marks gap and stops applying until recovery', () => {
    let state = createInitialRunReplicatedState(baseEvent.runId);
    state = runReplicatedReducer(state, {
      type: 'mark_gap',
      expectedSequence: 2,
      receivedSequence: 4,
    });
    expect(state.connectionHealth).toBe(ConnectionHealthState.GAP);
    state = runReplicatedReducer(state, {
      type: 'append_timeline_entry',
      entry: {
        schemaVersion: 1,
        sequence: 4,
        eventId: 'evt_gap',
        eventType: 'telemetry.api.request',
        label: 'Late event',
        timestamp: '2026-01-01T00:01:00.000Z',
        status: 'normal',
      },
    });
    expect(state.timelineEntries).toHaveLength(0);
  });

  it('freezes graph revision and applied sequence during a gap', () => {
    let state = createInitialRunReplicatedState(baseEvent.runId);
    state = runReplicatedReducer(state, {
      type: 'mark_gap',
      expectedSequence: 2,
      receivedSequence: 5,
    });
    const revisionBefore = state.graphRevision;
    const appliedBefore = state.lastAppliedSequence;

    state = runReplicatedReducer(state, {
      type: 'apply_graph_delta',
      delta: {
        schemaVersion: 1,
        runId: baseEvent.runId,
        sequence: 3,
        revision: 99,
        operation: 'upsert_node',
        node: {
          schemaVersion: 1,
          id: 'asset:svc-api-gateway',
          entityType: 'asset',
          assetType: 'service',
          label: 'API Gateway',
          riskScore: 0.5,
          criticality: 0.5,
          status: 'suspicious',
          revision: 99,
        },
      },
    });

    // The reducer must not advance the graph projection while frozen, so the
    // rendered graph revision cannot drift ahead of the applied sequence.
    expect(state.graphRevision).toBe(revisionBefore);
    expect(state.lastAppliedSequence).toBe(appliedBefore);
  });

  it('bounds seenEventIds so a long live session cannot grow without limit', () => {
    let state = createInitialRunReplicatedState(baseEvent.runId);
    const total = 700;
    for (let i = 1; i <= total; i += 1) {
      state = runReplicatedReducer(state, {
        type: 'advance_sequence',
        sequence: i,
        eventId: `evt_${String(i)}`,
      });
    }
    expect(state.lastAppliedSequence).toBe(total);
    expect(state.seenEventIds.length).toBeLessThanOrEqual(512);
    // The most recent id is always retained (the authoritative recency guard).
    expect(state.seenEventIds).toContain(`evt_${String(total)}`);
    // The oldest ids are evicted once the bound is exceeded.
    expect(state.seenEventIds).not.toContain('evt_1');
  });

  it('suppresses duplicate events', () => {
    const state = createInitialRunReplicatedState(baseEvent.runId);
    const duplicate = projectDomainEventToActions(baseEvent, {
      lastAppliedSequence: 1,
      seenEventIds: new Set([baseEvent.eventId]),
      knownNodes: new Map(),
    });
    expect(duplicate[0]?.type).toBe('noop_duplicate');
    const next = runReplicatedReducer(
      state,
      duplicate[0] ?? { type: 'noop_duplicate', eventId: 'evt', sequence: 0 },
    );
    expect(next.lastAppliedSequence).toBe(0);
  });
});
