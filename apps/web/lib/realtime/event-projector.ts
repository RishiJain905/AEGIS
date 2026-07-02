import type { DomainEventEnvelopeV1, GraphDeltaV1, GraphSnapshotV1 } from '@aegis/contracts-ts';
import {
  ConnectionHealthState,
  GRAPH_DELTA_SCHEMA_VERSION,
  type RealtimeReducerAction,
  type TimelineEntryV1,
} from '@aegis/contracts-ts';

const TIMELINE_EVENT_PREFIXES = [
  'telemetry.',
  'alert.',
  'model.score.',
  'risk.',
  'incident.',
  'sim.asset.',
  'sim.branch.',
  'sim.hidden_condition.',
];

function timelineStatusForEvent(eventType: string, payload: Record<string, unknown>): string {
  if (eventType === 'sim.asset.status_changed') {
    return typeof payload.status === 'string' ? payload.status : 'suspicious';
  }
  if (eventType.startsWith('alert.')) {
    return 'suspicious';
  }
  if (eventType.startsWith('incident.')) {
    return 'under_investigation';
  }
  if (eventType.includes('failed')) {
    return 'suspicious';
  }
  return 'normal';
}

function formatPayloadString(value: unknown, fallback: string): string {
  return typeof value === 'string' ? value : fallback;
}

function timelineLabelForEvent(event: DomainEventEnvelopeV1): string {
  const payload = event.payload;
  const subjectId = event.subject.id;
  switch (event.type) {
    case 'sim.run.started':
      return 'Run started';
    case 'sim.run.paused':
      return 'Run paused';
    case 'sim.run.resumed':
      return 'Run resumed';
    case 'sim.run.stopped':
      return 'Run stopped';
    case 'sim.asset.status_changed':
      return `Asset ${formatPayloadString(payload.assetId, subjectId)} → ${formatPayloadString(payload.status, 'updated')}`;
    case 'telemetry.authentication.failed':
      return `Authentication failed on ${formatPayloadString(payload.assetId, subjectId)}`;
    case 'telemetry.authentication.succeeded':
      return `Authentication succeeded on ${formatPayloadString(payload.assetId, subjectId)}`;
    case 'telemetry.api.request':
      return `API request on ${formatPayloadString(payload.assetId, subjectId)}`;
    case 'alert.created':
      return `Alert: ${formatPayloadString(payload.title, 'created')}`;
    case 'risk.score.computed':
      return `Graph risk updated on ${formatPayloadString(payload.assetId, subjectId)}`;
    case 'risk.projection.updated':
      return 'Graph risk projection updated';
    case 'incident.created':
      return `Incident: ${formatPayloadString(payload.title, 'created')}`;
    default:
      return event.type;
  }
}

function buildTimelineEntry(event: DomainEventEnvelopeV1): TimelineEntryV1 {
  return {
    schemaVersion: 1,
    sequence: event.sequence,
    eventId: event.eventId,
    eventType: event.type,
    label: timelineLabelForEvent(event),
    timestamp: event.simTime,
    status: timelineStatusForEvent(event.type, event.payload),
  };
}

function buildNodeDeltasFromRiskProjection(
  event: DomainEventEnvelopeV1,
  knownNodes: Map<string, GraphSnapshotV1['nodes'][number]>,
): GraphDeltaV1[] {
  if (event.type !== 'risk.projection.updated') {
    return [];
  }
  const payload = event.payload;
  const nodeUpdates = Array.isArray(payload.nodeUpdates) ? payload.nodeUpdates : [];
  const deltas: GraphDeltaV1[] = [];
  for (const update of nodeUpdates) {
    if (!update || typeof update !== 'object') {
      continue;
    }
    const record = update as Record<string, unknown>;
    const assetId = typeof record.assetId === 'string' ? record.assetId : null;
    const riskScore = typeof record.riskScore === 'number' ? record.riskScore : null;
    const revision = typeof record.revision === 'number' ? record.revision : null;
    if (!assetId || riskScore === null || revision === null) {
      continue;
    }
    const knownNode = knownNodes.get(assetId);
    if (knownNode === undefined) {
      continue;
    }
    deltas.push({
      schemaVersion: GRAPH_DELTA_SCHEMA_VERSION,
      runId: event.runId,
      sequence: event.sequence,
      revision,
      operation: 'upsert_node',
      node: {
        ...knownNode,
        riskScore,
        revision,
      },
    });
  }
  return deltas;
}

function buildNodeDeltaFromStatusChange(
  event: DomainEventEnvelopeV1,
  knownNodes: Map<string, GraphSnapshotV1['nodes'][number]>,
): GraphDeltaV1 | null {
  if (event.type !== 'sim.asset.status_changed') {
    return null;
  }
  const payload = event.payload;
  const assetId = typeof payload.assetId === 'string' ? payload.assetId : event.subject.id;
  const knownNode = knownNodes.get(assetId);
  if (knownNode === undefined) {
    return null;
  }
  const statusValue = (
    typeof payload.status === 'string' ? payload.status : knownNode.status
  ) as GraphSnapshotV1['nodes'][number]['status'];
  return {
    schemaVersion: GRAPH_DELTA_SCHEMA_VERSION,
    runId: event.runId,
    sequence: event.sequence,
    revision: knownNode.revision + 1,
    operation: 'upsert_node',
    node: {
      ...knownNode,
      status: statusValue,
      revision: knownNode.revision + 1,
    },
  };
}

export function projectDomainEventToActions(
  event: DomainEventEnvelopeV1,
  options: {
    lastAppliedSequence: number;
    seenEventIds: Set<string>;
    knownNodes: Map<string, GraphSnapshotV1['nodes'][number]>;
  },
): RealtimeReducerAction[] {
  if (options.seenEventIds.has(event.eventId)) {
    return [
      {
        type: 'noop_duplicate',
        eventId: event.eventId,
        sequence: event.sequence,
      },
    ];
  }
  if (event.sequence <= options.lastAppliedSequence) {
    return [
      {
        type: 'noop_duplicate',
        eventId: event.eventId,
        sequence: event.sequence,
      },
    ];
  }
  if (event.sequence > options.lastAppliedSequence + 1) {
    return [
      {
        type: 'mark_gap',
        expectedSequence: options.lastAppliedSequence + 1,
        receivedSequence: event.sequence,
      },
    ];
  }

  const actions: RealtimeReducerAction[] = [];

  if (event.type === 'graph.snapshot.created') {
    const snapshotPayload = event.payload as Partial<GraphSnapshotV1>;
    if (snapshotPayload.nodes && snapshotPayload.edges) {
      actions.push({
        type: 'load_graph_snapshot',
        snapshot: snapshotPayload as GraphSnapshotV1,
      });
    }
  }

  if (event.type.startsWith('sim.run.')) {
    const lifecycle = event.type.replace('sim.run.', '');
    const runStatus =
      lifecycle === 'started' ? 'running' : lifecycle === 'stopped' ? 'stopped' : lifecycle;
    actions.push({
      type: 'update_run_status',
      runStatus,
      simTime: event.simTime,
      sequence: event.sequence,
    });
  }

  const nodeDelta = buildNodeDeltaFromStatusChange(event, options.knownNodes);
  if (nodeDelta !== null) {
    actions.push({ type: 'apply_graph_delta', delta: nodeDelta });
    if (nodeDelta.node) {
      options.knownNodes.set(nodeDelta.node.id, nodeDelta.node);
    }
  }

  for (const riskDelta of buildNodeDeltasFromRiskProjection(event, options.knownNodes)) {
    actions.push({ type: 'apply_graph_delta', delta: riskDelta });
    if (riskDelta.node) {
      options.knownNodes.set(riskDelta.node.id, riskDelta.node);
    }
  }

  if (TIMELINE_EVENT_PREFIXES.some((prefix) => event.type.startsWith(prefix))) {
    actions.push({
      type: 'append_timeline_entry',
      entry: buildTimelineEntry(event),
    });
  }

  if (actions.length === 0) {
    actions.push({
      type: 'advance_sequence',
      sequence: event.sequence,
      eventId: event.eventId,
    });
  }

  return actions;
}

export function mapConnectionHealthFromRunStatus(
  runStatus: string,
  transportState: string,
): (typeof ConnectionHealthState)[keyof typeof ConnectionHealthState] {
  if (transportState === 'reconnecting') {
    return ConnectionHealthState.RECONNECTING;
  }
  if (transportState === 'disconnected' || transportState === 'closed') {
    return ConnectionHealthState.DISCONNECTED;
  }
  if (runStatus === 'paused') {
    return ConnectionHealthState.SIMULATOR_PAUSED;
  }
  return ConnectionHealthState.CONNECTED;
}
