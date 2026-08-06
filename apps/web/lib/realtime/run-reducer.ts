import type { RunReplicatedState, SnapshotBootstrapPayloadV1 } from '@aegis/contracts-ts';
import {
  ConnectionHealthState,
  LIVE_RUN_SCHEMA_VERSION,
  type RealtimeReducerAction,
} from '@aegis/contracts-ts';

/**
 * Upper bound on the recently-seen event-id ring. `lastAppliedSequence` is the
 * authoritative dedup key; `seenEventIds` is only a bounded secondary guard, so
 * it must not grow without limit over a long-lived live session.
 */
const SEEN_EVENT_ID_LIMIT = 512;

export function createInitialRunReplicatedState(
  runId: string,
  bootstrap?: SnapshotBootstrapPayloadV1,
): RunReplicatedState {
  return {
    schemaVersion: LIVE_RUN_SCHEMA_VERSION,
    runId,
    lastAppliedSequence: bootstrap?.lastAppliedSequence ?? 0,
    runStatus: bootstrap?.run.status ?? 'created',
    simTime: bootstrap?.run.simTime ?? '2026-01-01T00:00:00.000Z',
    graphRevision: bootstrap?.graphSnapshot.revision ?? 0,
    timelineEntries: [],
    connectionHealth: ConnectionHealthState.DISCONNECTED,
    isStale: false,
    locallyPaused: false,
    seenEventIds: [],
    runOutcome: null,
  };
}

export function runReplicatedReducer(
  state: RunReplicatedState,
  action: RealtimeReducerAction,
): RunReplicatedState {
  switch (action.type) {
    case 'noop_duplicate':
      return state;
    case 'mark_gap':
      return {
        ...state,
        connectionHealth: ConnectionHealthState.GAP,
        isStale: true,
      };
    case 'set_connection_health':
      return {
        ...state,
        connectionHealth: action.connectionHealth,
        isStale: action.isStale ?? state.isStale,
      };
    case 'update_run_status':
      // Strictly-older only. This action rides *alongside* the other actions for the
      // same event (and alongside the bootstrap's `load_graph_snapshot`), so it
      // routinely arrives at a sequence already claimed by a sibling action. Rejecting
      // `<=` here froze the header on the initial "created"/epoch sim time: the
      // bootstrap dispatches `load_graph_snapshot` first, and whenever the snapshot's
      // sequence equalled the run's last event sequence the status update that followed
      // was discarded. Re-applying at the current sequence is idempotent — duplicate and
      // out-of-order events are already filtered by the projector.
      if (action.sequence < state.lastAppliedSequence) {
        return state;
      }
      if (state.connectionHealth === ConnectionHealthState.GAP) {
        return state;
      }
      return {
        ...state,
        runStatus: action.runStatus,
        simTime: action.simTime,
        lastAppliedSequence: action.sequence,
        connectionHealth:
          action.runStatus === 'paused'
            ? ConnectionHealthState.SIMULATOR_PAUSED
            : state.locallyPaused
              ? ConnectionHealthState.LOCALLY_PAUSED
              : state.connectionHealth === ConnectionHealthState.SIMULATOR_PAUSED
                ? ConnectionHealthState.CONNECTED
                : state.connectionHealth,
      };
    case 'set_run_outcome':
      // The verdict is fire-once and rides alongside the other actions for the same
      // event, so it routinely arrives at a sequence already claimed by a sibling
      // action — same strictly-older rule as `update_run_status`. It must also claim
      // the sequence: the STOP that follows lands at the next sequence, and a cursor
      // that never advanced past the verdict would read the STOP as a gap.
      if (action.sequence < state.lastAppliedSequence) {
        return state;
      }
      if (state.connectionHealth === ConnectionHealthState.GAP) {
        return state;
      }
      return {
        ...state,
        runOutcome: action.outcome,
        lastAppliedSequence: Math.max(state.lastAppliedSequence, action.sequence),
      };
    case 'append_timeline_entry': {
      if (action.entry.sequence <= state.lastAppliedSequence) {
        const exists = state.timelineEntries.some(
          (entry) => entry.sequence === action.entry.sequence,
        );
        if (exists) {
          return state;
        }
      }
      if (state.connectionHealth === ConnectionHealthState.GAP) {
        return state;
      }
      if (state.timelineEntries.some((entry) => entry.sequence === action.entry.sequence)) {
        return state;
      }
      const timelineEntries = [...state.timelineEntries, action.entry].sort(
        (left, right) => left.sequence - right.sequence,
      );
      return {
        ...state,
        timelineEntries,
        lastAppliedSequence: Math.max(state.lastAppliedSequence, action.entry.sequence),
      };
    }
    case 'apply_graph_delta':
      if (action.delta.sequence <= state.lastAppliedSequence) {
        return state;
      }
      if (state.connectionHealth === ConnectionHealthState.GAP) {
        return state;
      }
      return {
        ...state,
        graphRevision: action.delta.revision,
        lastAppliedSequence: Math.max(state.lastAppliedSequence, action.delta.sequence),
      };
    case 'load_graph_snapshot':
      if (state.connectionHealth === ConnectionHealthState.GAP) {
        return state;
      }
      return {
        ...state,
        graphRevision: action.snapshot.revision,
        lastAppliedSequence: Math.max(state.lastAppliedSequence, action.snapshot.sequence),
        isStale: false,
        connectionHealth:
          state.connectionHealth === ConnectionHealthState.SNAPSHOT_RESYNC
            ? ConnectionHealthState.CATCHING_UP
            : state.connectionHealth,
      };
    case 'advance_sequence':
      if (action.sequence <= state.lastAppliedSequence) {
        return state;
      }
      if (state.connectionHealth === ConnectionHealthState.GAP) {
        return state;
      }
      return {
        ...state,
        lastAppliedSequence: action.sequence,
        seenEventIds: [...new Set([...state.seenEventIds, action.eventId])].slice(
          -SEEN_EVENT_ID_LIMIT,
        ),
      };
    case 'set_locally_paused':
      return {
        ...state,
        locallyPaused: action.locallyPaused,
        connectionHealth: action.locallyPaused
          ? ConnectionHealthState.LOCALLY_PAUSED
          : state.connectionHealth === ConnectionHealthState.LOCALLY_PAUSED
            ? ConnectionHealthState.CONNECTED
            : state.connectionHealth,
        isStale: action.locallyPaused,
      };
    default: {
      const _exhaustive: never = action;
      return _exhaustive;
    }
  }
}

export function applyBootstrapToState(
  state: RunReplicatedState,
  bootstrap: SnapshotBootstrapPayloadV1,
): RunReplicatedState {
  return {
    ...state,
    runStatus: bootstrap.run.status,
    simTime: bootstrap.run.simTime,
    graphRevision: bootstrap.graphSnapshot.revision,
    lastAppliedSequence: bootstrap.lastAppliedSequence,
    isStale: false,
    connectionHealth: ConnectionHealthState.CATCHING_UP,
  };
}
