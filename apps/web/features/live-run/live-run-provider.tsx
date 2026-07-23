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

  const applyEventToGraph = useCallback(
    (event: DomainEventEnvelopeV1) => {
      const actions = projectDomainEventToActions(event, {
        lastAppliedSequence: state.lastAppliedSequence,
        seenEventIds: new Set(state.seenEventIds),
        knownNodes: knownNodesRef.current,
      });
      for (const action of actions) {
        dispatch(action);
        if (action.type === 'mark_gap') {
          // Mirror the reducer: once a gap is detected, freeze the graph store
          // too until a snapshot resync reconciles both projections.
          connectionHealthRef.current = ConnectionHealthState.GAP;
          continue;
        }
        if (connectionHealthRef.current === ConnectionHealthState.GAP) {
          continue;
        }
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
    },
    [state.lastAppliedSequence, state.seenEventIds],
  );

  const processEnvelope = useCallback(
    (envelope: RealtimeMessageEnvelopeV1) => {
      if (envelope.event.runId !== runId) {
        return;
      }
      if (state.locallyPaused) {
        dispatch({
          type: 'set_connection_health',
          connectionHealth: ConnectionHealthState.LOCALLY_PAUSED,
          isStale: true,
        });
        return;
      }
      applyEventToGraph(envelope.event);
      // Fog-of-war reveal moment: on a disclosure flip, converge the graph to the now-
      // disclosed truth by resyncing the snapshot (throttled against bursts). The timeline
      // already announces these events for accessibility (aria-live status region).
      if (
        envelope.event.type === 'sim.hidden_condition.revealed' ||
        envelope.event.type.startsWith('alert.')
      ) {
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
    [applyEventToGraph, queryClient, runId, state.locallyPaused],
  );

  const performResync = useCallback(async () => {
    gapRecoveryRef.current = true;
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
      dispatch({
        type: 'load_graph_snapshot',
        snapshot: bootstrap.graphSnapshot,
      });
      dispatch({
        type: 'set_connection_health',
        connectionHealth: ConnectionHealthState.CATCHING_UP,
        isStale: false,
      });

      const cursor = loadStoredCursor(runId);
      const fromSequence = Math.max(cursor, bootstrap.lastAppliedSequence) + 1;
      const events = await fetchMissingEvents(
        runId,
        fromSequence,
        bootstrap.lastAppliedSequence + 500,
      );
      for (const event of events) {
        applyEventToGraph(event);
        saveStoredCursor(runId, event.sequence);
      }

      dispatch({
        type: 'set_connection_health',
        connectionHealth: ConnectionHealthState.CONNECTED,
        isStale: false,
      });
    } finally {
      gapRecoveryRef.current = false;
    }
  }, [applyEventToGraph, runId]);

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

      const transport = new RealtimeTransport({
        url: getWsUrl(),
        token: ticket,
        autoReconnect: true,
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
  }, [isLiveMode, performResync, processEnvelope, runId]);

  useEffect(() => {
    return () => {
      clearStoredCursor();
    };
  }, [runId]);

  const setLocallyPaused = useCallback((paused: boolean) => {
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
