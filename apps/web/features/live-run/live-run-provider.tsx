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
  GraphDeltaV1,
  GraphSnapshotV1,
  RealtimeMessageEnvelopeV1,
  RunReplicatedState,
  SnapshotBootstrapPayloadV1,
} from '@aegis/contracts-ts';
import { ConnectionHealthState } from '@aegis/contracts-ts';
import { createGraphStore, GraphDeltaApplyStatus, type GraphStore } from '@aegis/graph-domain';
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

/**
 * Floor between the starts of two snapshot resyncs, and the ceiling that floor decays to
 * while resyncs keep failing.
 *
 * A resync is three HTTP requests against a run that is, by definition, already having a bad
 * time. Nothing used to sit between "a gap was detected" and "fetch the whole snapshot
 * again", so a run whose bootstrap was failing re-armed on the very next event and QA watched
 * a single browser tab issue 43 back-to-back bootstrap-fallback pairs, all rate-limited. The
 * server's limit is 120 requests/minute; the ceiling here keeps a permanently broken endpoint
 * to roughly one attempt a minute instead.
 */
const RESYNC_MIN_INTERVAL_MS = 2_000;
const RESYNC_MAX_INTERVAL_MS = 60_000;

/** Live events held while one resync rebuilds state. See `bufferLiveEvent`. */
const BUFFERED_EVENT_LIMIT = 1_000;

/**
 * Trailing window over which realtime-driven query invalidations are collapsed.
 *
 * An active run emits `agent.*`/`alert.*`/`risk.*` in bursts, and one invalidation per event
 * meant one refetch per event — the copilot's session list was being re-read several times a
 * second. Coalescing costs at most this much latency on a refresh nobody is watching to the
 * millisecond, and turns a burst of N events into one request.
 */
const INVALIDATION_COALESCE_MS = 400;

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
  // client converges by resyncing the (serve-time disclosure-correct) snapshot.
  // `requestResyncRef` lets `processEnvelope` reach the resync scheduler declared below;
  // every caller goes through it, so the interval floor and the coalescing are enforced in
  // one place rather than per trigger.
  const requestResyncRef = useRef<(() => void) | null>(null);
  // The run this provider is currently for. Mounted once per shell and updated in place, so
  // moving between runs re-runs the effects but keeps every ref above — which means a resync
  // still in flight for the run just left would otherwise finish and load that run's snapshot
  // over the one now on screen. Read during render rather than from an effect so an async
  // continuation always compares against the newest value.
  const activeRunIdRef = useRef(runId);
  activeRunIdRef.current = runId;
  // Resync scheduling state. `gapRecoveryRef` above doubles as the in-flight flag.
  const resyncQueuedRef = useRef(false);
  const resyncFailuresRef = useRef(0);
  const lastResyncStartedAtRef = useRef(0);
  const resyncTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Live envelopes that arrived while a resync was in flight, plus the hook the drain uses
  // to feed them back through the normal path once state is whole again.
  const bufferedEventsRef = useRef<RealtimeMessageEnvelopeV1[]>([]);
  const processEnvelopeRef = useRef<((envelope: RealtimeMessageEnvelopeV1) => void) | null>(null);
  // Query keys awaiting a coalesced invalidation, keyed by their serialized form.
  const pendingInvalidationsRef = useRef(new Map<string, readonly unknown[]>());
  const invalidationTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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
    const graphDeltas: GraphDeltaV1[] = [];
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
        graphDeltas.push(action.delta);
      }
      if (action.type === 'load_graph_snapshot') {
        graphStoreRef.current.loadSnapshot(action.snapshot);
        knownNodesRef.current = new Map(action.snapshot.nodes.map((node) => [node.id, node]));
        setBootstrapSnapshot(action.snapshot);
        setGraphRevision((value) => value + 1);
      }
    }

    // One event, one cursor position — and every delta it produced applied at that
    // position. Handing these to `applyDelta` one at a time asked the store to treat a run
    // sequence as a delta sequence: the store's cursor sits where the last graph-relevant
    // event left it, the run head races ahead on telemetry and agent traffic, and the next
    // real delta — the one carrying an executed containment — arrived hundreds of sequences
    // later and was refused as a gap. Nothing read the refusal, so the board simply stopped
    // moving while the API had already settled on `contained`. Stream contiguity is checked
    // above by the projector, which is the only place that sees every event.
    if (graphDeltas.length > 0) {
      const results = graphStoreRef.current.applyEventDeltas(event.sequence, graphDeltas);
      if (results.some((result) => result.status === GraphDeltaApplyStatus.APPLIED)) {
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
    // `requestResync` handles re-entrancy and pacing, so a burst of gaps — or a gap found
    // while already recovering — costs at most one further resync.
    if (markedGap) {
      requestResyncRef.current?.();
    }
  }, []);

  /**
   * Collapse realtime-driven cache invalidations into one trailing flush.
   *
   * Stable: only `queryClient` is captured, so this adds no dependency that could tear down
   * the WebSocket lifecycle effect.
   */
  const scheduleInvalidate = useCallback(
    (queryKey: readonly unknown[]) => {
      pendingInvalidationsRef.current.set(JSON.stringify(queryKey), queryKey);
      if (invalidationTimerRef.current !== null) {
        return;
      }
      invalidationTimerRef.current = setTimeout(() => {
        invalidationTimerRef.current = null;
        const keys = Array.from(pendingInvalidationsRef.current.values());
        pendingInvalidationsRef.current.clear();
        for (const key of keys) {
          void queryClient.invalidateQueries({ queryKey: key });
        }
      }, INVALIDATION_COALESCE_MS);
    },
    [queryClient],
  );

  /**
   * Hold a live event that arrived mid-resync instead of discarding it.
   *
   * Discarding was the structural cause of the resync loop: a dropped sequence guarantees the
   * *next* live event fails the contiguity check, which marks a gap, which asks for another
   * resync — during which more events are dropped. A run ticking faster than a resync
   * completes could therefore never leave that state, and each turn of the loop cost up to
   * three requests.
   */
  const bufferLiveEvent = useCallback((envelope: RealtimeMessageEnvelopeV1) => {
    const buffer = bufferedEventsRef.current;
    if (buffer.length >= BUFFERED_EVENT_LIMIT) {
      // Overflow. Trimming would reintroduce the very hole this buffer exists to prevent, so
      // discard the lot and ask for one more resync: its catch-up re-reads the whole range
      // from the server, which is the authoritative recovery path anyway.
      bufferedEventsRef.current = [];
      resyncQueuedRef.current = true;
      return;
    }
    buffer.push(envelope);
  }, []);

  /** Replay held events in sequence order through the normal live path. */
  const drainBufferedEvents = useCallback(() => {
    const buffered = bufferedEventsRef.current;
    bufferedEventsRef.current = [];
    if (buffered.length === 0) {
      return;
    }
    const ordered = [...buffered].sort((left, right) => left.event.sequence - right.event.sequence);
    for (const envelope of ordered) {
      processEnvelopeRef.current?.(envelope);
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
      if (gapRecoveryRef.current) {
        bufferLiveEvent(envelope);
        return;
      }
      applyEventToGraph(envelope.event);
      // Fog-of-war reveal moment: on an actual disclosure flip, converge the graph to the
      // now-disclosed truth by resyncing the snapshot (throttled against bursts). Restricted
      // to real reveal events — resyncing on every `alert.*` flipped the view to
      // SNAPSHOT_RESYNC/"stale" every ~1.5s during an active run, which read as a flicker.
      // Alerts still update the graph via their own risk/status delta events.
      if (envelope.event.type === 'sim.hidden_condition.revealed') {
        // No throttle of its own any more — `requestResync` enforces one interval floor for
        // every trigger, so a flurry of reveals costs at most one resync per window.
        requestResyncRef.current?.();
      }
      if (envelope.event.type.startsWith('alert.')) {
        scheduleInvalidate(queryKeys.runs.alerts(runId));
      }
      if (envelope.event.type.startsWith('model.score.')) {
        scheduleInvalidate(queryKeys.runs.alerts(runId));
      }
      if (envelope.event.type.startsWith('risk.')) {
        scheduleInvalidate(queryKeys.runs.riskScores(runId));
        scheduleInvalidate(queryKeys.runs.graph(runId));
      }
      // The inspector and the feed's asset labels read the *served* graph snapshot rather
      // than this provider's live store, so the event that changes an asset's posture or
      // applies a control has to invalidate that query itself. Riding on `risk.*` alone
      // meant the badge waited for an unrelated event to refetch it — on a paused run,
      // forever.
      if (envelope.event.type === 'sim.asset.status_changed') {
        scheduleInvalidate(queryKeys.runs.graph(runId));
      }
      if (
        envelope.event.type === 'report.generation.completed' ||
        envelope.event.type === 'report.version.created'
      ) {
        // The header's REPORT instrument and the inspector's SCRIBE panel gate their
        // report queries on the run being terminal, and a terminal run's first fetch
        // routinely answers 404 — the report is generated asynchronously after the run
        // stops. Without this the "Debrief pending" chip stayed up until a page
        // navigation remounted the query, even though the tape already showed generation
        // completed.
        scheduleInvalidate(queryKeys.runs.afterActionReport(runId));
        scheduleInvalidate(queryKeys.runs.reportVersions(runId));
      }
      if (
        envelope.event.type.startsWith('action.proposal.') ||
        envelope.event.type === 'action.executed'
      ) {
        const incidentId = envelope.event.payload.incidentId;
        if (typeof incidentId === 'string' && incidentId.length > 0) {
          scheduleInvalidate(queryKeys.incidents.investigation(incidentId));
        }
      }
      if (envelope.event.type.startsWith('investigation.')) {
        const incidentId = envelope.event.payload.incidentId;
        if (typeof incidentId === 'string' && incidentId.length > 0) {
          scheduleInvalidate(queryKeys.incidents.investigation(incidentId));
        }
      }
      if (envelope.event.type.startsWith('agent.')) {
        // The copilot panel reads the run-scoped session list; refresh it so a task
        // reaching a terminal state clears the pending "Working…" turn promptly instead
        // of waiting on the poll interval.
        scheduleInvalidate(queryKeys.agentSessions.listForRun(runId));
        const sessionId = envelope.event.payload.sessionId;
        if (typeof sessionId === 'string' && sessionId.length > 0) {
          scheduleInvalidate(queryKeys.agentSessions.detail(sessionId));
        }
        const incidentId = envelope.event.payload.incidentId;
        if (typeof incidentId === 'string' && incidentId.length > 0) {
          scheduleInvalidate(queryKeys.incidents.investigation(incidentId));
        }
      }
      saveStoredCursor(runId, envelope.event.sequence);
    },
    [applyEventToGraph, bufferLiveEvent, runId, scheduleInvalidate],
  );

  // The drain feeds held events back through `processEnvelope`; the ref breaks the
  // declaration cycle between the two without adding a dependency to either.
  useEffect(() => {
    processEnvelopeRef.current = processEnvelope;
  }, [processEnvelope]);

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
    const forRunId = runId;
    gapRecoveryRef.current = true;
    lastResyncStartedAtRef.current = Date.now();
    connectionHealthRef.current = ConnectionHealthState.SNAPSHOT_RESYNC;
    dispatch({
      type: 'set_connection_health',
      connectionHealth: ConnectionHealthState.SNAPSHOT_RESYNC,
      isStale: true,
    });
    let succeeded = false;
    try {
      const bootstrap: SnapshotBootstrapPayloadV1 = await buildBootstrapFromEndpoints(forRunId);
      if (activeRunIdRef.current !== forRunId) {
        // The operator moved to another run while this was in flight. Its snapshot describes
        // a run nobody is looking at; applying it would replace the current run's graph.
        return;
      }
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
      // Re-anchor the server-side subscription on the cursor this resync just established.
      // A resync exists because the cursor moved discontinuously, and `subscribe` is the
      // only way the gateway hears about it: after the gateway pauses a subscription (its
      // response to an outbound queue it could not fill, announced as `snapshot_required`),
      // nothing else ever un-pauses it, so the socket stayed open and silent and every
      // later update reached the operator only through another resync. The backfill this
      // costs is empty by construction — the cursor is the head we just caught up to.
      transportRef.current?.subscribe({
        runId: forRunId,
        channel: 'events',
        lastAppliedSequence: lastAppliedSequenceRef.current,
      });
      succeeded = true;
    } catch {
      // A resync that could not reach the server used to leave the client mid-recovery with
      // nothing rescheduled: the next live event marked a gap and asked for another resync
      // immediately, so one failing bootstrap became a request storm. Say plainly that the
      // view is stale and let the backoff in `requestResync` decide when asking again is
      // worth it. Held events are discarded — the next successful resync re-reads the whole
      // range from the server, which is the authoritative recovery path.
      //
      // A superseded resync is exempt from all of that: its failure says nothing about the
      // run now on screen, and charging it would back that run's first resync off for free.
      if (activeRunIdRef.current !== forRunId) {
        return;
      }
      resyncFailuresRef.current += 1;
      bufferedEventsRef.current = [];
      connectionHealthRef.current = ConnectionHealthState.STALE;
      dispatch({
        type: 'set_connection_health',
        connectionHealth: ConnectionHealthState.STALE,
        isStale: true,
      });
    } finally {
      // Only if this is still the run in context: the new run's own bootstrap has already
      // raised this flag for itself, and clearing it here would let its live events through
      // mid-rebuild — the very hole the buffer exists to close.
      if (activeRunIdRef.current === forRunId) {
        gapRecoveryRef.current = false;
      }
    }

    if (succeeded) {
      resyncFailuresRef.current = 0;
      // Only now that `gapRecoveryRef` is clear can held events take the normal path.
      drainBufferedEvents();
    }
  }, [catchUpFromSnapshot, drainBufferedEvents, runId]);

  /**
   * The one way to ask for a resync.
   *
   * Serializes (a request during one in flight queues exactly one follow-up rather than
   * stacking concurrent rebuilds), and rate-limits: no two resyncs start closer together
   * than the interval floor, which doubles per consecutive failure up to
   * {@link RESYNC_MAX_INTERVAL_MS} and resets on the first success. Every trigger — client
   * gap detection, a reveal, the server's `snapshot_required`, a transport sequence-gap
   * error — comes through here, so the budget is enforced once rather than per call site.
   */
  const requestResync = useCallback(() => {
    if (gapRecoveryRef.current) {
      resyncQueuedRef.current = true;
      return;
    }
    if (resyncTimerRef.current !== null) {
      return;
    }

    const failures = resyncFailuresRef.current;
    const minIntervalMs =
      failures === 0
        ? RESYNC_MIN_INTERVAL_MS
        : Math.min(RESYNC_MAX_INTERVAL_MS, RESYNC_MIN_INTERVAL_MS * 2 ** failures);
    const waitMs = Math.max(0, lastResyncStartedAtRef.current + minIntervalMs - Date.now());

    const start = () => {
      void (async () => {
        await performResync();
        if (resyncQueuedRef.current) {
          resyncQueuedRef.current = false;
          requestResyncRef.current?.();
        }
      })();
    };

    if (waitMs === 0) {
      start();
      return;
    }
    resyncTimerRef.current = setTimeout(() => {
      resyncTimerRef.current = null;
      start();
    }, waitMs);
  }, [performResync]);

  // Keep the trigger ref pointed at the latest scheduler closure so the event handlers (and
  // the scheduler's own follow-up) can reach it without a declaration-order dependency.
  useEffect(() => {
    requestResyncRef.current = requestResync;
  }, [requestResync]);

  /**
   * Operator-initiated resync (the banner's and the transport controls' button).
   *
   * Bypasses the interval floor — someone is watching and asked — but never runs a second
   * rebuild on top of one already in flight.
   */
  const resyncNow = useCallback(async () => {
    if (gapRecoveryRef.current) {
      return;
    }
    await performResync();
  }, [performResync]);

  useEffect(() => {
    if (!isLiveMode) {
      return;
    }

    const cancelledRef = { current: false };

    async function bootstrap() {
      // Hold live events until the snapshot and its catch-up have landed. The WebSocket
      // connects in parallel below, so without this an event can arrive while the sequence
      // cursor is still zero — which reads as a gap and triggers a second, entirely
      // redundant bootstrap on every single mount.
      gapRecoveryRef.current = true;
      lastResyncStartedAtRef.current = Date.now();
      dispatch({
        type: 'set_connection_health',
        connectionHealth: ConnectionHealthState.CATCHING_UP,
        isStale: false,
      });
      let succeeded = false;
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
        succeeded = true;
      } catch {
        // Counts against the resync budget: a run whose bootstrap is failing must not be
        // asked again on the next event, which is precisely the loop that produced the
        // storm. A superseded bootstrap is exempt: its failure says nothing about the run
        // now on screen, and charging it would back that run's first resync off for nothing.
        if (!cancelledRef.current) {
          resyncFailuresRef.current += 1;
          bufferedEventsRef.current = [];
          dispatch({
            type: 'set_connection_health',
            connectionHealth: ConnectionHealthState.STALE,
            isStale: true,
          });
        }
      } finally {
        // Hand the gate back only if this bootstrap is still the current one. A superseded
        // run's replacement has already raised the flag for itself, and clearing it here
        // would let that run's live events through mid-rebuild — the hole the buffer exists
        // to close. See the matching guard in `performResync`.
        gapRecoveryRef.current = cancelledRef.current;
      }

      if (succeeded) {
        resyncFailuresRef.current = 0;
        drainBufferedEvents();
        // Settle on CONNECTED, exactly as `performResync` does. The socket's own
        // connection_state callback usually lands this — but it can fire while the
        // bootstrap above is still mid-flight, and its CONNECTED then gets overwritten
        // by the second CATCHING_UP dispatch. On a terminal run no later event or
        // resync ever corrects that, which left the header narrating a catch-up
        // forever on stopped runs. A bootstrap that completed IS caught up; if the
        // socket is genuinely down, its retry lifecycle re-reports within its backoff.
        if (!cancelledRef.current) {
          connectionHealthRef.current = ConnectionHealthState.CONNECTED;
          dispatch({
            type: 'set_connection_health',
            connectionHealth: ConnectionHealthState.CONNECTED,
            isStale: false,
          });
        }
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
        requestResync();
      });

      offError = transport.on('error', (error) => {
        if (error.code === 'WS_SEQUENCE_GAP') {
          requestResync();
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
  }, [catchUpFromSnapshot, drainBufferedEvents, isLiveMode, processEnvelope, requestResync, runId]);

  // Everything the resync scheduler and the invalidation coalescer hold is run-scoped: a
  // pending timer that fires after the run changed would rebuild the wrong run's state.
  useEffect(() => {
    return () => {
      if (resyncTimerRef.current !== null) {
        clearTimeout(resyncTimerRef.current);
        resyncTimerRef.current = null;
      }
      if (invalidationTimerRef.current !== null) {
        clearTimeout(invalidationTimerRef.current);
        invalidationTimerRef.current = null;
      }
      pendingInvalidationsRef.current.clear();
      bufferedEventsRef.current = [];
      resyncQueuedRef.current = false;
      resyncFailuresRef.current = 0;
      lastResyncStartedAtRef.current = 0;
    };
  }, [runId]);

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
      resync: resyncNow,
    }),
    [bootstrapSnapshot, graphRevision, isLiveMode, resyncNow, runId, setLocallyPaused, state],
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
