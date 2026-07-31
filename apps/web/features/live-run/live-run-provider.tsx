'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
  type ReactNode,
} from 'react';

import type {
  DomainEventEnvelopeV1,
  GraphSnapshotV1,
  RealtimeMessageEnvelopeV1,
  RunReplicatedState,
  SnapshotBootstrapPayloadV1,
} from '@aegis/contracts-ts';
import { ConnectionHealthState } from '@aegis/contracts-ts';
import { createGraphStore, type GraphStore } from '@aegis/graph-domain';
import { RealtimeTransport } from '@aegis/realtime-client';
import { useQueryClient } from '@tanstack/react-query';

import { queryKeys } from '@/lib/api/query-keys';
import { apiFetchJson } from '@/lib/api/auth-fetch';

import { fetchMissingEvents } from '@/lib/realtime/catch-up';
import {
  clearStoredCursor,
  loadStoredCursor,
  saveStoredCursor,
} from '@/lib/realtime/cursor-storage';
import { projectDomainEventToActions } from '@/lib/realtime/event-projector';
import { createInitialRunReplicatedState, runReplicatedReducer } from '@/lib/realtime/run-reducer';
import { buildBootstrapFromEndpoints } from '@/lib/realtime/snapshot-resync';

interface LiveRunContextValue {
  runId: string;
  state: RunReplicatedState;
  graphStore: GraphStore;
  graphRevision: number;
  bootstrapSnapshot: GraphSnapshotV1 | null;
  isLiveMode: boolean;
  setLocallyPaused: (paused: boolean) => void;
  resync: () => Promise<void>;
}

const LiveRunContext = createContext<LiveRunContextValue | null>(null);

// Upper bound on the recently-seen event-id ring maintained client-side. Mirrors
// the reducer's own bound; `lastAppliedSequence` is the authoritative dedup key.
const SEEN_EVENT_ID_LIMIT = 512;

function getWsUrl(): string {
  return process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000/ws/v1/realtime';
}

async function fetchWsTicket(): Promise<string> {
  const payload = await apiFetchJson<{ ticket: string }>('/api/v1/auth/ws-ticket', {
    method: 'POST',
  });
  return payload.ticket;
}

function isLiveDataSource(): boolean {
  return process.env.NEXT_PUBLIC_AEGIS_DATA_SOURCE === 'api';
}

/**
 * The sequence the bootstrap's graph snapshot actually reflects — the point live event
 * application has to resume from.
 *
 * Snapshots are only written by an emitting simulation command, while the run's sequence
 * stream also carries alerts, agent tasks and approved actions. The run head
 * (`lastAppliedSequence`) is therefore routinely ahead of the snapshot, and treating it as
 * the applied cursor silently declares that gap already applied.
 */
function graphSequenceFloor(bootstrap: SnapshotBootstrapPayloadV1): number {
  return Math.min(bootstrap.graphSnapshot.sequence, bootstrap.lastAppliedSequence);
}

interface LiveRunProviderProps {
  runId: string;
  children: ReactNode;
}

export function LiveRunProvider({ runId, children }: LiveRunProviderProps) {
  const isLiveMode = isLiveDataSource();
  const queryClient = useQueryClient();
  const graphStoreRef = useRef(createGraphStore());
  const knownNodesRef = useRef(new Map<string, GraphSnapshotV1['nodes'][number]>());
  const [bootstrapSnapshot, setBootstrapSnapshot] = useState<GraphSnapshotV1 | null>(null);
  const [graphRevision, setGraphRevision] = useState(0);
  const transportRef = useRef<RealtimeTransport | null>(null);
  const gapRecoveryRef = useRef(false);
  // Synchronous mirrors of the reducer's dedup keys. The reducer state updates
  // asynchronously (dispatch is batched), so a burst of live events processed
  // in the same tick would all read the same stale `state.lastAppliedSequence`
  // closure and spuriously mark a gap. These refs advance synchronously as each
  // event is applied, keeping gap detection accurate and — crucially — keeping
  // `applyEventToGraph` free of per-event state dependencies so the WebSocket
  // lifecycle effect does not tear down and re-subscribe on every delta.
  const lastAppliedSequenceRef = useRef(0);
  const seenEventIdsRef = useRef<Set<string>>(new Set());
  // Latest known run status, mirrored synchronously so every applied event can carry the
  // run's sim clock into the reducer without the (stable, dependency-free) apply callback
  // having to read reducer state. Seeded from the bootstrap/resync run record and advanced
  // by the projector's own `sim.run.*` lifecycle mapping — no second copy of that mapping.
  const runStatusRef = useRef('created');
  const locallyPausedRef = useRef(false);
  // Fog-of-war reveal convergence: a disclosure flip (hidden-condition reveal, or an alert
  // landing on a previously-undisclosed asset) means the server will now serve the asset's
  // true state. The live status deltas that changed it already passed redacted, so the
  // client converges by resyncing the (serve-time disclosure-correct) snapshot. `resyncRef`
  // lets `processEnvelope` invoke `performResync` (declared below); `lastRevealResyncRef`
  // throttles bursts so a flurry of alerts triggers at most one resync per window.
  const resyncRef = useRef<(() => Promise<void>) | null>(null);
  const lastRevealResyncRef = useRef(0);

  const [state, dispatch] = useReducer(
    (current: RunReplicatedState, action: Parameters<typeof runReplicatedReducer>[1]) =>
      runReplicatedReducer(current, action),
    runId,
    (initialRunId) => createInitialRunReplicatedState(initialRunId),
  );

  // The graph store is mutated on a code path parallel to the reducer. Track the
  // reducer's freeze condition so the store cannot advance past
  // `lastAppliedSequence` while the reducer is frozen in a gap — the two live
  // projections must stay single-sourced on the applied sequence.
  const connectionHealthRef = useRef(state.connectionHealth);
  useEffect(() => {
    connectionHealthRef.current = state.connectionHealth;
  }, [state.connectionHealth]);

  // Stable across renders: reads/writes the synchronous sequence + seen-id refs
  // rather than reducer state, so it never re-creates per applied event. That
  // stability is what keeps `processEnvelope`/`performResync` — and therefore the
  // WebSocket lifecycle effect — from tearing down and re-subscribing on every
  // delta. `fromResync` events come from `performResync`'s own catch-up loop and
  // must bypass the in-progress-resync drop guard.
  const applyEventToGraph = useCallback((event: DomainEventEnvelopeV1, fromResync = false) => {
    // While a snapshot resync is rebuilding authoritative state, drop live deltas
    // to avoid interleaving a stale live stream with the freshly loaded snapshot.
    // Any sequences skipped here are recovered by post-resync gap detection.
    if (gapRecoveryRef.current && !fromResync) {
      return;
    }

    const actions = projectDomainEventToActions(event, {
      lastAppliedSequence: lastAppliedSequenceRef.current,
      seenEventIds: seenEventIdsRef.current,
      knownNodes: knownNodesRef.current,
    });

    let markedGap = false;
    let applied = false;
    for (const action of actions) {
      dispatch(action);
      if (action.type === 'mark_gap') {
        // Mirror the reducer: once a gap is detected, freeze the graph store too
        // until a snapshot resync reconciles both projections.
        connectionHealthRef.current = ConnectionHealthState.GAP;
        markedGap = true;
        continue;
      }
      if (connectionHealthRef.current === ConnectionHealthState.GAP) {
        continue;
      }
      if (action.type === 'noop_duplicate') {
        continue;
      }
      if (action.type === 'update_run_status') {
        runStatusRef.current = action.runStatus;
      }
      applied = true;
      if (action.type === 'apply_graph_delta') {
        graphStoreRef.current.applyDelta(action.delta);
        setGraphRevision((value) => value + 1);
      }
      if (action.type === 'load_graph_snapshot') {
        graphStoreRef.current.loadSnapshot(action.snapshot);
        knownNodesRef.current = new Map(action.snapshot.nodes.map((node) => [node.id, node]));
        setBootstrapSnapshot(action.snapshot);
        setGraphRevision((value) => value + 1);
      }
    }

    if (applied) {
      lastAppliedSequenceRef.current = Math.max(lastAppliedSequenceRef.current, event.sequence);
      seenEventIdsRef.current.add(event.eventId);
      if (seenEventIdsRef.current.size > SEEN_EVENT_ID_LIMIT) {
        seenEventIdsRef.current = new Set(
          Array.from(seenEventIdsRef.current).slice(-SEEN_EVENT_ID_LIMIT),
        );
      }
      // Carry the run's sim clock forward on every applied event. `sim.run.*` lifecycle
      // events are the only ones the projector turns into a status update, and they fire
      // once per transition — so without this the header's SIM TIME froze at whatever the
      // bootstrap reported while the backend advanced. `dispatch` is stable, so this adds
      // no dependency to the callback and cannot cause a WebSocket resubscribe.
      dispatch({
        type: 'update_run_status',
        runStatus: runStatusRef.current,
        simTime: event.simTime,
        sequence: event.sequence,
      });
    }

    // A client-detected gap must recover by resyncing the authoritative snapshot.
    // Guarded against re-entrancy so a gap found while already recovering (or a
    // burst of gaps) triggers at most one resync.
    if (markedGap && !gapRecoveryRef.current) {
      void resyncRef.current?.();
    }
  }, []);

  const processEnvelope = useCallback(
    (envelope: RealtimeMessageEnvelopeV1) => {
      if (envelope.event.runId !== runId) {
        return;
      }
      if (locallyPausedRef.current) {
        dispatch({
          type: 'set_connection_health',
          connectionHealth: ConnectionHealthState.LOCALLY_PAUSED,
          isStale: true,
        });
        return;
      }
      applyEventToGraph(envelope.event);
      // Fog-of-war reveal moment: on an actual disclosure flip, converge the graph to the
      // now-disclosed truth by resyncing the snapshot (throttled against bursts). Restricted
      // to real reveal events — resyncing on every `alert.*` flipped the view to
      // SNAPSHOT_RESYNC/"stale" every ~1.5s during an active run, which read as a flicker.
      // Alerts still update the graph via their own risk/status delta events.
      if (envelope.event.type === 'sim.hidden_condition.revealed') {
        const now = Date.now();
        if (now - lastRevealResyncRef.current > 1500 && !gapRecoveryRef.current) {
          lastRevealResyncRef.current = now;
          void resyncRef.current?.();
        }
      }
      if (envelope.event.type.startsWith('alert.')) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.runs.alerts(runId) });
      }
      if (envelope.event.type.startsWith('model.score.')) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.runs.alerts(runId) });
      }
      if (envelope.event.type.startsWith('risk.')) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.runs.riskScores(runId) });
        void queryClient.invalidateQueries({ queryKey: queryKeys.runs.graph(runId) });
      }
      if (
        envelope.event.type.startsWith('action.proposal.') ||
        envelope.event.type === 'action.executed'
      ) {
        const incidentId = envelope.event.payload.incidentId;
        if (typeof incidentId === 'string' && incidentId.length > 0) {
          void queryClient.invalidateQueries({
            queryKey: queryKeys.incidents.investigation(incidentId),
          });
        }
      }
      if (envelope.event.type.startsWith('investigation.')) {
        const incidentId = envelope.event.payload.incidentId;
        if (typeof incidentId === 'string' && incidentId.length > 0) {
          void queryClient.invalidateQueries({
            queryKey: queryKeys.incidents.investigation(incidentId),
          });
        }
      }
      if (envelope.event.type.startsWith('agent.')) {
        // The copilot panel reads the run-scoped session list; refresh it so a task
        // reaching a terminal state clears the pending "Working…" turn promptly instead
        // of waiting on the poll interval.
        void queryClient.invalidateQueries({
          queryKey: queryKeys.agentSessions.listForRun(runId),
        });
        const sessionId = envelope.event.payload.sessionId;
        if (typeof sessionId === 'string' && sessionId.length > 0) {
          void queryClient.invalidateQueries({
            queryKey: queryKeys.agentSessions.detail(sessionId),
          });
        }
        const incidentId = envelope.event.payload.incidentId;
        if (typeof incidentId === 'string' && incidentId.length > 0) {
          void queryClient.invalidateQueries({
            queryKey: queryKeys.incidents.investigation(incidentId),
          });
        }
      }
      saveStoredCursor(runId, envelope.event.sequence);
    },
    [applyEventToGraph, queryClient, runId],
  );

  /**
   * Replay every persisted event the freshly loaded snapshot does not already contain.
   *
   * Runs on both the first bootstrap and every resync: both load a snapshot that can lag
   * the run head, and without this the client simply never sees the events in between —
   * the live socket only carries what happens from now on.
   */
  const catchUpFromSnapshot = useCallback(
    async (bootstrap: SnapshotBootstrapPayloadV1) => {
      const fromSequence = graphSequenceFloor(bootstrap) + 1;
      if (fromSequence > bootstrap.lastAppliedSequence) {
        return;
      }
      const events = await fetchMissingEvents(runId, fromSequence, bootstrap.lastAppliedSequence);
      for (const event of events) {
        applyEventToGraph(event, true);
        saveStoredCursor(runId, event.sequence);
      }
    },
    [applyEventToGraph, runId],
  );

  const performResync = useCallback(async () => {
    gapRecoveryRef.current = true;
    connectionHealthRef.current = ConnectionHealthState.SNAPSHOT_RESYNC;
    dispatch({
      type: 'set_connection_health',
      connectionHealth: ConnectionHealthState.SNAPSHOT_RESYNC,
      isStale: true,
    });
    try {
      const bootstrap: SnapshotBootstrapPayloadV1 = await buildBootstrapFromEndpoints(runId);
      graphStoreRef.current.loadSnapshot(bootstrap.graphSnapshot);
      knownNodesRef.current = new Map(bootstrap.graphSnapshot.nodes.map((node) => [node.id, node]));
      setBootstrapSnapshot(bootstrap.graphSnapshot);
      setGraphRevision((value) => value + 1);
      // Reset the synchronous dedup mirrors to the snapshot's authoritative
      // sequence before replaying missed events on top of it. That is the *snapshot's*
      // sequence, not the run head: the graph we just loaded reflects world state as of
      // the snapshot, and any event after it has not been applied. Seeding the cursor
      // with the head instead declared those events already applied and skipped them —
      // which is how the inspector could keep showing `normal` for an asset the tape had
      // already recorded as compromised. Seen-ids are cleared for the same reason: the
      // replay below must be allowed to re-apply events this client saw before the
      // snapshot reset the graph underneath them.
      lastAppliedSequenceRef.current = graphSequenceFloor(bootstrap);
      seenEventIdsRef.current = new Set();
      runStatusRef.current = bootstrap.run.status;
      connectionHealthRef.current = ConnectionHealthState.CATCHING_UP;
      dispatch({
        type: 'load_graph_snapshot',
        snapshot: bootstrap.graphSnapshot,
      });
      dispatch({
        type: 'set_connection_health',
        connectionHealth: ConnectionHealthState.CATCHING_UP,
        isStale: false,
      });
      // A resync reloads authoritative state; the run record it carries is the freshest
      // status/sim-time we have, so republish it rather than leaving the header on
      // whatever the interrupted live stream last managed to apply. It is stamped with
      // the snapshot's sequence, not the head — the reducer drops any delta at or below
      // its `lastAppliedSequence`, so publishing the head first would discard the entire
      // catch-up that follows.
      dispatch({
        type: 'update_run_status',
        runStatus: bootstrap.run.status,
        simTime: bootstrap.run.simTime,
        sequence: graphSequenceFloor(bootstrap),
      });

      await catchUpFromSnapshot(bootstrap);

      // Settle the header on the run's true head once the catch-up has landed.
      dispatch({
        type: 'update_run_status',
        runStatus: runStatusRef.current,
        simTime: bootstrap.run.simTime,
        sequence: bootstrap.lastAppliedSequence,
      });

      connectionHealthRef.current = ConnectionHealthState.CONNECTED;
      dispatch({
        type: 'set_connection_health',
        connectionHealth: ConnectionHealthState.CONNECTED,
        isStale: false,
      });
    } finally {
      gapRecoveryRef.current = false;
    }
  }, [applyEventToGraph, catchUpFromSnapshot, runId]);

  // Keep the reveal-convergence ref pointed at the latest resync closure so the
  // event handler can trigger it without a declaration-order dependency.
  useEffect(() => {
    resyncRef.current = performResync;
  }, [performResync]);

  useEffect(() => {
    if (!isLiveMode) {
      return;
    }

    const cancelledRef = { current: false };

    async function bootstrap() {
      dispatch({
        type: 'set_connection_health',
        connectionHealth: ConnectionHealthState.CATCHING_UP,
        isStale: false,
      });
      try {
        const bootstrapPayload = await buildBootstrapFromEndpoints(runId);
        if (cancelledRef.current) {
          return;
        }
        graphStoreRef.current.loadSnapshot(bootstrapPayload.graphSnapshot);
        knownNodesRef.current = new Map(
          bootstrapPayload.graphSnapshot.nodes.map((node) => [node.id, node]),
        );
        // The snapshot's own sequence, not the run head — see `graphSequenceFloor`. The
        // head is only reached after the catch-up below replays what the snapshot misses.
        lastAppliedSequenceRef.current = graphSequenceFloor(bootstrapPayload);
        runStatusRef.current = bootstrapPayload.run.status;
        setBootstrapSnapshot(bootstrapPayload.graphSnapshot);
        setGraphRevision((value) => value + 1);
        dispatch({
          type: 'set_connection_health',
          connectionHealth: ConnectionHealthState.CATCHING_UP,
          isStale: false,
        });
        dispatch({
          type: 'load_graph_snapshot',
          snapshot: bootstrapPayload.graphSnapshot,
        });
        dispatch({
          type: 'update_run_status',
          runStatus: bootstrapPayload.run.status,
          simTime: bootstrapPayload.run.simTime,
          sequence: graphSequenceFloor(bootstrapPayload),
        });
        await catchUpFromSnapshot(bootstrapPayload);
        dispatch({
          type: 'update_run_status',
          runStatus: runStatusRef.current,
          simTime: bootstrapPayload.run.simTime,
          sequence: bootstrapPayload.lastAppliedSequence,
        });
      } catch {
        dispatch({
          type: 'set_connection_health',
          connectionHealth: ConnectionHealthState.STALE,
          isStale: true,
        });
      }
    }

    void bootstrap();

    let offState = () => {};
    let offEvent = () => {};
    let offSnapshotRequired = () => {};
    let offError = () => {};
    let offResyncComplete = () => {};

    void (async () => {
      let ticket: string;
      try {
        ticket = await fetchWsTicket();
      } catch {
        if (!cancelledRef.current) {
          dispatch({
            type: 'set_connection_health',
            connectionHealth: ConnectionHealthState.DISCONNECTED,
            isStale: true,
          });
        }
        return;
      }
      if (cancelledRef.current) {
        return;
      }

      // WebSocket tickets are single-shot and expire after 5 minutes, so every
      // attempt has to mint its own. The pre-flight ticket above (which is what
      // surfaces an initial failure as DISCONNECTED) is spent on the first
      // attempt; reconnects fetch a fresh one.
      let preflightTicket: string | null = ticket;
      const transport = new RealtimeTransport({
        url: getWsUrl(),
        autoReconnect: true,
        getToken: async () => {
          if (preflightTicket !== null) {
            const spent = preflightTicket;
            preflightTicket = null;
            return spent;
          }
          return fetchWsTicket();
        },
      });
      transportRef.current = transport;

      offState = transport.on('connection_state', (connectionState) => {
        if (connectionState === 'reconnecting') {
          dispatch({
            type: 'set_connection_health',
            connectionHealth: ConnectionHealthState.RECONNECTING,
            isStale: true,
          });
        } else if (connectionState === 'connected') {
          dispatch({
            type: 'set_connection_health',
            connectionHealth: ConnectionHealthState.CONNECTED,
            isStale: false,
          });
        } else if (connectionState === 'disconnected' || connectionState === 'closed') {
          dispatch({
            type: 'set_connection_health',
            connectionHealth: ConnectionHealthState.DISCONNECTED,
            isStale: true,
          });
        }
      });

      offEvent = transport.on('event', (envelope) => {
        processEnvelope(envelope);
      });

      offSnapshotRequired = transport.on('snapshot_required', () => {
        void performResync();
      });

      offError = transport.on('error', (error) => {
        if (error.code === 'WS_SEQUENCE_GAP') {
          void performResync();
          return;
        }
        dispatch({
          type: 'set_connection_health',
          connectionHealth: ConnectionHealthState.STALE,
          isStale: true,
        });
      });

      offResyncComplete = transport.on('resync_complete', () => {
        dispatch({
          type: 'set_connection_health',
          connectionHealth: ConnectionHealthState.CONNECTED,
          isStale: false,
        });
      });

      await transport.connect();
      transport.subscribe({
        runId,
        channel: 'events',
        lastAppliedSequence: loadStoredCursor(runId),
      });
    })();

    return () => {
      cancelledRef.current = true;
      offState();
      offEvent();
      offSnapshotRequired();
      offError();
      offResyncComplete();
      transportRef.current?.disconnect();
      transportRef.current = null;
    };
  }, [catchUpFromSnapshot, isLiveMode, performResync, processEnvelope, runId]);

  useEffect(() => {
    return () => {
      clearStoredCursor();
    };
  }, [runId]);

  const setLocallyPaused = useCallback((paused: boolean) => {
    locallyPausedRef.current = paused;
    dispatch({ type: 'set_locally_paused', locallyPaused: paused });
  }, []);

  const value = useMemo(
    (): LiveRunContextValue => ({
      runId,
      state,
      graphStore: graphStoreRef.current,
      graphRevision,
      bootstrapSnapshot,
      isLiveMode,
      setLocallyPaused,
      resync: performResync,
    }),
    [bootstrapSnapshot, graphRevision, isLiveMode, performResync, runId, setLocallyPaused, state],
  );

  return <LiveRunContext.Provider value={value}>{children}</LiveRunContext.Provider>;
}

export function useLiveRun(): LiveRunContextValue | null {
  return useContext(LiveRunContext);
}

export function useLiveRunRequired(): LiveRunContextValue {
  const context = useLiveRun();
  if (context === null) {
    throw new Error('useLiveRunRequired must be used within LiveRunProvider');
  }
  return context;
}
