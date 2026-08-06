import type { DomainEventEnvelopeV1, GraphDeltaV1, GraphSnapshotV1 } from '@aegis/contracts-ts';
import {
  ConnectionHealthState,
  GRAPH_DELTA_SCHEMA_VERSION,
  isControlStatus,
  projectEffectiveStatus,
  projectNodeStatus,
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
  'investigation.',
  'action.proposal.',
  'agent.',
  'report.',
];

/**
 * Run lifecycle event -> the run status it puts the run into. `resumed` maps back to
 * `running`: "resumed" is a transition, not a state, and the run record/replay projector
 * both settle on `running`, so mapping it literally left the header reading "resumed".
 *
 * This table is exhaustive on purpose. Not every `sim.run.*` event is a lifecycle
 * transition — `sim.run.outcome_resolved` announces the run's win/lose *verdict* while
 * the run keeps running — so an event absent from this table must leave the run status
 * alone. Deriving one from the event name published a status (`outcome_resolved`) that
 * no run record ever holds, which is what made the header claim a terminal run while
 * after-action, reports and replay all correctly still read `running`.
 */
const RUN_STATUS_BY_LIFECYCLE_EVENT: Record<string, string> = {
  'sim.run.started': 'running',
  'sim.run.resumed': 'running',
  'sim.run.paused': 'paused',
  'sim.run.stopped': 'stopped',
};

function timelineStatusForEvent(eventType: string, payload: Record<string, unknown>): string {
  if (eventType === 'sim.asset.status_changed') {
    return typeof payload.status === 'string' ? projectNodeStatus(payload.status) : 'suspicious';
  }
  if (eventType.startsWith('alert.')) {
    return 'suspicious';
  }
  if (eventType.startsWith('incident.')) {
    return 'under_investigation';
  }
  if (eventType.startsWith('sim.hidden_condition.')) {
    return 'suspicious';
  }
  if (eventType.includes('failed')) {
    return 'suspicious';
  }
  return 'normal';
}

function formatPayloadString(value: unknown, fallback: string): string {
  return typeof value === 'string' ? value : fallback;
}

/**
 * Turn a scenario-local condition id into something an operator can read.
 * `condition-vendor-key-reuse` -> `Vendor key reuse`. The id is the only identity the
 * reveal event carries, so this is as close to the author's `causeLabel` as the client can
 * get without leaking the scenario manifest into the operator's session.
 */
function humaniseConditionId(conditionId: string): string {
  const words = conditionId
    .replace(/^(hidden[-_]?)?condition[-_]?/i, '')
    .split(/[-_.]+/)
    .filter(Boolean);
  if (words.length === 0) {
    return 'an undisclosed cause';
  }
  const [first, ...rest] = words as [string, ...string[]];
  return [first.charAt(0).toUpperCase() + first.slice(1), ...rest].join(' ');
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
    // The internal event names never reach the operator: a hidden condition is a *cause*
    // the scenario kept out of view, so it is announced as one.
    case 'sim.hidden_condition.triggered':
      return `Underlying cause active: ${humaniseConditionId(formatPayloadString(payload.conditionId, 'unknown'))}`;
    case 'sim.hidden_condition.revealed':
      return `Underlying cause revealed: ${humaniseConditionId(formatPayloadString(payload.conditionId, 'unknown'))}`;
    case 'report.generation.completed':
      return 'After-action report generation completed';
    case 'report.version.created':
      return 'After-action report version created';
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
  // The payload carries one value from either vocabulary: a posture the attacker drove
  // the asset into, or a control the defender applied ("isolated", "observed", ...).
  // Composing the two rather than overwriting is what keeps an observed compromise
  // visibly compromised; projecting is also what stops a raw control value reaching the
  // graph store, where the inspector, legend and status table have no entry for it.
  const applied = typeof payload.status === 'string' ? payload.status : null;
  if (applied === null) {
    return null;
  }
  const appliedControls = [...(knownNode.appliedControls ?? [])];
  let posture = knownNode.status as string;
  if (isControlStatus(applied)) {
    if (!appliedControls.includes(applied)) {
      appliedControls.push(applied);
    }
  } else {
    posture = applied;
  }
  return {
    schemaVersion: GRAPH_DELTA_SCHEMA_VERSION,
    runId: event.runId,
    sequence: event.sequence,
    revision: knownNode.revision + 1,
    operation: 'upsert_node',
    node: {
      ...knownNode,
      status: projectEffectiveStatus(posture, appliedControls),
      appliedControls,
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

  const lifecycleRunStatus = RUN_STATUS_BY_LIFECYCLE_EVENT[event.type];
  if (lifecycleRunStatus !== undefined) {
    actions.push({
      type: 'update_run_status',
      runStatus: lifecycleRunStatus,
      simTime: event.simTime,
      sequence: event.sequence,
    });
  }

  // The win/lose verdict. Announced while the run is still `running` (the ticker STOPs
  // right after), so it is projected into its own state slot rather than a status — the
  // SIM instrument reads both to explain why a terminal run ended. The full verdict
  // (disruption cost, campaign ids) stays in the payload for the after-action; the
  // cockpit only narrates the outcome, reason, and resolution time.
  if (event.type === 'sim.run.outcome_resolved') {
    const payload = event.payload;
    const outcome = typeof payload.outcome === 'string' ? payload.outcome : null;
    const reason = typeof payload.reason === 'string' ? payload.reason : null;
    const resolvedSimTime =
      typeof payload.resolvedSimTime === 'string' ? payload.resolvedSimTime : null;
    const resolvedSequence =
      typeof payload.resolvedSequence === 'number' ? payload.resolvedSequence : null;
    if (
      outcome !== null &&
      reason !== null &&
      resolvedSimTime !== null &&
      resolvedSequence !== null
    ) {
      actions.push({
        type: 'set_run_outcome',
        outcome: { outcome, reason, resolvedSimTime, resolvedSequence },
        sequence: event.sequence,
      });
    }
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
